####################################
SKA SDP Benchmark Monitor - benchmon
####################################

SKA SDP Benchmark Monitor, also known as **benchmon**, is a tool for monitoring resource usage, energy consumption, and tracing callgraphs. It is designed to analyze and optimize the performance and energy efficiency of applications, whether running on a single node or across multiple nodes. It is non-intrusive and runs in the background, allowing applications to execute without interference from the monitoring process.

This guide describes the main features, installation, usage, and visualization capabilities of benchmon.

- **Resource usage monitoring:** benchmon can monitor and record a wide range of system metrics, including:

  - **CPU**: Average and per-core usage, usage per space, and frequencies.
  - **Memory & Swap**: Used, cached, and free memory and swap.
  - **Network & Infiniband**: Bandwidth.
  - **Disk**: Bandwidth and IOPS.

- **Energy consumption**

  - **RAPL measurements**: Uses ``perf`` for power profiling and energy consumption.
  - **Wattmeter integration**: Supports Grid5000 wattmeters and BMCs for node-level power monitoring.

- **Callgraph tracing:** benchmon uses ``perf`` to capture callgraphs for plot annotation and to generate flame graphs for in-depth profiling.


.. toctree::
  :maxdepth: 1
  :caption: Getting started

  ./guide/getting_started.md


.. toctree::
  :maxdepth: 1
  :caption: Tutorials

  ./guide/tutorial_mono-node.md
  ./guide/tutorial_multi-node.md
  ./guide/tutorial_ical.md
  ./guide/tutorial_pre-defined_levels.md
  ./guide/tutorial_influxdb-grafna-integration.md
  ./guide/tutorial_export-benchmon-influxdb.md
  
.. toctree::
  :maxdepth: 1
  :caption: Developer guide

  ./api/benchmon.rst
  ./api/benchmon.common.rst
  ./api/benchmon.common.slurm.rst
  ./api/benchmon.exceptions.rst
  ./api/benchmon.hardware.rst
  ./api/benchmon.hardware.advanced.rst
  ./api/benchmon.hardware.gatherers.rst
  ./api/benchmon.run.rst
  ./api/benchmon.software.rst
  ./api/benchmon.software.gatherers.rst
  ./api/benchmon.visualization.rst
