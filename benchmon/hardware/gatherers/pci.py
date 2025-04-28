"""Docstring @todo."""

import shutil

from benchmon.common.utils import execute_cmd
from benchmon.hardware.gatherers.mounts import logger


class PciReader:
    """Docstring @todo."""

    def read(self):
        """Docstring @todo."""

        if shutil.which("lspci") is not None:
            logger.debug("LSPCI Found!")
            return execute_cmd("lspci -vvv", handle_exception=False)
        elif shutil.which("/sbin/lspci") is not None:
            logger.debug("LSPCI Found at /sbin/lspci!")
            return execute_cmd("/sbin/lspci -vvv", handle_exception=False)
        else:
            logger.warn("Lspci not found")
            return None
