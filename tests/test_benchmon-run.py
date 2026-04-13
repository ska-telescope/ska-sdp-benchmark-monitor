"""Module to test benchmon-run"""

import os
from pathlib import Path
import subprocess
import tempfile
import time

HOSTNAME = os.uname()[1]
JOBID = os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID") or ""
REPO_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = REPO_ROOT / f".benchmon-run_pid_{JOBID}_{HOSTNAME}"


def _env():
    env = os.environ.copy()
    env["PATH"] = f"{REPO_ROOT / '.venv' / 'bin'}:{REPO_ROOT / 'exec'}:{env['PATH']}"
    return env


def _wait_for_pid_file(process: subprocess.Popen, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if PID_FILE.exists():
            content = PID_FILE.read_text(encoding="utf-8").strip().strip(",")
            if content:
                return content
        if process.poll() is not None:
            break
        time.sleep(0.1)
    return ""


def test_benchmon_run():
    """benchmon-run should publish its own PID for CSV mode."""
    PID_FILE.unlink(missing_ok=True)
    save_dir = tempfile.mkdtemp(prefix="benchmon-run-csv-")
    cmd = [
        str(REPO_ROOT / "exec" / "benchmon-run"),
        "--save-dir", save_dir,
        "--verbose",
        "--sys",
        "--test-timeout", "2",
    ]

    process = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        pid_text = _wait_for_pid_file(process)
        assert pid_text == str(process.pid)
        stdout, stderr = process.communicate(timeout=15)
    finally:
        PID_FILE.unlink(missing_ok=True)

    assert process.returncode == 0, f"{stdout}\n{stderr}"


def test_benchmon_run_binary_mode_keeps_parent_pid():
    """benchmon-run should keep the parent PID contract in binary mode."""
    PID_FILE.unlink(missing_ok=True)
    save_dir = tempfile.mkdtemp(prefix="benchmon-run-bin-")
    cmd = [
        str(REPO_ROOT / "exec" / "benchmon-run"),
        "--save-dir", save_dir,
        "--verbose",
        "--sys",
        "--binary",
        "--test-timeout", "2",
    ]

    process = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        pid_text = _wait_for_pid_file(process)
        assert pid_text == str(process.pid)
        stdout, stderr = process.communicate(timeout=15)
    finally:
        PID_FILE.unlink(missing_ok=True)

    assert process.returncode == 0, f"{stdout}\n{stderr}"
