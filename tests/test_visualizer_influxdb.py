import argparse
from datetime import datetime, timezone
import logging
import re

import pytest

from benchmon.visualization.system_metrics_influxdb import SystemDataInfluxDB
from benchmon.visualization.visualizer_influxdb import BenchmonInfluxDBVisualizer


BASE_TS = 1_700_000_000
HOSTNAME = "test-host-a"
HOSTNAME_2 = "test-host-b"


def ts(offset: int) -> datetime:
    return datetime.fromtimestamp(BASE_TS + offset, tz=timezone.utc)


def ts_text(offset: int) -> str:
    return datetime.fromtimestamp(BASE_TS + offset).strftime("%Y-%m-%dT%H:%M:%S")


DATA = {
    "variable": [
        {"hostname": HOSTNAME, "time": ts(0), "stamp": int(ts(0).timestamp() * 1e9)},
        {"hostname": HOSTNAME_2, "time": ts(3600), "stamp": int(ts(3600).timestamp() * 1e9)},
    ],
    "cpu_total": [
        {"hostname": HOSTNAME, "time": ts(0), "user": 100, "nice": 0, "system": 50, "idle": 800, "iowait": 10, "irq": 0, "softirq": 5, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "time": ts(60), "user": 140, "nice": 0, "system": 70, "idle": 840, "iowait": 10, "irq": 0, "softirq": 10, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "time": ts(120), "user": 180, "nice": 0, "system": 95, "idle": 870, "iowait": 10, "irq": 0, "softirq": 15, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME_2, "time": ts(3600), "user": 200, "nice": 0, "system": 60, "idle": 900, "iowait": 10, "irq": 0, "softirq": 5, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME_2, "time": ts(3660), "user": 230, "nice": 0, "system": 80, "idle": 930, "iowait": 10, "irq": 0, "softirq": 7, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME_2, "time": ts(3720), "user": 260, "nice": 0, "system": 95, "idle": 970, "iowait": 10, "irq": 0, "softirq": 9, "steal": 0, "guest": 0, "guest_nice": 0},
    ],
    "cpu_core": [
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(0), "user": 50, "nice": 0, "system": 20, "idle": 400, "iowait": 5, "irq": 0, "softirq": 2, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(0), "user": 50, "nice": 0, "system": 30, "idle": 400, "iowait": 5, "irq": 0, "softirq": 3, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(60), "user": 70, "nice": 0, "system": 30, "idle": 420, "iowait": 5, "irq": 0, "softirq": 4, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(60), "user": 70, "nice": 0, "system": 40, "idle": 420, "iowait": 5, "irq": 0, "softirq": 6, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(120), "user": 90, "nice": 0, "system": 40, "idle": 435, "iowait": 5, "irq": 0, "softirq": 6, "steal": 0, "guest": 0, "guest_nice": 0},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(120), "user": 90, "nice": 0, "system": 55, "idle": 435, "iowait": 5, "irq": 0, "softirq": 9, "steal": 0, "guest": 0, "guest_nice": 0},
    ],
    "cpu_freq": [
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(0), "value": 2_000_000},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(0), "value": 1_800_000},
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(60), "value": 2_100_000},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(60), "value": 1_900_000},
        {"hostname": HOSTNAME, "cpu": "cpu0", "time": ts(120), "value": 2_200_000},
        {"hostname": HOSTNAME, "cpu": "cpu1", "time": ts(120), "value": 2_000_000},
    ],
    "memory": [
        {"hostname": HOSTNAME, "time": ts(0), "memtotal": 8 * 1024**3, "memfree": 4 * 1024**3, "buffers": 200_000_000, "cached": 300_000_000, "slab": 100_000_000, "swaptotal": 2 * 1024**3, "swapfree": 2 * 1024**3, "swapcached": 0},
        {"hostname": HOSTNAME, "time": ts(60), "memtotal": 8 * 1024**3, "memfree": 3 * 1024**3, "buffers": 220_000_000, "cached": 350_000_000, "slab": 110_000_000, "swaptotal": 2 * 1024**3, "swapfree": 2 * 1024**3, "swapcached": 0},
        {"hostname": HOSTNAME, "time": ts(120), "memtotal": 8 * 1024**3, "memfree": 2 * 1024**3, "buffers": 240_000_000, "cached": 400_000_000, "slab": 120_000_000, "swaptotal": 2 * 1024**3, "swapfree": int(1.5 * 1024**3), "swapcached": 0},
        {"hostname": HOSTNAME_2, "time": ts(3600), "memtotal": 16 * 1024**3, "memfree": 12 * 1024**3, "buffers": 300_000_000, "cached": 500_000_000, "slab": 200_000_000, "swaptotal": 0, "swapfree": 0, "swapcached": 0},
        {"hostname": HOSTNAME_2, "time": ts(3660), "memtotal": 16 * 1024**3, "memfree": 11 * 1024**3, "buffers": 320_000_000, "cached": 540_000_000, "slab": 210_000_000, "swaptotal": 0, "swapfree": 0, "swapcached": 0},
        {"hostname": HOSTNAME_2, "time": ts(3720), "memtotal": 16 * 1024**3, "memfree": 10 * 1024**3, "buffers": 340_000_000, "cached": 600_000_000, "slab": 220_000_000, "swaptotal": 0, "swapfree": 0, "swapcached": 0},
    ],
    "network_stats": [
        {"hostname": HOSTNAME, "interface": "eth0", "time": ts(0), "rx_bytes": 0, "tx_bytes": 0},
        {"hostname": HOSTNAME, "interface": "eth0", "time": ts(60), "rx_bytes": 60_000_000, "tx_bytes": 120_000_000},
        {"hostname": HOSTNAME, "interface": "eth0", "time": ts(120), "rx_bytes": 120_000_000, "tx_bytes": 180_000_000},
    ],
    "disk_stats": [
        {"hostname": HOSTNAME, "device": "sda", "time": ts(0), "sectors_read": 0, "sectors_written": 0},
        {"hostname": HOSTNAME, "device": "sda", "time": ts(60), "sectors_read": 60_000, "sectors_written": 30_000},
        {"hostname": HOSTNAME, "device": "sda", "time": ts(120), "sectors_read": 120_000, "sectors_written": 45_000},
    ],
    "infiniband": [
        {"hostname": HOSTNAME, "device": "mlx5_0", "time": ts(0), "port_rcv_data": 0, "port_xmit_data": 0},
        {"hostname": HOSTNAME, "device": "mlx5_0", "time": ts(60), "port_rcv_data": 15_000_000, "port_xmit_data": 20_000_000},
        {"hostname": HOSTNAME, "device": "mlx5_0", "time": ts(120), "port_rcv_data": 30_000_000, "port_xmit_data": 35_000_000},
    ],
}


