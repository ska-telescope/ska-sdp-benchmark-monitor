from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import logging
from typing import Any

import numpy as np

from .system_metrics import SystemData


MEMORY_FIELD_ALIASES = {
    "MemTotal": ("MemTotal", "memtotal"),
    "MemFree": ("MemFree", "memfree"),
    "Buffers": ("Buffers", "buffers"),
    "Cached": ("Cached", "cached"),
    "Slab": ("Slab", "slab"),
    "SwapTotal": ("SwapTotal", "swaptotal"),
    "SwapFree": ("SwapFree", "swapfree"),
    "SwapCached": ("SwapCached", "swapcached"),
}
MEMORY_FIELDS = list(MEMORY_FIELD_ALIASES.keys())
CPU_FIELDS = [
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guestnice",
]
RESOLUTION_TO_SECONDS = {
    "raw": 0,
    "1s": 1,
    "5s": 5,
    "10s": 10,
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}
RESOLUTION_ORDER = list(RESOLUTION_TO_SECONDS.keys())


def normalize_query_rows(result: Any) -> list[dict[str, Any]]:
    """Normalize InfluxDB query results into a list of dictionaries."""
    if result is None:
        return []
    if isinstance(result, dict):
        return [result]
    if isinstance(result, list):
        rows = []
        for item in result:
            rows.extend(normalize_query_rows(item))
        return rows
    if isinstance(result, tuple):
        rows = []
        for item in result:
            rows.extend(normalize_query_rows(item))
        return rows
    if hasattr(result, "read_all"):
        return normalize_query_rows(result.read_all())
    if hasattr(result, "column_names") and hasattr(result, "column"):
        column_names = list(result.column_names)
        if not column_names:
            return []
        columns = [result.column(name) for name in column_names]
        nrows = len(columns[0]) if columns else 0
        rows = []
        for idx in range(nrows):
            row = {}
            for name, column in zip(column_names, columns):
                row[name] = column[idx]
            rows.append(row)
        return rows
    if hasattr(result, "to_pylist"):
        return list(result.to_pylist())
    if hasattr(result, "to_pydict"):
        data = result.to_pydict()
        if not data:
            return []
        keys = list(data.keys())
        nrows = len(data[keys[0]])
        return [{key: data[key][idx] for key in keys} for idx in range(nrows)]
    if hasattr(result, "to_dict"):
        data = result.to_dict()
        if isinstance(data, dict):
            return [data]
    return []


def parse_query_timestamp(value: Any) -> float:
    """Convert query timestamp-like values to epoch seconds."""
    if value is None:
        return 0.0
    if hasattr(value, "value"):
        raw_value = value.value
        if isinstance(raw_value, (int, np.integer)):
            return int(raw_value) / 1e9
    if hasattr(value, "to_pydatetime") and not isinstance(value, datetime):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return datetime(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
        ).timestamp()
    if isinstance(value, (int, np.integer)):
        value = int(value)
        if value > 10**15:
            return value / 1e9
        if value > 10**12:
            return value / 1e6
        return float(value)
    if isinstance(value, (float, np.floating)):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime(
                parsed.year,
                parsed.month,
                parsed.day,
                parsed.hour,
                parsed.minute,
                parsed.second,
                parsed.microsecond,
                tzinfo=parsed.tzinfo,
            ).timestamp()
        except ValueError:
            return float(value)
    raise TypeError(f"Unsupported timestamp value: {type(value)!r}")


