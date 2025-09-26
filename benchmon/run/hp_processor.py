import os
import time
import threading
import logging
import select

class HighPerformanceDataProcessor:
    """High-performance data processor for benchmon."""

    def __init__(self, logger: logging.Logger, influxdb_sender, pipe_path: str):
        self.logger = logger
        self.influxdb_sender = influxdb_sender
        self.pipe_path = pipe_path
        self.is_running = False
        self.processor_thread = None
        self.data_points_processed = 0
        self.start_time = 0

        # Create the named pipe if it doesn't exist
        if not os.path.exists(self.pipe_path):
            try:
                os.mkfifo(self.pipe_path)
                self.logger.info(f"Created named pipe: {self.pipe_path}")
            except Exception as e:
                self.logger.error(f"Failed to create named pipe {self.pipe_path}: {e}")

    def start(self):
        """Start the data processor"""
        self.is_running = True
        self.start_time = time.time()
        self.processor_thread = threading.Thread(target=self._processor_worker, daemon=True)
        self.processor_thread.start()
        self.logger.info("High-performance data processor started")

    def stop(self):
        """Stops the processor thread."""
        if not self.is_running:
            return
        self.is_running = False

        if self.processor_thread:
            self.processor_thread.join(timeout=3.0)

        # Clean up named pipe
        try:
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
        except Exception as e:
            self.logger.warning(f"Failed to clean up named pipe: {e}")

        # Report performance
        if self.start_time > 0:
            elapsed = time.time() - self.start_time
            if elapsed > 0 and self.data_points_processed > 0:
                rate = self.data_points_processed / elapsed
                self.logger.info(f"Processed {self.data_points_processed} data points at {rate:.1f} points/sec")

    def _processor_worker(self):
        """Worker thread that processes data from named pipe"""
        pipe_fd = None
        try:
            pipe_fd = os.open(self.pipe_path, os.O_RDONLY)
            self.logger.debug("Named pipe opened for reading")

            buffer = ""
            poller = select.poll()
            poller.register(pipe_fd, select.POLLIN)

            while self.is_running:
                events = poller.poll(1000)  # 1 second timeout
                for fileno, event in events:
                    if fileno == pipe_fd and (event & select.POLLIN):
                        data = os.read(pipe_fd, 8192).decode('utf-8')
                        if not data:  # Pipe closed by writer
                            self.is_running = False
                            break
                        buffer += data
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip():
                                self._process_data_line(line.strip())
                if not self.is_running:
                    break
        except Exception as e:
            self.logger.error(f"Error in processor worker: {e}")
        finally:
            if pipe_fd:
                os.close(pipe_fd)
            self.logger.debug("Pipe processing worker finished.")

    def _process_data_line(self, line: str):
        """
        Process a single data line from monitoring script
        Args:
            line: Data line in format "TYPE|aggregated_data"
        """
        try:
            # --- TIMESTAMP FIX: Generate a single timestamp for the entire aggregated batch ---
            timestamp_str = f"{time.time():.9f}"

            parts = line.split('|', 1)
            if len(parts) != 2:
                return

            data_type, aggregated_data = parts
            
            # Split the aggregated data by the pipe separator
            records = aggregated_data.split('|')
            
            # --- BATCHING FIX: Collect all metrics from this line into a single batch ---
            metrics_batch = []

            for record in records:
                if not record.strip():
                    continue
                
                data = record.strip()
                metric = None
                hostname = os.uname()[1]

                if data_type == 'CPU':
                    parts = data.split()
                    if len(parts) >= 8:
                        # --- CRITICAL FIX: Separate total and per-core metrics ---
                        core_id = parts[0]
                        fields_data = {
                            'user': int(parts[1]), 'nice': int(parts[2]), 'system': int(parts[3]),
                            'idle': int(parts[4]), 'iowait': int(parts[5]), 'irq': int(parts[6]),
                            'softirq': int(parts[7]), 'steal': int(parts[8]) if len(parts) > 8 else 0
                        }
                        
                        if core_id == 'cpu':
                            # This is the total CPU usage, write to 'cpu_total' measurement
                            metric = {
                                'metric_name': 'cpu_total',
                                'timestamp': timestamp_str,
                                'hostname': hostname,
                                'fields': fields_data
                            }
                        else:
                            # This is a per-core usage, write to 'cpu_core' measurement
                            metric = {
                                'metric_name': 'cpu_core',
                                'timestamp': timestamp_str,
                                'hostname': hostname,
                                'cpu': core_id,
                                'fields': fields_data
                            }
                elif data_type == 'CPUFREQ':
                    parts = data.split()
                    if len(parts) == 2:
                        metric = {
                            'metric_name': 'cpu_freq', 'timestamp': timestamp_str, 'hostname': hostname,
                            'cpu': parts[0], 'value': int(parts[1])
                        }
                elif data_type == 'MEMORY':
                    values = data.split(',')
                    fields = {k.lower(): v for k, v in zip(['MemTotal', 'MemFree', 'MemAvailable', 'Buffers', 'Cached', 'Slab'], values)}
                    metric = {
                        'metric_name': 'memory', 'timestamp': timestamp_str, 'hostname': hostname,
                        'fields': {k: int(v) for k, v in fields.items() if v}
                    }
                elif data_type == 'NETWORK':
                    if ':' in data:
                        iface_part, data_part = data.split(':', 1)
                        iface = iface_part.strip()
                        parts = data_part.strip().split()
                        if len(parts) >= 16:
                            metric = {
                                'metric_name': 'network_stats', 'timestamp': timestamp_str, 'hostname': hostname,
                                'interface': iface,
                                'fields': {'rx_bytes': int(parts[0]), 'tx_bytes': int(parts[8])}
                            }
                elif data_type == 'DISK':
                    parts = data.strip().split()
                    if len(parts) >= 14:
                         metric = {
                            'metric_name': 'disk_stats', 'timestamp': timestamp_str, 'hostname': hostname,
                            'device': parts[2],
                            'fields': {'sectors_read': int(parts[5]), 'sectors_written': int(parts[9])}
                        }
                elif data_type == 'IB':
                    parts = data.split()
                    if len(parts) == 3:
                        metric = {
                            'metric_name': 'infiniband', 'timestamp': timestamp_str, 'hostname': hostname,
                            'device': parts[0],
                            'fields': {
                                'port_rcv_data': int(parts[1]),
                                'port_xmit_data': int(parts[2])
                            }
                        }

                if metric:
                    metrics_batch.append(metric)

            # --- Send the entire batch of metrics from this sample at once ---
            if metrics_batch:
                self.influxdb_sender.send_metrics(metrics_batch)
                self.data_points_processed += len(metrics_batch)

        except Exception as e:
            self.logger.debug(f"Error processing data line '{line}': {e}")
