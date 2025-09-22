"""
High-performance data processor for direct monitoring integration
Reads named pipe data and sends directly to InfluxDB, avoiding CSV file intermediate performance overhead
"""

import os
import time
import threading
import logging
from typing import Dict
import select


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


class HighPerformanceDataProcessor:
    """
    High-performance data processor that receives data directly from monitoring scripts and sends to Grafana
    """

    def __init__(self, logger: logging.Logger, data_sender, pipe_path: str):
        """
        Initialize high-performance data processor

        Args:
            logger: Logger instance
            data_sender: Data sender instance (InfluxDBSender)
            pipe_path: Named pipe path for receiving data
        """
        self.logger = logger
        self.data_sender = data_sender
        self.pipe_path = pipe_path

        # Create InfluxDB hook
        self.hook = InfluxDBMonitorHook(data_sender)

        self.should_run = True
        self.processor_thread = None

        # Performance counters
        self.data_points_processed = 0
        self.start_time = time.time()

    def start(self):
        """Start the data processor"""
        if not getattr(self.data_sender, 'config', {}).get('enabled', True):
            self.logger.info("Data sender disabled, skipping high-performance processor")
            return

        # Create named pipe
        try:
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
            os.mkfifo(self.pipe_path)
            self.logger.info(f"Created named pipe: {self.pipe_path}")
        except Exception as e:
            self.logger.error(f"Failed to create named pipe {self.pipe_path}: {e}")
            return

        self.should_run = True
        self.processor_thread = threading.Thread(target=self._processor_worker, daemon=True)
        self.processor_thread.start()
        self.logger.info("High-performance data processor started")

    def stop(self):
        """Stop the data processor"""
        if not self.processor_thread:
            return

        self.should_run = False

        # Force flush any remaining data
        self.hook.flush()

        # Clean up named pipe
        try:
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
        except Exception as e:
            self.logger.warning(f"Failed to clean up named pipe: {e}")

        self.processor_thread.join(timeout=3.0)

        # Report performance
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            rate = self.data_points_processed / elapsed
            self.logger.info(f"Processed {self.data_points_processed} data points at {rate:.1f} points/sec")

    def _processor_worker(self):
        """Worker thread that processes data from named pipe"""
        pipe_fd = None

        try:
            # Open named pipe for reading (non-blocking)
            pipe_fd = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
            self.logger.debug("Named pipe opened for reading")

            buffer = ""

            while self.should_run:
                try:
                    # Use select to check if data is available
                    ready, _, _ = select.select([pipe_fd], [], [], 0.1)

                    if ready:
                        # Read data from pipe
                        data = os.read(pipe_fd, 4096).decode('utf-8')
                        if data:
                            buffer += data

                            # Process complete lines
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                if line.strip():
                                    self._process_data_line(line.strip())

                    # Periodic flush to ensure data is sent (every 100 data points)
                    if self.data_points_processed > 0 and self.data_points_processed % 100 == 0:
                        self.hook.flush()

                except OSError as e:
                    if e.errno != 11:  # EAGAIN/EWOULDBLOCK
                        self.logger.error(f"Error reading from pipe: {e}")
                        break
                except Exception as e:
                    self.logger.error(f"Error in processor worker: {e}")
                    time.sleep(0.1)

        finally:
            if pipe_fd:
                try:
                    os.close(pipe_fd)
                except OSError:
                    pass

    def _process_data_line(self, line: str):
        """
        Process a single data line from monitoring script

        Args:
            line: Data line in format "TYPE|timestamp|data"
        """
        try:
            parts = line.split('|', 2)
            if len(parts) != 3:
                return

            data_type, timestamp_str, data = parts
            timestamp = float(timestamp_str)

            if data_type == 'CPU':
                self._process_cpu_data(timestamp, data)
            elif data_type == 'CPUFREQ':
                self._process_cpufreq_data(timestamp, data)
            elif data_type == 'MEMORY':
                self._process_memory_data(timestamp, data)
            elif data_type == 'NETWORK':
                self._process_network_data(timestamp, data)
            elif data_type == 'DISK':
                self._process_disk_data(timestamp, data)

            self.data_points_processed += 1

        except Exception as e:
            self.logger.debug(f"Error processing data line '{line}': {e}")

    def _process_cpu_data(self, timestamp: float, data: str):
        """Process CPU data line"""
        try:
            # Parse CPU data: "cpu0 user nice system idle iowait irq softirq steal guest guest_nice"
            parts = data.strip().split()
            if len(parts) < 8:
                return

            cpu_core = parts[0]
            stats = {
                'user': int(parts[1]),
                'nice': int(parts[2]),
                'system': int(parts[3]),
                'idle': int(parts[4]),
                'iowait': int(parts[5]),
                'irq': int(parts[6]),
                'softirq': int(parts[7]),
                'steal': int(parts[8]) if len(parts) > 8 else 0
            }

            self.hook.on_cpu_data(timestamp, cpu_core, stats)

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing CPU data '{data}': {e}")

    def _process_cpufreq_data(self, timestamp: float, data: str):
        """Process CPU frequency data line"""
        try:
            # Parse CPU frequency data: "cpu0 2400000"
            parts = data.strip().split()
            if len(parts) < 2:
                return

            cpu_core = parts[0]
            frequency = int(parts[1])

            self.hook.on_cpufreq_data(timestamp, cpu_core, frequency)

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing CPU frequency data '{data}': {e}")

    def _process_memory_data(self, timestamp: float, data: str):
        """Process memory data line"""
        try:
            # Parse memory data from /proc/meminfo values
            values = data.split(',')

            # Get memory field names (simplified)
            memory_fields = [
                'MemTotal', 'MemFree', 'MemAvailable', 'Buffers', 'Cached',
                'SwapCached', 'Active', 'Inactive', 'SwapTotal', 'SwapFree'
            ]

            stats = {}
            for i, field in enumerate(memory_fields[:len(values)]):
                try:
                    stats[field] = int(values[i])
                except (ValueError, IndexError):
                    continue

            self.hook.on_memory_data(timestamp, stats)

        except Exception as e:
            self.logger.debug(f"Error parsing memory data '{data}': {e}")

    def _process_network_data(self, timestamp: float, data: str):
        """Process network data line"""
        try:
            # Parse network data: "interface rx_bytes rx_packets ... tx_bytes tx_packets ..."
            parts = data.strip().split()
            if len(parts) < 17:
                return

            interface = parts[0].rstrip(':')
            stats = {
                'rx_bytes': int(parts[1]),
                'rx_packets': int(parts[2]),
                'rx_errs': int(parts[3]),
                'rx_drop': int(parts[4]),
                'tx_bytes': int(parts[9]),
                'tx_packets': int(parts[10]),
                'tx_errs': int(parts[11]),
                'tx_drop': int(parts[12])
            }

            self.hook.on_network_data(timestamp, interface, stats)

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing network data '{data}': {e}")

    def _process_disk_data(self, timestamp: float, data: str):
        """Process disk data line"""
        try:
            # Parse disk data from /proc/diskstats
            parts = data.strip().split()
            if len(parts) < 14:
                return

            device = parts[2]
            stats = {
                'reads_completed': int(parts[3]),
                'sectors_read': int(parts[5]),
                'writes_completed': int(parts[7]),
                'sectors_written': int(parts[9])
            }

            self.hook.on_disk_data(timestamp, device, stats)

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing disk data '{data}': {e}")


