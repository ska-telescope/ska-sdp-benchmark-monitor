# Benchmon Data Export to InfluxDB - Detailed Tutorial

## Overview

This tutorial provides a comprehensive guide on implementing high-performance data export to InfluxDB in the SKA SDP Benchmark Monitor. We will explore InfluxDB fundamentals, Benchmon's data processing architecture, and specific implementation methods for various system metrics.

## InfluxDB Fundamentals

### What is InfluxDB?

InfluxDB is an open-source time-series database specifically designed for handling large volumes of timestamped data. It features:

- **Time-series Optimization**: Storage engine designed specifically for timestamped data
- **High-performance Writes**: Support for massive concurrent write operations
- **SQL-like Queries**: Uses Flux query language for data retrieval
- **Automatic Data Compression**: Efficient data storage and retrieval
- **Tag and Field Separation**: Flexible data model

### InfluxDB Core Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **Database** | Database (v1.x) / Bucket (v2.x) | `benchmon` |
| **Measurement** | Measurement name, similar to SQL table name | `cpu`, `memory`, `network` |
| **Tags** | Indexed labels for fast querying | `host=server1`, `core=cpu0` |
| **Fields** | Actual numeric data | `usage_percent=45.2` |
| **Timestamp** | Timestamp | `1640995200` |

### Line Protocol Format

InfluxDB uses Line Protocol as the data write format:

```
measurement,tag1=value1,tag2=value2 field1=value1,field2=value2 timestamp
```

Example:
```
cpu,host=server1,core=cpu0 usage_percent=45.2,user_time=123.4 1640995200
```

## Benchmon InfluxDB Integration Architecture