class FakeInfluxDBClient3:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def close(self):
        self.closed = True

    def query(self, query, language="sql", mode="all", database=None, query_parameters=None, **kwargs):
        params = query_parameters or {}
        match = re.search(r"FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)", query)
        measurement = match.group(1) if match else None

        if "SELECT DISTINCT hostname" in query:
            if measurement is None:
                return []
            rows = self._filter_rows(DATA.get(measurement, []), params)
            return [{"hostname": hostname} for hostname in sorted({row["hostname"] for row in rows})]

        if measurement is None:
            return []

        rows = self._filter_rows(DATA[measurement], params)

        if measurement == "variable" and "SELECT stamp" in query:
            return [{"stamp": rows[0]["stamp"]}] if rows else []

        if "COUNT(DISTINCT time)" in query:
            return [{"sample_count": len({row["time"] for row in rows})}]

        if "MIN(time) AS min_time" in query:
            if not rows:
                return [{"min_time": None, "max_time": None}]
            times = [row["time"] for row in rows]
            return [{"min_time": min(times), "max_time": max(times)}]

        if measurement in ("network_stats", "disk_stats", "infiniband") and "MAX(" in query:
            return self._metric_totals(rows, measurement)

        return [dict(row) for row in rows]

    def _filter_rows(self, rows, params):
        hostname = params.get("hostname")
        start_time = self._normalize_time_param(params.get("start_time"))
        end_time = self._normalize_time_param(params.get("end_time"))
        filtered = []
        for row in rows:
            if hostname and row.get("hostname") != hostname:
                continue
            if start_time and row["time"] < start_time:
                continue
            if end_time and row["time"] >= end_time:
                continue
            filtered.append(dict(row))
        return filtered

    @staticmethod
    def _normalize_time_param(value):
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.fromtimestamp(parsed.timestamp(), tz=timezone.utc)
        return value

    def _metric_totals(self, rows, measurement):
        tag_key = {
            "network_stats": "interface",
            "disk_stats": "device",
            "infiniband": "device",
        }[measurement]
        fields = {
            "network_stats": [("rx_bytes", "rx_bytes_total"), ("tx_bytes", "tx_bytes_total")],
            "disk_stats": [("sectors_read", "sect_rd_total"), ("sectors_written", "sect_wr_total")],
            "infiniband": [("port_rcv_data", "port_rcv_data_total"), ("port_xmit_data", "port_xmit_data_total")],
        }[measurement]
        grouped = {}
        for row in rows:
            grouped.setdefault(row[tag_key], []).append(row)
        output = []
        for tag, entries in sorted(grouped.items()):
            item = {tag_key: tag}
            for source_key, alias in fields:
                values = [entry[source_key] for entry in entries]
                item[alias] = max(values) - min(values)
            output.append(item)
        return output