class InfluxDBMonitorHook:
    """Monitor hook for InfluxDB integration"""

    def __init__(self, influxdb_sender):
        self.influxdb_sender = influxdb_sender

    def flush(self):
        """Flush any pending data to InfluxDB"""
        # InfluxDBSender handles batching internally, nothing to flush here
        pass

    def on_cpu_data(self, timestamp: float, cpu: str, stats: Dict[str, float]):
        """Handle CPU data for InfluxDB"""
        metrics = []
        hostname = os.uname()[1]

        for metric_name, value in stats.items():
            metrics.append({
                'metric_name': f'cpu_{metric_name}',
                'value': value,
                'timestamp': get_ns_timestamp(timestamp),
                'hostname': hostname,
                'cpu': cpu
            })

        self.influxdb_sender.send_metrics(metrics)

    def on_cpufreq_data(self, timestamp: float, cpu: str, frequency: int):
        """Handle CPU frequency data for InfluxDB"""
        hostname = os.uname()[1]

        metric = {
            'metric_name': 'cpu_frequency',
            'value': frequency,
            'timestamp': get_ns_timestamp(timestamp),
            'hostname': hostname,
            'cpu': cpu
        }

        self.influxdb_sender.send_metrics([metric])

    def on_memory_data(self, timestamp: float, stats: Dict[str, int]):
        """Handle memory data for InfluxDB"""
        metrics = []
        hostname = os.uname()[1]

        for metric_name, value in stats.items():
            metrics.append({
                'metric_name': f'memory_{metric_name.lower()}',
                'value': value,
                'timestamp': get_ns_timestamp(timestamp),
                'hostname': hostname
            })

        self.influxdb_sender.send_metrics(metrics)

    def on_network_data(self, timestamp: float, interface: str, stats: Dict[str, int]):
        """Handle network data for InfluxDB"""
        hostname = os.uname()[1]

        # Create single measurement with multiple fields for dashboard compatibility
        metric = {
            'metric_name': 'network_stats',
            'value': stats.get('rx_bytes', 0),  # Use rx_bytes as primary value
            'timestamp': get_ns_timestamp(timestamp),
            'hostname': hostname,
            'interface': interface,
            'fields': {
                'rx_bytes': stats.get('rx_bytes', 0),
                'tx_bytes': stats.get('tx_bytes', 0),
                'rx_packets': stats.get('rx_packets', 0),
                'tx_packets': stats.get('tx_packets', 0)
            }
        }

        self.influxdb_sender.send_metrics([metric])

    def on_disk_data(self, timestamp: float, device: str, stats: Dict[str, int]):
        """Handle disk data for InfluxDB"""
        hostname = os.uname()[1]

        # Create single measurement with multiple fields for dashboard compatibility
        metric = {
            'metric_name': 'disk_stats',
            'value': stats.get('sectors_read', 0),  # Use sectors_read as primary value
            'timestamp': get_ns_timestamp(timestamp),
            'hostname': hostname,
            'device': device,
            'fields': {
                'sectors_read': stats.get('sectors_read', 0),
                'sectors_written': stats.get('sectors_written', 0),
                'reads_completed': stats.get('reads_completed', 0),
                'writes_completed': stats.get('writes_completed', 0)
            }
        }

        self.influxdb_sender.send_metrics([metric])
