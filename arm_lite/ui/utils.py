import os
import secrets
from flask_login import current_user

import arm_lite.config.config as cfg

def get_or_create_secret_key() -> str:
    key = cfg.arm_config.get("FLASK_SECRET_KEY")
    if key:
        return key
    key = secrets.token_hex(32)
    cfg.arm_config["FLASK_SECRET_KEY"] = key
    try:
        cfg.build_config()
    except Exception as e:
        print(f"WARN: Could not persist generated FLASK_SECRET_KEY to arm_lite.yaml: {e}")
    return key

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