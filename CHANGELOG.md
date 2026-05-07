## Unreleased

### Added
- `benchmon-setup` (including `benchmon-check`) for pre-run validation, environment checks, and hardware/software characterisation
- `benchmon-postprocess` for visualization, report generation, and HPCToolkit post-processing
- `--report-template` option in `benchmon-postprocess` for custom Markdown report templates
- Annotation support with `--annotate-with-log`, CSV parsing via `read_annotation_csv()`, and visualization via `plot_annotation_stages()`, including multi-node filtering from a shared `events.csv`

### Changed
- Refactored execution workflow: `benchmon-setup` → `benchmon-start` → `benchmon-stop` → `benchmon-postprocess`
- `--sys-freq` type changed from `int` to `float` to support sub-Hz sampling (e.g. 0.1 Hz = 1 sample/10s)
- Per-level system sampling frequency: 0.1 Hz (level 0), 1 Hz (level 1), 10 Hz (level 2)
- sys monitoring processes now terminated with SIGUSR1 instead of SIGTERM to align with `benchmon-stop` behaviour
- Introduced a 3-level argument priority system in `benchmon-setup`, `benchmon-start` and `benchmon-postprocess`:
  - (1) `BENCHMON_ARGS` env var (must be exported) — highest priority
  - (2) command line args
  - (3) defaults: `level=0`, `save-dir=./benchmon_savedir_JOBID`
  - Extra args in `BENCHMON_ARGS` are forwarded to `benchmon-run` only
  - `--report-template` in `benchmon-postprocess` is exclusively user-side

### Fixed
- Fixed report generation in `benchmon-postprocess`

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