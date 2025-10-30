​​​​​# Installation
benchmon is mainly written in Python and BASH, and can be installed on Linux systems equipped with Python 3.6 or higher. To install benchmon, clone the repository and install it using `pip`. Using a Python virtual environment is recommended.

```bash
git clone https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor.git
cd ska-sdp-benchmark-monitor

# (Optional but recommended) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

pip install .
```

This installs `ska-sdp-benchmark-monitor` and adds the benchmon executables to the `PATH`.

### Permissions for `perf`
benchmon uses `perf` for energy profiling and call-stack tracing. To use `perf` without root privileges, set the following parameters:
```bash
kernel.perf_event_paranoid = -1
kernel.kptr_restrict = 0
```

### Installing `hpctoolkit`
to generate software performance metrics or collect execution traces, HPCToolkit is required. It can be installed using the following [instructions]([https://hpctoolkit.org/software-instructions.html])

---

# Check System availability
`benchmon-check` can be used to check the system availability and check if the environment is compatible for `benchmon`. We recommended that the users should run this command before running `benchmon` for the first time. 

```bash
benchmon-check
```

# Basic procedure
To monitor an application with benchmon, follow these four main steps:
1. **Start benchmon** using `benchmon-start` (or `benchmon-multinode-start` for multi-node setups). benchmon runs in the background and does not block subsequent executions. The type and frequency of monitoring can be configured by passing various arguments. A subdirectory is created to store all trace files.
2. **Run the target applications** as usual. benchmon performs all enabled types of monitoring in the background while the applications are running.
3. **Stop benchmon** with `benchmon-stop` (or `benchmon-multinode-stop`). This finalizes and terminates benchmon background processes, and post-processes the trace files. The traces are saved in the directory specified in step 1.
4. **Visualize the trace files** using `benchmon-visu`. This generates plots and figures for all collected metrics. Visualization can be customized by passing different arguments to select which metrics to display.

Example workflow with benchmon:
```bash
#!/usr/bin/bash

# Start benchmon (step 1)
benchmon-start --sys --pow --call --save-dir ./traces

# Target app (step 2)
./app_0
./app_1

# Stop benchmon (step 3)
benchmon-stop

# Visualize traces (step 4)
benchmon-visu --cpu --mem --recursive ./traces
```
The number of steps can be reduced to 3 by using the `--level` option. This option specifies a pre-defined set of monitoring options, which is useful for common benchmarking scenarios. See [Pre-defined Benchmarking Levels](#pre-defined-benchmarking-levels) for more details.

---

# Monitoring options and flags
benchmon offers a set of options for customizing monitoring. Specific types of monitoring can be enabled or disabled, sampling frequencies adjusted, and system resources or metrics selected for tracking. This flexibility allows the monitoring process to be tailored to the application's requirements and the desired level of detail for analysis.

### `benchmon-start` and `benchmon-multinode-start`

##### General Options
- `-d`, `--save-dir`: Directory to save traces (default: `./save_dir_<JobId>/`).
- `-v`, `--verbose`: Enable verbose output.
- `-b`, `--backend`: Backend for multi-node monitoring (`mpi`, `ssh`; default: `mpi`).
##### Resource Usage
- `--system`, `--sys`: Enable system monitoring.
- `--sys-freq`: Monitoring frequency in Hz (default: 10).

##### Energy Consumption
- `--pow`, `--power`: Enable power monitoring.
- `--pow-sampl-intv`, `--power-sampling-interval`: Power sampling interval in ms (default: 250).
- `--pow-g5k`, `--power-g5k`: Enable Grid5000 power monitoring.

##### Callgraph Tracing using `perf`

- `--call`: Enable callstack tracing.
- `--call-mode`: Callgraph collection mode (`dwarf`, `lbr`, `fp`; default: `dwarf,32`).
- `--call-prof-freq`, `--call-profiling-frequency`: Profiling frequency in Hz (default: 10, min: 1).

#### Trace collection and generation of performance metrics using `hpctoolkit`

- `-e`, `--hpc-exe`: executables to be traced.
- `-f`, `--hpc-flags`: flags passed to `hpcrun` for configuring data collection.

***
### `benchmon-stop` and `benchmon-multinode-stop`
These commands stop the monitoring process and post-process the trace files. For `benchmon-multinode-stop`, the flag `-b | --backend` can be used to specify the backend to spread the stop command to all nodes. Possible values are `mpi` and `ssh` (default: `mpi`).


### `benchmon-visu`
The `benchmon-visu` tool provides detailed visualization of collected metrics, supporting both partial and comprehensive displays of resource usage, power consumption, and call tracing data. It enables selection of specific metrics for plotting, supports multi-node synchronized visualization, and offers options for interactive or figure generation. Output formats and figure quality can be customized for reporting or analysis.

For multi-node runs, `benchmon-visu` can generate synchronized graphs across nodes using the `--recursive` option. This feature aligns metrics from different nodes on a common timeline, making it easier to analyze distributed workloads and correlate events across the system.

```bash
benchmon-visu <traces-directory> [options]
```
If no directory is specified, the current directory (`./`) is used.

Available options:
##### Resource usage
- `--mem`: Visualize memory usage.
- `--cpu`: Show average CPU usage (user, system, wait, idle, virt).
- `--cpu-all`: Show all CPU cores usage.
- `--cpu-freq`: Show CPU core frequencies.
- `--cpu-cores-full`: Show core usage per space (comma-separated).
- `--cpu-cores-in`: Include specific CPU cores (comma-separated).
- `--cpu-cores-out`: Exclude specific CPU cores (comma-separated).
- `--net`: Show network activity.
- `--net-all`: Show all network interfaces.
- `--net-rx-only`: Show only RX activity.
- `--net-tx-only`: Show only TX activity.
- `--net-data`: Label network plot with total data.
- `--disk`: Show disk bandwidth.
- `--disk-iops`: Show disk IOPS.
- `--disk-data`: Label disk plots with total data.
- `--disk-rd-only`: Show disk reads only.
- `--disk-wr-only`: Show disk writes only.
- `--ib`: Show Infiniband activity.

##### Energy Consumption
- `--pow`: Visualize perf power profiles.
- `--pow-g5k`: Visualize G5K power profiles.

##### Callgraph Tracing using `perf`
- `--call`: Visualize call stack.
- `--call-depth`: Set call stack depth (integer).
- `--call-cmd`: (Optional) Set command to show in call stack plots.

##### Plot annotations
- `--inline-call`: Annotate plots with running commands (if `--call` is enabled).
- `--inline-call-cmd`: Comma-separated list of commands for inline call annotations.
- `--ical-log`: Annotate with ICAL stages; the log file (`wflow-selfcal.*.log`) must be in the same directory as the traces.

##### Global visualization
- `--recursive`: Generate synchronized plots for multi-node runs.
- `--interactive`: Enable interactive mode (matplotlib).
- `--start-time`: Set start time (`YYYY-MM-DDTHH:MM:SS`).
- `--end-time`: Set end time (`YYYY-MM-DDTHH:MM:SS`).
- `--fig-path`: Directory to save figures (default: traces directory).
- `--fig-fmt`: Figure format (default: `svg`).
- `--fig-name`: Figure name.
- `--fig-dpi`: Figure quality (`low`, `medium`, `high`; default: `medium`).
- `--fig-width`: Figure width in inches (default: 25.6).
- `--fig-height-unit`: Figure subplot height in inches (default: 3).
- `--fig-xrange`: Number of ticks on the x-axis (default: 25).
- `--fig-yrange`: Number of ticks on the y-axis (default: 11).
**

# SW/HW contexts
benchmon can automatically generate detailed files describing both the software and hardware contexts of the current benchmark. The `benchmon-hardware` command produces a JSON file containing information such as CPU details, memory configuration, disk data, network interfaces, accelerator information, system topology, and operating system data. Similarly, the `benchmon-software` command generates a JSON file that includes environment variables, Spack dependencies, Python environment details, and loaded modules. Both commands accept the `--save-dir` option to specify the path where the JSON files will be generated. These JSON files can be visualized in graph mode using tools like JSON Crack for easier inspection and analysis.


# Pre-defined benchmarking levels

benchmon provides pre-defined levels to simplify common benchmarking scenarios. Each level enables a specific set of monitoring and tracing options, as well as visualization options. When the `--level` flag is used, benchmon automatically configures metric collection, and at stop time (`benchmon-stop`), it calls `benchmon-visu` with the associated visualization options for that level. Software execution is traced either using `perf` or `hpctoolkit` for level 1 and above. `perf` will trace all software activity at a frequency increasing with the level. Conversely, `hpctoolkit` will only record information for the executables passed as arguments, performance metrics are produced for level 1 and execution traces for level 2. The save directory can also be specified with `--save-dir` to control where traces and figures are stored.

For each benchmarking level, `benchmon-visu` automatically generates two figures: an _overview_ figure and a _detailed_ figure, and both figures are produced in `svg` and `png` formats.

In addition, when using pre-defined benchmarking levels, benchmon always runs `benchmon-software` and `benchmon-hardware` to capture the software and hardware contexts of the benchmark.

|    Level    | Monitoring options enabled                        | Visualization options enabled                                                                            |
| :---------: | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `--level 0` | `--sys --sys-freq 1`                              | _overview:_ `--cpu --mem --net --disk --fig-name benchmon_figure_overview`                                                                   |
|             |                                                   | _detailed:_ `--cpu --cpu-all --cpu-freq --mem --net --net-all --net-data --disk --disk-data --disk-iops --fig-name benchmon_figure_detailed`  |
| `--level 1` | `--sys --sys-freq 5 --call --call-prof-freq 1` using `perf`   | _overview:_ `<level 0>` + `--inline-call`                                                               |
|             |                                                   | _detailed:_ `<level 0>` + `--inline-call`                                                                |
| `--level 1` | `--sys --sys-freq 5 ` requires `--hpc-exe` to use `hpctoolkit`   | _overview:_ `<level 0>`|
|             |                                                   | _detailed:_ `<level 0>`                                                                       |
| `--level 2` | `--sys --sys-freq 100 --call --call-prof-freq 50` using `perf | _overview:_ `<level 1>` + `--call --call-depth 4`                                                        |
|             |                                                   | _detailed:_ `<level 1>` + `--call --call-depth 4`                                                        |
| `--level 2` | `--sys --sys-freq 100` requires `--hpc-exe` to use `hpctoolkit`| _overview:_ `<level 1>`                                                        |
|             |                                                   | _detailed:_ `<level 1>`                                                        |


```bash
#!/usr/bin/bash
benchmon-start --level <level> --save-dir <dir>

<applications>

benchmon-stop --level <level> --save-dir <dir>
```
***

# benchmon-report

The `benchmon-report` tool provides a way to automatically extract and summarize parts of the data from the raw output files generated by benchmon. It fills an Markdown file based on a pre-written template. The template can be adapted to the user's needs.

This tool is able to extract and summarize data from the following benchmon outputs:
- software report
- hardware report
- process timings report
- monitoring graphs

The data is formatted to make it easily readable. To integrate these pieces of data in a Markdown file, you can add bracket-enclosed labels wherever you want the data to be written like in this example:
```
# Hardware description
- Partition name: <partition_name>
- Compute nodes:
    - CPUs:
        - model name: <CPU_Model>
        - number of cores: <Cores_per_socket>
        - threads per core: <Threads_per_core>
        - sockets and NUMA organisation: <Sockets> socket(s), <NUMA_nodes> NUMA nodes
        - min frequency: <CPU_Min_Speed_MHz> MHz
        - max frequency: <CPU_Max_Speed_MHz> MHz
        - L1d cache: <L1d_cache> per socket
        - L1i cache: <L1i_cache> per socket
        - L2 cache: <L2_cache> per socket
        - L3 cache: <L3_cache> per socket
    - Memory:
        - RAM: <ram_gib> GiB (<ram_per_core_gib> GiB per core)
        - Swap: <swap_gib> GiB

# Software description
## Environment variables
<environment_variables>

## Spack environment
<spack_dependencies>

## Python environment
<python_environment>

# Pipeline performance
## Process timings
<ps_data>

## Resource usage
<benchmon_plot>
```

You can also use the default template provided in `benchmon/report/template.md`. Then, run the following command:
```
benchmon-report --software-report <path/to/swmon/file> --hardware-report <path/to/hwmon/file> --ps-report <path/to/ps/report/file> --figure-path <path/to/graph/file.png>
```