def create_args(**overrides):
    defaults = dict(
        traces_repo="",
        recursive=False,
        binary=False,
        influxdb=True,
        influxdb_url="http://localhost:8181",
        influxdb_token="",
        influxdb_org="",
        influxdb_database="metrics",
        influxdb_hostname="",
        resolution="raw",
        cpu=False,
        cpu_all=False,
        cpu_freq=False,
        cpu_cores_full="",
        cpu_cores_in="",
        cpu_cores_out="",
        mem=False,
        net=False,
        net_all=False,
        net_rx_only=False,
        net_tx_only=False,
        net_data=False,
        disk=False,
        disk_iops=False,
        disk_rd_only=False,
        disk_wr_only=False,
        disk_data=False,
        ib=False,
        sys=False,
        pow_g5k=False,
        pow=False,
        inline_call=False,
        inline_call_cmd="",
        call=False,
        call_depth=1,
        call_depths="",
        call_cmd="",
        annotate_with_log="",
        start_time=None,
        end_time=None,
        interactive=False,
        fig_path=None,
        fig_fmt="png",
        fig_name="benchmon_test_fig",
        fig_dpi="unset",
        fig_call_legend_ncol=8,
        fig_width=12.8,
        fig_height_unit=3,
        fig_xrange=10,
        fig_yrange=11,
        verbose=False,
        test=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def logger():
    test_logger = logging.getLogger("benchmon_influxdb_test_logger")
    test_logger.setLevel(logging.DEBUG)
    test_logger.handlers.clear()
    return test_logger


def test_system_data_influxdb_builds_profiles_with_runtime_memory_fields(logger):
    client = FakeInfluxDBClient3()
    metrics = SystemDataInfluxDB(
        logger=logger,
        client=client,
        database="metrics",
        hostname=HOSTNAME,
        start_time=ts(0).timestamp(),
        end_time=ts(180).timestamp(),
        enabled_metrics={"cpu": True, "cpufreq": True, "mem": True, "net": True, "disk": True, "ib": True},
        resolution="raw",
        target_points=100,
    )

    assert metrics.cpu_profile_valid
    assert metrics.cpufreq_profile_valid
    assert metrics.mem_profile_valid
    assert metrics.net_profile_valid
    assert metrics.disk_profile_valid
    assert metrics.ib_profile_valid
    assert metrics.mem_prof["MemTotal"][0] == 8 * 1024**3
    assert set(metrics.cpufreq_prof.keys()) == {"cpu0", "cpu1"}
    assert "eth0:" in metrics.net_prof
    assert "sda" in metrics.disk_prof
    assert "mlx5_0" in metrics.ib_prof
    assert metrics.net_data["eth0:"]["rx-bytes"] > 0
    assert metrics.disk_data["sda"]["sect-rd"] > 0


def test_system_data_influxdb_auto_resolution_buckets_memory(logger):
    client = FakeInfluxDBClient3()
    metrics = SystemDataInfluxDB(
        logger=logger,
        client=client,
        database="metrics",
        hostname=HOSTNAME,
        start_time=ts(0).timestamp(),
        end_time=ts(180).timestamp(),
        enabled_metrics={"cpu": False, "cpufreq": False, "mem": True, "net": False, "disk": False, "ib": False},
        resolution="auto",
        target_points=1,
    )

    assert metrics.actual_resolution != "raw"
    assert len(metrics.mem_stamps) >= 1
    assert metrics.mem_prof["MemTotal"][0] > 0


def test_parse_query_timestamp_normalizes_datetime_like_values():
    class DummyTimestamp:
        def __init__(self, dt):
            self._dt = dt

        def to_pydatetime(self):
            return self._dt

    naive = datetime(2026, 2, 4, 21, 48, 20)
    expected = naive.timestamp()

    from benchmon.visualization.system_metrics_influxdb import parse_query_timestamp

    assert parse_query_timestamp(naive) == expected
    assert parse_query_timestamp(DummyTimestamp(naive)) == expected


def test_influxdb_visualizer_rejects_unsupported_flags(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    args = create_args(pow=True, cpu=True)
    with pytest.raises(ValueError):
        BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))


