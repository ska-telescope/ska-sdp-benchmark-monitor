"""InfluxDB3 sender for real-time data streaming (FlightSQL/Arrow)"""

import logging
import queue
import threading
import time
import math
import re
import socket
from typing import Dict, Any, List


class InfluxDBSender:
    """Send metrics data to InfluxDB3 (FlightSQL) in real-time"""

    def __init__(self, logger: logging.Logger, config: Dict[str, Any]):
        self.logger = logger
        self.config = config
        self.influxdb_url = config.get('url', 'http://localhost:8181')  # host:port
        self.database = config.get('database', 'metrics')
        self.token = config.get('token', '')
        self.job_name = config.get('job_name', 'benchmon')
        self.batch_size = config.get('batch_size', 100)  # 建议更大批量
        self.send_interval = config.get('send_interval', 1.0)
        self.data_queue = queue.Queue()
        self.is_running = False
        self.sender_thread = None
        self._init_client()

    def _init_client(self):
        try:
            from influxdb_client_3 import InfluxDBClient3, Point
            self.Point = Point
            # host参数直接传http://host:port，与test脚本一致
            self.client = InfluxDBClient3(
                host=self.influxdb_url,
                token=self.token,
                database=self.database,
                use_ssl=False,
                insecure=True
            )
            self.logger.info(f"InfluxDBSender: Using InfluxDB3 (FlightSQL) mode, host={self.influxdb_url}, database={self.database}")
        except ImportError:
            self.logger.error("influxdb_client_3 not installed. Please pip install influxdb3-python.")
            raise
        except Exception as e:
            self.logger.error(f"InfluxDB3 client init failed: {e}")
            raise

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        self.logger.info(f"InfluxDB3 sender started (host:port={self.influxdb_url}, database: {self.database})")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.sender_thread:
            self.sender_thread.join(timeout=5)
        self._send_remaining_data()
        self.logger.info("InfluxDB3 sender stopped")

    def send_metrics(self, metrics: List[Dict[str, Any]]):
        for metric in metrics:
            try:
                self.data_queue.put(metric, block=False)
            except queue.Full:
                self.logger.warning("InfluxDB queue full, dropping metric")

    def _sender_loop(self):
        batch = []
        last_send_time = time.time()
        while self.is_running:
            try:
                try:
                    metric = self.data_queue.get(timeout=0.1)
                    batch.append(metric)
                except queue.Empty:
                    pass
                current_time = time.time()
                batch_full = len(batch) >= self.batch_size
                time_expired = batch and current_time - last_send_time >= self.send_interval
                should_send = batch_full or time_expired
                if should_send:
                    self._send_batch(batch)
                    batch = []
                    last_send_time = current_time
            except Exception as e:
                self.logger.error(f"Error in InfluxDB sender loop: {e}")
                time.sleep(1)
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        try:
            lines = []
            for metric in batch:
                try:
                    # measurement名仅用英文字母数字和_，且不为空，不以_开头
                    mname = str(metric.get('metric_name', 'unknown'))
                    mname = ''.join(c for c in mname if c.isalnum() or c == '_')
                    if not mname or mname.startswith('_') or mname == '_':
                        mname = 'unknown'
                    # tags
                    tags = []
                    # Prefer explicit 'host' then 'hostname' if provided by sender
                    host_raw = None
                    if metric.get('host'):
                        host_raw = str(metric.get('host'))
                    elif metric.get('hostname'):
                        host_raw = str(metric.get('hostname'))
                    else:
                        # fallback to system fqdn
                        try:
                            host_raw = socket.getfqdn()
                        except Exception:
                            host_raw = None
                    if host_raw:
                        # allow alnum, dot, dash, underscore in tag value
                        host_clean = re.sub(r'[^0-9A-Za-z\.\-_]', '', host_raw)
                        if host_clean:
                            tags.append(f"host={host_clean}")

                    # 新增cpu标签 (preserve dots/dashes if any, but cpu names usually simple)
                    if metric.get('cpu') is not None:
                        cpu_tag = str(metric.get('cpu'))
                        cpu_tag = re.sub(r'[^0-9A-Za-z\.\-_]', '', cpu_tag)
                        if cpu_tag:
                            tags.append(f"cpu={cpu_tag}")

                    tag_str = ','.join(tags)
                    # fields
                    fields = []
                    if 'fields' in metric and metric['fields']:
                        for k, val in metric['fields'].items():
                            # Skip None
                            if val is None:
                                continue

                            # Preserve incoming types:
                            # - bool -> true/false (unquoted)
                            # - int/float -> numeric literal (no coercion)
                            # - everything else -> string (quoted, escaped)
                            if isinstance(val, bool):
                                fields.append(f'{k}={"true" if val else "false"}')
                            elif isinstance(val, (int, float)):
                                # filter NaN/Inf for floats
                                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                                    continue
                                fields.append(f'{k}={val}')
                            else:
                                # Treat any other type (including numeric-looking strings) as string
                                s = str(val)
                                # remove non-printable characters
                                s = ''.join(c for c in s if c.isprintable())
                                # escape backslashes and double quotes
                                s = s.replace('\\', '\\\\').replace('"', '\\"')
                                fields.append(f'{k}="{s}"')
                    else:
                        v = None
                        if metric.get('value') is not None:
                            raw = metric.get('value')
                            # Preserve incoming types similarly for single 'value'
                            if isinstance(raw, bool):
                                v = f'{"true" if raw else "false"}'
                                is_string = False
                            elif isinstance(raw, (int, float)):
                                if isinstance(raw, float) and (math.isinf(raw) or math.isnan(raw)):
                                    v = None
                                else:
                                    v = str(raw)
                                    is_string = False
                            else:
                                # Always treat as string
                                sval = str(raw)
                                sval = ''.join(c for c in sval if c.isprintable())
                                sval = sval.replace('\\', '\\\\').replace('"', '\\"')
                                v = f'"{sval}"'
                                is_string = True
                        if v is not None:
                            # If v already a quoted string (starts with "), append as-is
                            if isinstance(v, str) and v.startswith('"'):
                                fields.append(f'value={v}')
                            else:
                                # numeric or boolean literal represented as string
                                fields.append(f'value={v}')

                    field_str = ','.join(fields)
                    if not field_str:
                        continue

                    # timestamp
                    ts_str = ''
                    if 'timestamp' in metric and metric['timestamp'] is not None:
                        try:
                            ts = int(metric['timestamp'])
                            # 自动判断单位并转为纳秒
                            if ts < 1e10:  # 秒
                                ts = ts * 1_000_000_000
                            elif ts < 1e13:  # 毫秒
                                ts = ts * 1_000_000
                            elif ts < 1e16:  # 微秒
                                ts = ts * 1_000
                            # If ts looks like nanoseconds, include it
                            if ts > 1e17 and ts < 1e20:
                                ts_str = f' {ts}'
                        except Exception:
                            pass

                    # Compose line without extra comma when no tags
                    if tag_str:
                        line = f"{mname},{tag_str} {field_str}{ts_str}"
                    else:
                        line = f"{mname} {field_str}{ts_str}"

                    lines.append(line)
                except Exception as e:
                    self.logger.warning(f"Failed to convert metric to line: {e}")
            if lines:
                self.client.write(lines)
                self.logger.debug(f"Successfully sent {len(lines)} metrics to InfluxDB3")
        except Exception as e:
            self.logger.error(f"Failed to send metrics to InfluxDB3: {e}")

    def _send_remaining_data(self):
        batch = []
        try:
            while True:
                metric = self.data_queue.get_nowait()
                batch.append(metric)
        except queue.Empty:
            pass
        if batch:
            self._send_batch(batch)
            self.logger.info(f"Sent {len(batch)} remaining metrics to InfluxDB3")


def create_influxdb_config(influxdb_url: str = None, enabled: bool = True, **kwargs) -> Dict[str, Any]:
    """Create high-performance InfluxDB3 configuration"""
    return {
        'url': influxdb_url or 'localhost:8182',
        'database': kwargs.get('database', 'metrics'),
        'token': kwargs.get('token', 'admin123'),
        'job_name': kwargs.get('job_name', 'benchmon'),
        'batch_size': kwargs.get('batch_size', 100),
        'send_interval': kwargs.get('send_interval', 1.0)
    }


def get_ns_timestamp(ts=None):
    """返回纳秒级时间戳"""
    import time
    if ts is None:
        ts = time.time()
    ts = float(ts)
    if ts < 1e10:  # 秒
        return int(ts * 1_000_000_000)
    elif ts < 1e13:  # 毫秒
        return int(ts * 1_000_000)
    elif ts < 1e16:  # 微秒
        return int(ts * 1_000)
    else:
        return int(ts)
