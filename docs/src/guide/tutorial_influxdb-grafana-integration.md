# SKA SDP Benchmark Monitor - InfluxDB + Grafana Integration

## 🚀 Overview

This document describes the comprehensive InfluxDB + Grafana integration for the SKA SDP Benchmark Monitor. This modern solution provides real-time monitoring, automated deployment, and high-performance data collection with beautiful visualizations.

## 🏗️ Architecture

```
Benchmon → InfluxDB → Grafana → Dashboards
    ↓         ↓         ↓         ↓
CSV Files  Time-Series  REST API  Visualizations
          Database    Queries   & Alerts
```

### Key Components

- **InfluxDB 2.7**: Time-series database for storing metrics with batch processing
- **Grafana 10.x**: Advanced visualization and dashboarding platform  
- **InfluxDBSender**: High-performance Python module for direct data transmission
- **Line Protocol**: Native InfluxDB data format optimized for time-series data
- **Auto-deployment**: Automated dashboard deployment and management tools

## 📦 Installation & Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ with required packages
- Network access to ports 3000 (Grafana) and 8086 (InfluxDB)

### 1. Automated Installation

The complete Grafana + InfluxDB stack can be deployed automatically:

```bash
# Navigate to the grafana directory
cd grafana/

# Start the complete stack
docker compose -f docker-compose.influxdb.yml up -d

# Verify services are running
docker compose -f docker-compose.influxdb.yml ps
```

**Service Status Check:**
```bash
# Check InfluxDB health
curl http://localhost:8086/health

# Check Grafana health  
curl http://localhost:3000/api/health
```

### 2. Automated Dashboard Deployment

Deploy pre-configured dashboards using our deployment tool:

```bash
# Deploy all dashboards
python3 deploy_dashboard.py --deploy-all

# Deploy specific dashboard
python3 deploy_dashboard.py --deploy dashboards/benchmon-system-metrics.json

# List available dashboards
python3 deploy_dashboard.py --list

# Update existing dashboards
python3 deploy_dashboard.py --deploy-all --overwrite
```

### 3. Start Monitoring

```bash
# Full monitoring with Grafana integration (recommended)
benchmon-run --system --csv --grafana

# Grafana-only monitoring (no CSV files) 
benchmon-run --system --grafana --no-csv

# High-performance mode with custom settings
benchmon-run --system --grafana --grafana-batch-size 100 --grafana-send-interval 1.0
```

### 4. Access Services

- **Grafana Dashboard**: http://localhost:3000
  - Username: `admin`
  - Password: `admin123`
  - Pre-configured datasource: InfluxDB connection
  - Available dashboards: System Metrics (Unified/Separated views)
  
- **InfluxDB Management UI**: http://localhost:8086
  - Username: `admin`
  - Password: `admin123`
  - Organization: `benchmon`
  - Bucket: `metrics`
  - Token: `admin123` (for API access)

### 5. Verify Installation

```bash
# Check container status
docker compose -f grafana/docker-compose.influxdb.yml ps

# Test data flow
benchmon-run --system --grafana --duration 30  # Run for 30 seconds

# Verify data in InfluxDB
curl -H "Authorization: Token admin123" \
     "http://localhost:8086/api/v2/query?org=benchmon" \
     -d 'from(bucket:"metrics")|>range(start:-5m)|>limit(n:5)'
```

## 🔧 Configuration & Advanced Usage

### Command Line Options

```bash
benchmon-run [OPTIONS]

Grafana Integration Options:
  --grafana                Enable Grafana/InfluxDB integration
  --no-grafana            Disable Grafana integration (default)
  --grafana-url URL       InfluxDB URL (default: http://localhost:8086)
  --grafana-token TOKEN   InfluxDB token (default: admin123)
  --grafana-org ORG       InfluxDB organization (default: benchmon)
  --grafana-bucket BUCKET InfluxDB bucket (default: metrics)
  --grafana-batch-size N  Batch size for data sending (default: 50)
  --grafana-send-interval S Send interval in seconds (default: 2.0)

CSV Output Options:
  --csv                   Enable CSV file output (default)
  --no-csv               Disable CSV file output

Performance Options:
  --duration SECONDS      Run for specified duration (useful for testing)
  --interval SECONDS      Data collection interval (default: 1.0)
```

### Dashboard Management Tool

The `deploy_dashboard.py` script provides comprehensive dashboard management:

```bash
# Available commands
python3 grafana/deploy_dashboard.py --help

# Deploy all dashboards in directory
python3 grafana/deploy_dashboard.py --deploy-all

# Deploy specific dashboard
python3 grafana/deploy_dashboard.py --deploy dashboards/benchmon-system-metrics.json

# List all dashboards in Grafana
python3 grafana/deploy_dashboard.py --list

# Delete dashboard
python3 grafana/deploy_dashboard.py --delete "Dashboard Name"

# Update dashboard (overwrite existing)
python3 grafana/deploy_dashboard.py --deploy dashboard.json --overwrite

# Custom Grafana connection
python3 grafana/deploy_dashboard.py --grafana-url http://remote:3000 \
                                   --username admin --password secret \
                                   --deploy-all
```

### Available Dashboards

Located in `grafana/dashboards/`:

1. **benchmon-system-metrics.json**: Complete system overview
2. **benchmon-system-metrics-unified.json**: Single-page unified view  
3. **benchmon-system-metrics-separated.json**: Multi-page detailed view

Each dashboard includes:
- Real-time CPU usage (per-core and aggregate)
- Memory utilization and availability
- Network I/O statistics per interface
- Disk I/O metrics per device
- InfiniBand statistics (when available)
- System load and process information

### Environment Variables

```bash
# InfluxDB Configuration
export INFLUXDB_URL="http://localhost:8086"
export INFLUXDB_TOKEN="admin123"
export INFLUXDB_ORG="benchmon"
export INFLUXDB_BUCKET="metrics"

# Performance Tuning
export INFLUXDB_BATCH_SIZE="50"
export INFLUXDB_SEND_INTERVAL="2.0"
```

## 📊 Metrics Format

### Line Protocol Format

Benchmon converts system metrics to InfluxDB line protocol:

```
cpu,host=hostname,core=0 usage_percent=45.2,user_time=123.4 1640995200
memory,host=hostname usage_percent=67.8,used_bytes=8589934592 1640995200
disk,host=hostname,device=sda read_bytes=1048576,write_bytes=2097152 1640995200
network,host=hostname,interface=eth0 rx_bytes=1024,tx_bytes=2048 1640995200
```

### Supported Metrics

- **CPU**: Usage percentage, user/system time, per-core metrics
- **Memory**: Usage percentage, available/used bytes, swap usage
- **Disk**: Read/write bytes, IOPS, per-device metrics
- **Network**: RX/TX bytes/packets, per-interface metrics
- **InfiniBand**: RX/TX bytes/packets (if available)

## 🎯 High-Performance Features

### Optimized Data Pipeline

The InfluxDB integration includes several performance optimizations:

- **Batch Processing**: Metrics are batched (default: 50 records) before transmission
- **Async I/O**: Non-blocking HTTP requests prevent monitoring delays
- **Memory Management**: Automatic buffer management prevents overflow
- **Error Resilience**: Automatic retry with exponential backoff
- **Efficient Protocols**: Native Line Protocol reduces parsing overhead

### Performance Tuning Examples

```bash
# High-frequency monitoring (every 0.5s, large batches)
benchmon-run --system --grafana \
             --grafana-send-interval 0.5 \
             --grafana-batch-size 100 \
             --interval 0.5

# Low-frequency monitoring (every 10s, small batches)
benchmon-run --system --grafana \
             --grafana-send-interval 10.0 \
             --grafana-batch-size 20 \
             --interval 5.0

# Memory-optimized mode (frequent small batches)
benchmon-run --system --grafana \
             --grafana-send-interval 1.0 \
             --grafana-batch-size 10

# Network-optimized mode (large infrequent batches)
benchmon-run --system --grafana \
             --grafana-send-interval 5.0 \
             --grafana-batch-size 200
```

### Multi-Node Deployment

For distributed monitoring across multiple nodes:

```bash
# Node 1 (InfluxDB + Grafana server)
cd grafana/
docker compose -f docker-compose.influxdb.yml up -d

# Node 2+ (monitoring clients)
benchmon-run --system --grafana \
             --grafana-url http://node1:8086 \
             --no-csv
```

## 📈 Grafana Dashboards

### Pre-configured Dashboard

The system includes a pre-configured dashboard with:

- CPU usage by core
- Memory usage and availability
- Network I/O by interface
- Disk I/O by device
- Real-time updates (5-second refresh)

### Custom Dashboards

Create custom dashboards using Flux queries:

```flux
// CPU usage over time
from(bucket: "metrics")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)

// Memory usage percentage
from(bucket: "metrics")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "memory")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

## 🐳 Docker Deployment & Infrastructure

### Automated Docker Setup

The `grafana/docker-compose.influxdb.yml` file provides a complete monitoring stack:

```yaml
version: '3.8'
services:
  influxdb:
    image: influxdb:2.7
    container_name: influxdb
    restart: unless-stopped
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=admin123
      - DOCKER_INFLUXDB_INIT_ORG=benchmon
      - DOCKER_INFLUXDB_INIT_BUCKET=metrics
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=admin123
    ports:
      - "8086:8086"
    volumes:
      - influxdb_data:/var/lib/influxdb2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8086/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./provisioning:/etc/grafana/provisioning
      - ./dashboards:/var/lib/grafana/dashboards
    depends_on:
      influxdb:
        condition: service_healthy