def test_influxdb_visualizer_discovers_hosts_and_saves_one_figure_set_per_host(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    args = create_args(cpu=True, mem=True, fig_name="influxdb_hosts", fig_fmt="png")

    visualizer = BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))
    visualizer.run_plots()

    assert (tmp_path / f"benchmon_traces_{HOSTNAME}" / "influxdb_hosts.png").exists()
    assert (tmp_path / f"benchmon_traces_{HOSTNAME_2}" / "influxdb_hosts.png").exists()


def test_influxdb_visualizer_discovers_only_hosts_in_requested_time_window(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    args = create_args(
        cpu=True,
        mem=True,
        fig_name="influxdb_time_window",
        fig_fmt="png",
        start_time=ts_text(0),
        end_time=ts_text(180),
    )

    visualizer = BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))
    visualizer.run_plots()

    assert (tmp_path / f"benchmon_traces_{HOSTNAME}" / "influxdb_time_window.png").exists()
    assert not (tmp_path / f"benchmon_traces_{HOSTNAME_2}").exists()


def test_influxdb_visualizer_recursive_mode_also_saves_multi_node_sync(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    args = create_args(recursive=True, cpu=True, mem=True, fig_name="influxdb_recursive", fig_fmt="png")

    visualizer = BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))
    visualizer.run_plots()

    assert (tmp_path / f"benchmon_traces_{HOSTNAME}" / "influxdb_recursive.png").exists()
    assert (tmp_path / f"benchmon_traces_{HOSTNAME_2}" / "influxdb_recursive.png").exists()
    assert (tmp_path / "multi-node_sync.png").exists()


def test_influxdb_visualizer_paginates_when_figure_is_too_large(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    monkeypatch.setattr(BenchmonInfluxDBVisualizer, "MAX_FIGURE_SIDE_PX", 300)
    args = create_args(
        influxdb_hostname=HOSTNAME,
        cpu=True,
        cpu_all=True,
        cpu_freq=True,
        cpu_cores_full="0,1",
        mem=True,
        net=True,
        disk=True,
        ib=True,
        fig_name="influxdb_paginated",
        fig_fmt="png",
        fig_width=25.6,
        fig_height_unit=3,
    )

    visualizer = BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))
    visualizer.run_plots()

    assert (tmp_path / f"benchmon_traces_{HOSTNAME}" / "influxdb_paginated__part01.png").exists()


def test_influxdb_visualizer_falls_back_to_single_subplot_pages_on_render_failure(tmp_path, logger, monkeypatch):
    monkeypatch.setattr("benchmon.visualization.visualizer_influxdb.InfluxDBClient3", FakeInfluxDBClient3)
    args = create_args(influxdb_hostname=HOSTNAME, cpu=True, mem=True, net=True, fig_name="influxdb_retry", fig_fmt="png")

    visualizer = BenchmonInfluxDBVisualizer(args=args, logger=logger, traces_repo=str(tmp_path))
    calls = []

    def fake_render(self, specs, hostname, page_idx=None):
        calls.append((hostname, page_idx, [name for name, *_ in specs]))
        if page_idx is None:
            raise RuntimeError("save failed")

    monkeypatch.setattr(visualizer, "_render_page", fake_render.__get__(visualizer, BenchmonInfluxDBVisualizer))

    visualizer.run_plots()

    assert calls[0] == (HOSTNAME, None, ["cpu", "mem", "net"])
    assert calls[1:] == [
        (HOSTNAME, 1, ["cpu"]),
        (HOSTNAME, 2, ["mem"]),
        (HOSTNAME, 3, ["net"]),
    ]
