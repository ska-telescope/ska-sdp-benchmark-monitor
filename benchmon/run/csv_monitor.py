"""CSV file monitor for real-time data parsing and InfluxDB sending"""

import os
import time
import threading
from typing import Dict
import logging


class CSVMonitor:
    """
    Monitors CSV files in real-time and parses new lines for sending to InfluxDB
    """

    def __init__(self, logger: logging.Logger, data_sender):
        """
        Initialize CSV monitor

        Args:
            logger: Logger instance
            data_sender: Data sender instance (InfluxDBSender or similar)
        """
        self.logger = logger
        self.data_sender = data_sender
        self.monitored_files = {}
        self.should_run = True
        self.monitor_threads = []

    def add_file_monitor(self, file_path: str, file_type: str):
        """
        Add a CSV file to monitor

        Args:
            file_path: Path to CSV file to monitor
            file_type: Type of file (cpu, mem, net, disk, etc.)
        """
        if file_type not in ['cpu', 'mem', 'net', 'disk', 'cpufreq', 'ib']:
            self.logger.warning(f"Unknown file type: {file_type}")
            return

        self.monitored_files[file_path] = {
            'type': file_type,
            'last_position': 0,
            'headers': None
        }

        self.logger.info(f"Added {file_type} monitor for: {file_path}")

    def start_monitoring(self):
        """Start monitoring all added files"""
        if not getattr(self.data_sender, 'config', {}).get('enabled', True):
            self.logger.info("Data sender disabled, skipping CSV monitoring")
            return

        for file_path in self.monitored_files.keys():
            thread = threading.Thread(
                target=self._monitor_file,
                args=(file_path,),
                daemon=True
            )
            thread.start()
            self.monitor_threads.append(thread)

        self.logger.info(f"Started monitoring {len(self.monitored_files)} CSV files")

    def stop_monitoring(self):
        """Stop monitoring all files"""
        self.should_run = False
        for thread in self.monitor_threads:
            thread.join(timeout=2.0)
        self.logger.info("Stopped CSV file monitoring")

    def _monitor_file(self, file_path: str):
        """
        Monitor a single CSV file for new lines

        Args:
            file_path: Path to CSV file to monitor
        """
        file_info = self.monitored_files[file_path]
        file_type = file_info['type']

        self.logger.debug(f"Starting to monitor {file_type} file: {file_path}")

        # Wait for file to be created
        while self.should_run and not os.path.exists(file_path):
            time.sleep(0.5)

        if not self.should_run:
            return

        with open(file_path, 'r') as file:
            # Read headers
            first_line = file.readline().strip()
            if first_line:
                file_info['headers'] = first_line.split(',')
                self.logger.debug(f"{file_type} headers: {file_info['headers']}")

            file_info['last_position'] = file.tell()

            while self.should_run:
                try:
                    # Seek to last known position
                    file.seek(file_info['last_position'])

                    # Read new lines
                    new_lines = file.readlines()

                    if new_lines:
                        # Process each new line
                        for line in new_lines:
                            line = line.strip()
                            if line:
                                self._process_csv_line(line, file_type, file_info['headers'])

                        # Update position
                        file_info['last_position'] = file.tell()

                    time.sleep(0.1)  # Small delay to prevent excessive CPU usage

                except Exception as e:
                    self.logger.error(f"Error monitoring {file_type} file {file_path}: {e}")
                    time.sleep(1.0)

    def _process_csv_line(self, line: str, file_type: str, headers: list):
        """
        Process a CSV line and send metrics to Grafana

        Args:
            line: CSV line to process
            file_type: Type of file (cpu, mem, net, disk, etc.)
            headers: CSV headers
        """
        try:
            values = line.split(',')
            if len(values) != len(headers):
                self.logger.debug(f"Skipping malformed {file_type} line: {line}")
                return

            # Create data dictionary
            data = dict(zip(headers, values))

            # Extract timestamp
            timestamp = float(data.get('timestamp', time.time()))

            # Send to Grafana based on file type
            if file_type == 'cpu':
                self._send_cpu_data(timestamp, data)
            elif file_type == 'mem':
                self._send_memory_data(timestamp, data)
            elif file_type == 'net':
                self._send_network_data(timestamp, data)
            elif file_type == 'disk':
                self._send_disk_data(timestamp, data)
            elif file_type == 'cpufreq':
                self._send_cpufreq_data(timestamp, data)
            elif file_type == 'ib':
                self._send_ib_data(timestamp, data)

        except Exception as e:
            self.logger.error(f"Error processing {file_type} line '{line}': {e}")

    def _send_cpu_data(self, timestamp: float, data: Dict[str, str]):
        """Send CPU data to InfluxDB"""
        try:
            cpu_core = data.get('cpu_core', 'cpu')

            # CPU utilization metrics
            metrics_to_send = []
            for metric in ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guestnice']:
                if metric in data and data[metric].isdigit():
                    metrics_to_send.append({
                        'metric_name': f'cpu_{metric}',
                        'value': float(data[metric]),
                        'timestamp': int(timestamp),
                        'cpu': cpu_core
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending CPU data: {e}")

    def _send_memory_data(self, timestamp: float, data: Dict[str, str]):
        """Send memory data to InfluxDB"""
        try:
            # Skip timestamp column and process memory values
            metrics_to_send = []
            for key, value in data.items():
                if key != 'timestamp' and value.isdigit():
                    # Convert memory metric names and values
                    metric_name = f"memory_{key.lower().replace(':', '_').replace('(', '').replace(')', '')}"
                    # Values are typically in kB, convert to bytes
                    metric_value = float(value) * 1024

                    metrics_to_send.append({
                        'metric_name': metric_name,
                        'value': metric_value,
                        'timestamp': int(timestamp)
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending memory data: {e}")

    def _send_network_data(self, timestamp: float, data: Dict[str, str]):
        """Send network data to InfluxDB"""
        try:
            interface = data.get('interface', 'unknown')

            # Network metrics mapping
            metric_mapping = {
                'rx-bytes': 'network_receive_bytes_total',
                'tx-bytes': 'network_transmit_bytes_total',
                'rx-packets': 'network_receive_packets_total',
                'tx-packets': 'network_transmit_packets_total',
                'rx-errs': 'network_receive_errors_total',
                'tx-errs': 'network_transmit_errors_total',
                'rx-drop': 'network_receive_drop_total',
                'tx-drop': 'network_transmit_drop_total'
            }

            metrics_to_send = []
            for csv_key, metric_name in metric_mapping.items():
                if csv_key in data and data[csv_key].isdigit():
                    metrics_to_send.append({
                        'metric_name': metric_name,
                        'value': float(data[csv_key]),
                        'timestamp': int(timestamp),
                        'interface': interface
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending network data: {e}")

    def _send_disk_data(self, timestamp: float, data: Dict[str, str]):
        """Send disk data to InfluxDB"""
        try:
            device = data.get('device', 'unknown')

            # Disk metrics mapping
            metric_mapping = {
                '#rd-cd': 'disk_reads_completed_total',
                '#wr-cd': 'disk_writes_completed_total',
                'sect-rd': 'disk_sectors_read_total',
                'sect-wr': 'disk_sectors_written_total',
                'time-rd': 'disk_read_time_seconds_total',
                'time-wr': 'disk_write_time_seconds_total',
                '#io-ip': 'disk_io_in_progress',
                'time-io': 'disk_io_time_seconds_total'
            }

            metrics_to_send = []
            for csv_key, metric_name in metric_mapping.items():
                if csv_key in data and data[csv_key].isdigit():
                    value = float(data[csv_key])

                    # Convert milliseconds to seconds for time metrics
                    if 'time' in metric_name and 'seconds' in metric_name:
                        value = value / 1000.0

                    metrics_to_send.append({
                        'metric_name': metric_name,
                        'value': value,
                        'timestamp': int(timestamp),
                        'device': device
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending disk data: {e}")

    def _send_cpufreq_data(self, timestamp: float, data: Dict[str, str]):
        """Send CPU frequency data to InfluxDB"""
        try:
            metrics_to_send = []
            for key, value in data.items():
                if key != 'timestamp' and value.isdigit():
                    # CPU frequency metrics
                    cpu_num = key.replace('cpu', '') if 'cpu' in key else '0'

                    metrics_to_send.append({
                        'metric_name': 'cpu_frequency_hz',
                        'value': float(value),
                        'timestamp': int(timestamp),
                        'cpu': cpu_num
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending CPU frequency data: {e}")

    def _send_ib_data(self, timestamp: float, data: Dict[str, str]):
        """Send InfiniBand data to InfluxDB"""
        try:
            metrics_to_send = []
            for key, value in data.items():
                if key != 'timestamp' and value.isdigit():
                    # InfiniBand metrics
                    metric_name = f"infiniband_{key.lower().replace('-', '_')}"

                    metrics_to_send.append({
                        'metric_name': metric_name,
                        'value': float(value),
                        'timestamp': int(timestamp)
                    })

            if metrics_to_send:
                self.data_sender.send_metrics(metrics_to_send)
        except Exception as e:
            self.logger.error(f"Error sending InfiniBand data: {e}")
