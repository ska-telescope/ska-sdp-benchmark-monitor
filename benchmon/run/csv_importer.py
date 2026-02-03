import argparse
import csv
import json
import logging
import os
import time
from pathlib import Path

from influxdb_client_3 import InfluxDBClient3, WriteOptions, write_client_options

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Import Benchmon CSV traces into InfluxDB 3")
    parser.add_argument("--dir", required=True, help="Directory containing benchmon traces (CSV files)")
    
    # Matching benchmon-run argument style
    parser.add_argument(
        "--grafana-influxdb-url",
        default=None, # Will try to load from connection.json file if None
        help="InfluxDB URL. If not provided, tries to load from connection.json"
    )
    parser.add_argument(
        "--grafana-token",
        default=None,
        help="InfluxDB Token. If not provided, tries to load from connection.json"
    )
    
    # Extra args usually not present in benchmon-run but needed for Client3
    parser.add_argument("--org", default="", help="InfluxDB Org (optional)")
    parser.add_argument("--database", default="metrics", help="InfluxDB Database/Bucket (default: metrics)")
    
    parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for writing to InfluxDB")
    
    return parser.parse_args()

def load_connection_info(trace_dir):
    """
    Try to find grafana-data/connection.json in parent directories of the trace directory.
    Returns a dict with 'influxdb_url' and 'influxdb_token' if found.
    """
    current = Path(trace_dir).resolve()
    # Search up to 3 levels up
    for _ in range(3):
        candidate = current / "grafana-data" / "connection.json"
        if candidate.is_file():
            try:
                with open(candidate, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded connection info from {candidate}")
                    return data
            except Exception as e:
                logger.warning(f"Found connection.json at {candidate} but failed to read: {e}")
        
        if current.parent == current: # Reached root
            break
        current = current.parent
        
    return {}

def get_hostname_from_path(path):
    dirname = os.path.basename(os.path.normpath(path))
    if dirname.startswith("benchmon_traces_"):
        return dirname.replace("benchmon_traces_", "")
    return "unknown_host"

def to_nanos(timestamp_str):
    try:
        if not timestamp_str:
            return int(time.time() * 1e9)
        return int(float(timestamp_str) * 1e9)
    except ValueError:
        return int(time.time() * 1e9)



def process_cpu(filepath, hostname, timestamp_holder=None):
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        first_row = True
        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                
                # Capture first timestamp for variable generation later
                if first_row and timestamp_holder is not None and timestamp_holder.get('first_ts') is None:
                    timestamp_holder['first_ts'] = ts
                    first_row = False
                    
                cpu_core = row['cpu_core']
                
                tags = f"hostname={hostname}"
                if cpu_core != 'cpu':
                    tags += f",cpu={cpu_core}"
                    measurement = "cpu_core"
                else:
                    measurement = "cpu_total"
                
                fields = []
                # user,nice,system,idle,iowait,irq,softirq,steal,guest,guestnice
                # MAPPING: guestnice (CSV) -> guest_nice (LP) to match hp_collector.py
                for field in ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guestnice']:
                    if field in row and row[field]:
                        # Map guestnice to guest_nice
                        lp_key = field
                        if field == 'guestnice':
                            lp_key = 'guest_nice'
                            
                        fields.append(f"{lp_key}={row[field]}i")
                
                if fields:
                    yield f"{measurement},{tags} {','.join(fields)} {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in cpu_report: {e}")


def process_cpufreq(filepath, hostname):
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        freq_key = None
        if reader.fieldnames:
            for key in reader.fieldnames:
                if key.startswith('frequency'):
                    freq_key = key
                    break
        
        if not freq_key:
            logger.error("Could not find frequency column in cpufreq_report")
            return

        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                cpu_core = row['cpu_core']
                value = row[freq_key]
                
                yield f"cpu_freq,hostname={hostname},cpu={cpu_core} value={value}i {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in cpufreq_report: {e}")

def process_mem(filepath, hostname):
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                fields = []
                for k, v in row.items():
                    if k == 'timestamp':
                        continue
                    if v:
                        fields.append(f"{k.lower()}={v}i")
                
                if fields:
                    yield f"memory,hostname={hostname} {','.join(fields)} {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in mem_report: {e}")

def process_net(filepath, hostname):
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                iface = row['interface'].strip(':') # clean colon if present
                
                fields = []
                for k, v in row.items():
                    if k in ['timestamp', 'interface']:
                        continue
                    clean_key = k.replace('-', '_')
                    fields.append(f"{clean_key}={v}i")
                
                if fields:
                    yield f"network_stats,hostname={hostname},interface={iface} {','.join(fields)} {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in net_report: {e}")

