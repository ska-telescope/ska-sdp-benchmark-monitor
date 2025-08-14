"""Module to test benchmon-visu"""

import os
import subprocess


def test_unit_benchmon_visu():
    """Unit test for benchmon-visu"""
    cwd = os.path.dirname(__file__)

    cmd = [f"{cwd}/../exec/benchmon-visu",
           "--cpu", "--cpu-all",
           "--cpu-cores-full", "5,6",
           "--cpu-cores-in", "0,11,12",
           "--cpu-cores-out", "8,9,10",
           "--cpu-freq",
           "--mem",
           "--net", "--net-all", "--net-data",
           "--net-rx-only", "--net-tx-only",
           "--disk", "--disk-iops", "--disk-data",
           "--disk-rd-only", "--disk-wr-only",
           "--ib",
           "--sys",
           "--pow",
           "--inline-call",
           "--inline-call-cmd", "cmd0,cmd1,cmd2",
           "--call",
           "--call-depth", "5",
           "--call-depths", "0,2,5",
           "--call-cmd", "cmd0",
           "--annotate-with-log", "ical",
           "--start-time", "'2025-01-01T11:30'",
           "--end-time", "'2025-01-01T11:45'",
           "--interactive",
           "--fig-fmt", "png,svg",
           "--fig-name", "myfig",
           "--fig-dpi", "high",
           "--fig-call-legend-ncol", "8",
           "--fig-width", "25.6",
           "--fig-height-unit", "3",
           "--fig-xrange", "25",
           "--fig-yrange", "11",
           "--verbose",
           "--test",
           f"{cwd}/tmp"]

    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert process.returncode == 0, f"{process.stdout}"
