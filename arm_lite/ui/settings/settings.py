import os, re
import platform, importlib
import subprocess
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, \
    session, request, flash
from flask_login import login_required

import arm_lite.config.config as cfg
import arm_lite.ui.utils as ui_utils
from arm_lite.ui import app, db
from arm_lite.ui.forms import GeneralSettingsForm, SystemInfoDrives
from arm_lite.ui.settings import DriveUtils as drive_utils
from arm_lite.ui.settings.ServerUtil import ServerUtil
from arm_lite.core.ProcessHandler import arm_subprocess
from arm_lite.models.system_drives import SystemDrives
from arm_lite.models.system_info import SystemInfo

route_settings = Blueprint("settings", __name__,
                           static_folder="./static",
                           template_folder="templates",
                           url_prefix="/settigns")
REDIRECT_SETTINGS = "settings.settings_page"

def check_hw_transcode_support():
    handbrakecli = os.path.expandvars(cfg.arm_config.get("HANDBRAKE_CLI"))
    cmd = f"nice {handbrakecli}"

    app.logger.debug(f"Sending command: {cmd}")
    hw_support_status = {
        "nvidia": False,
        "intel": False,
        "amd": False
    }
    try:
        hand_brake_output = arm_subprocess(f"{cmd}", shell=True, check=True)

        # NVENC
        if re.search(r'nvenc: version ([0-9\\.]+) is available', str(hand_brake_output)):
            app.logger.info("NVENC supported!")
            hw_support_status["nvidia"] = True
        # Intel QuickSync
        if re.search(r'qsv:\sis(.*?)available\son', str(hand_brake_output)):
            app.logger.info("Intel QuickSync supported!")
            hw_support_status["intel"] = True
        # AMD VCN
        if re.search(r'vcn:\sis(.*?)available\son', str(hand_brake_output)):
            app.logger.info("AMD VCN supported!")
            hw_support_status["amd"] = True
        app.logger.info("Handbrake call successful")
        app.logger.debug(hand_brake_output)
    except subprocess.CalledProcessError:
        pass
    return hw_support_status

@route_settings.route('/settings')
@login_required
def settings_page():
    # Get server time and timezone
    current_time = datetime.now()
    server_datetime = current_time.strftime(cfg.arm_config.get("DATE_FORMAT"))
    server_timezone = os.environ.get("TZ", "Etc/UTC")
    [arm_version_local, arm_version_remote] = ui_utils.git_check_version()
    local_get_hash = ui_utils.get_git_revision_hash()

    stats = {
        "server_datetime": server_datetime,
        "server_timezone": server_timezone,
        "python_version": platform.python_version(),
        "arm_local_version": arm_version_local,
        "arm_remote_version": arm_version_remote,
        'git_commit': local_get_hash,
        "updated": ui_utils.git_check_updates(local_get_hash),
        "hw_support": check_hw_transcode_support()
    }
    server = SystemInfo.query.filter_by(id='1').first()
    serverutil = ServerUtil()
    arm_path = os.path.expandvars(cfg.arm_config.get("TRANSCODE_PATH"))
    media_path = os.path.expandvars(cfg.arm_config.get("COMPLETED_PATH"))

    drives = drive_utils.get_drives()
    form_drive = SystemInfoDrives(request.form)

    comments = ui_utils.generate_comments()
    form = GeneralSettingsForm()

    session["page_title"] = "Settings"

    return render_template("settings/settings.html", settings=cfg.arm_config, stats=stats, server=server,
                           serverutil=serverutil, arm_path=arm_path, media_path=media_path, form=form, 
                           jsoncomments=comments, drives=drives, form_drive=form_drive)

@route_settings.route("/save-settings", methods=["POST"])
@login_required
def save_settings():
    """
    Page - save-settings
    Method - POST
    Overview - Save ARM ripper settings from post. Not a user page.
    """
    comments = ui_utils.generate_comments()
    success = False
    arm_cfg = {}
    form = GeneralSettingsForm()
    if form.validate_on_submit():
        arm_cfg = ui_utils.build_arm_cfg(request.form.to_dict(), comments)
        try:
            with open(cfg.arm_config_path, 'w') as settings_file:
                settings_file.write(arm_cfg)
                settings_file.close()
            success = True
            importlib.reload(cfg)
            app.logger.info(f"Setting log level to: {cfg.arm_config["LOGLEVEL"]}")
            app.logger.setLevel(cfg.arm_config["LOGLEVEL"])
        except OSError as e:
            app.logger.error(f"{cfg.arm_config_path} is read-only", exc_info=e)
    return {'success': success, 'settings': cfg.arm_config, 'form': "arm ripper settings"}

@route_settings.route("/system-info", methods=["POST"])
@login_required
def server_info():
    form_drive = SystemInfoDrives(request.form)
    if request.method == "POST" and form_drive.validate():
        app.logger.debug(
            f"Drive id: {str(form_drive.id.data)}" +
            f"Updated name: {str(form_drive.name.data)}" +
            f"Updated description: [{str(form_drive.description.data)}]" +
            f"Updated mode: [{str(form_drive.drive_mode.data)}]")
        drive = SystemDrives.query.filter_by(drive_id=form_drive.id.data).first()
        drive.description = str(form_drive.description.data).strip()
        drive.name = str(form_drive.name.data).strip()
        drive.drive_mode = str(form_drive.drive_mode.data).strip()
        db.session.commit()
        app.logger.info(f"Updated Drive {drive.name} details")
        return redirect(url_for(REDIRECT_SETTINGS))
    else:
        app.logger.error(f"ERROR: Unable to update Drive details")
        return redirect(url_for(REDIRECT_SETTINGS))

@route_settings.route('/updatesysinfo')
@login_required
def update_sysinfo():
    """
    Update system information
    """
    # Get current system information from database
    current_system = SystemInfo.query.first()
    # Query system for new information
    new_system = SystemInfo()

    app.logger.debug("****** System Information ******")
    if current_system is not None:
        app.logger.debug(f"Name old [{current_system.name}] new [{new_system.name}]")
        app.logger.debug(f"Name old [{current_system.cpu}] new [{new_system.cpu}]")
        app.logger.debug(f"Name old [{current_system.mem_total}] new [{new_system.mem_total}]")
        current_system.name = new_system.name
        current_system.cpu = new_system.cpu
        current_system.mem_total = new_system.mem_total
        db.session.add(current_system)
    else:
        app.logger.debug(f"Name old [No Info] new [{new_system.name}]")
        app.logger.debug(f"Name old [No Info] new [{new_system.cpu}]")
        app.logger.debug(f"Name old [No Info] new [{new_system.mem_total}]")
        db.session.add(new_system)

    app.logger.debug("****** End System Information ******")
    app.logger.info(f"Updated CPU Details with new info - {new_system.name} - {new_system.cpu} - "
                    f"{new_system.mem_total}")

    db.session.commit()

    return redirect(url_for(REDIRECT_SETTINGS))

@route_settings.route('/systemdrivescan')
@login_required
def system_drive_scan():
    """
    Page - systemdrivescan
    Method - GET
    Overview - Scan for the system drives and update the database.
    """
    # Update to scan for changes to the ripper system
    new_count = drive_utils.drives_update()
    flash(f"ARM found {new_count} new drives", "success")
    return redirect(url_for(REDIRECT_SETTINGS))
