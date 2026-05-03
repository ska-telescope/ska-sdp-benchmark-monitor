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

After cloning the repository, **you must run the installer from inside the cloned repository** so it can locate the packaged dashboards via a relative path. A safe sequence is:

```bash
$ git clone <repo-url>
$ cd ska-sdp-benchmark-monitor
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install .
$ benchmon-install-grafana            # run from repository root
```

Installation directory selection (what the script actually does):

- No argument provided → defaults to `${HOME}/benchmon-stack`.
- Provide a path argument without a flag → uses that path, e.g. `benchmon-install-grafana /opt/benchmon-stack`.
- Provide `--install-dir <path>` → uses the supplied path, e.g. `benchmon-install-grafana --install-dir ~/bm-stack`.
- Any other `-`-prefixed option is rejected with an error.

Resulting layout when no `--install-dir` is given (default `${HOME}/benchmon-stack`):

- `${HOME}/benchmon-stack/grafana` – Grafana binaries, dashboards copied from `grafana/dashboards`, `conf/custom.ini`, plus created `data/` and `logs/` folders.
- `${HOME}/benchmon-stack/influxdb3` – InfluxDB3 binaries (ports configured at runtime by `benchmon-start-grafana`).

Resulting layout when `--install-dir /custom/path` (or positional `/custom/path`) is given:

- `/custom/path/grafana` – Same content as above, but rooted in your chosen directory.
- `/custom/path/influxdb3` – Same content as above.

Optional environment helpers (set if you pick a custom install dir and want to avoid retyping paths):

```bash
export BENCHMON_GRAFANA_PATH=/custom/path/grafana
export BENCHMON_INFLUXDB_PATH=/custom/path/influxdb3
```

Persist them in your shell profile if desired.

## Start Grafana and InfluxDB

> **Note:** If you installed the monitoring stack to a custom directory (using `--install-dir`), you need to define the `BENCHMON_GRAFANA_PATH` and `BENCHMON_INFLUXDB_PATH` environment variables pointing to the respective installation directories. You may also need to explicitly provide the `--dashboard-dir` argument if the automatic detection fails.

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

## End-to-End Example: Monitoring a Compute Workload

This walkthrough demonstrates the full lifecycle of monitoring a computationally intensive task.

**1. Prepare the Environment**

First, ensure the monitoring stack is running. 

```bash
# Start InfluxDB and Grafana in the background
benchmon-start-grafana --save-dir /tmp/benchmon-demo 

# or using default directory
benchmon-start-grafana
```

**2. Generate Load & Monitor**

We will use `benchmon-run` to start benchmarking monitoring. In this example, we'll simulate a CPU-intensive task using `stress-ng` (or a simple shell loop if `stress-ng` isn't available). We enabled both system monitoring (`--system`) and Grafana streaming (`--grafana`).

```bash
# Example: Monitor a 60-second CPU load
benchmon-run --system --grafana \
             --save-dir /tmp/benchmon-demo/run-stress-test
```

Open a new terminal, run stree-ng
```bash
stress-ng --cpu 4 --timeout 60s
# Note: If you don't have stress-ng, any command works:
# sleep 60
```
**3. Visualise in Real-time**

While the command above is running:

The user opens the browser on the node where benchmon-run is running
the user is accessing a server via ssh and then opening his browser on his own machine and an additional connection is need via ssh -L

1.  Open your browser to `http://<hostname>:3000`.
2.  Navigate to **Dashboards** > **System Monitoring**.
3.  You will see the **CPU Usage** graph spike corresponding to the load generated in step 2. High-frequency metrics like CPU frequency will also reflect the processor's boost behavior.

**4. Cleanup**

Once the run is complete, stop the background services to free up resources.

```bash
benchmon-stop-grafana --save-dir /tmp/benchmon-demo
```

## Stop the Stack

```bash
# Graceful stop
$ benchmon-stop-grafana --save-dir /tmp/benchmon-demo

# Manual fallback
$ pkill -F /tmp/benchmon-demo/grafana-data/pids.json
```

Logs remain under `/tmp/benchmon-demo/grafana-data/logs/`.