### Overall Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Monitor Scripts│    │   HP Processor   │    │   InfluxDB      │
│   (*_hp.sh)     │────│  (hp_processor)  │────│   Write API     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  System Metrics │    │   Data Formatting│    │   Time-series   │
│   /proc/*       │    │   Line Protocol  │    │   Storage       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Data Flow

1. **Data Collection**: `*_hp.sh` scripts read raw data from system files
2. **Data Transmission**: Transfer to HP processor via Named Pipe
3. **Data Processing**: HP processor parses and formats to Line Protocol
4. **Batch Sending**: InfluxDBSender sends batches to InfluxDB
5. **Data Storage**: InfluxDB stores as time-series data

### High-Performance Features

| Feature | Description | Advantage |
|---------|-------------|-----------|
| **Named Pipes** | Inter-process communication, avoiding file I/O | Reduce disk operations, improve performance |
| **Batch Sending** | Aggregate multiple data points before sending | Reduce network requests, improve throughput |
| **Async Processing** | Background thread handles data sending | Non-blocking monitoring data collection |
| **Connection Reuse** | HTTP session reuse | Reduce connection overhead |

## 🔧 Monitoring Module Detailed Analysis

### 1. CPU Monitoring (cpu_mon_hp.sh)

#### Data Source
```bash
# Read /proc/stat file
cat /proc/stat | grep cpu
```

#### Data Format
```bash
# HP processor format
CPU|timestamp|cpu_core user nice system idle iowait irq softirq steal guest guestnice
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp=$1
    local cpu_core=$2
    local user=$3
    local nice=$4
    local system=$5
    local idle=$6
    local iowait=$7
    local irq=$8
    local softirq=$9
    local steal=${10}
    local guest=${11}
    local guestnice=${12}
    
    # Send to named pipe
    echo "CPU|$timestamp|$cpu_core $user $nice $system $idle $iowait $irq $softirq $steal $guest $guestnice" > "$influxdb_pipe"
}
```

#### Convert to InfluxDB Format
```python
def _process_cpu_data(self, timestamp: float, data: str):
    """Process CPU data"""
    parts = data.strip().split()
    cpu_core = parts[0]
    stats = {
        'user': int(parts[1]),
        'nice': int(parts[2]),
        'system': int(parts[3]),
        'idle': int(parts[4]),
        'iowait': int(parts[5]),
        'irq': int(parts[6]),
        'softirq': int(parts[7]),
        'steal': int(parts[8]) if len(parts) > 8 else 0
    }
    
    # Generate Line Protocol
    # cpu,host=hostname,core=cpu0 user=123,nice=456,system=789 timestamp
    self.hook.on_cpu_data(timestamp, cpu_core, stats)
```

#### Generated InfluxDB Data
```
cpu,host=server1,core=cpu0 user=1234,nice=0,system=567,idle=8901,iowait=23,irq=0,softirq=45 1640995200
cpu,host=server1,core=cpu1 user=1123,nice=0,system=623,idle=8654,iowait=34,irq=1,softirq=56 1640995200
```

### 2. Memory Monitoring (mem_mon_hp.sh)

#### Data Source
```bash
# Read /proc/meminfo file
grep "^MemTotal:\|^MemFree:\|^MemAvailable:" /proc/meminfo
```

#### Data Format
```bash
# HP processor format
MEMORY|timestamp|value1,value2,value3,...
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp=$1
    local meminfo_values=""
    local memory_fields=("MemTotal" "MemFree" "MemAvailable" "Buffers" "Cached")
    
    for field in "${memory_fields[@]}"; do
        local value=$(grep "^${field}:" /proc/meminfo | awk '{print $2}')
        if [[ -n "$meminfo_values" ]]; then
            meminfo_values="${meminfo_values},${value}"
        else
            meminfo_values="$value"
        fi
    done
    
    echo "MEMORY|$timestamp|$meminfo_values" > "$influxdb_pipe"
}
```

#### Generated InfluxDB Data
```
memory,host=server1 total=16777216,free=8388608,available=12345678,buffers=1234567,cached=2345678 1640995200
```

### 3. Network Monitoring (net_mon_hp.sh)

#### Data Source
```bash
# Read /proc/net/dev file
cat /proc/net/dev
```

#### Data Format
```bash
# HP processor format
NETWORK|timestamp|interface rx_bytes rx_packets ... tx_bytes tx_packets ...
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp=$1
    local interface=$2
    local rx_bytes=$3
    local rx_packets=$4
    local tx_bytes=$11
    local tx_packets=$12
    # ... other parameters
    
    echo "NETWORK|$timestamp|$interface $rx_bytes $rx_packets $rx_errs $rx_drop $rx_fifo $rx_frame $rx_compressed $rx_multicast $tx_bytes $tx_packets $tx_errs $tx_drop $tx_fifo $tx_colls $tx_carrier $tx_compressed" > "$influxdb_pipe"
}
```

#### Generated InfluxDB Data
```
network,host=server1,interface=eth0 rx_bytes=1048576,rx_packets=1024,tx_bytes=2097152,tx_packets=2048 1640995200
network,host=server1,interface=lo rx_bytes=12345,rx_packets=123,tx_bytes=12345,tx_packets=123 1640995200
```

### 4. Disk Monitoring (disk_mon_hp.sh)

#### Data Source
```bash
# Read /proc/diskstats file
cat /proc/diskstats
```

#### Data Format
```bash
# HP processor format (following /proc/diskstats format)
DISK|timestamp|major minor device rd_cd rd_md sect_rd time_rd wr_cd wr_md sect_wr time_wr io_ip time_io time_wei_io
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp=$1
    local major=$2
    local minor=$3
    local device=$4
    # ... other disk statistics parameters
    
    echo "DISK|$timestamp|$major $minor $device $rd_cd $rd_md $sect_rd $time_rd $wr_cd $wr_md $sect_wr $time_wr $io_ip $time_io $time_wei_io" > "$influxdb_pipe"
}
```

#### Generated InfluxDB Data
```
disk,host=server1,device=sda reads_completed=1234,reads_merged=56,sectors_read=123456,time_reading=789,writes_completed=567,writes_merged=23,sectors_written=67890,time_writing=345 1640995200
```

### 5. CPU Frequency Monitoring (cpufreq_mon_hp.sh)

#### Data Source
```bash
# Read CPU frequency files
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
```

#### Data Format
```bash
# HP processor format
CPUFREQ|timestamp|cpu_core frequency
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp=$1
    local cpu_core=$2
    local frequency=$3
    
    echo "CPUFREQ|$timestamp|$cpu_core $frequency" > "$influxdb_pipe"
}
```

#### Generated InfluxDB Data
```
cpufreq,host=server1,core=cpu0 frequency=2400000 1640995200
cpufreq,host=server1,core=cpu1 frequency=2350000 1640995200
```

### 6. InfiniBand Monitoring (ib_mon_hp.sh)

#### Data Source
```bash
# Read InfiniBand counters
cat /sys/class/infiniband/*/ports/1/counters/*
```

#### Data Format
```bash
# Direct Line Protocol format
infiniband_stats,host=hostname,interface=interface,port=port,metric=metric_key value=metric_value timestamp_ns
```

#### Implementation Example
```bash
send_to_influxdb() {
    local timestamp_ns=$1
    local interface=$2
    local port=$3
    local metric_key=$4
    local metric_value=$5
    local hostname=$(hostname)
    
    # Convert timestamp to nanoseconds
    if [[ $timestamp_ns == *.* ]]; then
        timestamp_ns=$(echo "$timestamp_ns * 1000000000" | bc | cut -d. -f1)
    else
        timestamp_ns="${timestamp_ns}000000000"
    fi
    
    echo "infiniband_stats,host=$hostname,interface=$interface,port=$port,metric=$metric_key value=$metric_value $timestamp_ns" > "$influxdb_pipe"
}
```

#### Generated InfluxDB Data
```
infiniband_stats,host=server1,interface=mlx5_0,port=1,metric=port_rcv_data value=1234567890 1640995200000000000
infiniband_stats,host=server1,interface=mlx5_0,port=1,metric=port_xmit_data value=9876543210 1640995200000000000
```

## HP Processor (hp_processor.py) Detailed Analysis

### Core Functions

The HP processor is the core component of Benchmon's high-performance data processing, responsible for:

1. **Named Pipe Reading**: Receive data from `*_hp.sh` scripts
2. **Data Parsing**: Parse different types of monitoring data
3. **Format Conversion**: Convert to InfluxDB Line Protocol format
4. **Batch Sending**: Send to database via InfluxDBSender

### Data Processing Flow

```python
def _process_data_line(self, line: str):
    """Process data line"""
    try:
        # Parse data format: TYPE|timestamp|data
        parts = line.strip().split('|', 2)
        if len(parts) != 3:
            return
            
        data_type, timestamp_str, data = parts
        timestamp = float(timestamp_str)
        
        # Dispatch processing based on data type
        if data_type == 'CPU':
            self._process_cpu_data(timestamp, data)
        elif data_type == 'CPUFREQ':
            self._process_cpufreq_data(timestamp, data)
        elif data_type == 'MEMORY':
            self._process_memory_data(timestamp, data)
        elif data_type == 'NETWORK':
            self._process_network_data(timestamp, data)
        elif data_type == 'DISK':
            self._process_disk_data(timestamp, data)
            
        self.data_points_processed += 1
        
    except Exception as e:
        self.logger.debug(f"Error processing data line '{line}': {e}")
```

### Performance Features

- **Non-blocking I/O**: Use `select` for non-blocking pipe reading
- **Batch Processing**: Aggregate data before batch sending
- **Error Recovery**: Single data point errors don't affect overall processing
- **Performance Statistics**: Real-time processing rate statistics

## InfluxDB Sender (influxdb_sender.py) Detailed Analysis

### Core Functions

InfluxDBSender is responsible for efficiently sending processed data to InfluxDB:

```python
class InfluxDBSender:
    """Send metrics data to InfluxDB in real-time"""
    
    def __init__(self, logger: logging.Logger, config: Dict[str, Any]):
        self.logger = logger
        self.config = config
        
        # Configuration parameters
        self.influxdb_url = config.get('url', 'http://localhost:8086')
        self.organization = config.get('organization', 'benchmon')
        self.bucket = config.get('bucket', 'metrics')
        self.token = config.get('token', 'admin123')
        
        # Performance settings
        self.batch_size = config.get('batch_size', 50)
        self.send_interval = config.get('send_interval', 2.0)
        
        # HTTP session reuse
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.token}',
            'Content-Type': 'text/plain; charset=utf-8'
        })
```

### Batch Sending Mechanism

```python
def _sender_loop(self):
    """Main sending loop"""
    batch = []
    last_send_time = time.time()
    
    while self.is_running:
        try:
            # Get data point
            metric = self.data_queue.get(timeout=0.1)
            batch.append(metric)
            
            # Check sending conditions
            current_time = time.time()
            should_send = (
                len(batch) >= self.batch_size or 
                (current_time - last_send_time) >= self.send_interval
            )
            
            if should_send and batch:
                self._send_batch(batch)
                batch.clear()
                last_send_time = current_time
                
        except queue.Empty:
            # Timeout sending
            if batch and (time.time() - last_send_time) >= self.send_interval:
                self._send_batch(batch)
                batch.clear()
                last_send_time = time.time()
```

### Sending Optimizations

| Optimization Strategy | Description | Configuration Parameter |
|----------------------|-------------|------------------------|
| **Batch Size** | Aggregate multiple data points before sending | `batch_size=50` |
| **Send Interval** | Maximum sending interval time | `send_interval=2.0` |
| **Connection Reuse** | HTTP session reuse | Automatic |
| **Retry Mechanism** | Exponential backoff retry after failure | Automatic |

## 🔍 Data Query and Retrieval

### Basic Queries

#### 1. Query CPU Usage
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> filter(fn: (r) => r["core"] == "cpu0")
```

#### 2. Query Memory Usage
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "memory")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
```

#### 3. Query Network I/O
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "network")
  |> filter(fn: (r) => r["interface"] == "eth0")
  |> filter(fn: (r) => r["_field"] =~ /^(rx_bytes|tx_bytes)$/)
```

### Advanced Queries

#### 1. Aggregation Query (per-minute average)
```flux
from(bucket: "metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

#### 2. Multi-host Comparison
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "memory")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> group(columns: ["host"])
```

#### 3. Disk IOPS Calculation
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "disk")
  |> filter(fn: (r) => r["_field"] =~ /^(reads_completed|writes_completed)$/)
  |> derivative(unit: 1s, nonNegative: true)
```

### REST API Queries

#### Using curl for queries
```bash
# Query CPU data from the last 5 minutes
curl -H "Authorization: Token admin123" \
     "http://localhost:8086/api/v2/query?org=benchmon" \
     -d 'from(bucket:"metrics")|>range(start:-5m)|>filter(fn:(r)=>r["_measurement"]=="cpu")|>limit(n:10)'
```

#### Using Python for queries
```python
import requests

def query_influxdb(query):
    headers = {'Authorization': 'Token admin123'}
    data = {'query': query, 'org': 'benchmon'}
    response = requests.post('http://localhost:8086/api/v2/query', 
                           headers=headers, data=data)
    return response.text

# Query example
cpu_query = '''
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
'''

result = query_influxdb(cpu_query)
print(result)
```

## Performance Optimization Recommendations

### 1. Collection Frequency Optimization

```bash
# High-frequency collection (suitable for real-time monitoring)
benchmon-run --system --grafana --interval 0.5 --grafana-send-interval 1.0 --grafana-batch-size 100

# Low-frequency collection (suitable for long-term trends)
benchmon-run --system --grafana --interval 10.0 --grafana-send-interval 30.0 --grafana-batch-size 50
```

### 2. Batch Size Tuning

| Scenario | Batch Size | Send Interval | Use Case |
|----------|------------|---------------|----------|
| **Real-time Monitoring** | 10-20 | 1.0s | Low latency required |
| **Standard Monitoring** | 50-100 | 2.0s | Balance performance and latency |
| **Batch Processing** | 200-500 | 5.0s | Maximum throughput |

### 3. Network Optimization

```python
# InfluxDB sender configuration
config = {
    'batch_size': 100,          # Reduce network requests
    'send_interval': 2.0,       # Balance latency and throughput
    'connection_timeout': 30,   # Connection timeout
    'read_timeout': 60          # Read timeout
}
```

## Troubleshooting

### 1. Data Not Reaching InfluxDB

**Check Named Pipe**:
```bash
# Check if pipe is created
ls -la /tmp/benchmon_data_pipe

# Check pipe data flow
tail -f /tmp/benchmon_data_pipe
```

**Check HP Processor**:
```bash
# View processor logs
grep "hp_processor" /var/log/benchmon.log

# Check processing statistics
grep "data points" /var/log/benchmon.log
```

### 2. InfluxDB Connection Issues

**Test Connection**:
```bash
# Test InfluxDB health status
curl http://localhost:8086/health

# Test authentication
curl -H "Authorization: Token admin123" \
     http://localhost:8086/api/v2/buckets
```

**Check Sender Status**:
```bash
# View sender logs
grep "InfluxDBSender" /var/log/benchmon.log

# Check error messages
grep "ERROR.*influx" /var/log/benchmon.log
```

### 3. Performance Issue Diagnosis

**Monitor Resource Usage**:
```bash
# View benchmon process resource usage
ps aux | grep benchmon

# View pipe buffer
lsof | grep benchmon_data_pipe

# View network connections
netstat -an | grep 8086
```

**Tuning Recommendations**:
- Increase batch size to reduce network overhead
- Increase send interval to reduce CPU usage
- Use SSD storage to improve I/O performance
- Optimize network configuration to reduce latency

## Monitoring Metrics Summary

### Supported Measurement Types

| Measurement Type | Tags | Fields | Update Frequency |
|------------------|------|--------|------------------|
| **cpu** | host, core | user, nice, system, idle, iowait, irq, softirq, steal | 1Hz |
| **cpufreq** | host, core | frequency | 1Hz |
| **memory** | host | total, free, available, buffers, cached, usage_percent | 1Hz |
| **network** | host, interface | rx_bytes, rx_packets, tx_bytes, tx_packets, rx_errors, tx_errors | 1Hz |
| **disk** | host, device | reads_completed, writes_completed, sectors_read, sectors_written | 1Hz |
| **infiniband** | host, interface, port, metric | value | 1Hz |

### Data Retention Policy

Recommended InfluxDB data retention policies:

```flux
// High-precision data retention for 7 days
option task = {name: "retention-7d", every: 1d}

from(bucket: "metrics")
  |> range(start: -7d)
  |> aggregateWindow(every: 1h, fn: mean)
  |> to(bucket: "metrics-hourly")

// Hourly data retention for 30 days  
// Daily data retention for 1 year
```

---

## Summary

Through this tutorial, you should now have mastered:

1. **InfluxDB Fundamentals**: Understanding core concepts of time-series databases
2. **Data Collection Mechanisms**: Understanding various system metric collection methods
3. **High-Performance Processing**: Mastering optimization techniques like named pipes and batch sending
4. **Data Querying**: Learning to use Flux language for data retrieval
5. **Performance Optimization**: Understanding various tuning strategies and best practices

Benchmon's InfluxDB integration provides a high-performance, scalable monitoring solution that can meet various needs from real-time monitoring to large-scale data analysis.
