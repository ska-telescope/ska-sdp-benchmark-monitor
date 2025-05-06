"""Test flake8 compatibility"""

import subprocess


def test_flake8():
    """Test flake8 compatiblity"""
    process = subprocess.run(["flake8", "."], capture_output=True, text=True, check=False)
    assert process.returncode == 0, f"{process.stdout}"
