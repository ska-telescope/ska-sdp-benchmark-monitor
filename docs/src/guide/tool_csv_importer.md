# CSV Importer Tool

## Overview

Benchmon allows you to run benchmarks in "offline mode" (without `--grafana` flag), where metrics are solely recorded to local CSV files. The **CSV Importer** (`csv_importer.py`) is a utility designed to ingest these offline traces into InfluxDB post-execution (or post-run re-ingestion), enabling visualization via Grafana.

This tool has been optimized for high performance, capable of handling large datasets (millions of points) by using a concurrent multi-threaded architecture.

## Location

The script is located at:
`benchmon/run/csv_importer.py`

## Features

*   **Batched Import**: Reads CSV files and groups data points into efficient batches.
*   **Auto-Configuration**: Automatically detects InfluxDB connection details from `connection.json` if available in the traces folder hierarchy.
*   **High Performance**: Uses a concurrent **Producer-Consumer** model:
    *   **Main Thread (Producer)**: High-speed streaming parser for `cpu`, `mem`, `net`, `disk`, `ib`, etc.
    *   **Worker Threads (Consumers)**: Parallel workers (configurable count) to write data to InfluxDB, maximizing network throughput.
*   **Backpressure Handling**: Prevents memory overflow by pausing parsing if the write queue is full.

## Usage

### 1. Basic Usage

If you have a standard Benchmon trace directory structure (with `grafana-data/connection.json` present), you typically only need to specify the directory and execute it as a module or script.

```bash
python3 benchmon/run/csv_importer.py --dir /path/to/trace_folder/benchmon_traces_hostname
```

### 2. Manual Connection Configuration

If `connection.json` is missing or you want to upload to a different server:

```bash
python3 benchmon/run/csv_importer.py \
    --dir /path/to/traces \
    --grafana-influxdb-url "http://localhost:8181" \
    --workers 8
```

### 3. Arguments Reference

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--dir` | **(Required)** Path to the folder containing `cpu_report.csv`, etc. | - |
| `--grafana-influxdb-url`| InfluxDB URL v3. Overrides `connection.json`. | http://localhost:8181 |
| `--grafana-token` | InfluxDB Token. Overrides `connection.json`. | (Empty) |
| `--database` | Target bucket/database name. | `metrics` |
| `--org` | InfluxDB Organization (optional). | (Empty) |
| `--batch-size` | Number of points per write request. | 5000 |
| `--workers` | Number of concurrent write threads. Increase for high bandwidth. | 4 |

## Architecture

To solve issues with slow imports on large datasets (10GB+ traces), the tool uses `threading` and `queue` in Python:

1.  **Parsing**: The main thread reads CSV files line-by-line using generators to keep memory footprint low (~Constant memory).
2.  **Buffering**: Parsed points are aggregated into lists of `batch-size`.
3.  **Queuing**: Batches are pushed to a thread-safe `queue.Queue`.
4.  **Writing**: `N` worker threads pull batches from the queue and send HTTP requests to InfluxDB in parallel.

This design ensures that network latency (waiting for InfluxDB response) does not block the file reading process, significantly accelerating the import speed.
