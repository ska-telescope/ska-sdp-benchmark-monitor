"""Docstring @todo."""
import shutil

from benchmon.common.utils import execute_cmd


class TopologyReader:
    """Docstring @todo."""

    def read(self):
        """Docstring @todo."""

        if shutil.which("lstopo") is not None:
            return execute_cmd("lstopo -vvv")
        return None