volumes:
  influxdb_data:
  grafana_data:
```

### Stack Management Commands

```bash
# Start the complete stack
cd grafana/
docker compose -f docker-compose.influxdb.yml up -d

# Check service status
docker compose -f docker-compose.influxdb.yml ps

# View logs
docker compose -f docker-compose.influxdb.yml logs influxdb
docker compose -f docker-compose.influxdb.yml logs grafana

# Stop services
docker compose -f docker-compose.influxdb.yml down

# Clean restart (removes volumes)
docker compose -f docker-compose.influxdb.yml down -v
docker compose -f docker-compose.influxdb.yml up -d
```

### Container Health Monitoring

```bash
# Check container health
docker compose -f grafana/docker-compose.influxdb.yml ps

# Monitor real-time logs
docker compose -f grafana/docker-compose.influxdb.yml logs -f

# Restart specific service
docker compose -f grafana/docker-compose.influxdb.yml restart influxdb
docker compose -f grafana/docker-compose.influxdb.yml restart grafana
```

## 🔍 Troubleshooting & Debugging

### Quick Diagnostic Commands

```bash
# 1. Check all services are running
docker compose -f grafana/docker-compose.influxdb.yml ps

# 2. Test network connectivity
curl http://localhost:8086/health     # InfluxDB health
curl http://localhost:3000/api/health # Grafana health

# 3. Verify authentication
curl -H "Authorization: Token admin123" \
     http://localhost:8086/api/v2/buckets

# 4. Check recent data
curl -H "Authorization: Token admin123" \
     "http://localhost:8086/api/v2/query?org=benchmon" \
     -d 'from(bucket:"metrics")|>range(start:-5m)|>limit(n:5)'
```

### Common Issues & Solutions

#### 1. "Connection Refused" Errors

**Problem**: Cannot connect to InfluxDB/Grafana
```bash
# Diagnosis
docker compose -f grafana/docker-compose.influxdb.yml ps
docker compose -f grafana/docker-compose.influxdb.yml logs

# Solution
docker compose -f grafana/docker-compose.influxdb.yml restart
```

#### 2. "Authentication Failed" 

**Problem**: InfluxDB authentication issues
```bash
# Check token validity
curl -H "Authorization: Token admin123" \
     http://localhost:8086/api/v2/buckets

# Reset if needed
docker compose -f grafana/docker-compose.influxdb.yml down -v
docker compose -f grafana/docker-compose.influxdb.yml up -d
```

#### 3. "No Data in Grafana"

**Problem**: Dashboards show no data
```bash
# Test data writing
benchmon-run --system --grafana --duration 30

# Verify data exists in InfluxDB
curl -H "Authorization: Token admin123" \
     "http://localhost:8086/api/v2/query?org=benchmon" \
     -d 'from(bucket:"metrics")|>range(start:-1h)|>count()'

# Re-deploy dashboards
python3 grafana/deploy_dashboard.py --deploy-all --overwrite
```

#### 4. Dashboard Deployment Issues

**Problem**: Dashboard deployment fails
```bash
# Check Grafana connection
python3 grafana/deploy_dashboard.py --test-connection

# Deploy with debug mode
python3 grafana/deploy_dashboard.py --deploy-all --verbose

# Manual dashboard check
curl -u admin:admin123 http://localhost:3000/api/dashboards/home
```

### Debug Mode & Logging

```bash
# Enable debug logging
export BENCHMON_LOG_LEVEL=DEBUG

# Run with verbose output
benchmon-run --system --grafana --verbose

# Monitor container logs in real-time
docker compose -f grafana/docker-compose.influxdb.yml logs -f influxdb
docker compose -f grafana/docker-compose.influxdb.yml logs -f grafana

# Check specific log files
tail -f /var/log/benchmon/influxdb_sender.log
```

### Performance Troubleshooting

```bash
# Check InfluxDB performance
curl -H "Authorization: Token admin123" \
     http://localhost:8086/metrics

# Monitor batch processing
benchmon-run --system --grafana --grafana-batch-size 1  # Force frequent sends

