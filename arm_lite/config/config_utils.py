import re
import yaml

def yaml_check_groups(comments: dict, key):
    """
    Check the current key to be added to arm.yaml and insert the group
    separator comment, if the key matches\n
    :param comments: comments dict, containing all comments from the arm.yaml
    :param key: the current post key from form.args
    :return: arm.yaml config with any new comments added
    """
    comment_groups = {'RAW_PATH': "\n" + comments['ARM_CFG_GROUPS']['DIR_SETUP'],
                      'WEBSERVER_IP': "\n" + comments['ARM_CFG_GROUPS']['WEB_SERVER'],
                      'MAKEMKVCON': "\n" + comments['ARM_CFG_GROUPS']['MAKE_MKV'],
                      'HB_PRESETS_FILE': "\n" + comments['ARM_CFG_GROUPS']['HANDBRAKE'],
                      'CUETOOLS_PATH': "\n" + comments['ARM_CFG_GROUPS']['CUETOOLS'],
                      'FFMPEG_CLI': "\n" + comments['ARM_CFG_GROUPS']['FFMPEG'],
                      'METADATA_PROVIDER': "\n" + comments['ARM_CFG_GROUPS']['METADATA']}
    if key in comment_groups:
        arm_cfg = comment_groups[key]
    else:
        arm_cfg = ""

    return arm_cfg

def yaml_check_bool(key: str, value):
    """
    we need to test if the key is a bool, as we need to lower() it for yaml\n\n
    or check if key is the webserver ip. \nIf not we need to wrap the value with quotes\n
    :param key: the current key
    :param value: the current value
    :return: the new updated arm.yaml config with new key: values
    """
    if value.lower() == 'false' or value.lower() == 'true':
        arm_cfg = f"{key}: {value.lower()}\n"
    else:
        if key == "WEBSERVER_IP":
            arm_cfg = f"{key}: {value.lower()}\n"
        else:
            escaped = re.sub(r"(?<!\\)\"\'`", r'\"', value)
            arm_cfg = f"{key}: \"{escaped}\"\n"

    return arm_cfg

def yaml_check_list(key: str, value):
    """
    we need to test if the key is a list/dict. 
    If so we need to format it for yaml
    :param key: the current key
    :param value: the current value
    :return: the new updated arm_lite.yaml config with new key: values
    """
    if isinstance(value, (list, dict)):
        dumped_value = yaml.safe_dump(value, default_flow_style=False).strip()
        return f"{key}: {dumped_value}\n"
    str_value = str(value)
    try:
        post_value = int(str_value)
        return f"{key}: {post_value}\n"
    except ValueError:
        return yaml_check_bool(key, str_value)
