import os
import json, yaml
from pathlib import Path

import arm_lite.config.config_utils as cfg_utils

CONFIG_PATH = Path(__file__).resolve().parent.parent
COMMENTS_PATH = CONFIG_PATH / "ui" / "comments.json"
arm_config: dict[str, str]
arm_config_path: str = os.path.join(CONFIG_PATH, "arm_lite.yaml")

hb_presets: dict[str, str]

def load_config(file_path: str | os.PathLike) -> dict[str, str]:
    """
    Load configuration from a YAML or JSON file.

    Args:
        file_path (str | os.PathLike): Path to the configuration file.
    """
    path = Path(file_path)
    if path.exists():
        try:
            with open(path, 'r') as yaml_file:
                config = yaml.safe_load(yaml_file) or {}
            return config
        except Exception as e:
            print(f"ERROR: Unable to read configuration file {file_path} - {e}")
            return {}
    else:
        print(f"ERROR: Unable to locate configuration file {file_path}")
        return {}

cur_config = load_config(arm_config_path)                                   # Load User Configuration
arm_config = load_config(CONFIG_PATH.parent / "setup" / "arm_lite.yaml")    # Load Template Configuration
arm_config.update(cur_config)                                               # Update Template Configuration with User Configuration

def load_hb_presets(file_path: str | os.PathLike = None) -> dict[str, str]:
    """
    Load presets from a JSON file.
    
    Args:
        file_path (str | os.PathLike): Path to the presets file.
    """
    if file_path is None:
        file_path = arm_config.get("HB_PRESETS_FILE")
        if not file_path:
            print("ERROR: HandBrake Presets file path not specified in configuration.")
            return {}
        json_path = Path(os.path.expandvars(file_path))
    elif not json_path.exists():
        print(f"ERROR: Unable to locate HandBrake Presets file {json_path}")
        return {}

    try:
        with open(json_path, 'r') as json_file:
            data = json.load(json_file)
    except Exception as e:
        print(f"ERROR: Unable to read HandBrake Presets file {json_path} - {e}")
        return {}
    hb_presets = {}
    for category in data.get("PresetList", []):
        cat_name = category.get("PresetName", "Unrecognized")
        children = category.get("ChildrenArray", [])
        presets = [c["PresetName"] for c in children if "PresetName" in c]
        hb_presets[cat_name] = presets
    return hb_presets

hb_presets_cfg = load_hb_presets()

def save_config(new_config: dict, path: str = None):
    """
    Save the configuration to a YAML file, and reload HandBrake presets.
    Args:
        new_config (dict): The configuration dictionary to save.
        path (str): The path to the configuration file. If None, uses the default arm_config_path.
    """
    global arm_config, hb_presets_cfg
    write_path = path if path else arm_config_path
    os.makedirs(os.path.dirname(write_path), exist_ok=True)
    try:
        with open(write_path, 'w') as yaml_file:
            yaml.safe_dump(new_config, yaml_file, default_flow_style=False, sort_keys=False)
        arm_config = new_config
    except Exception as e:
        print(f"ERROR: Unable to write configuration file {write_path} - {e}")
    try:
        hb_presets_cfg = load_hb_presets()
    except Exception as e:
        print(f"ERROR: Unable to reload HandBrake presets after save - {e}")
        hb_presets_cfg = {}

def build_config(config: dict = None, write_path: str = None) -> str:
    """
    Rebuild arm_config.yaml with the human-readable comments from
    comments.json, preserving the given config's values (defaults to the
    live arm_config).
    Args:
        key (str): The configuration key to update.
        value: The new value for the configuration key.
    Returns:
        str: The updated configuration as a YAML-formatted string.
    """
    config = arm_config if config is None else config
    target_path = arm_config_path if write_path is None else write_path

    try:
        with open(COMMENTS_PATH, 'r') as comments_file:
            comments = json.load(comments_file)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: Unable to read comments file {COMMENTS_PATH} - {e}")
        return ""

    arm_cfg = comments["ARM_CFG_GROUPS"]["BEGIN"] + "\n\n"
    for key, value in config.items():
        arm_cfg += cfg_utils.yaml_check_groups(comments, key)    # Add any grouping comments
        # Check for comments for this key in comments.json, add them if they exist
        try:
            if comment := comments[str(key)]:
                arm_cfg += f"\n{comment}\n"
        except KeyError:
            arm_cfg += '\n'
        arm_cfg += cfg_utils.yaml_check_list(key, value)

    if target_path is not False:
        try:
            with open(target_path, 'w') as settings_file:
                settings_file.write(arm_cfg)
        except OSError as e:
            print(f"ERROR: Unable to write {target_path} - {e}")

    return arm_cfg
