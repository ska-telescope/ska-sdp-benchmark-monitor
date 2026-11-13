"""Module for testing the benchmon-check"""

import os
import subprocess


def test_benchmon_check():
    """Test benchmon-check"""
    cwd = os.path.dirname(__file__)

    cmd = [f"{cwd}/../exec/benchmon-check"]

    process = subprocess.run(cmd, capture_output=True, text=True)
    assert process.returncode == 0, f"{process.stdout}"
