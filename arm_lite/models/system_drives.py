import ctypes
import logging
import platform

try:
    import wmi
    HAVE_WMI = True
except ImportError:
    wmi = None
    HAVE_WMI = False

from arm_lite.ui import db

def _mci_send(command: str) -> str:
    """Send a single MCI command via winmm.dll and return its response."""
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.winmm.mciSendStringW(command, buf, 254, 0)
    return buf.value
 
 
class SystemDrives(db.Model):
    """
    Class to hold the system cd/dvd/Blu-ray drive information
    """
    drive_id = db.Column(db.Integer, index=True, primary_key=True)
    serial_id = db.Column(db.String(100))
    name = db.Column(db.String(100))
    serial = db.Column(db.String(25))
    type = db.Column(db.String(20))
    mount = db.Column(db.String(100))    # Windows drive letter, e.g. "D:"
    open = db.Column(db.Boolean)
    job_id_current = db.Column(db.Integer, db.ForeignKey("Jobs.job_id"))
    job_id_previous = db.Column(db.Integer, db.ForeignKey("Jobs.job_id"))
    description = db.Column(db.Unicode(200))
    drive_mode = db.Column(db.String(100))
 
    # relationship - join current and previous jobs to the Job model
    job_current = db.relationship("Job", backref=db.backref("current_drive", uselist=False), foreign_keys=[job_id_current])
    job_previous = db.relationship("Job", backref=db.backref("previous_drive", uselist=False), foreign_keys=[job_id_previous])
 
    def __init__(self, name, mount, job, job_previous, description):
        self.name = name
        self.mount = mount
        self.open = False
        self.job_id_current = job
        self.job_id_previous = job_previous
        self.description = description
        self.get_wmi_info()
        self.drive_mode = "auto"

    def get_wmi_info(self):
        """
        Best-effort optical drive metadata via WMI: type (CD/DVD/BluRay),
        maker, model, and serial number.
 
        Windows doesn't expose a single reliable "this drive reads
        Blu-ray" property the way Linux's udev ID_CDROM_BD does, and
        Win32_CDROMDrive's own Manufacturer field is frequently just the
        generic Windows driver class name ("(Standard CD-ROM drives)")
        rather than the real vendor - so maker/model are both derived
        from Caption instead, which reliably combines vendor+model as one
        string (e.g. "HL-DT-ST BD-RE  WH16NS40"), split heuristically on
        whitespace when Manufacturer isn't trustworthy.
 
        SerialNumber is commonly blank for optical drives via WMI (far
        less reliable than it is for hard disks) - None for a lot of real
        drives is expected behavior here, not a bug.
 
        Defaults to type="CD" and maker/model/serial=None if WMI is
        unavailable or this drive's letter isn't found in WMI's results.
        """
        self.type = "CD"
        self.maker = None
        self.model = None
        self.serial = None
 
        if not HAVE_WMI:
            logging.debug("wmi not installed - defaulting drive type to CD, no maker/model/serial")
            return
 
        try:
            conn = wmi.WMI()
            for drive in conn.Win32_CDROMDrive():
                if not (drive.Drive and drive.Drive.upper() == self.mount.upper()):
                    continue
 
                caption = (drive.Caption or "").strip()
                capabilities = " ".join(drive.CapabilityDescriptions or [])
                combined = f"{caption} {capabilities}".lower()
 
                if "dvd" in combined:
                    self.type += "/DVD"
                if "blu-ray" in combined or "bd-rom" in combined or "bluray" in combined:
                    self.type += "/BluRay"
 
                manufacturer = (getattr(drive, "Manufacturer", None) or "").strip()
                if manufacturer and "standard" not in manufacturer.lower():
                    self.maker = manufacturer
                    self.model = caption or None
                elif caption:
                    # Manufacturer is missing/generic - fall back to
                    # splitting "VENDOR MODEL..." out of Caption, the only
                    # field that's reliably populated. Same "imperfect but
                    # reasonable" tradeoff as the type guess above.
                    parts = caption.split(None, 1)
                    self.maker = parts[0] if parts else None
                    self.model = parts[1] if len(parts) > 1 else caption
 
                serial = (getattr(drive, "SerialNumber", None) or "").strip()
                self.serial = serial or None
                break
        except Exception as e:
            logging.debug(f"Could not determine drive info for {self.mount} via WMI: {e}")

    def drive_type(self):
        """
        Best-effort optical drive type (CD/DVD/BluRay) via WMI.
 
        Windows doesn't expose a single reliable "this drive reads
        Blu-ray" property the way Linux's udev ID_CDROM_BD does - drive
        vendors report capability info inconsistently in WMI. This scans
        the drive's Caption and CapabilityDescriptions for common
        substrings as a best-effort guess. Defaults to "CD" (a safe
        assumption for virtually every optical drive sold in the last
        ~15 years) if WMI is unavailable or nothing more specific is found.
        """
        temp = "CD"
        if not HAVE_WMI:
            logging.debug("wmi not installed - defaulting drive type to CD")
            self.type = temp
            return
        try:
            conn = wmi.WMI()
            for drive in conn.Win32_CDROMDrive():
                if drive.Drive and drive.Drive.upper() == self.mount.upper():
                    caption = (drive.Caption or "").lower()
                    capabilities = " ".join(drive.CapabilityDescriptions or []).lower()
                    combined = f"{caption} {capabilities}"
                    if "dvd" in combined:
                        temp += "/DVD"
                    if "blu-ray" in combined or "bd-rom" in combined or "bluray" in combined:
                        temp += "/BluRay"
                    break
        except Exception as e:
            logging.debug(f"Could not determine drive type for {self.mount} via WMI: {e}")
        self.type = temp
 
    def new_job(self, job_id):
        """new job assigned to the drive, update with new job id, and previous job_id"""
        self.job_id_previous = self.job_id_current
        self.job_id_current = job_id
 
    def job_finished(self):
        """update Job IDs between current and previous jobs"""
        self.job_id_previous = self.job_id_current
        self.job_id_current = None
        # eject drive (not implemented, as job.eject() declared in a lot of places)
        # self.open_close()
 
    def open_close(self):
        """
        Open or close the drive tray via the Windows MCI API (winmm.dll).
        A no-op (logged, not raised) on any non-Windows platform, since
        ctypes.windll only exists on Windows.
        """
        if platform.system() != "Windows":
            logging.debug(f"{self.mount} eject/close skipped - not running on Windows")
            return
 
        alias = "arm_drive_" + self.mount.rstrip(":")
        if self.open:
            # If open, then close the drive
            try:
                _mci_send(f"open {self.mount} type cdaudio alias {alias}")
                _mci_send(f"set {alias} door closed")
                _mci_send(f"close {alias}")
                self.open = False
                logging.debug(f"Closed drive {self.mount}")
            except Exception as error:
                logging.debug(f"{self.mount} unable to be closed {error}")
        else:
            # if closed, open/eject the drive
            if self.job_id_current:
                logging.debug(f"{self.mount} unable to eject - current job [{self.job_id_current}] is in progress.")
            else:
                try:
                    _mci_send(f"open {self.mount} type cdaudio alias {alias}")
                    _mci_send(f"set {alias} door open")
                    _mci_send(f"close {alias}")
                    self.open = True
                    logging.debug(f"Ejected disc {self.mount}")
                except Exception as error:
                    logging.debug(f"{self.mount} couldn't be ejected {error}")
