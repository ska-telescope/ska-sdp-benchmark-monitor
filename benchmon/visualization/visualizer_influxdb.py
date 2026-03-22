from __future__ import annotations

import argparse
from datetime import datetime
import logging
import os
import time
from types import SimpleNamespace

import numpy as np
from influxdb_client_3 import InfluxDBClient3
import matplotlib.pyplot as plt

from .system_metrics_influxdb import SystemDataInfluxDB, normalize_query_rows, parse_query_timestamp
from .utils import plot_ical_stages, read_ical_log_file
from .visualizer import BenchmonVisualizer


class BenchmonInfluxDBVisualizer(BenchmonVisualizer):
    """Visualize Benchmon metrics directly from InfluxDB."""

    MAX_FIGURE_SIDE_PX = 60000
    MAX_TOTAL_PIXELS = 2e8
    DPI_MAP = {"unset": None, "low": 200, "medium": 600, "high": 1200}
    UNSUPPORTED_FLAGS = {
        "binary": "--binary",
        "pow": "--pow",
        "pow_g5k": "--pow-g5k",
        "call": "--call",
        "inline_call": "--inline-call",
    }

    def __init__(self, args: argparse.Namespace, logger: logging.Logger, traces_repo: str) -> None:
        self.args = args
        self.logger = logger
        self.traces_repo = traces_repo
        self.args.traces_repo = traces_repo
        self.hostname = args.influxdb_hostname or ""

        self.system_metrics = None
        self.power_g5k_metrics = None
        self.power_perf_metrics = None
        self.call_traces = None
        self.n_subplots = 0
        self.xlim = []
        self.xticks = []
        self.is_any_sys = False
        self.call_depths = []
        self.call_chosen_cmd = ""
        self.call_recorded_cmds = []
        self.call_monotonic_to_real = 0
        self.inline_calls_prof = None
        self.ical_stages = {}

        if self.args.annotate_with_log == "ical":
            self.ical_stages = read_ical_log_file(self.traces_repo)

        self._validate_args()
        self.enabled_metrics = self._enabled_metrics()
        self.is_any_sys = any(self.enabled_metrics.values())
        self.n_subplots = self._count_subplots()
        self.target_points = self._target_points()

        self.client = InfluxDBClient3(
            host=self.args.influxdb_url,
            token=self.args.influxdb_token,
            org=self.args.influxdb_org,
            database=self.args.influxdb_database,
        )
        self.requested_start_time = self._parse_user_time(self.args.start_time)
        self.requested_end_time = self._parse_user_time(self.args.end_time)
        self.discovery_start_time, self.discovery_end_time = self._resolve_discovery_time_range()
        self.discovered_hostnames = self._discover_hostnames()

    def _validate_args(self) -> None:
        if not self.args.influxdb_url:
            raise ValueError("InfluxDB mode requires --influxdb-url")

        for attr, flag in self.UNSUPPORTED_FLAGS.items():
            if getattr(self.args, attr, False):
                raise ValueError(f"InfluxDB mode does not support {flag}")

        if self.args.inline_call_cmd:
            raise ValueError("InfluxDB mode does not support --inline-call-cmd")

        if self.args.recursive:
            self.logger.info("InfluxDB recursive mode will render per-host figures and a multi-node sync figure when possible")

    def _enabled_metrics(self) -> dict[str, bool]:
        is_net = self.args.net or self.args.net_all or self.args.net_data
        is_disk = self.args.disk or self.args.disk_iops or self.args.disk_data
        enabled = {
            "cpu": self.args.cpu or self.args.cpu_all or bool(self.args.cpu_cores_full),
            "cpufreq": self.args.cpu_freq,
            "mem": self.args.mem,
            "net": is_net,
            "disk": is_disk,
            "ib": self.args.ib,
        }
        if not any(enabled.values()):
            raise ValueError("InfluxDB mode requires at least one supported system metric flag")
        return enabled

    def _enabled_measurements(self) -> list[str]:
        measurements = []
        if self.enabled_metrics["cpu"]:
            measurements.extend(["cpu_total", "cpu_core"])
        if self.enabled_metrics["cpufreq"]:
            measurements.append("cpu_freq")
        if self.enabled_metrics["mem"]:
            measurements.append("memory")
        if self.enabled_metrics["net"]:
            measurements.append("network_stats")
        if self.enabled_metrics["disk"]:
            measurements.append("disk_stats")
        if self.enabled_metrics["ib"]:
            measurements.append("infiniband")
        return measurements

    def _count_subplots(self) -> int:
        extra_cpu = len(self.args.cpu_cores_full.split(",")) if self.args.cpu_cores_full else 0
        return (
            int(bool(self.args.cpu))
            + int(bool(self.args.cpu_all))
            + int(bool(self.args.cpu_freq))
            + extra_cpu
            + int(bool(self.args.mem))
            + int(bool(self.args.net or self.args.net_all or self.args.net_data))
            + int(bool(self.args.disk or self.args.disk_iops or self.args.disk_data))
            + int(bool(self.args.ib))
        )

    def _target_points(self) -> int:
        dpi = self._effective_dpi()
        return max(int(self.args.fig_width * dpi * 2), 1)

    def _effective_dpi(self) -> int:
        if self.args.fig_dpi == "unset":
            return int(plt.rcParams.get("figure.dpi", 100))
        return self.DPI_MAP[self.args.fig_dpi]

    def _query_rows(self, query: str, **params):
        result = self.client.query(
            query,
            language="sql",
            mode="all",
            database=self.args.influxdb_database,
            query_parameters=params or None,
        )
        return normalize_query_rows(result)

    def _parse_user_time(self, value: str | None) -> float | None:
        if not value:
            return None
        value = value.strip().strip("\"'")
        fmt = "%Y-%m-%dT%H:%M:%S"
        return datetime.strptime(value, fmt).timestamp()

    def _reference_measurement(self) -> str:
        if self.enabled_metrics["cpu"]:
            return "cpu_total"
        if self.enabled_metrics["cpufreq"]:
            return "cpu_freq"
        if self.enabled_metrics["mem"]:
            return "memory"
        if self.enabled_metrics["net"]:
            return "network_stats"
        if self.enabled_metrics["disk"]:
            return "disk_stats"
        if self.enabled_metrics["ib"]:
            return "infiniband"
        raise ValueError("No enabled measurement for InfluxDB mode")

    @staticmethod
    def _local_time_param(timestamp: float | None):
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S")

    def _query_bounds(
        self,
        measurement: str,
        hostname: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> tuple[float | None, float | None]:
        conditions = []
        params = {}
        if hostname:
            conditions.append("hostname = $hostname")
            params["hostname"] = hostname
        if start_time is not None:
            conditions.append("time >= $start_time")
            params["start_time"] = self._local_time_param(start_time)
        if end_time is not None:
            conditions.append("time < $end_time")
            params["end_time"] = self._local_time_param(end_time)
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._query_rows(
            f"SELECT MIN(time) AS min_time, MAX(time) AS max_time FROM {measurement}{where_clause}",
            **params,
        )
        if not rows or rows[0].get("max_time") is None:
            return None, None
        return (
            parse_query_timestamp(rows[0]["min_time"]),
            parse_query_timestamp(rows[0]["max_time"]),
        )

    def _resolve_discovery_time_range(self) -> tuple[float, float]:
        start_time = self.requested_start_time
        end_time = self.requested_end_time
        hostname_scope = self.args.influxdb_hostname or None

        if start_time is None:
            variable_min, _ = self._query_bounds("variable", hostname=hostname_scope, end_time=end_time)
            if variable_min is not None:
                start_time = variable_min

        ref_measurement = self._reference_measurement()
        ref_min, ref_max = self._query_bounds(
            ref_measurement,
            hostname=hostname_scope,
            start_time=start_time,
            end_time=end_time,
        )
        if ref_max is None:
            raise ValueError(f"No data found in {ref_measurement} for the requested time range")

        if start_time is None:
            start_time = ref_min
        if end_time is None:
            end_time = ref_max + 1.0
        if start_time is None or end_time <= start_time:
            raise ValueError("InfluxDB mode requires end time to be greater than start time")
        return start_time, end_time

    def _discover_hostnames(self) -> list[str]:
        if self.args.influxdb_hostname:
            return [self.args.influxdb_hostname]

        query_params = {
            "start_time": self._local_time_param(self.discovery_start_time),
            "end_time": self._local_time_param(self.discovery_end_time),
        }
        hostnames = set()
        for measurement in ["variable", *self._enabled_measurements()]:
            rows = self._query_rows(
                f"SELECT DISTINCT hostname FROM {measurement} WHERE time >= $start_time AND time < $end_time ORDER BY hostname",
                **query_params,
            )
            for row in rows:
                hostname = row.get("hostname")
                if hostname:
                    hostnames.add(str(hostname))

        if not hostnames:
            raise ValueError("No hostnames found in InfluxDB for the requested time range")
        return sorted(hostnames)

    def _resolve_host_time_range(self, hostname: str) -> tuple[float, float]:
        start_time = self.requested_start_time
        end_time = self.requested_end_time

        if start_time is None:
            variable_min, _ = self._query_bounds("variable", hostname=hostname, end_time=end_time)
            if variable_min is not None:
                start_time = variable_min

        ref_measurement = self._reference_measurement()
        ref_min, ref_max = self._query_bounds(
            ref_measurement,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
        )
        if ref_max is None:
            raise ValueError(f"No data found in {ref_measurement} for host {hostname}")

        if start_time is None:
            start_time = ref_min
        if end_time is None:
            end_time = ref_max + 1.0
        if start_time is None or end_time <= start_time:
            raise ValueError(f"InfluxDB mode requires a valid time range for host {hostname}")
        return start_time, end_time

    def _build_sync_xaxis(self, xmargin: float = 0.0):
        t0 = self.requested_start_time if self.requested_start_time is not None else self.discovery_start_time
        tf = self.requested_end_time if self.requested_end_time is not None else self.discovery_end_time
        if t0 is None or tf is None or tf <= t0:
            return [], []

        xticks_val = np.linspace(t0, tf, self.args.fig_xrange)
        t0_fmt = time.strftime("%H:%M:%S\n%b-%d", time.localtime(t0))
        tf_fmt = time.strftime("%H:%M:%S\n%b-%d", time.localtime(tf))

        inbetween_labels = []
        days = [t0_fmt.split("\n")[1].split("-")[1]]
        for stamp in xticks_val[1:-1]:
            inbetween_labels.append(time.strftime("%H:%M:%S", time.localtime(stamp)))
            days.append(time.strftime("%d", time.localtime(stamp)))
            if days[-1] != days[-2]:
                inbetween_labels[-1] += "\n" + time.strftime("%b-%d", time.localtime(stamp))
        xticks = (xticks_val, [t0_fmt] + inbetween_labels + [tf_fmt])

        dx = (tf - t0) * xmargin
        xlim = [t0 - dx, tf + dx]
        return xticks, xlim

    def _build_node_view(self, hostname: str, system_metrics: SystemDataInfluxDB, xticks, xlim):
        return SimpleNamespace(
            hostname=hostname,
            system_metrics=system_metrics,
            power_g5k_metrics=None,
            power_perf_metrics=None,
            xticks=xticks,
            xlim=xlim,
        )

    def _run_recursive_sync_plots(self, node_views: list[SimpleNamespace]) -> None:
        if not self.args.recursive or not node_views:
            return
        from .multi_node_visualizer import BenchmonMNSyncVisualizer

        BenchmonMNSyncVisualizer(self.args, self.logger, node_views)

    def _build_system_metrics(self, hostname: str) -> SystemDataInfluxDB:
        start_time, end_time = self._resolve_host_time_range(hostname)
        self.logger.info(
            f"Loading InfluxDB metrics for host {hostname} in [{start_time}, {end_time})"
        )
        return SystemDataInfluxDB(
            logger=self.logger,
            client=self.client,
            database=self.args.influxdb_database,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            enabled_metrics=self.enabled_metrics,
            resolution=self.args.resolution,
            target_points=self.target_points,
        )

    def _plot_specs(self):
        specs = []

        if self.args.cpu:
            specs.append(("cpu", lambda: self.system_metrics.plot_cpu(), 100))

        if self.args.cpu_cores_full:
            for core in self.args.cpu_cores_full.split(","):
                specs.append((f"cpu-core-{core}", lambda core=core: self.system_metrics.plot_cpu(number=core), 100))

        if self.args.cpu_all:
            specs.append((
                "cpu-all",
                lambda: self.system_metrics.plot_cpu_per_core(
                    cores_in=self.args.cpu_cores_in,
                    cores_out=self.args.cpu_cores_out,
                ),
                100,
            ))

        if self.args.cpu_freq:
            specs.append((
                "cpu-freq",
                lambda: self.system_metrics.plot_cpufreq(
                    cores_in=self.args.cpu_cores_in,
                    cores_out=self.args.cpu_cores_out,
                ),
                None,
            ))

        if self.args.mem:
            specs.append(("mem", lambda: self.system_metrics.plot_memory_usage(), None))

        if self.args.net or self.args.net_all or self.args.net_data:
            specs.append((
                "net",
                lambda: self.system_metrics.plot_network(
                    all_interfaces=self.args.net_all,
                    is_rx_only=self.args.net_rx_only,
                    is_tx_only=self.args.net_tx_only,
                    is_netdata_label=self.args.net_data,
                ),
                None,
            ))

        if self.args.disk or self.args.disk_iops or self.args.disk_data:
            specs.append((
                "disk",
                lambda: self.system_metrics.plot_disk(
                    is_with_iops=self.args.disk_iops,
                    is_rd_only=self.args.disk_rd_only,
                    is_wr_only=self.args.disk_wr_only,
                    is_diskdata_label=self.args.disk_data,
                ),
                None,
            ))

        if self.args.ib:
            specs.append(("ib", lambda: self.system_metrics.plot_ib(), None))

        return specs

    def _host_output_dir(self, hostname: str) -> str:
        root = self.traces_repo if self.args.fig_path is None else self.args.fig_path
        if self.args.fig_path is not None and len(self.discovered_hostnames) == 1:
            return root
        safe_hostname = hostname.replace(os.sep, "_")
        return os.path.join(root, f"benchmon_traces_{safe_hostname}")

    def _save_paths(self, hostname: str, page_idx: int | None = None) -> list[tuple[str, str | int]]:
        dpi = "figure" if self.args.fig_dpi == "unset" else self.DPI_MAP[self.args.fig_dpi]
        figpath = self._host_output_dir(hostname)
        os.makedirs(figpath, exist_ok=True)
        outputs = []
        for fmt in self.args.fig_fmt.split(","):
            suffix = f"__part{page_idx:02d}" if page_idx is not None else ""
            figname = f"{figpath}/{self.args.fig_name}{suffix}.{fmt}"
            outputs.append((figname, dpi))
        return outputs

    def _is_large_figure(self, n_subplots: int) -> bool:
        dpi = self._effective_dpi()
        width_px = self.args.fig_width * dpi
        height_px = n_subplots * self.args.fig_height_unit * dpi
        total_pixels = width_px * height_px
        return (
            width_px > self.MAX_FIGURE_SIDE_PX
            or height_px > self.MAX_FIGURE_SIDE_PX
            or total_pixels > self.MAX_TOTAL_PIXELS
        )

    def _max_subplots_per_page(self) -> int:
        dpi = self._effective_dpi()
        max_inches = self.MAX_FIGURE_SIDE_PX / dpi
        return max(int(max_inches // self.args.fig_height_unit), 1)

    def _split_pages(self, specs):
        if not self._is_large_figure(len(specs)):
            return [specs]
        per_page = self._max_subplots_per_page()
        return [specs[idx: idx + per_page] for idx in range(0, len(specs), per_page)]

    def _render_page(self, specs, hostname: str, page_idx: int | None = None) -> None:
        fig, _ = plt.subplots(len(specs), sharex=True)
        fig.set_size_inches(self.args.fig_width, len(specs) * self.args.fig_height_unit)
        fig.add_gridspec(len(specs), hspace=0)

        for sbp, (_, plotter, default_ymax) in enumerate(specs, start=1):
            plt.subplot(len(specs), 1, sbp)
            ymax = plotter()
            ymax = default_ymax if ymax in (-1, 0) and default_ymax is not None else ymax
            if self.ical_stages:
                kwargs = {"ymax": ymax} if ymax not in (None, -1) else {}
                plot_ical_stages(self.ical_stages, **kwargs)

        fig.suptitle(hostname)
        plt.subplots_adjust(hspace=0.5)
        plt.tight_layout()

        if self.args.interactive:
            plt.show()

        for figname, dpi in self._save_paths(hostname, page_idx=page_idx):
            fig.savefig(figname, format=figname.rsplit(".", 1)[1], dpi=dpi)
            self.logger.info(f"Figure saved: {os.path.realpath(figname)}")
        plt.close(fig)

    def _render_host_plots(self, hostname: str) -> bool:
        specs = self._plot_specs()
        if not specs:
            self.logger.warning(f"No supported InfluxDB plots requested for host {hostname}")
            return False

        pages = self._split_pages(specs)
        if len(pages) > 1:
            self.logger.info(f"InfluxDB visualizer switched to paginated output for host {hostname} ({len(pages)} pages)")
            for idx, page in enumerate(pages, start=1):
                self._render_page(page, hostname, page_idx=idx)
            return True

        try:
            self._render_page(specs, hostname)
        except (MemoryError, RuntimeError, ValueError) as exc:
            if len(specs) == 1:
                raise
            self.logger.warning(f"Single-figure save failed for host {hostname}, retrying with pagination: {exc}")
            for idx, spec in enumerate(specs, start=1):
                self._render_page([spec], hostname, page_idx=idx)
        return True

    def run_plots(self) -> None:
        saved_hosts = 0
        node_views = []
        try:
            self.logger.info(
                "InfluxDB visualizer discovered hosts in requested time range: %s",
                ", ".join(self.discovered_hostnames),
            )
            sync_xticks, sync_xlim = self._build_sync_xaxis(xmargin=0)
            for hostname in self.discovered_hostnames:
                try:
                    system_metrics = self._build_system_metrics(hostname)
                except ValueError as exc:
                    self.logger.warning(str(exc))
                    continue

                if not system_metrics.has_any_data():
                    self.logger.warning(f"No valid InfluxDB data found for host {hostname}")
                    continue

                self.hostname = hostname
                self.system_metrics = system_metrics
                self.get_xaxis_params(xmargin=0)
                self.apply_xaxis_params()
                if self._render_host_plots(hostname):
                    saved_hosts += 1
                    node_views.append(self._build_node_view(hostname, system_metrics, sync_xticks or self.xticks, sync_xlim or self.xlim))

            if saved_hosts == 0:
                raise ValueError("No valid InfluxDB data found for any discovered host")

            self._run_recursive_sync_plots(node_views)
        finally:
            self.client.close()
