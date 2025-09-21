"""InfluxDB sender for real-time data streaming"""

import logging
import queue
import threading
import time
from typing import Dict, Any, List
import requests


class InfluxDBSender:
    """Send metrics data to InfluxDB in real-time"""

    def __init__(self, logger: logging.Logger, config: Dict[str, Any]):
        self.logger = logger
        self.config = config

        # Configuration
        self.influxdb_url = config.get('url', 'http://localhost:8086')
        self.organization = config.get('organization', 'benchmon')
        self.bucket = config.get('bucket', 'metrics')
        self.token = config.get('token', 'admin123')
        self.job_name = config.get('job_name', 'benchmon')

        # Performance settings
        self.batch_size = config.get('batch_size', 50)
        self.send_interval = config.get('send_interval', 2.0)

        # Internal state
        self.data_queue = queue.Queue()
        self.is_running = False
        self.sender_thread = None

        # HTTP session for connection reuse
        self.session = requests.Session()
        headers = {
            'Content-Type': 'text/plain; charset=utf-8'
        }
        if self.token:
            headers['Authorization'] = f'Token {self.token}'
        self.session.headers.update(headers)

        self.write_url = f"{self.influxdb_url}/api/v2/write?org={self.organization}&bucket={self.bucket}&precision=s"

    @staticmethod
    def create_config(influxdb_url: str = None, enabled: bool = True, **kwargs) -> Dict[str, Any]:
        """Create configuration dictionary for InfluxDB sender"""
        return {
            'enabled': enabled,
            'url': influxdb_url or 'http://localhost:8086',
            'organization': kwargs.get('organization', 'benchmon'),
            'bucket': kwargs.get('bucket', 'metrics'),
            'token': kwargs.get('token', 'admin123'),
            'job_name': kwargs.get('job_name', 'benchmon'),
            'batch_size': kwargs.get('batch_size', 50),
            'send_interval': kwargs.get('send_interval', 2.0)
        }

    def start(self):
        """Start the InfluxDB sender thread"""
        if self.is_running:
            return

        self.is_running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        self.logger.info(f"InfluxDB sender started (URL: {self.influxdb_url}, bucket: {self.bucket})")

    def stop(self):
        """Stop the InfluxDB sender thread"""
        if not self.is_running:
            return

        self.is_running = False
        if self.sender_thread:
            self.sender_thread.join(timeout=5)

        # Send any remaining data
        self._send_remaining_data()
        self.session.close()
        self.logger.info("InfluxDB sender stopped")

    def send_metrics(self, metrics: List[Dict[str, Any]]):
        """Queue metrics for sending to InfluxDB"""
        for metric in metrics:
            try:
                self.data_queue.put(metric, block=False)
            except queue.Full:
                self.logger.warning("InfluxDB queue full, dropping metric")

    def _sender_loop(self):
        """Main sender loop running in background thread"""
        batch = []
        last_send_time = time.time()

        while self.is_running:
            try:
                # Try to get data with timeout
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

        # Send remaining data before exit
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send a batch of metrics to InfluxDB"""
        if not batch:
            return

        try:
            line_protocol_data = self._convert_to_line_protocol(batch)
            if not line_protocol_data:
                return

            response = self.session.post(
                self.write_url,
                data=line_protocol_data,
                timeout=10
            )

            # If 401 Unauthorized and token is empty, try again without Authorization header
            if response.status_code == 401 and self.token:
                self.logger.error("InfluxDB write failed: 401 Unauthorized. Check your token or try running without --grafana-token.")
            elif response.status_code == 401 and not self.token:
                # Remove Authorization header and retry
                self.session.headers.pop('Authorization', None)
                response = self.session.post(
                    self.write_url,
                    data=line_protocol_data,
                    timeout=10
                )

            if response.status_code == 204:
                self.logger.debug(f"Successfully sent {len(batch)} metrics to InfluxDB")
            else:
                self.logger.error(f"InfluxDB write failed: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send metrics to InfluxDB: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending metrics to InfluxDB: {e}")

    def _convert_to_line_protocol(self, metrics: List[Dict[str, Any]]) -> str:
        """Convert metrics to InfluxDB line protocol format"""
        lines = []

        for metric in metrics:
            try:
                measurement = metric.get('metric_name', 'unknown')
                timestamp = metric.get('timestamp', int(time.time()))
                value = metric.get('value')

                if value is None:
                    continue

                # Build tags
                tags = {
                    'job': self.job_name,
                    'instance': metric.get('hostname', 'unknown')
                }

                # Add metric-specific tags
                if 'cpu' in metric:
                    tags['cpu'] = str(metric['cpu'])
                if 'interface' in metric:
                    tags['interface'] = metric['interface']
                if 'device' in metric:
                    tags['device'] = metric['device']

                # Build tag string
                tag_string = ','.join([f"{k}={v}" for k, v in tags.items()])

                # Build fields
                fields = {}
                if 'fields' in metric and metric['fields']:
                    # Use multiple fields if provided
                    fields = metric['fields']
                else:
                    # Fall back to single value field
                    fields['value'] = value

                # Build field string
                field_string = ','.join([f"{k}={v}" for k, v in fields.items()])

                # Build line protocol entry
                # Format: measurement,tag1=value1,tag2=value2 field1=value1,field2=value2 timestamp
                line = f"{measurement},{tag_string} {field_string} {timestamp}"
                lines.append(line)

            except Exception as e:
                self.logger.warning(f"Failed to convert metric to line protocol: {e}")
                continue

        return '\n'.join(lines)

    def _send_remaining_data(self):
        """Send any remaining data in the queue"""
        batch = []
        try:
            while True:
                metric = self.data_queue.get_nowait()
                batch.append(metric)
        except queue.Empty:
            pass

        if batch:
            self._send_batch(batch)
            self.logger.info(f"Sent {len(batch)} remaining metrics to InfluxDB")


def create_influxdb_config(influxdb_url: str = None, enabled: bool = True, **kwargs) -> Dict[str, Any]:
    """Create high-performance InfluxDB configuration"""
    return InfluxDBSender.create_config(
        influxdb_url=influxdb_url,
        enabled=enabled,
        organization=kwargs.get('organization', 'benchmon'),
        bucket=kwargs.get('bucket', 'metrics'),
        token=kwargs.get('token', 'admin123'),
        job_name=kwargs.get('job_name', 'benchmon'),
        batch_size=kwargs.get('batch_size', 50),
        send_interval=kwargs.get('send_interval', 2.0)
    )
