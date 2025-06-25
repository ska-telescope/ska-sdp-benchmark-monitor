"""Module to test benchmon-run"""

import os
import subprocess
import time


def test_benchmon_run():
    """Test benchmon-run"""
    cwd = os.path.dirname(__file__)

    cmd = [f"{cwd}/../exec/benchmon-run",
           "--save-dir", f"{cwd}/tmp/benchmon_traces_{int(time.time())}",
           "--verbose",
           "--sys", "--sys-freq", "100",
           "--pow", "--pow-sampl-intv", "100",
           "--call", "--call-mode", "br,32",
           "--call-prof-freq", "100",
           "--call-keep-datafile",
           "--test-timeout", "5"]

    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert process.returncode == 0, f"{process.stdout}"
