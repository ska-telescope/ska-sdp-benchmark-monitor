"""Functional test for benchmon-visu"""

import os
import shutil
import subprocess
import time


def test_func_benchmon_visu():
    """Functional test for benchmon-visu"""
    cwd = os.path.dirname(__file__)

    cwd = os.path.dirname(__file__)
    now = time.time()
    test_repo = f"{cwd}/tmp/benchmon_savedir_test_{now}"
    os.makedirs(test_repo)

    for i in (8, 9):
        ref_repo = f"{cwd}/data_for_visu/benchmon_traces_neowise-{i}.lyon.grid5000.fr"
        test_subrepo = f"{test_repo}/{os.path.basename(ref_repo)}"
        shutil.copytree(ref_repo, test_subrepo, dirs_exist_ok=True)
        shutil.rmtree(f"{test_subrepo}/pkl_dir")

    cmd = [f"{cwd}/../exec/benchmon-visu",
           "--cpu", "--cpu-all",
           "--cpu-cores-full", "0",
           "--cpu-freq",
           "--mem",
           "--net", "--net-all", "--net-data",
           "--disk", "--disk-iops", "--disk-data",
           "--ib",
           "--pow", "--pow-g5k",
           "--inline-call",
           "--call", "--call-depth", "5",
           "--call-depths", "0,2,5",
           "--interactive",
           "--fig-fmt", "png",
           "--verbose",
           "--recursive",
           f"{test_repo}"]

    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert process.returncode == 0, f"csv stage: {process.stdout}"

    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert process.returncode == 0, f"pkl stage: {process.stdout}"
