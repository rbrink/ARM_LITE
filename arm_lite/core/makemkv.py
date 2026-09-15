"""
Thin wrapper around makemkvcon (MakeMKV's command-line tool): list
drives, list titles on a disc, and rip selected titles.

MakeMKV must be installed and, ideally, have a valid license registered
(arm_config.yaml's MAKEMKV_PERMA_KEY) so it can decrypt commercial discs.
Get it from https://www.makemkv.com/

Robot mode (-r) prints stable, parseable lines - see apdefs.h in MakeMKV's
own source for the full list of TINFO/CINFO codes; only the handful used
here are named below.

Config this module actually acts on:
  - MAKEMKVCON        path to makemkvcon(64).exe
  - MKV_ARGS          extra CLI args passed through on every call
  - MINLENGTH/MAXLENGTH   title duration filter, in seconds (get_titles())
  - PREVENT_99        reject a disc reporting exactly 99 titles (get_titles())
  - RIPMETHOD         only "mkv" is implemented; "backup"/"backup_dvd" log a
                       clear warning and fall back to "mkv" rather than
                       silently doing something the config didn't ask for
"""
import os
import re
import subprocess
from typing import Callable, Dict, List, Optional

import arm_lite.config.config as cfg

# Title-level info codes we care about (see MakeMKV apdefs.h for full list)
TINFO_NAME = 2
TINFO_CHAPTERS = 8
TINFO_DURATION = 9
TINFO_SIZE_HUMAN = 10
TINFO_SIZE_BYTES = 11
TINFO_FILENAME = 27

_TINFO_RE = re.compile(r'^TINFO:(\d+),(\d+),(\d+),"(.*)"\s*$')
_CINFO_RE = re.compile(r'^CINFO:(\d+),(\d+),"(.*)"\s*$')
_PRGV_RE = re.compile(r"^PRGV:(\d+),(\d+),(\d+)\s*$")
_MSG_RE = re.compile(r'^MSG:\d+,\d+,\d+,"(.*?)"')


class Track99Error(RuntimeError):
    """
    Raised by get_titles() when PREVENT_99 is enabled and the disc reports
    exactly 99 titles - the signature of the "Track 99" DRM scheme, which
    arm_config.yaml warns can crash/hang HandBrake if ripped anyway.

    This module only detects it and raises; it does NOT eject the drive
    itself (it only knows a MakeMKV disc index, not a SystemDrives row/
    drive letter). The caller - the job-orchestration layer, which does
    have that context - is expected to catch this and call
    SystemDrives.open_close() to actually eject, then mark the job failed.
    """


def _makemkvcon_path() -> str:
    exe = cfg.arm_config.get("MAKEMKVCON")
    if not exe:
        raise RuntimeError("MAKEMKVCON isn't configured in arm_config.yaml")
    return os.path.expandvars(exe)


def _extra_args() -> List[str]:
    raw = (cfg.arm_config.get("MKV_ARGS") or "").strip()
    return raw.split() if raw else []


def _rip_method() -> str:
    method = cfg.arm_config.get("RIPMETHOD", "mkv")
    if method != "mkv":
        import logging
        logging.warning(
            f"RIPMETHOD={method!r} isn't implemented yet (only 'mkv' is) - "
            f"using 'mkv' instead of the configured value"
        )
        return "mkv"
    return method


