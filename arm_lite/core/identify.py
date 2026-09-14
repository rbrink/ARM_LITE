"""
Reacts to disc_monitor's on_disc_inserted/on_disc_removed callbacks:
creates a Job row for a newly-detected disc, links it to its drive via
SystemDrives, and (for video discs) looks up metadata to populate
title/year/poster/etc. Ripping itself is triggered later, manually - this
module only ever gathers information, consistent with disc_monitor being
the one automatic step.

Audio identification (GET_AUDIO_TITLE: musicbrainz) needs core/audio_cd.py
to read the disc's TOC and compute a MusicBrainz disc ID first - that
module doesn't exist yet, so _identify_audio() below leaves the job in a
sensible waiting state rather than guessing. Fill in the TOC read there
once audio_cd.py exists; nothing else here should need to change.

Callers (see runui.py) MUST invoke handle_disc_inserted/handle_disc_removed
from inside a Flask app context - disc_monitor's polling loop runs on a
background thread, and Flask-SQLAlchemy's db.session/Model.query are tied
to whatever app context is current, which a plain background thread
doesn't have on its own.
"""
import logging

import arm_lite.config.config as cfg
from arm_lite.core import metadata_omdb
from arm_lite.core.disc_monitor import DiscState
from arm_lite.models.job import Job, JobState
from arm_lite.models.system_drives import SystemDrives
from arm_lite.ui import db
from arm_lite.ui.settings.DriveUtils import update_drive_job


def handle_disc_inserted(drive: str, state: DiscState):
    """disc_monitor callback: create and identify a Job for this disc."""
    logging.info(f"Disc inserted in {drive}: type={state.disc_type} label={state.label!r}")

    job = Job(devpath=drive, disc_type=state.disc_type, label=state.label)
    db.session.add(job)
    db.session.commit()

    drive_row = SystemDrives.query.filter_by(mount=drive).first()
    if drive_row:
        update_drive_job(job)
    else:
        logging.debug(f"{drive} isn't a registered SystemDrives entry - job {job.job_id} not linked to a drive")

    if state.disc_type in ("dvd", "bluray"):
        _identify_video(job, state)
    elif state.disc_type == "audio":
        _identify_audio(job, state)
    else:
        # data disc / unknown - nothing to identify automatically
        job.status = JobState.VIDEO_WAITING
        db.session.commit()

    return job


def handle_disc_removed(drive: str, state: DiscState):
    """disc_monitor callback: nothing to identify, but log it and leave any
    in-flight job alone for a human to deal with via the UI rather than
    silently marking it failed - the disc could've been pulled mid-browse
    with no rip ever started."""
    logging.info(f"Disc removed from {drive}")
    drive_row = SystemDrives.query.filter_by(mount=drive).first()
    if drive_row and drive_row.job_id_current:
        job = Job.query.filter_by(job_id=drive_row.job_id_current).first()
        if job and job.status not in (JobState.SUCCESS, JobState.FAILURE):
            logging.debug(f"Job {job.job_id} left as-is after disc removal (status={job.status})")


def _identify_video(job: Job, state: DiscState):
    provider = cfg.arm_config.get("METADATA_PROVIDER", "omdb")
    if provider != "omdb":
        logging.warning(f"METADATA_PROVIDER={provider!r} isn't implemented yet (only 'omdb' is) - skipping identification")
        job.status = JobState.VIDEO_WAITING
        db.session.commit()
        return

    guessed_title, guessed_year = metadata_omdb.clean_label(state.label or job.devpath)
    result = metadata_omdb.search(guessed_title, guessed_year)

    if result:
        job.title = result.get("Title", guessed_title)
        job.year = result.get("Year", guessed_year or "")
        job.imdb_id = result.get("imdbID", "")
        poster = result.get("Poster")
        job.poster_url = poster if poster and poster != "N/A" else None
        # Only let OMDB's Type override video_type if the user hasn't
        # pinned it via VIDEO_TYPE - Job.__init__ already applied that
        # override as the starting value, so "auto" is what's left when
        # there's nothing to respect here.
        if cfg.arm_config.get("VIDEO_TYPE") == "auto":
            job.video_type = "series" if result.get("Type") == "series" else "movie"
    else:
        job.title = guessed_title or state.label or "Unknown disc"
        job.year = guessed_year or ""
        logging.info(f"No OMDB match found for {job.devpath} (guessed title: {guessed_title!r})")

    job.status = JobState.VIDEO_WAITING
    db.session.commit()


def _identify_audio(job: Job, state: DiscState):
    provider = cfg.arm_config.get("GET_AUDIO_TITLE", "musicbrainz")

    if provider == "none":
        job.status = JobState.VIDEO_WAITING
        db.session.commit()
        return

    if provider != "musicbrainz":
        logging.warning(f"GET_AUDIO_TITLE={provider!r} isn't implemented yet (only 'musicbrainz' is) - skipping identification")
        job.status = JobState.VIDEO_WAITING
        db.session.commit()
        return

    # TODO: needs core/audio_cd.py to read the disc TOC and compute a
    # MusicBrainz disc ID before metadata_musicbrainz.lookup_by_disc_id()
    # can be called - not built yet (see this module's docstring).
    logging.info(f"Audio disc in {job.devpath} detected, but TOC reading (core/audio_cd.py) isn't built yet")
    job.status = JobState.VIDEO_WAITING
    db.session.commit()
