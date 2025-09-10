## 0.2.0 - 2025-08-08
### Added
- InfluxDB integration for real-time monitoring
- High-performance monitoring scripts (_hp versions) for direct InfluxDB output
- Grafana dashboard support with 6 panels (CPU Usage, CPU Frequency, Memory Usage, Network I/O, Disk I/O, InfiniBand)
- New command line options: --grafana, --grafana-url, --grafana-job-name, --grafana-batch-size, --grafana-send-interval
- CSV output control with --csv/--no-csv parameters

### Enhanced
- Extended monitoring to include CPU frequency, disk I/O, network I/O, and InfiniBand metrics
- Improved Grid5000 power monitoring with hostname validation
- Updated test suite to support new parameters

### Fixed
- Dashboard queries to match actual measurement names and field structures
- Grid5000 power download to skip gracefully on non-Grid5000 nodes
- Test parameter compatibility for CI/CD pipeline

## 0.1.0 - 2025-05-30
Initial release