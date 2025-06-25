import subprocess
from pathlib import Path


def test_flake8():
    """Test flake8 compatibility"""
    root_dir = Path(__file__).resolve().parent
    process = subprocess.run(
        ["flake8", str(root_dir)],
        capture_output=True,
        text=True,
        check=False
    )
    assert process.returncode == 0, process.stdout + process.stderr
