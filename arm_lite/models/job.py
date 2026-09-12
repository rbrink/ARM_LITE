import logging
import enum

import arm_lite.config.config as cfg
from arm_lite.ui import db


class JobState(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "fail"
    IDLE = "active"
    VIDEO_RIPPING = "ripping"
    VIDEO_WAITING = "waiting"
    VIDEO_INFO = "info"
    AUDIO_RIPPING = "ripping_audio"
    TRANSCODE_ACTIVE = "transcoding"
    TRANSCODE_WAITING = "waiting_transcode"


JOB_STATUS_FINISHED = {
    JobState.SUCCESS,
    JobState.FAILURE,
}
JOB_STATUS_RIPPING = {
    JobState.AUDIO_RIPPING,
    JobState.VIDEO_RIPPING,
    JobState.VIDEO_WAITING,
    JobState.VIDEO_INFO,
}
JOB_STATUS_TRANSCODING = {
    JobState.TRANSCODE_ACTIVE,
    JobState.TRANSCODE_WAITING,
}


class Job(db.Model):
    __tablename__ = "Jobs"

    job_id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime)
    stop_time = db.Column(db.DateTime)
    job_length = db.Column(db.String(12))
    status = db.Column(db.Enum(JobState, name="job_state_enum", native_enum=False, validate_strings=True),
                       nullable=False)
    no_titles = db.Column(db.Integer)
    title = db.Column(db.String(256))
    year = db.Column(db.String(4))
    video_type = db.Column(db.String(20))
    imdb_id = db.Column(db.String(15))
    poster_url = db.Column(db.String(256))
    devpath = db.Column(db.String(100))
    disc_type = db.Column(db.String(20))
    label = db.Column(db.String(256))
    ejected = db.Column(db.Boolean)
    updated = db.Column(db.Boolean)

    def __init__(self, devpath: str, disc_type: str = None, label: str = None):
        self.devpath = devpath
        # disc_type/label are now accepted as constructor params - previously
        # neither was, so `self.disc_type == "dvd"` below was always False
        # (a freshly-constructed Job hadn't set disc_type yet at that point)
        # and the branch could never run.
        self.disc_type = disc_type
        self.label = label
        self.video_type = "unknown"
        self.ejected = False
        self.updated = False
        # status is nullable=False but was never set here before - a plain
        # Job(devpath) would have failed that constraint on insert.
        self.status = JobState.VIDEO_INFO
        if cfg.arm_config.get("VIDEO_TYPE") != "auto":
            self.video_type = cfg.arm_config.get("VIDEO_TYPE")
        if self.disc_type == "dvd" and not self.label:
            logging.info("No disc label available")