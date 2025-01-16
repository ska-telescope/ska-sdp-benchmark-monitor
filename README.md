# SDP Benchmark Monitor

This repository contains the benchmark monitor that is used in conjunction with the [benchmark tests repository](https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-tests)

In the `bin` directory there are three executable scripts. `benchmon-hardware.py` and `benchmon-software.py` gather hardware- and software context respectively.
The third script, `benchmon-run.py` is used to measure runs of the benchmarks and is designed to be ran alongside the benchmarks.

This is currently a work in progress and work will continue during PI-23.

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-sdp-benchmark-monitor/badge/?version=latest)](https://developer.skao.int/projects/ska-sdp-benchmark-monitor/en/latest/?badge=latest)

## Installation
###### _[Dool](https://github.com/scottchiefbaker/dool)_
```bash
https://github.com/scottchiefbaker/dool.git
cd dool
./install.py
```
This locally installs `dool`. The executable of `dool`, that will be used later, is located in `~/bin/dool`.
###### _Python dependencies_
Install the following Python packages within your Python environment
```bash
pip install upgrade psutil ping3 numpy matplotlib
```
### Download
- Git clone
```bash
git clone -b scoop-352 https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor.git
```
All scripts are available in `ska-sdp-benchmark-monitor/bin`.
- You may add `ska-sdp-benchmark-monitor/bin` to your path
```bash
cd ska-sdp-benchmark-monitor/bin
export PATH=$PATH/$PWD
```
## Monitoring mode
This mode allows background monitoring of resource usage and recording of energy consumption. This includes: total CPU usage, per-core CPU usage, CPU frequencies, memory and swap utilization, network activity, and I/O operations. To use this mode, start monitoring with the `benchmon-start`, with chosen options, before launching the target application. Once the application has finished execution, stop the monitoring by running `benchmon-stop`. Upon completion, several reports will be saved in the traces directory, which can be visualized using the `benchmon-visu` described below. Additional options/flags available for the monitoring mode are described as follows:
  - `-d | --save-dir`:  Traces repository (default: `./traces_<JobId>/`). For each compute nodes, a sub-repository will be created in, and named `<traces>/benchmon_traces_<hostname>`
 -  `-v | --verbose`: Enable verbose mode.
 - `--dool`:   Path to the dool executable. If unset, a dool executable is searched in the PATH.
- `--sys | --system`: Enable system monitoring.
- `--sys-sampl-intv | --system-sampling-interval` Sampling interval to collect system metrics (default: `1` second).
- `--pow | --power`: Enable power monitoring (with perf).
- `--pow-sampl-intv | --power-sampling-interval`: Sampling interval to collect power metrics (default: `250` milliseconds)
- `--call`: Enable callstack tracing.
- `--call-mode`: Call graph collection mode (`dwarf`; `lbr`; `fp`) (default: `dwarf`)
- `--call-prof-freq | --call-profiling-frequency`: Profiling frequency (default: 10 Hz)
## Visualization
The visualization tool `benchmon-visu` allows for partial or complete display of monitoring and/or call tracing data. This tool accepts flags for the trace directory and information related to the desired metrics. It takes the traces repository as a positional arguments (if unset, it takes `./`). Here is the list of flags and options:
- `--traces-repo`: Set traces repository.
- `--cpu`: Display total CPU usage (usr, sys, wait, idle).
- `--cpu-all`: Display all CPU cores.
- `--cpu-freq`: Display all CPU cores frequencies.
- `--cpu-cores-in`: List of comma-separated CPU cores to display.
- `--cpu-cores-out`: List of comma-separated CPU cores to exclude.
- `--mem`: Display memory/swap.
-  `--net`: Display network activity.
- `--io`: Display io.
- `--interactive`: Enable interactive visualization (with matplotlib).
- `--fig-path`: Set the directory where to save the fig (default: same as traces)
- `--fig-fmt`: Set the figure format (default: `svg`).
- `--fig-name`: Set the figure name (default: `benchmonpsc_fig`)
- `--fig-dpi` Set the quality of figure: `low`, `medium`, `high` (default: `medium`).
## Example on AWS
```bash
#!/usr/bin/bash
# SBATCH ...

# Benchmon executables
benchmon=/shared/fsx1/benchmark-monitor/bin

# Traces repository
traces_repo=./traces_${USER}_${SLURM_JOB_ID}

# Collect hw/sw context
$benchmon/benchmon-hardware --save-dir $traces_repo
$benchmon/benchmon-software --save-dir $traces_repo

# Benchmon-run parameters
benchmon_params="--save-dir $traces_repo"
benchmon_params+=" --system --system-sampling-interval 1"
benchmon_params+=" --dool $HOME/bin/dool"
benchmon_params+=" --verbose"

# Run benchmon
$benchmon/benchmon-start $benchmon_params
sleep 2

# Target app
/shared/fsx1/benchmark-monitor/mytest/nas-omp/bin/ft.B.x

# Stop benchmon
sleep 2
$benchmon/benchmon-stop

# Create visualization plot
$benchmon/benchmon-visu --cpu --cpu-all --mem --fig-fmt png --fig-dpi medium "$traces_repo/benchmon_traces_$(hostname)"
```
