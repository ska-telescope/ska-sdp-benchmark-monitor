"""
InfluxDB sender that provides a method to send metrics via HTTP.
It uses a background thread for asynchronous, batched sending.
This version can handle complex nested 'fields' dictionaries.
"""

import logging
import sys
import os
import time
import requests
import threading
import queue
from typing import List, Dict, Any

class InfluxDBSender:
    """
    A threaded service that sends metrics to InfluxDB via the HTTP API.
    It is designed to be called by another process like hp_processor.
    """

    def __init__(self, logger: logging.Logger, config: dict):
        self.logger = logger

        # Be flexible with configuration keys
        url = config.get("url") or config.get("grafana_url")
        token = config.get("token") or config.get("grafana_token")
        org = config.get("org", "ska-sdp")
        bucket = config.get("bucket", "benchmon")

        if not all([url, token]):
            self.logger.error("InfluxDB config is missing 'url'/'grafana_url' or 'token'/'grafana_token'.")
            sys.exit(1)

        self.write_url = f"{url.rstrip('/')}/api/v2/write?org={org}&bucket={bucket}&precision=ns"
        self.headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "application/json",
        }

        self.batch_size = config.get("batch_size", 5000)
        self.send_interval = config.get("send_interval", 1.0)
        self.session = requests.Session()

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
        self.logger.info(f"Will send to InfluxDB at: {self.write_url}")

    def stop(self):
        """Stops the sender's background thread."""
        if not self.is_running:
            return
        self.is_running = False
        if self.sender_thread:
            self.sender_thread.join(timeout=5)
        self.logger.info("InfluxDB sender stopped.")

    def send_metrics(self, metrics: List[Dict[str, Any]]):
        """
        Public method for other components to queue metrics for sending.
        """
        for metric in metrics:
            try:
                self.data_queue.put(metric, block=False)
            except queue.Full:
                self.logger.warning("InfluxDB sender queue is full, dropping metric.")

    def _sender_loop(self):
        """Continuously takes data from the queue and sends it in batches."""
        batch = []
        last_send_time = time.time()

        while self.is_running or not self.data_queue.empty():
            try:
                metric = self.data_queue.get(timeout=0.1)
                batch.append(metric)
                self.data_queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            batch_full = len(batch) >= self.batch_size
            time_expired = (now - last_send_time) >= self.send_interval

            if batch and (batch_full or time_expired or not self.is_running):
                self._send_batch(batch)
                batch = []
                last_send_time = now

        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Converts a batch of metric dicts from hp_processor to line protocol and sends it."""
        if not batch:
            return
        
        lines = []
        for metric in batch:
            try:
                mname = metric.get('measurement') or metric.get('metric_name')
                if not mname:
                    self.logger.warning(f"Metric missing 'measurement' or 'metric_name': {metric}")
                    continue
                
                mname = mname.replace(',', '\\,').replace(' ', '\\ ')

                ts_str = metric.get('timestamp')
                
                # Handle tags, excluding special keys and the 'fields' dict
                tags = {k: v for k, v in metric.items() if k not in ['measurement', 'metric_name', 'value', 'timestamp', 'fields']}
                tag_parts = []
                for k, v in tags.items():
                    if v is not None and v != '':
                        key_esc = str(k).replace(',', '\\,').replace('=', '\\=').replace(' ', '\\ ')
                        val_esc = str(v).replace(',', '\\,').replace('=', '\\=').replace(' ', '\\ ')
                        tag_parts.append(f"{key_esc}={val_esc}")
                tag_str = ','.join(tag_parts)

                # Handle fields, merging 'value' and the 'fields' dictionary
                all_fields = {}
                if 'value' in metric and metric['value'] is not None:
                    all_fields['value'] = metric['value']
                if 'fields' in metric and isinstance(metric['fields'], dict):
                    all_fields.update(metric['fields'])

                if not all_fields:
                    continue

                field_parts = []
                for k, v in all_fields.items():
                    if isinstance(v, str):
                        v_esc = v.replace('\\', '\\\\').replace('"', '\\"')
                        field_parts.append(f'{k}="{v_esc}"')
                    elif isinstance(v, (int, float)):
                        field_parts.append(f'{k}={v}i') # Add 'i' to ensure integer type
                    elif isinstance(v, bool):
                        field_parts.append(f'{k}={"true" if v else "false"}')
                field_str = ','.join(field_parts)

                if not field_str:
                    continue

                ts_final_str = ""
                if ts_str:
                    try:
                        ts_final_str = f" {int(float(ts_str) * 1_000_000_000)}"
                    except (ValueError, TypeError):
                        pass

                if tag_str:
                    lines.append(f"{mname},{tag_str} {field_str}{ts_final_str}")
                else:
                    lines.append(f"{mname} {field_str}{ts_final_str}")

            except Exception as e:
                self.logger.warning(f"Failed to format metric to line protocol: {metric}, error: {e}")

        if not lines:
            return

        data = "\n".join(lines)
        try:
            response = self.session.post(self.write_url, headers=self.headers, data=data.encode('utf-8'), timeout=10)
            if response.status_code >= 300:
                self.logger.error(
                    f"Failed to write to InfluxDB. Status: {response.status_code}, Response: {response.text}"
                )
            else:
                self.logger.debug(f"Successfully sent {len(lines)} lines to InfluxDB.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error sending data to InfluxDB: {e}")
