"""Utils module"""

import subprocess
import logging
import re
from typing import Type

from benchmon.exceptions import CommandExecutionFailed

log = logging.getLogger(__name__)


def execute_cmd(cmd_str, handle_exception=True):
    """Accept command string and returns output.

    Args:
        cmd_str (str): Command string to be executed
        handle_exception (bool): Handle exception manually. If set to false, raises an exception
                                 to the caller function
    Returns:
        str: Output of the command. If command execution fails, returns 'not_available'
    Raises:
        subprocess.CalledProcessError: An error occurred in execution of command iff
                                       handle_exception is set to False
    """

    log.debug("Executing command: %s", cmd_str)

    try:
        # Execute command
        cmd_out = subprocess.run(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)

        # Get stdout and stderr. We are piping stderr to stdout as well
        cmd_out = cmd_out.stdout.decode("utf-8").rstrip()
    except subprocess.CalledProcessError as err:
        # If handle_exception is True, return 'not_available'
        if handle_exception:
            cmd_out = "not_available"
        else:
            # If handle_exception is False, raise an exception
            log.warning(f"Execution of command {cmd_str} failed")
            raise CommandExecutionFailed(f"Execution of command '{cmd_str}' failed.") from err

    return cmd_out


def get_parser(cmd_output, reg="lscpu"):
    """Regex parser.

    Args:
        cmd_output (str): Output of the executed command
        reg (str): Regex pattern to be used
    Returns:
        Function handle to parse the output
    """

    def parser(pattern):
        """Parser function."""

        # Different regex for parsing different outputs
        if reg == "perf":
            exp = r"(?P<Value>[0-9,]*\s*)(?P<Field>{}.*)".format(pattern)
        elif reg == "perf-intvl":
            exp = r"(?P<Time>[0-9.]*\s*)" r"(?P<Value>[0-9,><a-zA-Z\s]*\s*)" r"(?P<Field>{}.*)".format(pattern)
        else:
            exp = r"(?P<Field>{}:\s*\s)(?P<Value>.*)".format(pattern)

        # Search pattern in output
        result = re.search(exp, cmd_output)

        try:
            # Get value of the group if found
            return result.group("Value")

        except AttributeError:
            # If not found, return None
            return None

    return parser


def safe_parse(t: Type, data: str) -> str:
    """Docstring @todo."""

    try:
        return t(data)
    except Exception:
        log.info(f'Could not parse "{data}" to type "{t}". Setting value to N/A')
        return "N/A"