## Run Influxdb and Grafana Remotely (AWS)

#### Login into HEADNODE
```bash
srun -N 1 -n 1 -c 16 -p c7i-metal-24xl-noht-ond --pty bash

# Please record the IP address of the node
ifconfig 

# Change to venv
source <path/to/venv/bin/activate>

cd ska-sdp-benchmark-monitor/
pip uninstall ska-sdp-benchmark-monitor
pip install .

# Install Grafana and InfluxBD3 with deault value
benchmon-install-grafana

# Start InfluxDB and Grafana
benchmon-start-grafana

# Run Benchmark Monitoring (C++ version)
rt-monitor --sampling-frequency 5 --batch-size 10000  --cpu --grafana http://localhost:8181?db=metrics --log-level debug


# On the local notepad computer), forward SSH port
# Note: 10.192.34.110 is an example IP addrss retrived by `ifconfig` cmd
ssh -L 3000:10.192.34.110:3000 dp-hpc-headnode -N 

```

Open browser and visit: http://localhost:3000

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

## Create Standard PNG/SVG Benchmon Plots for Offline Access

Benchmon can run in offline mode (without `--grafana`) and record metrics to local CSV files. You can later import these CSV traces into InfluxDB and generate the standard benchmon PNG/SVG plots for offline access, archiving, and report sharing.

The importer utility is located at `benchmon/run/csv_importer.py`.

### Import Offline CSV Traces into InfluxDB

#### Basic Usage

If your trace directory includes `grafana-data/connection.json`, run:

```bash
python3 benchmon/run/csv_importer.py --dir /path/to/trace_folder/benchmon_traces_hostname
```

#### Manual Connection Settings

If `connection.json` is missing, or you want another InfluxDB target:

```bash
python3 benchmon/run/csv_importer.py \
  --dir /path/to/traces \
  --grafana-influxdb-url "http://localhost:8181" \
  --workers 8
```

#### CSV Importer Options

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--dir` | **(Required)** Path to folder containing CSV files such as `cpu_report.csv`. | - |
| `--grafana-influxdb-url`| InfluxDB URL v3. Overrides `connection.json`. | http://localhost:8181 |
| `--grafana-token` | InfluxDB token. Overrides `connection.json`. | (Empty) |
| `--database` | Target bucket/database name. | `metrics` |
| `--org` | InfluxDB organization (optional). | (Empty) |
| `--batch-size` | Number of points per write request. | 5000 |
| `--workers` | Number of concurrent write threads. | 4 |

### Generate Benchmon Figures from Imported Data

After CSV import, generate benchmon-style figures directly from InfluxDB:

Compared to the standard CSV-based `benchmon-visu` usage, where the positional argument is the trace directory, InfluxDB mode needs extra arguments so benchmon knows to query the database instead of reading local files. In practice, the extra required arguments are `--influxdb` and `--influxdb-url`, and you will typically also provide `--start-time` and `--end-time` to select the imported run window. `--influxdb-database` is additionally required when your database is not the default `metrics` bucket.

```bash
benchmon-visu ./benchmon_influx_figures \
  --influxdb \
  --influxdb-url http://localhost:8181 \
  --influxdb-database metrics \
  --start-time 2026-02-04T21:48:20 \
  --end-time 2026-02-04T22:03:20 \
  --sys \
  --recursive \
  --fig-fmt png \
  --fig-name benchmon_influx_overview
```

Notes:
- The positional argument is the output directory for generated figures and logs.
- If `--influxdb-hostname` is omitted, benchmon discovers all hostnames in the selected time range and generates one figure set per host.
- `--recursive` also creates `multi-node_sync.<fmt>` for synchronized multi-node view.
- `--resolution auto` chooses a coarser time bucket for long windows. You can force fixed resolution such as `--resolution 1m`.
- `--start-time` and `--end-time` use local wall-clock time in format `YYYY-MM-DDTHH:MM:SS`.
- InfluxDB visualization currently supports system plots only: `--cpu`, `--cpu-all`, `--cpu-freq`, `--mem`, `--net`, `--disk`, `--ib`, and `--sys`.

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