class SystemDataInfluxDB(SystemData):
    """InfluxDB-backed system metrics adapter that reuses SystemData plotting methods."""

    def __init__(
        self,
        logger: logging.Logger,
        client: Any,
        database: str,
        hostname: str,
        start_time: float,
        end_time: float,
        enabled_metrics: dict[str, bool],
        resolution: str,
        target_points: int,
    ) -> None:
        self.logger = logger
        self.traces_repo = ""
        self.client = client
        self.database = database
        self.hostname = hostname
        self.start_time = start_time
        self.end_time = end_time
        self.enabled_metrics = enabled_metrics
        self.target_points = max(int(target_points), 1)

        self.xticks = None
        self.xlim = None
        self.yrange = None

        self.ncpu = 0
        self.cpus = []
        self.cpu_prof = {}
        self.cpu_stamps = np.array([])
        self.cpu_profile_valid = False

        self.ncpu_freq = 0
        self.cpufreq_prof = {}
        self.cpufreq_vals = {}
        self.cpufreq_stamps = np.array([])
        self.cpufreq_min = None
        self.cpufreq_max = None
        self.cpufreq_profile_valid = False

        self.mem_prof = {"timestamp": np.array([])}
        self.mem_stamps = np.array([])
        self.mem_profile_valid = False

        self.net_prof = {}
        self.net_data = {}
        self.net_metric_keys = {"rx-bytes": 0, "tx-bytes": 1}
        self.net_interfs = []
        self.net_stamps = np.array([])
        self.net_rx_total = np.array([])
        self.net_tx_total = np.array([])
        self.net_rx_data = 0
        self.net_tx_data = 0
        self.net_profile_valid = False

        self.disk_prof = {}
        self.disk_data = {}
        self.disk_field_keys = {
            "#rd-cd": 0,
            "#rd-md": 1,
            "sect-rd": 2,
            "time-rd": 3,
            "#wr-cd": 4,
            "#wr-md": 5,
            "sect-wr": 6,
            "time-wr": 7,
            "#io-ip": 8,
            "time-io": 9,
            "time-wei-io": 10,
            "#disc-cd": 11,
            "#disc-md": 12,
            "sect-disc": 13,
            "time-disc": 14,
            "#flush-req": 15,
            "time-flush": 16,
        }
        self.maj_blks_sects = {}
        self.disk_blks = []
        self.disk_stamps = np.array([])
        self.disk_rd_total = np.array([])
        self.disk_wr_total = np.array([])
        self.disk_rd_data = 0
        self.disk_wr_data = 0
        self.disk_profile_valid = False

        self.ib_prof = {}
        self.ib_data = {}
        self.ib_metric_keys = ["port_rcv_data", "port_xmit_data"]
        self.ib_interfs = []
        self.ib_stamps = np.array([])
        self.ib_rx_total = np.array([])
        self.ib_tx_total = np.array([])
        self.ib_rx_data = 0
        self.ib_tx_data = 0
        self.ib_profile_valid = False

        self.actual_resolution = self._resolve_resolution(resolution)
        self.logger.info(
            f"InfluxDB visualizer resolution for host {self.hostname}: {self.actual_resolution}"
        )

        if self.enabled_metrics.get("cpu"):
            self._load_cpu()
        if self.enabled_metrics.get("cpufreq"):
            self._load_cpufreq()
        if self.enabled_metrics.get("mem"):
            self._load_mem()
        if self.enabled_metrics.get("net"):
            self._load_net()
        if self.enabled_metrics.get("disk"):
            self._load_disk()
        if self.enabled_metrics.get("ib"):
            self._load_ib()

    def has_any_data(self) -> bool:
        return any(
            (
                len(self.cpu_stamps) > 0,
                len(self.cpufreq_stamps) > 0,
                len(self.mem_stamps) > 0,
                len(self.net_stamps) > 0,
                len(self.disk_stamps) > 0,
                len(self.ib_stamps) > 0,
            )
        )

    def _query_rows(self, query: str, **query_parameters: Any) -> list[dict[str, Any]]:
        result = self.client.query(
            query,
            language="sql",
            mode="all",
            database=self.database,
            query_parameters=query_parameters or None,
        )
        return normalize_query_rows(result)

    def _resolve_resolution(self, requested: str) -> str:
        if requested != "auto":
            return requested

        reference_measurement = self._reference_measurement()
        if reference_measurement is None:
            return "raw"

        count_query = (
            f"SELECT COUNT(DISTINCT time) AS sample_count FROM {reference_measurement} "
            "WHERE hostname = $hostname AND time >= $start_time AND time < $end_time"
        )
        rows = self._query_rows(
            count_query,
            hostname=self.hostname,
            start_time=self._local_time_param(self.start_time),
            end_time=self._local_time_param(self.end_time),
        )
        sample_count = 0
        if rows:
            sample_count = int(rows[0].get("sample_count") or 0)

        duration = max(self.end_time - self.start_time, 1.0)
        if sample_count and sample_count <= self.target_points:
            return "raw"
        if not sample_count and duration <= self.target_points:
            return "raw"

        for candidate in RESOLUTION_ORDER[1:]:
            if duration / RESOLUTION_TO_SECONDS[candidate] <= self.target_points:
                return candidate
        return "1h"

    def _reference_measurement(self) -> str | None:
        if self.enabled_metrics.get("cpu"):
            return "cpu_total"
        if self.enabled_metrics.get("cpufreq"):
            return "cpu_freq"
        if self.enabled_metrics.get("mem"):
            return "memory"
        if self.enabled_metrics.get("net"):
            return "network_stats"
        if self.enabled_metrics.get("disk"):
            return "disk_stats"
        if self.enabled_metrics.get("ib"):
            return "infiniband"
        return None

    @staticmethod
    def _local_time_param(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _extract_field(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            if key in row and row[key] is not None:
                return float(row[key])
        return float(default)

    def _normalize_memory_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, float]]:
        normalized = []
        for row in rows:
            timestamp_value = row.get("timestamp", row.get("time"))
            if timestamp_value is None:
                continue
            sample = {"timestamp": parse_query_timestamp(timestamp_value)}
            for field, aliases in MEMORY_FIELD_ALIASES.items():
                sample[field] = self._extract_field(row, *aliases)
            normalized.append(sample)
        normalized.sort(key=lambda item: item["timestamp"])
        return normalized

    def _bucket_gauge_rows(self, rows: list[dict[str, float]], fields: list[str]) -> list[dict[str, float]]:
        if self.actual_resolution == "raw":
            return rows

        bucket_seconds = RESOLUTION_TO_SECONDS[self.actual_resolution]
        if bucket_seconds <= 0:
            return rows

        grouped = defaultdict(list)
        for row in rows:
            bucket_start = float(int(row["timestamp"] // bucket_seconds) * bucket_seconds)
            grouped[bucket_start].append(row)

        output = []
        for bucket_time, entries in sorted(grouped.items()):
            sample = {"timestamp": bucket_time}
            for field in fields:
                sample[field] = float(np.mean([entry[field] for entry in entries]))
            output.append(sample)
        return output

    def _load_cpu(self) -> None:
        total_profiles, total_stamps = self._load_cpu_measurement("cpu_total", None)
        core_profiles, core_stamps = self._load_cpu_measurement("cpu_core", "cpu")

        self.cpu_prof = {}
        if total_profiles:
            self.cpu_prof.update(total_profiles)
        if core_profiles:
            self.cpu_prof.update(core_profiles)

        if "cpu" not in self.cpu_prof and core_profiles:
            self.cpu_prof["cpu"] = {}
            for field in CPU_FIELDS:
                self.cpu_prof["cpu"][field] = np.mean(
                    np.vstack([profile[field] for profile in core_profiles.values()]), axis=0
                )

        self.cpu_stamps = total_stamps if len(total_stamps) else core_stamps
        self.ncpu = len([key for key in self.cpu_prof if key.startswith("cpu") and key != "cpu"])
        self.cpus = ["cpu"] + [f"cpu{idx}" for idx in range(self.ncpu)]
        self.cpu_profile_valid = len(self.cpu_stamps) > 0 and "cpu" in self.cpu_prof

    def _load_cpu_measurement(
        self,
        measurement: str,
        tag_key: str | None,
    ) -> tuple[dict[str, dict[str, np.ndarray]], np.ndarray]:
        extra_select = f", {tag_key}" if tag_key else ""
        order_by = f"time, {tag_key}" if tag_key else "time"
        base_params = {
            "hostname": self.hostname,
            "start_time": self._local_time_param(self.start_time),
            "end_time": self._local_time_param(self.end_time),
        }

        if self.actual_resolution == "raw":
            rows = self._query_rows(
                f"SELECT * FROM {measurement} WHERE hostname = $hostname AND time >= $start_time AND time < $end_time "
                f"ORDER BY {order_by}",
                **base_params,
            )
            return self._build_cpu_profiles_from_raw(rows, tag_key)

        partition = f"PARTITION BY {tag_key} ORDER BY time" if tag_key else "ORDER BY time"
        group_by = f", {tag_key}" if tag_key else ""
        bucket_query = f"""
            SELECT bucket_time AS time{extra_select},
                   AVG("user") AS "user",
                   AVG(nice) AS nice,
                   AVG(system) AS system,
                   AVG(idle) AS idle,
                   AVG(iowait) AS iowait,
                   AVG(irq) AS irq,
                   AVG(softirq) AS softirq,
                   AVG(steal) AS steal,
                   AVG(guest) AS guest,
                   AVG(guestnice) AS guestnice
            FROM (
                SELECT date_bin(INTERVAL '{self.actual_resolution}', time) AS bucket_time{extra_select},
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * user_delta / total_delta END AS "user",
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * nice_delta / total_delta END AS nice,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * system_delta / total_delta END AS system,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * idle_delta / total_delta END AS idle,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * iowait_delta / total_delta END AS iowait,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * irq_delta / total_delta END AS irq,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * softirq_delta / total_delta END AS softirq,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * steal_delta / total_delta END AS steal,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * guest_delta / total_delta END AS guest,
                       CASE WHEN total_delta = 0 THEN NULL ELSE 100.0 * guestnice_delta / total_delta END AS guestnice
                FROM (
                    SELECT time{extra_select},
                           "user" - LAG("user") OVER w AS user_delta,
                           nice - LAG(nice) OVER w AS nice_delta,
                           system - LAG(system) OVER w AS system_delta,
                           idle - LAG(idle) OVER w AS idle_delta,
                           iowait - LAG(iowait) OVER w AS iowait_delta,
                           irq - LAG(irq) OVER w AS irq_delta,
                           softirq - LAG(softirq) OVER w AS softirq_delta,
                           steal - LAG(steal) OVER w AS steal_delta,
                           guest - LAG(guest) OVER w AS guest_delta,
                           guest_nice - LAG(guest_nice) OVER w AS guestnice_delta,
                           ("user" - LAG("user") OVER w) +
                           (nice - LAG(nice) OVER w) +
                           (system - LAG(system) OVER w) +
                           (idle - LAG(idle) OVER w) +
                           (iowait - LAG(iowait) OVER w) +
                           (irq - LAG(irq) OVER w) +
                           (softirq - LAG(softirq) OVER w) +
                           (steal - LAG(steal) OVER w) +
                           (guest - LAG(guest) OVER w) +
                           (guest_nice - LAG(guest_nice) OVER w) AS total_delta
                    FROM {measurement}
                    WHERE hostname = $hostname AND time >= $start_time AND time < $end_time
                    WINDOW w AS ({partition})
                ) deltas
            ) pct
            WHERE "user" IS NOT NULL
            GROUP BY bucket_time{group_by}
            ORDER BY time{group_by}
        """
        rows = self._query_rows(bucket_query, **base_params)
        return self._build_cpu_profiles_from_percent_rows(rows, tag_key)

    def _build_cpu_profiles_from_raw(
        self,
        rows: list[dict[str, Any]],
        tag_key: str | None,
    ) -> tuple[dict[str, dict[str, np.ndarray]], np.ndarray]:
        grouped = defaultdict(list)
        default_label = "cpu"
        for row in rows:
            label = str(row[tag_key]) if tag_key else default_label
            grouped[label].append(row)

        profiles = {}
        stamps_ref = np.array([])
        for label, entries in grouped.items():
            entries.sort(key=lambda item: parse_query_timestamp(item["time"]))
            times = np.array([parse_query_timestamp(item["time"]) for item in entries], dtype=float)
            if len(times) < 2:
                continue

            field_values = {
                field: np.array(
                    [self._extract_field(item, field, field.replace("guestnice", "guest_nice")) for item in entries],
                    dtype=float,
                )
                for field in CPU_FIELDS
            }
            stamps = (times[1:] + times[:-1]) / 2.0
            series = {field: np.zeros(len(stamps), dtype=float) for field in CPU_FIELDS}

            for idx in range(len(stamps)):
                deltas = {field: field_values[field][idx + 1] - field_values[field][idx] for field in CPU_FIELDS}
                total_delta = sum(deltas.values())
                if total_delta <= 0:
                    continue
                for field in CPU_FIELDS:
                    series[field][idx] = deltas[field] / total_delta * 100.0

            profiles[label] = series
            if len(stamps_ref) == 0:
                stamps_ref = stamps

        return profiles, stamps_ref

    def _build_cpu_profiles_from_percent_rows(
        self,
        rows: list[dict[str, Any]],
        tag_key: str | None,
    ) -> tuple[dict[str, dict[str, np.ndarray]], np.ndarray]:
        grouped = defaultdict(list)
        default_label = "cpu"
        for row in rows:
            label = str(row[tag_key]) if tag_key else default_label
            grouped[label].append(row)

        profiles = {}
        stamps_ref = np.array([])
        for label, entries in grouped.items():
            entries.sort(key=lambda item: parse_query_timestamp(item["time"]))
            stamps = np.array([parse_query_timestamp(item["time"]) for item in entries], dtype=float)
            profiles[label] = {
                field: np.array([self._extract_field(item, field) for item in entries], dtype=float)
                for field in CPU_FIELDS
            }
            if len(stamps_ref) == 0:
                stamps_ref = stamps
        return profiles, stamps_ref

    def _load_cpufreq(self) -> None:
        base_params = {
            "hostname": self.hostname,
            "start_time": self._local_time_param(self.start_time),
            "end_time": self._local_time_param(self.end_time),
        }

        if self.actual_resolution == "raw":
            rows = self._query_rows(
                "SELECT time, cpu, value FROM cpu_freq "
                "WHERE hostname = $hostname AND time >= $start_time AND time < $end_time "
                "ORDER BY time, cpu",
                **base_params,
            )
        else:
            rows = self._query_rows(
                f"SELECT bucket_time AS time, cpu, AVG(value) AS value "
                f"FROM (SELECT date_bin(INTERVAL '{self.actual_resolution}', time) AS bucket_time, cpu, value "
                "FROM cpu_freq WHERE hostname = $hostname AND time >= $start_time AND time < $end_time) freq "
                "GROUP BY bucket_time, cpu ORDER BY time, cpu",
                **base_params,
            )

        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row["cpu"])].append(row)

        self.cpufreq_prof = {}
        self.cpufreq_stamps = np.array([])
        for cpu, entries in grouped.items():
            entries.sort(key=lambda item: parse_query_timestamp(item["time"]))
            stamps = np.array([parse_query_timestamp(item["time"]) for item in entries], dtype=float)
            values = np.array([self._extract_field(item, "value") for item in entries], dtype=float) / 1e6
            self.cpufreq_prof[cpu] = values
            if len(self.cpufreq_stamps) == 0:
                self.cpufreq_stamps = stamps

        self.ncpu_freq = len(self.cpufreq_prof)
        self.cpufreq_profile_valid = self.ncpu_freq > 0 and len(self.cpufreq_stamps) > 0
        if not self.cpufreq_profile_valid:
            return

        self.cpufreq_vals["mean"] = np.mean(np.vstack(list(self.cpufreq_prof.values())), axis=0)
        observed_min = min(float(np.min(values)) for values in self.cpufreq_prof.values())
        observed_max = max(float(np.max(values)) for values in self.cpufreq_prof.values())
        self.cpufreq_min = observed_min * 1e6
        self.cpufreq_max = observed_max * 1e6
        self.cpufreq_vals["min"] = self.cpufreq_min
        self.cpufreq_vals["max"] = self.cpufreq_max

    def _load_mem(self) -> None:
        base_params = {
            "hostname": self.hostname,
            "start_time": self._local_time_param(self.start_time),
            "end_time": self._local_time_param(self.end_time),
        }
        rows = self._query_rows(
            "SELECT * FROM memory "
            "WHERE hostname = $hostname AND time >= $start_time AND time < $end_time "
            "ORDER BY time",
            **base_params,
        )
        if not rows:
            return

        normalized_rows = self._normalize_memory_rows(rows)
        normalized_rows = self._bucket_gauge_rows(normalized_rows, MEMORY_FIELDS)
        if not normalized_rows:
            return

        self.mem_prof = {
            "timestamp": np.array([row["timestamp"] for row in normalized_rows], dtype=float)
        }
        for field in MEMORY_FIELDS:
            self.mem_prof[field] = np.array([row[field] for row in normalized_rows], dtype=float)
        self.mem_stamps = self.mem_prof["timestamp"]
        self.mem_profile_valid = len(self.mem_stamps) > 0

    def _load_net(self) -> None:
        rows, totals = self._load_rate_metric(
            measurement="network_stats",
            tag_key="interface",
            fields={"rx-bytes": "rx_bytes", "tx-bytes": "tx_bytes"},
            scale=1.0 / (1000**2),
        )
        self.net_prof = rows
        self.net_data = totals
        self.net_interfs = list(self.net_prof.keys())
        if self.net_prof:
            self.net_stamps = next(iter(self.net_prof.values()))["timestamp"]
            for interf in self.net_interfs:
                self.net_prof[interf].pop("timestamp", None)
        self.net_profile_valid = len(self.net_stamps) > 0

    def _load_disk(self) -> None:
        rows, totals = self._load_rate_metric(
            measurement="disk_stats",
            tag_key="device",
            fields={"sect-rd": "sectors_read", "sect-wr": "sectors_written"},
            scale=512.0 / (1000**2),
        )
        disk_defaults = [
            "#rd-cd", "#rd-md", "sect-rd", "time-rd", "#wr-cd", "#wr-md", "sect-wr",
            "time-wr", "#io-ip", "time-io", "time-wei-io", "#disc-cd", "#disc-md", "sect-disc",
            "time-disc", "#flush-req", "time-flush",
        ]
        self.disk_prof = {}
        self.disk_data = {}
        self.disk_blks = list(rows.keys())
        if rows:
            self.disk_stamps = next(iter(rows.values()))["timestamp"]
        for blk, profile in rows.items():
            self.maj_blks_sects[blk] = 512
            self.disk_prof[blk] = {field: np.zeros(len(self.disk_stamps), dtype=float) for field in disk_defaults}
            self.disk_prof[blk]["major"] = 0
            self.disk_prof[blk]["minor"] = 0
            self.disk_prof[blk]["sect-rd"] = profile.get("sect-rd", np.zeros(len(self.disk_stamps)))
            self.disk_prof[blk]["sect-wr"] = profile.get("sect-wr", np.zeros(len(self.disk_stamps)))
            self.disk_data[blk] = {field: 0 for field in disk_defaults}
            self.disk_data[blk]["sect-rd"] = totals[blk].get("sect-rd", 0)
            self.disk_data[blk]["sect-wr"] = totals[blk].get("sect-wr", 0)
        self.disk_profile_valid = len(self.disk_stamps) > 0

    def _load_ib(self) -> None:
        rows, totals = self._load_rate_metric(
            measurement="infiniband",
            tag_key="device",
            fields={"port_rcv_data": "port_rcv_data", "port_xmit_data": "port_xmit_data"},
            scale=4.0 / (1000**2),
        )
        self.ib_prof = {}
        self.ib_data = totals
        self.ib_interfs = list(rows.keys())
        if rows:
            self.ib_stamps = next(iter(rows.values()))["timestamp"]
        for interf, profile in rows.items():
            self.ib_prof[interf] = {
                "port_rcv_data": profile.get("port_rcv_data", np.zeros(len(self.ib_stamps))),
                "port_xmit_data": profile.get("port_xmit_data", np.zeros(len(self.ib_stamps))),
            }
        self.ib_profile_valid = len(self.ib_stamps) > 0

    def _load_rate_metric(
        self,
        measurement: str,
        tag_key: str,
        fields: dict[str, str],
        scale: float,
    ) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, dict[str, int]]]:
        base_params = {
            "hostname": self.hostname,
            "start_time": self._local_time_param(self.start_time),
            "end_time": self._local_time_param(self.end_time),
        }
        field_select = ", ".join(fields.values())

        if self.actual_resolution == "raw":
            rows = self._query_rows(
                f"SELECT time, {tag_key}, {field_select} FROM {measurement} "
                f"WHERE hostname = $hostname AND time >= $start_time AND time < $end_time ORDER BY time, {tag_key}",
                **base_params,
            )
            return self._build_rate_profiles_from_raw(rows, tag_key, fields, scale)

        rate_exprs = []
        for display_key in fields:
            alias = display_key.replace("-", "_")
            rate_exprs.append(f"AVG({alias}) AS {alias}")
        inner_exprs = []
        for display_key, source_key in fields.items():
            alias = display_key.replace("-", "_")
            inner_exprs.append(
                "CASE WHEN EXTRACT(EPOCH FROM (time - LAG(time) OVER w)) = 0 "
                "THEN NULL ELSE "
                f"GREATEST(0, ({source_key} - LAG({source_key}) OVER w) "
                f"/ EXTRACT(EPOCH FROM (time - LAG(time) OVER w)) * {scale}) "
                f"END AS {alias}"
            )
        bucket_query = f"""
            SELECT bucket_time AS time, {tag_key}, {', '.join(rate_exprs)}
            FROM (
                SELECT date_bin(INTERVAL '{self.actual_resolution}', time) AS bucket_time,
                       {tag_key},
                       {', '.join(inner_exprs)}
                FROM {measurement}
                WHERE hostname = $hostname AND time >= $start_time AND time < $end_time
                WINDOW w AS (PARTITION BY {tag_key} ORDER BY time)
            ) rates
            GROUP BY bucket_time, {tag_key}
            ORDER BY time, {tag_key}
        """
        rows = self._query_rows(bucket_query, **base_params)
        total_exprs = []
        for display_key, source_key in fields.items():
            total_exprs.append(
                f"GREATEST(0, MAX({source_key}) - MIN({source_key})) * {scale} AS {display_key.replace('-', '_total')}"
            )
        totals = self._query_rows(
            f"SELECT {tag_key}, {', '.join(total_exprs)} FROM {measurement} "
            f"WHERE hostname = $hostname AND time >= $start_time AND time < $end_time "
            f"GROUP BY {tag_key} ORDER BY {tag_key}",
            **base_params,
        )
        return self._build_rate_profiles_from_bucket(rows, totals, tag_key, fields)

    def _build_rate_profiles_from_raw(
        self,
        rows: list[dict[str, Any]],
        tag_key: str,
        fields: dict[str, str],
        scale: float,
    ) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, dict[str, int]]]:
        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row[tag_key])].append(row)

        profiles = {}
        totals = {}
        for label, entries in grouped.items():
            if tag_key == "interface" and not label.endswith(":"):
                label = f"{label}:"
            entries.sort(key=lambda item: parse_query_timestamp(item["time"]))
            times = np.array([parse_query_timestamp(item["time"]) for item in entries], dtype=float)
            if len(times) < 2:
                continue
            timestamps = (times[1:] + times[:-1]) / 2.0
            profile = {"timestamp": timestamps}
            data = {}
            for display_key, source_key in fields.items():
                values = np.array([self._extract_field(item, source_key) for item in entries], dtype=float)
                deltas = np.maximum(values[1:] - values[:-1], 0.0)
                delta_t = times[1:] - times[:-1]
                rate = np.divide(deltas, delta_t, out=np.zeros_like(deltas), where=delta_t > 0) * scale
                profile[display_key] = rate
                data[display_key] = int(max(float(np.max(values) - np.min(values)), 0.0) * scale)
            profiles[label] = profile
            totals[label] = data
        return profiles, totals

    def _build_rate_profiles_from_bucket(
        self,
        rows: list[dict[str, Any]],
        totals_rows: list[dict[str, Any]],
        tag_key: str,
        fields: dict[str, str],
    ) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, dict[str, int]]]:
        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row[tag_key])].append(row)

        profiles = {}
        for label, entries in grouped.items():
            if tag_key == "interface" and not label.endswith(":"):
                label = f"{label}:"
            entries.sort(key=lambda item: parse_query_timestamp(item["time"]))
            profiles[label] = {
                "timestamp": np.array(
                    [parse_query_timestamp(item["time"]) for item in entries],
                    dtype=float,
                )
            }
            for display_key in fields:
                alias = display_key.replace("-", "_")
                profiles[label][display_key] = np.array(
                    [self._extract_field(item, alias) for item in entries],
                    dtype=float,
                )

        totals = {}
        for row in totals_rows:
            label = str(row[tag_key])
            if tag_key == "interface" and not label.endswith(":"):
                label = f"{label}:"
            totals[label] = {}
            for display_key in fields:
                alias = display_key.replace("-", "_total")
                totals[label][display_key] = int(self._extract_field(row, alias))
        return profiles, totals
