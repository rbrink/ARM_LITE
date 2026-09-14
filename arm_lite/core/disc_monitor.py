"""
Polls the optical drives on the system for newly inserted media and
classifies what's on it - the one fully-automatic part of the pipeline.
Everything past this point (creating a Job row, metadata lookup, title
selection, ripping) is triggered elsewhere.

Deliberately decoupled from the Job/SystemDrives database models: this
module only knows about drive letters and what's physically in them.
Register on_disc_inserted/on_disc_removed callbacks to react to what it
finds - ui/routes.py is what actually creates Job rows and kicks off
identification, keeping "detect what changed" and "decide what to do
about it" as separate concerns.

Disc classification, in order of preference:
  - VIDEO_TS folder present   -> DVD-Video
  - BDMV folder present       -> Blu-ray
  - only .cda files present   -> Audio CD (Windows mounts audio discs via
                                 CDFS and shows one .cda placeholder file
                                 per track - this is the standard behavior
                                 on Windows Vista and later; unlike some
                                 other platforms, Windows audio discs are
                                 NOT unreadable/filesystem-less, so this
                                 module does not try to detect them via a
                                 failed directory listing)
  - anything else readable    -> Data disc
  - directory listing fails   -> no disc in the drive at all
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import arm_lite.config.config as cfg
from arm_lite.ui.settings.DriveUtils import HAVE_WIN32, drives_search

try:
    import win32api
except ImportError:
    win32api = None


@dataclass
class DiscState:
    drive: str                      # e.g. "D:"
    present: bool = False
    disc_type: str = "empty"        # empty | dvd | bluray | audio | data
    label: str = ""
    changed_at: float = field(default_factory=time.time)


class DiscMonitor:
    def __init__(self):
        self._states: Dict[str, DiscState] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # callback(drive: str, state: DiscState)
        self.on_disc_inserted: Optional[Callable[[str, DiscState], None]] = None
        self.on_disc_removed: Optional[Callable[[str, DiscState], None]] = None

    # ---------------------------------------------------------- discovery
    def _tracked_drives(self):
        """Drives to poll: an explicit DRIVE_LETTERS override in
        arm_config.yaml if set, otherwise every optical drive currently
        detected on the system."""
        configured = cfg.arm_config.get("DRIVE_LETTERS") or []
        if configured:
            return configured
        if not HAVE_WIN32:
            return []
        return drives_search()

    def _classify(self, drive: str) -> DiscState:
        root = f"{drive}\\"
        state = DiscState(drive=drive)

        try:
            entries = set(os.listdir(root))
        except OSError:
            # No disc in the drive - this IS the correct signal here
            # (unlike DriveUtils.drives_search(), which specifically
            # avoids relying on a listdir/stat failure, since that check
            # answers a different question: "what kind of drive is this,
            # regardless of what's loaded" vs. this method's "what's
            # currently loaded in it right now", where a failed listing
            # legitimately means "nothing's in there").
            state.present = False
            state.disc_type = "empty"
            return state

        state.present = True

        if win32api is not None:
            try:
                label, _serial, _maxlen, _flags, _fs_name = win32api.GetVolumeInformation(root)
                state.label = label
            except Exception:
                state.label = ""

        if "VIDEO_TS" in entries:
            state.disc_type = "dvd"
        elif "BDMV" in entries:
            state.disc_type = "bluray"
        elif entries and all(e.lower().endswith(".cda") for e in entries):
            state.disc_type = "audio"
        elif entries:
            state.disc_type = "data"
        else:
            # Readable but empty directory listing - a blank/unfinalized
            # data disc most commonly, or an edge case Windows didn't
            # mount CDFS for. Treated as data rather than guessing further.
            state.disc_type = "data"

        return state

    # -------------------------------------------------------------- loop
    def poll_once(self):
        for drive in self._tracked_drives():
            new_state = self._classify(drive)
            with self._lock:
                old_state = self._states.get(drive)
            was_present = old_state.present if old_state else False

            if new_state.present and not was_present:
                new_state.changed_at = time.time()
                with self._lock:
                    self._states[drive] = new_state
                if self.on_disc_inserted:
                    self.on_disc_inserted(drive, new_state)
            elif not new_state.present and was_present:
                with self._lock:
                    self._states[drive] = new_state
                if self.on_disc_removed:
                    self.on_disc_removed(drive, old_state)
            else:
                with self._lock:
                    self._states[drive] = new_state

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as e:
                print(f"[disc_monitor] poll error: {e}")
            self._stop.wait(cfg.arm_config.get("POLL_INTERVAL_SECONDS", 3))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self):
        with self._lock:
            return dict(self._states)


monitor = DiscMonitor()
