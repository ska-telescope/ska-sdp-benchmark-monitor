"""InfluxDB3 sender for real-time data streaming (FlightSQL/Arrow)"""

import logging
import queue
import threading
import time
import math
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
                    if metric.get('hostname') is not None:
                        hname = str(metric.get('hostname'))
                        hname = ''.join(c for c in hname if c.isalnum() or c == '_')
                        if hname:
                            tags.append(f"host={hname}")
                    # 新增cpu标签
                    if metric.get('cpu') is not None:
                        cpu_tag = str(metric.get('cpu'))
                        cpu_tag = ''.join(c for c in cpu_tag if c.isalnum() or c == '_')
                        if cpu_tag:
                            tags.append(f"cpu={cpu_tag}")
                    tag_str = ','.join(tags)
                    # fields
                    fields = []
                    v = None
                    if 'fields' in metric and metric['fields']:
                        for k, val in metric['fields'].items():
                            if val is not None and isinstance(val, (int, float, bool, str)):
                                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                                    continue
                                if isinstance(val, str):
                                    val = ''.join(c for c in val if c.isprintable())
                                    if not val:
                                        continue
                                v = val
                                break
                    if v is None and metric.get('value') is not None and isinstance(metric.get('value'), (int, float, bool, str)):
                        val = metric.get('value')
                        if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                            pass
                        elif isinstance(val, str):
                            val = ''.join(c for c in val if c.isprintable())
                            if val:
                                v = val
                        else:
                            v = val
                    if v is not None:
                        if isinstance(v, str):
                            fields.append(f'value="{v}"')
                        else:
                            fields.append(f'value={v}')
                        field_str = ','.join(fields)
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
                                # 纳秒范围
                                if ts > 1e17 and ts < 1e20:
                                    ts_str = f' {ts}'
                            except Exception:
                                pass
                        line = f"{mname},{tag_str} {field_str}{ts_str}"
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
