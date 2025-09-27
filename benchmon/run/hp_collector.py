import logging
import os
import queue
import threading
import time
import glob

from influxdb_client_3 import InfluxDBClient3


class HighPerformanceCollector:
    """
    A high-performance, pure Python data collector for benchmon.
    It uses a fully parallel model where each metric type has its own
    producer, queue, consumer, and InfluxDB client.
    """

    def __init__(self, logger: logging.Logger, config: dict, interval: float):
        self.logger = logger
        self.config = config
        self.interval = interval
        self.hostname = os.uname()[1]

        self.metric_types = ['cpu', 'mem', 'cpufreq', 'net', 'disk', 'ib']
        # --- REFACTOR: Create dedicated resources for each metric type ---
        self.queues = {name: queue.Queue(maxsize=100) for name in self.metric_types}
        self.clients = {}
        self.producer_threads = {}
        self.consumer_threads = {}
        self.reporter_thread = None
        self.stop_event = threading.Event()

    def start(self):
        """Starts a producer and consumer thread for each metric type."""
        self.logger.info(f"HP Collector starting with a {self.interval:.2f}s interval.")

        producers = {
            'cpu': self._cpu_producer,
            'mem': self._mem_producer,
            'cpufreq': self._cpufreq_producer,
            'net': self._net_producer,
            'disk': self._disk_producer,
            'ib': self._ib_producer,
        }

        for name in self.metric_types:
            # Create a dedicated client for each consumer
            try:
                client = InfluxDBClient3(
                    host=self.config.get("url"),
                    token=self.config.get("token"),
                    org=self.config.get("org"),
                    database=self.config.get("database")
                )
                self.clients[name] = client
                self.logger.info(f"HP Collector: InfluxDB3 client for '{name}' initialized.")
            except Exception as e:
                self.logger.error(f"HP Collector: Failed to initialize client for '{name}': {e}")
                continue  # Skip this metric if client fails

            # Create and start producer thread
            p_thread = threading.Thread(target=producers[name], args=(self.queues[name],))
            self.producer_threads[name] = p_thread
            p_thread.start()

            # Create and start consumer thread
            c_thread = threading.Thread(target=self._consumer, args=(self.queues[name], self.clients[name], name))
            self.consumer_threads[name] = c_thread
            c_thread.start()

        # --- ADDITION: Start the queue size reporter thread ---
        self.reporter_thread = threading.Thread(target=self._report_queue_sizes, args=(10,))  # Report every 10 seconds
        self.reporter_thread.start()

    def stop(self):
        """Stops all threads gracefully."""
        self.logger.info("HP Collector stopping...")
        self.stop_event.set()

        for thread in self.producer_threads.values():
            thread.join()

        for q in self.queues.values():
            q.put(None)

        for thread in self.consumer_threads.values():
            thread.join()

        if self.reporter_thread:
            self.reporter_thread.join()

        for client in self.clients.values():
            client.close()

        self.logger.info("HP Collector stopped.")

    def _consumer(self, q: queue.Queue, client: InfluxDBClient3, name: str):
        """A dedicated consumer for a single queue, using its own client."""
        while not self.stop_event.is_set():
            try:
                points = q.get(timeout=1)
                if points is None:
                    break
                if points:
                    client.write(points)
                q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"HP Collector consumer error for '{name}': {e}")

    def _report_queue_sizes(self, interval: int):
        """Periodically reports the size of all internal queues."""
        while not self.stop_event.wait(interval):
            try:
                sizes = {name: q.qsize() for name, q in self.queues.items()}
                # Format the sizes into a readable string: "cpu: 0, mem: 0, ..."
                size_report = ", ".join([f"{name}: {size}" for name, size in sizes.items()])
                self.logger.info(f"HP Collector queue sizes: [{size_report}]")
            except Exception as e:
                self.logger.error(f"Queue reporter error: {e}")

    def _cpu_producer(self, q: queue.Queue):
        """Producer for CPU metrics from /proc/stat."""
        while not self.stop_event.wait(self.interval):
            try:
                with open("/proc/stat", "r") as f:
                    content = f.read()
                timestamp = int(time.time() * 1e9)
                points = []
                for line in content.splitlines():
                    if line.startswith('cpu'):
                        parts = line.split()
                        core_id = parts[0]

                        # --- FIX: Handle different number of fields for total vs core ---
                        if len(parts) >= 9:  # For cpu0, cpu1, etc.
                            tags = f"hostname={self.hostname}"
                            fields = (
                                f"user={parts[1]}i,nice={parts[2]}i,system={parts[3]}i,"
                                f"idle={parts[4]}i,iowait={parts[5]}i,irq={parts[6]}i,"
                                f"softirq={parts[7]}i,steal={parts[8]}i"
                            )
                            if len(parts) >= 11:  # With guest and guest_nice
                                fields += f",guest={parts[9]}i,guest_nice={parts[10]}i"

                            if core_id == 'cpu':
                                lp = f"cpu_total,{tags} {fields} {timestamp}"
                            else:
                                lp = f"cpu_core,{tags},cpu={core_id} {fields} {timestamp}"
                            points.append(lp)

                if points:
                    q.put(points)
            except Exception as e:
                self.logger.warning(f"CPU producer error: {e}")

    def _mem_producer(self, q: queue.Queue):
        """Producer for Memory metrics from /proc/meminfo."""
        mem_fields_of_interest = {"MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "Slab"}
        while not self.stop_event.wait(self.interval):
            try:
                with open("/proc/meminfo", "r") as f:
                    content = f.read()

                timestamp = int(time.time() * 1e9)
                fields = []
                for line in content.splitlines():
                    parts = line.split(':')
                    if len(parts) == 2 and parts[0] in mem_fields_of_interest:
                        key = parts[0].lower()
                        value = parts[1].strip().split()[0]
                        fields.append(f"{key}={value}i")

                if fields:
                    lp = f"memory,hostname={self.hostname} {','.join(fields)} {timestamp}"
                    q.put([lp])
            except Exception as e:
                self.logger.warning(f"Memory producer error: {e}")

    def _cpufreq_producer(self, q: queue.Queue):
        """Producer for CPU frequency metrics."""
        freq_files = glob.glob(
            "/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"
        )
        while not self.stop_event.wait(self.interval):
            try:
                timestamp = int(time.time() * 1e9)
                points = []
                for file_path in freq_files:
                    with open(file_path, 'r') as f:
                        freq = f.read().strip()

                    core_id = file_path.split('/')[4]
                    lp = f"cpu_freq,hostname={self.hostname},cpu={core_id} value={freq}i {timestamp}"
                    points.append(lp)

                if points:
                    q.put(points)
            except Exception as e:
                self.logger.warning(f"CPU Freq producer error: {e}")

    def _net_producer(self, q: queue.Queue):
        """Producer for Network metrics from /proc/net/dev."""
        while not self.stop_event.wait(self.interval):
            try:
                with open("/proc/net/dev", "r") as f:
                    content = f.readlines()[2:]   # Skip header lines

                timestamp = int(time.time() * 1e9)
                points = []
                for line in content:
                    parts = line.split()
                    iface = parts[0].strip(':')
                    rx_bytes = parts[1]
                    tx_bytes = parts[9]
                    lp = (
                        f"network_stats,hostname={self.hostname},interface={iface} "
                        f"rx_bytes={rx_bytes}i,tx_bytes={tx_bytes}i {timestamp}"
                    )
                    points.append(lp)

                if points:
                    q.put(points)
            except Exception as e:
                self.logger.warning(f"Network producer error: {e}")

    def _disk_producer(self, q: queue.Queue):
        """Producer for Disk metrics from /proc/diskstats."""
        while not self.stop_event.wait(self.interval):
            try:
                with open("/proc/diskstats", "r") as f:
                    content = f.readlines()

                timestamp = int(time.time() * 1e9)
                points = []
                for line in content:
                    parts = line.split()
                    device = parts[2]
                    # Filter for common disk types
                    if not (device.startswith('sd') or device.startswith('nvme')
                            or device.startswith('vd') or device.startswith('xvd')):
                        continue

                    sectors_read = parts[5]
                    sectors_written = parts[9]
                    lp = (
                        f"disk_stats,hostname={self.hostname},device={device} "
                        f"sectors_read={sectors_read}i,sectors_written={sectors_written}i {timestamp}"
                    )
                    points.append(lp)

                if points:
                    q.put(points)
            except Exception as e:
                self.logger.warning(f"Disk producer error: {e}")

    def _ib_producer(self, q: queue.Queue):
        """Producer for InfiniBand metrics."""
        ib_ports_glob = "/sys/class/infiniband/*/ports/*/counters/port_xmit_data"
        ib_ports = [p.split('/')[4] for p in glob.glob(ib_ports_glob)]
        ib_ports = list(set(ib_ports))

        while not self.stop_event.wait(self.interval):
            try:
                timestamp = int(time.time() * 1e9)
                points = []
                for port in ib_ports:
                    try:
                        with open(f"/sys/class/infiniband/{port}/ports/1/counters/port_xmit_data") as f:
                            xmit_data = f.read().strip()
                        with open(f"/sys/class/infiniband/{port}/ports/1/counters/port_rcv_data") as f:
                            rcv_data = f.read().strip()

                        lp = (
                            f"infiniband,hostname={self.hostname},device={port} "
                            f"port_rcv_data={rcv_data}i,port_xmit_data={xmit_data}i {timestamp}"
                        )
                        points.append(lp)
                    except FileNotFoundError:
                        continue

                if points:
                    q.put(points)
            except Exception as e:
                self.logger.warning(f"IB producer error: {e}")