# Test different batch sizes
benchmon-run --system --grafana --grafana-batch-size 10 --duration 60
benchmon-run --system --grafana --grafana-batch-size 100 --duration 60
```

## 🚀 Migration from Previous Versions

### From Prometheus to InfluxDB

| Feature | Prometheus (Old) | InfluxDB (New) |
|---------|------------------|----------------|
| Architecture | Push Gateway | Direct Push |
| Data Format | Prometheus Metrics | Line Protocol |
| Query Language | PromQL | Flux |
| Default Port | 9091 | 8086 |
| Authentication | None | Token-based |
| Dashboard Location | Mixed | `grafana/` directory |
| Deployment | Manual | Automated via Docker Compose |

### Migration Steps

1. **Backup existing data** (if needed)
2. **Stop old Prometheus stack**
   ```bash
   docker compose -f old-prometheus-compose.yml down
   ```

3. **Update to latest benchmon version**
   ```bash
   git pull origin main
   pip install -e .
   ```

4. **Deploy new InfluxDB stack**
   ```bash
   cd grafana/
   docker compose -f docker-compose.influxdb.yml up -d
   ```

5. **Deploy new dashboards**
   ```bash
   python3 deploy_dashboard.py --deploy-all
   ```

6. **Update monitoring commands**
   ```bash
   # Old command
   benchmon-run --system --grafana --grafana-url http://localhost:9091/metrics/job/

   # New command  
   benchmon-run --system --grafana --grafana-url http://localhost:8086
   ```

### File Structure Changes

The new integration organizes all Grafana-related files in the `grafana/` directory:

```
grafana/
├── deploy_dashboard.py              # Automated deployment tool
├── docker-compose.influxdb.yml     # Complete stack definition  
├── dashboards/                     # Pre-built dashboard JSON files
│   ├── benchmon-system-metrics.json
│   ├── benchmon-system-metrics-unified.json
│   └── benchmon-system-metrics-separated.json
└── provisioning/                   # Grafana auto-configuration
    ├── datasources/                # InfluxDB datasource config
    └── dashboards/                 # Dashboard provider config
```

## 📚 References & Additional Resources

### Official Documentation
- [InfluxDB 2.7 Documentation](https://docs.influxdata.com/influxdb/v2.7/)
- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Line Protocol Reference](https://docs.influxdata.com/influxdb/v2.7/reference/syntax/line-protocol/)
- [Flux Query Language](https://docs.influxdata.com/flux/v0.x/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

### Benchmon Integration Files
- **Main monitoring script**: `exec/benchmon-run`
- **InfluxDB sender**: `benchmon/run/influxdb_sender.py`  
- **Docker stack**: `grafana/docker-compose.influxdb.yml`
- **Dashboard tool**: `grafana/deploy_dashboard.py`
- **Pre-built dashboards**: `grafana/dashboards/`

### Performance Optimization Guides
- [InfluxDB Performance Tuning](https://docs.influxdata.com/influxdb/v2.7/optimize/)
- [Grafana Dashboard Performance](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Docker Performance Best Practices](https://docs.docker.com/config/containers/resource_constraints/)

### Community Resources
- [InfluxDB Community Forum](https://community.influxdata.com/)
- [Grafana Community Forum](https://community.grafana.com/)
- [Docker Community Forums](https://forums.docker.com/)

## 🤝 Contributing & Development

### Contributing Guidelines

Contributions to improve the InfluxDB integration are welcome! Please:

1. **Test thoroughly** with the provided test script
2. **Update documentation** for new features  
3. **Follow code style** and linting standards (flake8)
4. **Include performance analysis** for changes affecting data flow
5. **Test dashboard compatibility** with multiple Grafana versions

### Development Setup

```bash
# Clone and setup development environment
git clone <repository-url>
cd ska-sdp-benchmark-monitor

# Install in development mode
pip install -e .

# Run linting
flake8 grafana/deploy_dashboard.py
flake8 benchmon/run/influxdb_sender.py

# Test the integration
cd grafana/
docker compose -f docker-compose.influxdb.yml up -d
python3 deploy_dashboard.py --deploy-all
benchmon-run --system --grafana --duration 60
```

### Testing Changes

```bash
# Test dashboard deployment
python3 grafana/deploy_dashboard.py --test-connection
python3 grafana/deploy_dashboard.py --deploy-all --overwrite

# Test data pipeline
benchmon-run --system --grafana --duration 30 --grafana-batch-size 10

# Verify data in InfluxDB
curl -H "Authorization: Token admin123" \
     "http://localhost:8086/api/v2/query?org=benchmon" \
     -d 'from(bucket:"metrics")|>range(start:-5m)|>count()'
```

### Code Quality Standards

All contributions must pass:
- **flake8** linting (configured in `.flake8`)
- **Integration tests** with real InfluxDB/Grafana stack
- **Documentation updates** for user-facing changes
- **Performance validation** for data pipeline modifications
