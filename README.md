# SDP Benchmark Monitor

This repository contains the benchmark monitor that is used in conjunction with the [benchmark tests repository](https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-tests)

In the `bin` directory there are three executable scripts. `benchmon-hardware.py` and `benchmon-software.py` gather hardware- and software context respectively.
The third script, `benchmon-run.py` is used to measure runs of the benchmarks and is designed to be ran alongside the benchmarks.

This is currently a work in progress and work will continue during PI-23.

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-sdp-benchmark-monitor/badge/?version=latest)](https://developer.skao.int/projects/ska-sdp-benchmark-monitor/en/latest/?badge=latest)

# Installation
###### _[Dool](https://github.com/scottchiefbaker/dool)_ (not mandatory)
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
## Benchmon modes
This mode allows background monitoring of resource usage and recording of energy consumption. This includes: total CPU usage, per-core CPU usage, CPU frequencies, memory and swap utilization, network activity, and I/O operations. To use this mode, start monitoring with the `benchmon-start` (or `benchmon-slurm-start` for slurm multi-nodes runs), with chosen options, before launching the target application. Once the application has finished execution, stop the monitoring by running `benchmon-stop` (or `benchmon-slurm-stop` for slurm multi-nodes runs). Upon completion, several reports will be saved in the traces directory, which can be visualized using the `benchmon-visu` described below. Additional options/flags available for the monitoring mode are described as follows:
  - `-d | --save-dir`: Traces repository (default: `./traces_<JobId>/`). For each compute nodes, a sub-repository will be created in, and named `<traces>/benchmon_traces_<hostname>`
 -  `-v | --verbose`: Enable verbose mode.
#### Native system monitoring (high-frequency monitoring)
- `--high-freq-system | --hf-sys`: Enable high-frequency native system monitoring
- `--hf-sys-freq`: Monitoring frequency (Default: 10 Hz)
#### Dool system monitoring
 - `--dool`:   Path to the dool executable. If unset, a dool executable is searched in the PATH.
- `--sys | --system`: Enable system monitoring with dool.
- `--sys-sampl-intv | --system-sampling-interval` Sampling interval to collect system metrics (default: `1` second).
#### Energy profiling
- `--pow | --power`: Enable power monitoring (with perf and g5k).
- `--pow-sampl-intv | --power-sampling-interval`: Sampling interval to collect power metrics (default: `250` milliseconds)
- `--pow-g5k | --power-g5k`: Enable only G5K power monitoring
#### Callstack recording
- `--call`: Enable callstack tracing.
- `--call-mode`: Call graph collection mode (`dwarf`; `lbr`; `fp`) (default: `dwarf`)
- `--call-prof-freq | --call-profiling-frequency`: Profiling frequency (default: 10 Hz)
## Visualization
The visualization tool `benchmon-visu` allows for partial or complete display of monitoring and/or call tracing data. This tool accepts flags for the trace directory and information related to the desired metrics. It takes the traces repository as a positional arguments (if unset, it takes `./`). Here is the list of flags and options:
###### If native monitoring is enabled
- `--hf-mem`: Visualize memory
- `--hf-cpu`: Display average cpu usage per space (usr, sys, wait, idle, virt)
- `--hf-cpu-all`: Visualize all CPU cores usage (usr+sys+wait)
- `--hf-cpu-freq`: Visualize all CPU cores frequencies
- `--hf-cpu-cores-full` Display core usage per space (comma-separated list)
- `--cpu-cores-in`: List of comma-separated CPU cores to display.
- `--cpu-cores-out`: List of comma-separated CPU cores to exclude.
###### If dool monitoring is enabled
- `--cpu`: Display total CPU usage (usr, sys, wait, idle).
- `--cpu-all`: Display all CPU cores.
- `--cpu-freq`: Display all CPU cores frequencies.
- `--cpu-cores-in`: List of comma-separated CPU cores to display.
- `--cpu-cores-out`: List of comma-separated CPU cores to exclude.
- `--mem`: Display memory/swap.
-  `--net`: Display network activity.
- `--io`: Display io.
##### Global visualization options
- `--interactive`: Enable interactive visualization (with matplotlib).
- `--fig-path`: Set the directory where to save the fig (default: same as traces)
- `--fig-fmt`: Set the figure format (default: `svg`).
- `--fig-name`: Set the figure name (default: `benchmonpsc_fig`)
- `--fig-dpi` Set the quality of figure: `low`, `medium`, `high` (default: `medium`).
## Example on AWS
```bash
#!/usr/bin/bash
#SBATCH -N 2 -n 8 -t 10

# Benchmon executables
benchmon=/shared/fsx1/benchmark-monitor/bin

# Traces repository
traces_repo=./traces_${USER}_${SLURM_JOB_ID}

# Collect hw/sw context
$benchmon/benchmon-hardware --save-dir $traces_repo
$benchmon/benchmon-software --save-dir $traces_repo

# Benchmon-run parameters
benchmon_params="--save-dir $traces_repo"
benchmon_params+=" --hf-sys --hf-sys-freq 5" # Native monitoring enabled
benchmon_params+=" --system --system-sampling-interval 1 --dool $HOME/bin/dool" # Dool monitoring enabled
benchmon_params+=" --verbose"

# Run benchmon
$benchmon/benchmon-slurm-start $benchmon_params
sleep 2

# Target app
mpirun -n $SLURM_NPROCS /shared/fsx1/benchmark-monitor/mytest/nas-mpiomp/bin/ft.B.x

# Stop benchmon
sleep 2
$benchmon/benchmon-slurm-stop

# Create visualization plot
for subrepo in $traces_repo/*/; do
    $benchmon/benchmon-visu --hf-mem --hf-cpu --hf-cpu-all --hf-cpu-freq \ # Native
						    --mem --cpu --cpu-all --cpu-freq --mem --net \ # Dool
							--cpu-cores-in 1,2,3,4 --fig-fmt png --fig-dpi medium $subrepo
done
```
