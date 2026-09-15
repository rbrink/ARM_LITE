"""
Thin wrapper around HandBrakeCLI for transcoding MakeMKV's raw remux down
to a smaller file - the RAW_PATH -> TRANSCODE_PATH step in the three-stage
pipeline (see arm_config.yaml).

Config this module acts on:
  - HANDBRAKE_CLI    path to HandBrakeCLI.exe
  - HB_PRESETS_FILE  presets.json to import/read presets from
  - HB_PRESET_DVD    preset name used for DVD sources
  - HB_PRESET_BD     preset name used for Blu-ray sources
  - DEST_EXT         output container extension (e.g. "mkv")

USE_FFMPEG (an experimental alternate transcode path, off by default in
arm_config.yaml) is NOT implemented here - the orchestration layer should
check it and log a clear "not implemented" warning if it's turned on,
rather than this module silently doing nothing, matching how
METADATA_PROVIDER/GET_AUDIO_TITLE/RIPMETHOD handle their own
not-yet-implemented options elsewhere in this project.
"""
import json
import os
import re
import subprocess
from typing import Callable, List, Optional

import arm_lite.config.config as cfg

# HandBrakeCLI prints progress like:
#   "Encoding: task 1 of 1, 42.35 % (23.11 fps, avg 22.87 fps, ETA 00h04m12s)"
_PROGRESS_RE = re.compile(r"Encoding:.*?(\d+(?:\.\d+)?)\s*%")


def is_configured() -> bool:
    path = cfg.arm_config.get("HANDBRAKE_CLI")
    if not path:
        return False
    return os.path.isfile(os.path.expandvars(path))


def get_preset_for(disc_type: str) -> Optional[str]:
    """
    DVD sources use HB_PRESET_DVD, Blu-ray sources use HB_PRESET_BD - the
    one place that disc-type-to-preset mapping lives, so the orchestration
    layer doesn't have to duplicate it. Returns None for anything else
    (audio/data discs don't get transcoded with HandBrake).
    """
    if disc_type == "dvd":
        return cfg.arm_config.get("HB_PRESET_DVD")
    if disc_type == "bluray":
        return cfg.arm_config.get("HB_PRESET_BD")
    return None


def _preset_import_args() -> List[str]:
    """Import HB_PRESETS_FILE if it's configured and actually exists -
    harmless if it's just HandBrake's own default presets.json (those
    preset names are already built in), and correctly picks up custom
    preset names if the user points this at an exported presets.json."""
    presets_file = cfg.arm_config.get("HB_PRESETS_FILE")
    if presets_file:
        expanded = os.path.expandvars(presets_file)
        if os.path.isfile(expanded):
            return ["--preset-import-file", expanded]
    return []


def list_presets() -> dict:
    """Category name -> [preset names], parsed from HB_PRESETS_FILE.
    Empty dict if it's not configured or can't be read."""
    presets_file = cfg.arm_config.get("HB_PRESETS_FILE")
    if not presets_file:
        return {}
    expanded = os.path.expandvars(presets_file)
    try:
        with open(expanded, "r") as f:
            data = json.load(f)
    except Exception as e:
        import logging
        logging.debug(f"Couldn't read HB_PRESETS_FILE ({expanded}): {e}")
        return {}

    result = {}
    for category in data.get("PresetList", []):
        cat_name = category.get("PresetName", "Unrecognized")
        children = category.get("ChildrenArray", [])
        result[cat_name] = [c["PresetName"] for c in children if "PresetName" in c]
    return result


def output_path_for(input_path: str, dest_dir: str = None) -> str:
    """Build the transcoded output filename using DEST_EXT, in dest_dir if
    given (otherwise alongside input_path)."""
    ext = (cfg.arm_config.get("DEST_EXT") or "mkv").lstrip(".")
    base = os.path.splitext(os.path.basename(input_path))[0]
    directory = dest_dir if dest_dir else os.path.dirname(input_path)
    return os.path.join(directory, f"{base}.{ext}")


def transcode(
    input_path: str,
    output_path: str,
    preset_name: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    timeout: int = 60 * 60 * 6,  # 6h ceiling - a big 4K encode can run long
):
    """
    Transcodes input_path -> output_path using the named preset.
    Raises RuntimeError if HandBrakeCLI isn't configured or exits non-zero.
    """
    if not is_configured():
        raise RuntimeError("HANDBRAKE_CLI isn't configured (or doesn't point at a real file) in arm_config.yaml")
    if not preset_name:
        raise RuntimeError("No HandBrake preset given - check HB_PRESET_DVD/HB_PRESET_BD in arm_config.yaml")

    exe = os.path.expandvars(cfg.arm_config.get("HANDBRAKE_CLI"))
    cmd = [exe, *_preset_import_args(), "-i", input_path, "-o", output_path, "--preset", preset_name]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    last_msg = ""
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            m = _PROGRESS_RE.search(line)
            if m:
                pct = float(m.group(1))
                if progress_cb:
                    progress_cb(pct, f"Transcoding ({preset_name})\u2026 {pct:.0f}%")
            else:
                last_msg = line
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"HandBrakeCLI timed out after {timeout}s")

    if proc.returncode != 0:
        raise RuntimeError(f"HandBrakeCLI exited with code {proc.returncode}: {last_msg}")

    if progress_cb:
        progress_cb(100, "Transcode complete")
        