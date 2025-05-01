"""Module to test benchmon-run"""


def test_benchmon_run(monkeypatch):
    monkeypatch.setattr("sys.argv", ["benchmon-run", "--save_dir", "/tmp/benchmon_traces", "--sys"])
