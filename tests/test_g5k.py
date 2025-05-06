"""Module to test a run on g5k"""
import subprocess
import time
import os

import pytest

HOSTNAME = os.uname()[1]


def test_g5k():
    """Test benchmon-run on g5k"""

    if "grid5000.fr" in HOSTNAME:

        cwd = os.path.dirname(__file__)
        cmd = [f"{cwd}/g5k/test.sh",
               f"{cwd}/../exec",
               f"{cwd}/tmp/benchmon_traces_{int(time.time())}",
               f"{cwd}/g5k"]

        process = subprocess.run(cmd, capture_output=True, text=False, check=False)
        assert process.returncode == 0, f"{process.stdout}"

    else:
        pytest.skip()
