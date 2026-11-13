import argparse

import pytest

from benchmon.run import csv_importer


class FailingClient:
    def __init__(self, *args, **kwargs):
        pass

    def write(self, batch):
        raise RuntimeError("synthetic write failure")

    def close(self):
        pass


class RecordingClient:
    instances = []

    def __init__(self, *args, **kwargs):
        self.batches = []
        RecordingClient.instances.append(self)

    def write(self, batch):
        self.batches.append(list(batch))

    def close(self):
        pass


class SplitOnLargeBatchClient:
    instances = []

    def __init__(self, *args, **kwargs):
        self.threshold = kwargs.pop("threshold", 2)
        self.batches = []
        SplitOnLargeBatchClient.instances.append(self)

    def write(self, batch):
        if len(batch) > self.threshold:
            raise RuntimeError("request too large")
        self.batches.append(list(batch))

    def close(self):
        pass


def test_csv_importer_surfaces_write_failures(monkeypatch, tmp_path):
    trace_dir = tmp_path / "benchmon_traces_test-host"
    trace_dir.mkdir()
    (trace_dir / "cpu_report.csv").write_text(
        "timestamp,cpu_core,user,nice,system,idle,iowait,irq,softirq,steal,guest,guestnice\n"
        "1745860070.500401679,cpu,1,0,1,1,0,0,0,0,0,0\n"
    )

    args = argparse.Namespace(
        dir=str(trace_dir),
        grafana_influxdb_url="http://localhost:8181",
        grafana_token="",
        org="",
        database="metrics",
        batch_size=1,
        max_batch_bytes=8 * 1024 * 1024,
        workers=1,
    )

    monkeypatch.setattr(csv_importer, "parse_args", lambda: args)
    monkeypatch.setattr(csv_importer, "InfluxDBClient3", FailingClient)
    monkeypatch.setattr(csv_importer, "load_connection_info", lambda _: {})

    with pytest.raises(RuntimeError, match="write failures"):
        csv_importer.main()


def test_csv_importer_flushes_when_batch_bytes_exceeded(monkeypatch, tmp_path):
    RecordingClient.instances.clear()

    trace_dir = tmp_path / "benchmon_traces_test-host"
    trace_dir.mkdir()
    long_user = "1" * 40
    (trace_dir / "cpu_report.csv").write_text(
        "timestamp,cpu_core,user,nice,system,idle,iowait,irq,softirq,steal,guest,guestnice\n"
        f"1745860070.500401679,cpu,{long_user},0,1,1,0,0,0,0,0,0\n"
        f"1745860071.500401679,cpu,{long_user},0,1,1,0,0,0,0,0,0\n"
        f"1745860072.500401679,cpu,{long_user},0,1,1,0,0,0,0,0,0\n"
    )

    args = argparse.Namespace(
        dir=str(trace_dir),
        grafana_influxdb_url="http://localhost:8181",
        grafana_token="",
        org="",
        database="metrics",
        batch_size=100,
        max_batch_bytes=140,
        workers=1,
    )

    monkeypatch.setattr(csv_importer, "parse_args", lambda: args)
    monkeypatch.setattr(csv_importer, "InfluxDBClient3", RecordingClient)
    monkeypatch.setattr(csv_importer, "load_connection_info", lambda _: {})

    csv_importer.main()

    written_batches = []
    for client in RecordingClient.instances:
        written_batches.extend(client.batches)

    assert [len(batch) for batch in written_batches] == [1, 1, 1, 1]


def test_csv_importer_splits_oversized_batches_on_413(monkeypatch, tmp_path):
    SplitOnLargeBatchClient.instances.clear()

    trace_dir = tmp_path / "benchmon_traces_test-host"
    trace_dir.mkdir()
    (trace_dir / "cpu_report.csv").write_text(
        "timestamp,cpu_core,user,nice,system,idle,iowait,irq,softirq,steal,guest,guestnice\n"
        "1745860070.500401679,cpu,1,0,1,1,0,0,0,0,0,0\n"
        "1745860071.500401679,cpu,1,0,1,1,0,0,0,0,0,0\n"
        "1745860072.500401679,cpu,1,0,1,1,0,0,0,0,0,0\n"
        "1745860073.500401679,cpu,1,0,1,1,0,0,0,0,0,0\n"
    )

    args = argparse.Namespace(
        dir=str(trace_dir),
        grafana_influxdb_url="http://localhost:8181",
        grafana_token="",
        org="",
        database="metrics",
        batch_size=100,
        max_batch_bytes=8 * 1024 * 1024,
        workers=1,
    )

    monkeypatch.setattr(csv_importer, "parse_args", lambda: args)
    monkeypatch.setattr(
        csv_importer, "InfluxDBClient3", SplitOnLargeBatchClient
    )
    monkeypatch.setattr(csv_importer, "load_connection_info", lambda _: {})

    csv_importer.main()

    written_batches = []
    for client in SplitOnLargeBatchClient.instances:
        written_batches.extend(client.batches)

    assert sorted(len(batch) for batch in written_batches) == [1, 2, 2]


def test_process_disk_preserves_sector_size_for_partitions(tmp_path):
    report = tmp_path / "disk_report.csv"
    report.write_text(
        "2\n"
        "4\n"
        "sda,512,nvme0n1,4096\n"
        "timestamp,device,sect-rd,sect-wr\n"
        "1745860070.500401679,nvme0n1p1,8,16\n"
    )

    lines = list(csv_importer.process_disk(str(report), "test-host"))

    assert lines == [
        "disk_stats,hostname=test-host,device=nvme0n1p1 "
        "sectors_read=8i,sectors_written=16i,sector_size=4096i "
        "1745860070500401664"
    ]