def _run(args: List[str]) -> subprocess.CompletedProcess:
    cmd = [_makemkvcon_path(), "-r", "--cache=64", *_extra_args(), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def list_drives() -> List[Dict]:
    """Ask MakeMKV which disc index maps to which Windows drive letter."""
    proc = _run(["info"])
    drives = []
    # DRV:<index>,<visible>,<enabled>,<flags>,"<drive name>","<disc name>","<device path>"
    for line in proc.stdout.splitlines():
        if line.startswith("DRV:"):
            parts = _split_csv_with_quotes(line[4:])
            if len(parts) >= 7 and parts[5]:
                drives.append(
                    {
                        "index": int(parts[0]),
                        "disc_name": parts[5].strip('"'),
                        "device_path": parts[6].strip('"'),
                    }
                )
    return drives


def _split_csv_with_quotes(s: str) -> List[str]:
    # Simple CSV splitter that respects double-quoted fields (MakeMKV's
    # robot output is comma separated with quoted strings).
    out, cur, in_quotes = [], "", False
    for ch in s:
        if ch == '"':
            in_quotes = not in_quotes
            cur += ch
        elif ch == "," and not in_quotes:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def find_disc_index_for_drive(drive_letter: str) -> Optional[int]:
    """Match a Windows drive letter (e.g. 'D:') to MakeMKV's disc index."""
    for d in list_drives():
        if d["device_path"].upper().startswith(drive_letter.upper()):
            return d["index"]
    return None


def _duration_to_seconds(duration: str) -> Optional[int]:
    """Parse MakeMKV's "H:MM:SS" duration string into seconds."""
    if not duration:
        return None
    try:
        parts = [int(p) for p in duration.split(":")]
    except ValueError:
        return None
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def _filter_by_length(titles: List[Dict]) -> List[Dict]:
    """MINLENGTH/MAXLENGTH from arm_config.yaml, in seconds - drops menu
    loops/trailers/etc. outside that window. A title whose duration can't
    be parsed is kept rather than silently dropped."""
    try:
        min_len = int(cfg.arm_config.get("MINLENGTH") or 0)
    except (TypeError, ValueError):
        min_len = 0
    try:
        max_len_raw = cfg.arm_config.get("MAXLENGTH")
        max_len = int(max_len_raw) if max_len_raw not in (None, "") else 99999
    except (TypeError, ValueError):
        max_len = 99999

    if min_len <= 0 and max_len >= 99999:
        return titles

    filtered = []
    for t in titles:
        secs = _duration_to_seconds(t["duration"])
        if secs is None or min_len <= secs <= max_len:
            filtered.append(t)
    return filtered


def get_titles(disc_index: int) -> Dict:
    """
    Returns {"disc_name": ..., "titles": [{id,name,duration,chapters,size,filename}]}.

    Applies MINLENGTH/MAXLENGTH filtering. Raises Track99Error if
    PREVENT_99 is enabled and the disc reports exactly 99 titles - see
    that exception's docstring for what the caller is expected to do
    about it.
    """
    proc = _run(["info", f"disc:{disc_index}"])
    titles: Dict[int, Dict] = {}
    disc_name = None

    for line in proc.stdout.splitlines():
        m = _CINFO_RE.match(line)
        if m:
            code, _flag, value = int(m.group(1)), m.group(2), m.group(3)
            if code == 2:  # disc name
                disc_name = value
            continue

        m = _TINFO_RE.match(line)
        if m:
            title_id, code, _flag, value = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
            t = titles.setdefault(
                title_id,
                {"id": title_id, "name": "", "duration": "", "chapters": "", "size": "", "filename": ""},
            )
            if code == TINFO_NAME:
                t["name"] = value
            elif code == TINFO_DURATION:
                t["duration"] = value
            elif code == TINFO_CHAPTERS:
                t["chapters"] = value
            elif code == TINFO_SIZE_HUMAN:
                t["size"] = value
            elif code == TINFO_FILENAME:
                t["filename"] = value

    ordered = [titles[k] for k in sorted(titles.keys())]
    for t in ordered:
        if not t["name"]:
            t["name"] = f"Title {t['id']}"

    prevent_99 = cfg.arm_config.get("PREVENT_99", True)
    if prevent_99 and len(ordered) == 99:
        raise Track99Error(
            f"Disc (index {disc_index}) reports exactly 99 titles, matching the "
            f"Track 99 DRM signature. PREVENT_99 is enabled, so this disc is "
            f"being rejected rather than risking a MakeMKV/HandBrake crash or hang."
        )

    ordered = _filter_by_length(ordered)

    return {"disc_name": disc_name, "titles": ordered}


def rip_titles(
    disc_index: int,
    title_ids: List[int],
    output_dir: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
):
    """
    Rip the given title ids from a disc to output_dir (typically somewhere
    under RAW_PATH - constructing that path is the orchestration layer's
    job, not this module's), one at a time. progress_cb(percent, message)
    is called as MakeMKV reports progress. Raises RuntimeError on failure.
    """
    os.makedirs(output_dir, exist_ok=True)
    method = _rip_method()  # only "mkv" is actually implemented right now
    exe = _makemkvcon_path()

    for n, title_id in enumerate(title_ids):
        cmd = [exe, "-r", "--cache=64", *_extra_args(), method, f"disc:{disc_index}", str(title_id), output_dir]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        last_msg = ""
        for line in proc.stdout:
            line = line.strip()
            pv = _PRGV_RE.match(line)
            if pv and progress_cb:
                current, _total, maxv = (int(x) for x in pv.groups())
                pct_this_title = (current / maxv * 100) if maxv else 0
                overall = (n * 100 + pct_this_title) / len(title_ids)
                progress_cb(overall, last_msg)
            mm = _MSG_RE.match(line)
            if mm:
                last_msg = mm.group(1)
                if progress_cb:
                    progress_cb(-1, last_msg)  # -1 = don't overwrite percent, just message
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"makemkvcon exited with code {proc.returncode} while ripping title {title_id}")

    if progress_cb:
        progress_cb(100, "Done")
        