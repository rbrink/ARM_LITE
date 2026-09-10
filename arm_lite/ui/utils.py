import os
import secrets

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

