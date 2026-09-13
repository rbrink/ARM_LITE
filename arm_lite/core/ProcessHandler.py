"""
Function definition
  Wrapper for the python subprocess module
"""

import logging
import subprocess
import platform
import re
from typing import Optional, List, Union


def arm_subprocess(cmd: Union[str, List[str]], shell=False, check=False) -> Optional[str]:
    """
    Spawn blocking subprocess

    :param cmd: Command to run
    :param shell: Run ``cmd`` in a shell
    :param check: Raise ``CalledProcessError`` if ``cmd`` returns non-zero exit code

    :return: Output (both stdout and stderr) of ``cmd``, or ``None`` if it returned a non-zero exit code

    :raise CalledProcessError:
    """
    arm_process = None
    # On Windows the `nice` utility is not available; strip it if present
    if platform.system() == "Windows":
        if isinstance(cmd, str):
            # remove leading 'nice' or 'nice -n <num>' from a string command
            cmd = re.sub(r'^nice(\s+-n\s+\S+)?\s+', '', cmd)
        elif isinstance(cmd, (list, tuple)) and len(cmd) > 0 and cmd[0] == 'nice':
            cmd = list(cmd[1:])

    logging.debug(f"Running command: {cmd}")
    try:
        arm_process = subprocess.check_output(
            cmd,
            shell=shell,
            stderr=subprocess.STDOUT,
            encoding="utf-8"
        )
    except (subprocess.CalledProcessError, OSError) as error:
        decoded_output: Optional[str] = None
        if isinstance(error, subprocess.CalledProcessError):
            decoded_output = error.output.strip()
        logging.error(
            f"Error while running command: {cmd}\n"
            + (
                f"Output was: {decoded_output}"
                if decoded_output
                else "The command produced no output."
            ),
            exc_info=error,
        )
        if check:
            raise error

    return arm_process