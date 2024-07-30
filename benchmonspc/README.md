# Benchmonspc
## Installation
#### Requirements
###### _[Dool](https://github.com/scottchiefbaker/dool)_
```bash
https://github.com/scottchiefbaker/dool.git
cd dool
./install.py
```
_Dool_'s binary will be usually located in `$HOME/bin`.
###### [_Perf_](https://perf.wiki.kernel.org/index.php/Main_Page) + _Perf permissions_
```bash
<package-manager-installer> linux-tools-<kernel-version>
```
###### _Python:_ _matplotlib; numpy._
```bash
pip3 install matplotlib numpy
```
### Download
- Git clone
```bash
git clone -b benchmonspc https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor.git
cd ska-sdp-benchmark-monitor/benchmonspc
```
All scripts are available in `ska-sdp-benchmark-monitor/benchmonspc`.
- You may add `ska-sdp-benchmark-monitor/benchmonspc` to your path
```bash
cd ska-sdp-benchmark-monitor/benchmonspc
export PATH=$PATH/$PWD
```
## Monitoring mode
This mode allows background monitoring of resource usage and recording of energy consumption. This includes: total CPU usage; per-core CPU usage; memory and swap utilization; network activity; and I/O operations. To use this mode, start monitoring with the `benchmonspc.sh`  before launching the target application. Once the application has finished execution, stop the monitoring by running `benchmonspc_kill.sh`. Upon completion, several reports will be saved in the traces directory, which can be visualized using the `benchmonspc_visu.py` described below. Additional options/flags available for the monitoring mode are described as follows:
- `-tr | --tr | --traces-repo`: Set traces repository (default: `./benchmonspc_traces_<JobId>/<Hostname>`).
- `-s | --sys]`: Enable recording of system resources usage (cpu, memory, io, network).
- `-sd | --sd | --sys-delay`: Set recording delay (in seconds) (default: `1 Seconds` ).
- `-p | --pow`: Enabling recording of power consumption.
- `-pd | --pd | --pow-delay`: Set recording delay (in milliseconds) (default: `500 Milliseconds`).
- `--sudo-perf-command`: If needed add `sudo command` for perf.
#### Example _(DemoMon)_
```bash
# Benchmonpsc repository
BENCHMONSPC=$HOME/ska-sdp-benchmark-monitor/benchmonspc

# Target application
APP=$HOME/NPB3.4-OMP/bin/ft.B.x

# Traces repository
TRACES_REPO=./demo_mon

# Run benchmonspc (this will only record system usage) (to record power consumption, add --pow)
$BENCHMONSPC_BIN/benchmonspc.sh --sys --traces-repo $TRACES_REPO

# Run App
sleep 5
exec $APP
sleep 5

# Kill benchmonspc
$BENCHMONSPC_BIN/benchmonspc_kill.sh
```
This collects system resource usage while `ft.B.x` is running. The traces are located in `./demo_mon`.
## Call tracing mode
To activate the execution call tracing mode:
- Add the `--call` flag to `benchmonspc.sh`.
- The target application is not launched separately and becomes the final argument of `benchmonspc.sh`.
- There is no need to add `benchmonspc_kill.sh`. The recording ends once the application's execution is complete.
This generates new traces that can be visualized using the `benchmonspc_visu` described below. This mode can be launched with or without the monitoring mode. Here are some optional flags for this mode:
- `-c | --call`: Enable recording of the callstack.
- `-cm | --cm | --call-mode`: Set recording mode: `dwarf`, `lbr`, `fp` (default: `dwarf`).
- `-cf | --cf | --call-freq`: Set recording frequency (in Hz) (default: `10 Hz`).
- `-ws | --ws | --wait` Set wait time before and after running the target application (in seconds) (default: `0 Second`).
- `--sudo-perf-command`: If needed add `sudo command` for perf.
#### Example _(DemoCall)_
```bash
# Benchmonpsc repository
BENCHMONSPC=$HOME/ska-sdp-benchmark-monitor/benchmonspc

# Target application
APP=$HOME/NPB3.4-OMP/bin/ft.B.x

# Traces repository
TRACES_REPO=./demo_call

# Run benchmonspc
$BENCHMONSPC_BIN/benchmonspc.sh --call --traces-repo $TRACES_REPO $APP
```
This collects the callstack of `ft.B.x`.  The traces are located in `./demo_call`.
## Visualization
The visualization tool `benchmonspc_visu.py` allows for partial or complete display of monitoring and/or call tracing data. This tool accepts flags for the trace directory and information related to the desired metrics. Here is the list of flags and options:
- `--traces-repo`: Set traces repository.
- `--cpu`: Display total CPU usage (usr, sys, wait, idle).
- `--cpu-all`: Display all CPU cores.
- `--mem`: Display memory/swap.
-  `--net`: Display network activity.
- `--io`: Display io.
- `--pow`: Display power profile.
- `--call`: Display callstack.
- `--call-depth`: Set callstack depth level (default: `1`)
- `--call-depths`: Set comma-separated depth levels.
- `--call-cmd`: Set command to display (default: command with the largest number of samples)
- `--interactive`: Enable interactive visualization (with matplotlib).
- `--fig-path`: Set the directory where to save the fig (default: same as traces)
- `--fig-fmt`: Set the figure format (default: `svg`).
- `--fig-name`: Set the figure name (default: `benchmonpsc_fig`)
- `--fig-dpi` Set the quality of figure: `low`, `medium`, `high` (default: `medium`).
- `--fig-call-legend-ncol` Set the number of columns of call traces legend (default: `8`).
#### Visualization example of _DemoMon_
```bash
$BENCHMONSPC/benchmonspc_visu.py --cpu --cpu-all --mem --io --net --fig-fmt svg,png --traces-repo $TRACES_REPO
```
#### Visualization example of _DemoCall_
```bash
$BENCHMONSPC/$benchmonspc_visu.py --call --call-depth 3 --fig-fmt svg,png --traces-repo $TRACES_REP
```
## More Complete example
```bash
# Benchmonpsc repository
BENCHMONSPC=$HOME/ska-sdp-benchmark-monitor/benchmonspc

# Target application
APP=$HOME/NPB3.4-OMP/bin/ft.B.x

# Traces repository
TRACES_REPO=./demo_call

# Run benchmonspc
$BENCHMONSPC/$benchmonspc.sh --traces-repo $TRACES_REPO \
	--sys --sys-delay 1 --pow --pow-delay 500 \
	--call --call-freq 25 --wait 5 \
	$APP

# Visualization
$BENCHMONSPC/$benchmonspc_visu.py \
	--cpu --cpu-all --mem --io --net --pow \
	--call --call-depth 4 \
	--fig-fmt svg,png --fig-name myfig --fig-dpi high \
	--traces-repo $TRACES_REPO
```