def process_disk(filepath, hostname):
    header_found = False
    
    with open(filepath, 'r') as f:
        # Scan for header line efficiently
        while True:
            # Save position to rewind if this is the start of data/header
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            if line.startswith('timestamp'):
                f.seek(pos)
                header_found = True
                break
        
        if not header_found:
            logger.error("Could not find header in disk_report.csv")
            return

        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                device = row['device']
                
                s_read = row.get('sect-rd', '0')
                s_write = row.get('sect-wr', '0')
                
                yield f"disk_stats,hostname={hostname},device={device} sectors_read={s_read}i,sectors_written={s_write}i {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in disk_report: {e}")


def process_ib(filepath, hostname):
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = to_nanos(row['timestamp'])
                dev_port = row['ib-interf:port']
                # hp_collector uses just the device name (e.g., mlx5_0), not with :port
                # Try to clean it up to match if separated by colon
                if ':' in dev_port:
                    device = dev_port.split(':')[0]
                else:
                    device = dev_port
                    
                metric_key = row['metric-key'].replace('-', '_')
                metric_value = row['metric-value']
                
                yield f"infiniband,hostname={hostname},device={device} {metric_key}={metric_value}i {ts}"
            except Exception as e:
                logger.error(f"Error parsing line in ib_report: {e}")


def generate_variable(hostname, dir_path, timestamp_holder=None):
    first_timestamp = None
    
    # Try to use cached timestamp
    if timestamp_holder and timestamp_holder.get('first_ts'):
        first_timestamp = timestamp_holder['first_ts']
    
    # Fallback to reading file if not captured
    if first_timestamp is None:
        cpu_report = os.path.join(dir_path, 'cpu_report.csv')
        if os.path.exists(cpu_report):
            try:
                with open(cpu_report, 'r') as f:
                    reader = csv.DictReader(f)
                    row = next(reader)
                    first_timestamp = to_nanos(row['timestamp'])
            except Exception:
                pass
            
    if first_timestamp is None:
        first_timestamp = int(time.time() * 1e9)
        
    return f"variable,hostname={hostname} stamp={first_timestamp} {first_timestamp}"

def main():
    args = parse_args()
    
    conn_info = load_connection_info(args.dir)
    
    url = args.grafana_influxdb_url
    if url is None:
        url = conn_info.get("influxdb_url", "http://localhost:8181")
        
    token = args.grafana_token
    if token is None:
        token = conn_info.get("influxdb_token", "")
        
    logger.info(f"Using InfluxDB URL: {url}")
    logger.info(f"Using Database: {args.database}")
    
    hostname = get_hostname_from_path(args.dir)
    logger.info(f"Detected hostname: {hostname}")
    
    client = InfluxDBClient3(
        host=url,
        token=token,
        org=args.org,
        database=args.database,
        # Remove WriteOptions to enforce synchronous (blocking) writes.
        # This prevents the client internal queue from filling up and causing OOM or timestamps
        # when reading files much faster than network speed.
        # write_client_options=write_client_options(
        #     write_options=WriteOptions(batch_size=args.batch_size)
        # )
    )
    
    processors = {
        'cpu_report.csv': process_cpu,
        'cpufreq_report.csv': process_cpufreq,
        'mem_report.csv': process_mem,
        'net_report.csv': process_net,
        'disk_report.csv': process_disk,
        'ib_report.csv': process_ib
    }
    
    # Context object to share data between processors and main
    ctx = {'first_ts': None}
    
    # Write buffer
    batch_buffer = []
    total_written = 0

    def flush_buffer():
        nonlocal total_written
        if batch_buffer:
            try:
                # With synchronous client (no WriteOptions), this will block until written
                # providing backpressure.
                client.write(batch_buffer)
                total_written += len(batch_buffer)
                logger.info(f"Written batch. Total points: {total_written}")
            except Exception as e:
                logger.error(f"Failed to write batch: {e}")
            batch_buffer.clear()

    # Iterate through all processors and stream data
    for filename, func in processors.items():
        filepath = os.path.join(args.dir, filename)
        if os.path.exists(filepath):
            logger.info(f"Processing {filename}...")
            count = 0
            
            # Pass context to process_cpu
            if func == process_cpu:
                iterator = func(filepath, hostname, timestamp_holder=ctx)
            else:
                iterator = func(filepath, hostname)
                
            for point in iterator:
                batch_buffer.append(point)
                count += 1
                if len(batch_buffer) >= args.batch_size:
                    flush_buffer()
            logger.info(f"Finished {filename}: {count} points generated.")
        else:
            logger.warning(f"File {filename} not found in {args.dir}")

    # Add variable point
    variable_point = generate_variable(hostname, args.dir, timestamp_holder=ctx)
    batch_buffer.append(variable_point)
    
    # Flush remaining
    flush_buffer()
            
    client.close()
    logger.info("Import finished.")

if __name__ == "__main__":
    main()
