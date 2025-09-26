"""
InfluxDB sender that provides a method to send metrics via HTTP.
This version uses the influxdb3-python client to send data,
while preserving the existing queue and batching logic from the requests-based implementation.
"""

import logging
import sys
import time
import threading
import queue
from typing import List, Dict, Any
from datetime import datetime, timezone

from influxdb_client_3 import InfluxDBClient3, Point

class InfluxDBSender:
    """
    A threaded service that sends metrics to InfluxDB via the HTTP API,
    using the influxdb3-python client for synchronous writes within a background thread.
    """

    def __init__(self, logger: logging.Logger, config: dict):
        self.logger = logger
        self.config = config

        host = config.get("url") or config.get("grafana_url")
        token = config.get("token") or config.get("grafana_token")
        org = config.get("org", "benchmon")
        database = config.get("bucket", "benchmon")

        if not all([host, token, database]):
            self.logger.error("InfluxDB config is missing url, token, or bucket/database.")
            sys.exit(1)

        try:
            # Initialize the client without its own batching to avoid fork-related deadlocks.
            # We will use our own threading model.
            self.client = InfluxDBClient3(host=host, token=token, org=org, database=database)
            self.logger.info(f"InfluxDB3 client initialized for database '{database}'.")
        except Exception as e:
            self.logger.error(f"Failed to initialize InfluxDB3 client: {e}")
            sys.exit(1)

        self.batch_size = config.get("batch_size", 50)
        # 'send_interval' is no longer used and has been removed from the config.
        
        self.data_queue = queue.Queue()
        self.is_running = False
        self.sender_thread = None

    def start(self):
        """Starts the sender's background thread."""
        if self.is_running:
            return
        self.is_running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        self.logger.info("InfluxDB sender thread started.")

    def stop(self):
        """Stops the sender's background thread and flushes remaining data."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping InfluxDB sender...")
        self.is_running = False
        if self.sender_thread:
            # Wait for the loop to process remaining items
            self.sender_thread.join(timeout=self.send_interval + 2)
        
        self.client.close()
        self.logger.info("InfluxDB sender stopped.")

    def send_metrics(self, metrics: List[Dict[str, Any]]):
        """
        Public method for other components to queue metrics for sending.
        This now queues the entire batch as a single item.
        """
        if not metrics:
            return
        try:
            # --- CRITICAL FIX: Put the entire list into the queue as one item ---
            self.data_queue.put(metrics, block=False)
        except queue.Full:
            self.logger.warning("InfluxDB sender queue is full, dropping a batch of metrics.")

    def _sender_loop(self):
        """
        Continuously takes data from the queue and sends it when a batch is full.
        It no longer waits for a time interval, adhering to a "process as fast as possible" design.
        """
        batch = []

        while self.is_running or not self.data_queue.empty():
            try:
                # Get a list of metrics from the queue (sent by hp_processor)
                metrics_list = self.data_queue.get(timeout=0.1)
                batch.extend(metrics_list)
                self.data_queue.task_done()
            except queue.Empty:
                # This is normal when no new data is coming in.
                # If the loop is stopping and there's a partial batch, we'll send it after the loop.
                continue

            # Send the batch ONLY if it's full
            if len(batch) >= self.batch_size:
                self._send_batch(batch)
                batch = []
        
        # Final flush for any remaining items when the loop exits
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Converts a batch of metric dicts to Point objects and sends them."""
        points = []
        for metric in batch:
            try:
                measurement_name = metric.get('metric_name')
                if not measurement_name:
                    continue

                point = Point(measurement_name)

                tags = {k: v for k, v in metric.items() if k not in ['metric_name', 'value', 'timestamp', 'fields']}
                for k, v in tags.items():
                    if v is not None and v != '':
                        point.tag(k, str(v))

                all_fields = {}
                if 'value' in metric and metric['value'] is not None:
                    all_fields['value'] = metric['value']
                if 'fields' in metric and isinstance(metric['fields'], dict):
                    all_fields.update(metric['fields'])

                if not all_fields:
                    continue
                
                for k, v in all_fields.items():
                    point.field(k, v)
                
                if 'timestamp' in metric:
                    timestamp_str = str(metric['timestamp'])
                    # --- PRECISION FIX: Convert to ISO 8601 format string ---
                    # We process the timestamp as a string to preserve full nanosecond
                    # precision, as Python's standard datetime objects are limited
                    # to microseconds.
                    try:
                        if '.' in timestamp_str:
                            parts = timestamp_str.split('.', 1)
                            sec_part = parts[0]
                            nsec_part = parts[1]

                            # Ensure nanosecond part is exactly 9 digits
                            nsec_part = nsec_part.ljust(9, '0')[:9]

                            # Create datetime object from the seconds part
                            dt_object = datetime.fromtimestamp(int(sec_part), tz=timezone.utc)
                            
                            # Format to RFC3339 / ISO 8601 and append the nanosecond part
                            iso_ts = dt_object.strftime('%Y-%m-%dT%H:%M:%S') + f".{nsec_part}Z"
                        else:
                            # Handle case where timestamp has no fractional part
                            dt_object = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
                            iso_ts = dt_object.strftime('%Y-%m-%dT%H:%M:%S') + ".000000000Z"
                        
                        point.time(iso_ts)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")

                points.append(point)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to create Point from metric: {metric}, error: {e}")

        if not points:
            return

        try:
            # This `write` call is synchronous and sends the data immediately.
            # It runs inside our own background thread, not the main thread.
            self.client.write(record=points)
            self.logger.debug(f"Successfully sent {len(points)} points to InfluxDB.")
        except Exception as e:
            self.logger.error(f"Error sending data to InfluxDB: {e}")
            self.logger.debug(f"Successfully sent {len(points)} points to InfluxDB.")
        except Exception as e:
            self.logger.error(f"Error sending data to InfluxDB: {e}")
