"""Tests for the Grafana/InfluxDB collector."""

import io
import logging
import queue
import threading
from unittest.mock import patch

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


def test_mem_producer_flushes_residual_batch_on_shutdown():
    """Low-volume producers should flush their final partial batch on shutdown."""
    collector = HighPerformanceCollector(
        logger=logging.getLogger("benchmon-test-hp"),
        config={"url": "http://localhost:8181", "token": "", "database": "metrics"},
        interval=1.0,
        batch_size=50,
    )

    class StopAfterOneCycle:
        def __init__(self):
            self.calls = 0

        def wait(self, interval):
            self.calls += 1
            return self.calls > 1

    q = queue.Queue()
    collector.stop_event = StopAfterOneCycle()
    meminfo = "\n".join([
        "MemTotal:       1000 kB",
        "MemFree:         500 kB",
        "MemAvailable:    700 kB",
        "Buffers:          10 kB",
        "Cached:           20 kB",
        "Slab:             30 kB",
    ])

    with patch("builtins.open", return_value=io.StringIO(meminfo)):
        collector._mem_producer(q)

    payload = q.get_nowait()
    assert len(payload) == 1
    assert payload[0].startswith("memory,hostname=")
