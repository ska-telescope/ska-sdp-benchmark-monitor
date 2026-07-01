"""Module to test benchmon-visu"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import types


def test_unit_benchmon_visu():
    """Unit test for benchmon-visu"""
    cwd = os.path.dirname(__file__)

    cmd = [sys.executable, f"{cwd}/../exec/benchmon-visu",
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
           "--pow-g5k",
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


def test_influxdb_mode_creates_output_directory(tmp_path, monkeypatch):
    """InfluxDB mode should treat the positional argument as an output directory."""
    script_path = os.path.join(os.path.dirname(__file__), "..", "exec", "benchmon-visu")
    loader = importlib.machinery.SourceFileLoader("benchmon_visu_script", script_path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    output_dir = tmp_path / "benchmon_influx_figures"

    class DummyVisualizer:
        def __init__(self, args, logger, traces_repo):
            assert traces_repo == str(output_dir)
            assert output_dir.exists()

        def run_plots(self):
            return None

    fake_module = types.ModuleType("benchmon.visualization.visualizer_influxdb")
    fake_module.BenchmonInfluxDBVisualizer = DummyVisualizer

    monkeypatch.setitem(sys.modules, "benchmon.visualization.visualizer_influxdb", fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_path,
            str(output_dir),
            "--influxdb",
            "--influxdb-url",
            "http://localhost:8181",
            "--cpu",
        ],
    )

    assert module.main() == 0
    assert output_dir.exists()
