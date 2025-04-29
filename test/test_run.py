"""Module to test benchmon-run"""
import sys
import pytest

from benchmon.run import RunMonitor
from benchmon.run import RunUtils


def test_benchmon_run(monkeypatch):
    monkeypatch.setattr("sys.argv", ["benchmon-run", "--save_dir", "/tmp/benchmon_traces", "--sys"])






