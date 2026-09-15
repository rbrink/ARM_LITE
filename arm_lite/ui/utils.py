import os, re
import json
import requests
import subprocess
from flask_login import current_user

import arm_lite.config.config as cfg
import arm_lite.config.config_utils as config_utils
from arm_lite.ui import app

def authenticated_state() -> bool:
    """
    Determines whether the current user is considered authenticated.

    This function checks the application's configuration to see if login
    authentication is disabled. If login is disabled, it automatically
    returns `True`, indicating that the user is authenticated. Otherwise,
    it checks the `current_user.is_authenticated` attribute provided by
    Flask-Login to determine if the user is logged in.

    Returns:
        bool: `True` if the user is authenticated, either by bypassing
        the login requirement or by being a logged-in user; `False` otherwise.
    """
    authenticated = False
    if cfg.arm_config['DISABLE_LOGIN']:
        authenticated = True
    else:
        if current_user.is_authenticated:
            authenticated = True

    return authenticated

def git_check_version():
    """
    Check the current ARM version locally against the remote (GitHub) version.

    This function compares the installed ARM version with the latest version available
    in the remote GitHub repository.

    :return:
        tuple: (local_version, remote_version)
            - local_version (str): The version currently installed locally (from the VERSION file).
            - remote_version (str): The latest version available in the remote repository.
    """

    install_path = os.path.expandvars(cfg.arm_config['INSTALL_PATH'])

    # Read the local version from the VERSION file
    version_file_path = os.path.join(install_path, 'VERSION')
    try:
        with open(version_file_path) as version_file:
            local_version = version_file.read().strip()
    except FileNotFoundError as e:
        app.logger.debug(f"Error - ARM Local Version file not found: {e}")
    except IOError as e:
        app.logger.debug(f"Error - ARM Local Version file error: {e}")

    # Read the remote version from Git (without modifying local files)
    try:
        remote_version = subprocess.check_output(
            ['git', 'show', 'origin/HEAD:VERSION'], cwd=install_path
        ).decode('ascii').strip()
    except subprocess.CalledProcessError as e:
        app.logger.debug(f"Error - ARM Remote Version error: {e}")
        remote_version = "Unknown"

    app.logger.debug(f"Local version: {local_version}")
    app.logger.debug(f"Remote version: {remote_version}")

    return local_version, remote_version

def generate_comments():
    """
    load comments.json and use it for settings page
    allows us to easily add more settings later
    :return: json
    """
    comments_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comments.json")
    try:
        with open(comments_file, "r") as comments_read_file:
            try:
                comments = json.load(comments_read_file)
            except Exception as error:
                app.logger.debug(f"Error with comments file. {error}")
                comments = "{'error':'" + str(error) + "'}"
    except FileNotFoundError:
        comments = "{'error':'File not found'}"
    return comments

def build_arm_cfg(form_data: dict, comments):
    """
    Main function for saving new updated arm.yaml\n
    :param form_data: post data
    :param comments: comments file loaded as dict
    :return: full new arm.yaml as a String
    """
    arm_cfg = comments['ARM_CFG_GROUPS']['BEGIN'] + "\n\n"
    # This is not the safest way to do things.
    # It assumes the user isn't trying to mess with us.
    # This really should be hard coded.
    app.logger.debug("save_settings: START")
    for key, value in form_data.items():
        # Skip the Cross Site Request Forgery (CSRF) token
        if key == "csrf_token":
            continue

        if value is None:
            value = ""
        # Strip whitespace from values to prevent issues with keys/values
        if isinstance(value, str):
            value = value.strip()
        # Check if value contains "KEY" or "API" (any case)
        if re.search(r"_KEY|_API|_PASSWORD", key):
            key_value = "####--redacted--####"
        else:
            key_value = value
        # Print output
        app.logger.debug(f"save_settings: [{key}] = {key_value} ")

        # Add any grouping comments
        arm_cfg += config_utils.yaml_check_groups(comments, key)
        # Check for comments for this key in comments.json, add them if they exist
        try:
            arm_cfg += "\n" + comments[str(key)] + "\n" if comments[str(key)] != "" else ""
        except KeyError:
            arm_cfg += "\n"

        arm_cfg += config_utils.yaml_check_list(key, value)

    app.logger.debug("save_settings: FINISH")
    return arm_cfg

def get_git_revision_hash() -> str:
    """Get full hash of current git commit"""
    git_hash: str = 'unknown'
    install_path = os.path.expandvars(cfg.arm_config.get("INSTALL_PATH"))
    try:
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                           cwd=install_path).decode('ascii').strip()
        # Trunkate to seven characters (aligns with the github commit values reported)
        git_hash = git_hash[:7]
        app.logger.debug(f"GIT revision: {git_hash}")
    except subprocess.CalledProcessError as e:
        app.logger.debug(f"GIT revision error: {e}")

    return git_hash

def git_check_updates(current_hash) -> bool:
    """
    Check the ARM commit hash against the remote (GitHub) commit hash
    :param
        current_hash: str - string of current ARM commit hash
    :return:
        arm_current: Bool - True for no update (or exceptions), False for update possible
    """
    # GitHub API url - branch main
    url = "https://api.github.com/repos/rbrink/ARM_LITE/commits/main"
    arm_current = True      # set True, any exceptions will return a true value

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an error for HTTP failures (4xx, 5xx)

        latest_commit = response.json().get("sha", "").strip()
        if not latest_commit:
            app.logger.error("Failed to retrieve latest commit hash from GitHub API.")

        # Compare local and remote hashes
        arm_current = latest_commit.startswith(current_hash)

        app.logger.debug(f"Remote hash: {latest_commit}")
        app.logger.debug(f"Local hash: {current_hash}")
        app.logger.debug(f"ARM current: {arm_current}")

    except requests.RequestException as e:
        app.logger.error(f"GitHub API request failed: {e}")

    return arm_current
