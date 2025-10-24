####################################
SKA SDP Benchmark Monitor - benchmon
####################################

SKA SDP Benchmark Monitor, also known as **benchmon**, is a tool for monitoring hardware resource usage, energy consumption, and recording software execution events. It is designed to analyze and optimize the performance and energy efficiency of applications, whether running on a single node or across multiple nodes. It intends to bridge the gap between existing tools for infrastructure monitoring and those dedicated to profiling by providing several levels of analysis with varying detail and overhead. It is non-intrusive and runs in the background, allowing applications to execute with minimum interference from the monitoring process.

This guide describes the main features, installation, usage, and visualization capabilities of benchmon.

- **Hardware resource usage monitoring**: benchmon can monitor and record a wide range of system metrics, including:

  - **CPU**: Average and per-core usage, usage per space, and frequencies.
  - **Memory & Swap**: Used, cached, and free memory and swap.
  - **Network & Infiniband**: Bandwidth.
  - **Disk**: Bandwidth and IOPS.

- **Energy consumption**

  - **RAPL measurements**: Uses ``perf`` for power profiling and energy consumption.
  - **Wattmeter integration**: Supports Grid5000 wattmeters and BMCs for node-level power monitoring.

- **Software monitoring**: benchmon allows for computing software performance metrics or for collecting execution traces

  - **Callgraph tracing**: benchmon uses ``perf`` to capture callgraphs for plot annotation and to generate flame graphs for in-depth profiling.
  - **Software performance metrics**: benchmon uses ``hpctoolkit`` for computing performance metrics based on counting a variety of software events, the distribution of these events can be visualised using ``hpcviewer``
  - **Execution traces**: benchmon uses ``hpctoolkit`` for recording function calls in all threads and all nodes which can be visualised using ``hpcviewer``.
  

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
