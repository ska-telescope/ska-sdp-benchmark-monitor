# SKA SDP Benchmark Monitor – InfluxDB + Grafana Integration

## Overview

Benchmon ships with a lightweight monitoring stack based on InfluxDB 3 and Grafana 12. Helper scripts in `exec/` install, configure, and launch both services, deploy dashboards, and keep runtime metadata so that benchmon can stream metrics in real time.

```
benchmon-run ──▶ InfluxDB 3 ──▶ Grafana ──▶ Dashboards
      │                │              │
      └── CSV traces   └── Time-series └── Visualization
```

## Components

- **`benchmon-install-grafana`** – Downloads Grafana `12.1.1` and InfluxDB3 `3.4.2`, prepares data/log directories, enables anonymous Grafana access, and copies packaged dashboards.
- **`benchmon-start-grafana`** – Launches `influxd run` and `grafana-server`, waits for readiness, configures the datasource, and deploys dashboards.
- **`benchmon-stop-grafana`** – Shuts down both services using stored PID files.
- **`benchmon-run`** – Collects metrics, streams them to InfluxDB (optional), and writes CSV artifacts.

## Requirements

- Python 3.9 or newer.
- HTTPS access to `dl.grafana.com` and `dl.influxdata.com` during installation.
- Disk space for the installation directory and trace outputs.

## Install the Monitoring Stack

```bash
$ benchmon-install-grafana --install-dir ~/benchmon-stack
```

Resulting layout:

- `~/benchmon-stack/grafana` – Grafana binaries, dashboards, `conf/custom.ini`.
- `~/benchmon-stack/influxdb3` – InfluxDB3 binaries, `admin_token.json`, data directory.

Optional environment helpers:

```bash
export BENCHMON_GRAFANA_PATH=~/benchmon-stack/grafana
export BENCHMON_INFLUXDB_PATH=~/benchmon-stack/influxdb3
```

Persist them in your shell profile if desired.

## Start Grafana and InfluxDB

```bash
$ benchmon-start-grafana \
  --save-dir /tmp/benchmon-demo \
  --influxdb-port 8181 \
  --grafana-port 3000
```
If a requested port is busy, the script automatically increments it until a free port is found and reports the chosen values.

The script:

1. Creates `/tmp/benchmon-demo/grafana-data/…` (logs, PIDs, connection info).
2. Starts InfluxDB with `influxd run …` and Grafana with `grafana-server …`.
3. Waits for Grafana readiness and configures the datasource targeting `http://<hostname>:8181`.
4. Deploys packaged dashboards.
5. Records metadata in `pids.json` and `connection.json`.

## Access Grafana

Open the printed URL, for example:

```
http://<hostname>:3000
```

Anonymous access is enabled. Administrator credentials use `admin / admin123`.

## Run Benchmon with Grafana Integration

```bash
# Recommended capture (CSV + Grafana)
benchmon-run --system --csv --grafana \
             --save-dir /tmp/benchmon-demo/run-001

# Grafana-only streaming
benchmon-run --system --grafana --no-csv

# Tuning the streaming pipeline
benchmon-run --system --grafana \
             --grafana-batch-size 10000 \
             --grafana-sample-interval 0.1
```

Metrics appear in InfluxDB immediately and dashboards refresh in real time.

## Stop the Stack

```bash
# Graceful stop
$ benchmon-stop-grafana --save-dir /tmp/benchmon-demo

# Manual fallback
$ pkill -F /tmp/benchmon-demo/grafana-data/pids.json
```

Logs remain under `/tmp/benchmon-demo/grafana-data/logs/`.

## Command Line Options

| Command | Key flags | Description |
|---------|-----------|-------------|
| `benchmon-install-grafana` | `--install-dir <path>` | Target installation directory (default `~/benchmon-stack`). |
| `benchmon-start-grafana` | `--save-dir <path>`<br>`--influxdb-port <port>`<br>`--grafana-port <port>`<br>`--dashboard-dir <path>` | Runtime directory for logs/PIDs, preferred InfluxDB port (auto-increments if occupied), preferred Grafana port (auto-increments if occupied), dashboard source override. |
| `benchmon-run` | `--save-dir <path>` | Output directory for run artifacts. |
| | `--system` / `--csv` | Enable system monitoring and CSV dumps. |
| | `--grafana` | Stream metrics to the Grafana/InfluxDB stack. |
| | `--no-csv` | Disable CSV generation. |
| | `--grafana-url <url>` | Custom Grafana/InfluxDB endpoint (default `http://localhost:3000`). |
| | `--grafana-token <token>` | Authentication token (blank by default). |
| | `--grafana-job-name <name>` | Logical job name attached to metrics (default `benchmon`). |
| | `--grafana-batch-size <int>` | Batch size for uploads (default `50`). |
| | `--grafana-sample-interval <seconds>` | Sampling interval for uploads (default `1.0`). |
| `benchmon-stop-grafana` | `--save-dir <path>` | Directory containing `pids.json` (must match start). |

## Dashboards

Packaged dashboards live in `<install-dir>/grafana/dashboards`. `benchmon-start-grafana` deploys every JSON file in that directory automatically, providing CPU, memory, network, disk, and InfiniBand (when available) views with real-time refresh.

## Troubleshooting

| Symptom | Resolution |
|---------|------------|
| Installer cannot download archives | Ensure internet access to Grafana/InfluxData and rerun. |
| `benchmon-start-grafana` cannot find binaries | Re-run the installer or export `BENCHMON_*` paths correctly. |
| Grafana dashboards missing | Verify `<install-dir>/grafana/dashboards`; reinstall if needed. |
| InfluxDB rejects writes | Confirm `admin_token.json` exists and port `8181` is free. |
| Grafana unreachable | Check port usage and inspect logs under `<save-dir>/grafana-data/logs/`. |

## References

- Dashboards: `<install-dir>/grafana/dashboards`
- Runtime helpers: `exec/benchmon-install-grafana`, `exec/benchmon-start-grafana`, `exec/benchmon-stop-grafana`
- Metric streaming: `benchmon/run/influxdb_sender.py`
- Official docs: [InfluxDB 3](https://docs.influxdata.com/), [Grafana](https://grafana.com/docs/)
- Metric streaming: `benchmon/run/influxdb_sender.py`
- Official docs: [InfluxDB 3](https://docs.influxdata.com/), [Grafana](https://grafana.com/docs/)
