"""Tests for the Grafana/InfluxDB collector."""

import logging
import queue
import threading

from benchmon.run.hp_collector import HighPerformanceCollector


class FakeClient:
    """Minimal client used to capture queued writes."""

    def __init__(self):
        self.writes = []

    def write(self, points):
        self.writes.append(points)


def test_consumer_drains_queue_after_stop_signal():
    """Pending queue items should still be written during shutdown."""
    collector = HighPerformanceCollector(
        logger=logging.getLogger("benchmon-test-hp"),
        config={"url": "http://localhost:8181", "token": "", "database": "metrics"},
        interval=1.0,
        batch_size=50,
    )
    client = FakeClient()
    q = queue.Queue()
    collector.stop_event.set()

    thread = threading.Thread(target=collector._consumer, args=(q, client, "cpu"))
    thread.start()

    payload = ["cpu_total,hostname=test user=1i 1"]
    q.put(payload)
    q.put(None)

    thread.join(timeout=5)

    assert not thread.is_alive()
    assert client.writes == [payload]
