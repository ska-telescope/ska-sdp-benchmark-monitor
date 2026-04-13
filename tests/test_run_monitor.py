"""Module to test benchmon-run"""

import argparse
import json
import os
from pathlib import Path
import time

from benchmon.run import RunMonitor
from benchmon.run import RunUtils

HOSTNAME = os.uname()[1]
JOBID = os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID") or ""


def create_args(save_dir: str = "/tmp/benchmon_savedir_test",
                binary: bool = False,
                verbose: bool = False,
                system: bool = False,
                sys_freq: int = 10,
                power: bool = False,
                power_sampling_interval: int = 250,
                power_g5k: bool = False,
                call: bool = False,
                call_mode: str = "dwarf,32",
                call_profiling_frequency: int = 10,
                call_keep_datafile: bool = False,
                csv: bool = True,
                grafana: bool = False,
                grafana_influxdb_url: str = "http://localhost:8086",
                grafana_token: str = "",
                grafana_job_name: str = "benchmon",
                grafana_batch_size: int = 50,
                grafana_sample_interval: float = 2.0,
                start_after: int = 0) -> argparse.ArgumentParser:
    """
    Create arguments for run_monitor test
    """
    save_dir += f"_{int(time.time())}"
    os.makedirs(save_dir, exist_ok=True)

    return argparse.Namespace(**locals())


def run(args: argparse.ArgumentParser, timeout: int = 1, with_pid: bool = False):
    """
    run_monitor with args and timeout
    """
    logger = RunUtils.create_logger(save_dir=args.save_dir, verbose=args.verbose)

    if with_pid:
        RunUtils.get_benchmon_pid(logger)

    run_monitor = RunMonitor(args, logger)
    run_monitor.run(timeout=timeout)


def test_repo_log_pid():
    """Test existence of traces repo and log file"""
    args = create_args()
    timeout = 1
    run(args=args, timeout=timeout, with_pid=True)

    path = Path(f"./.benchmon-run_pid_{JOBID}_{HOSTNAME}")
    assert path.is_file(), f"{path} file does not exist"

    path = Path(f"{args.save_dir}/benchmon_traces_{HOSTNAME}")
    assert path.is_dir(), f"{path} directory does not exist"

    path = Path(f"{args.save_dir}/benchmon_{HOSTNAME}.log")
    assert path.is_file(), f"{path} file does not exist"


def test_sys():
    """Test system monitoring"""
    args = create_args(system=True, sys_freq=10)
    timeout = 2
    run(args=args, timeout=timeout)

    filenames = ["cpufreq_report.csv", "cpu_report.csv", "disk_report.csv", "mem_report.csv", "net_report.csv"]
    for filename in filenames:
        path = Path(f"{args.save_dir}/benchmon_traces_{HOSTNAME}/{filename}")
        assert path.is_file(), f"{path} file does not exist"
        assert sum(1 for _ in path.open()) >= 10, f"{path} file has less than 10 lines"


def test_pow():
    """Test power monitoring"""
    args = create_args(power=True, power_sampling_interval=100)
    timeout = 2
    run(args=args, timeout=timeout)

    path = Path(f"{args.save_dir}/benchmon_traces_{HOSTNAME}/pow_report.csv")
    assert path.is_file(), f"{path} file does not exist"
    assert sum(1 for _ in path.open()) >= 10, f"{path} file has less than 10 lines"


def test_pow_g5k():
    """Test retrieving g5k power metrics"""

    if "grid5000.fr" in HOSTNAME:

        args = create_args(power_g5k=True)
        timeout = 3
        run(args=args, timeout=timeout)

        filenames = ["g5k_pow_report_bmc_node_power_watt.json", "g5k_pow_report_wattmetre_power_watt.json"]
        for filename in filenames:
            path = Path(f"{args.save_dir}/benchmon_traces_{HOSTNAME}/{filename}")
            assert path.is_file(), f"{path} file does not exist"
            assert sum(1 for _ in path.open()) >= 1, f"{path} file has less than 10 lines"


def test_call():
    """Test call stack recording"""
    args = create_args(call=True, call_mode="dwarf,32",
                       call_profiling_frequency=10, call_keep_datafile=True)
    timeout = 2
    run(args=args, timeout=timeout)

    filenames = ["call_report.txt", "mono_to_real_file.txt", "_temp_perf.data"]
    for filename in filenames:
        path = Path(f"{args.save_dir}/benchmon_traces_{HOSTNAME}/{filename}")
        assert path.is_file(), f"{path} file does not exist"


def test_grafana_mode_uses_cli_config_without_connection_file():
    """Grafana mode should start without requiring connection.json."""
    args = create_args(grafana=True, csv=False, grafana_influxdb_url="http://localhost:8181")
    logger = RunUtils.create_logger(save_dir=args.save_dir, verbose=args.verbose)

    class DummyCollector:
        def __init__(self):
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    dummy_collector = DummyCollector()
    run_monitor = RunMonitor(args, logger)
    run_monitor._create_hp_collector = lambda: dummy_collector
    run_monitor.run(timeout=1)

    assert dummy_collector.started
    assert dummy_collector.stopped
    assert run_monitor.influxdb_config["url"] == "http://localhost:8181"


def test_grafana_mode_prefers_cli_over_connection_file():
    """CLI Grafana settings should override connection.json values."""
    args = create_args(
        grafana=True,
        csv=False,
        grafana_influxdb_url="http://override-host:8181",
        grafana_token="override-token",
    )
    connection_dir = Path(args.save_dir) / "grafana-data"
    connection_dir.mkdir(parents=True, exist_ok=True)
    with open(connection_dir / "connection.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "influxdb_url": "http://file-host:8181",
                "influxdb_token": "file-token",
            },
            f,
        )

    logger = RunUtils.create_logger(save_dir=args.save_dir, verbose=args.verbose)
    run_monitor = RunMonitor(args, logger)

    config = run_monitor._build_influxdb_config()

    assert config["url"] == "http://override-host:8181"
    assert config["token"] == "override-token"
