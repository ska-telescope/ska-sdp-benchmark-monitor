# Instrumental Calibration (INST) Pipeline with Annotations

Benchmark Monitor provides detailed visualization of system metrics (CPU, memory, network, etc.).  
It also supports **timeline annotations**, added in a separate subplot, showing the duration of each pipeline event.

This feature relies on an `events.csv` file containing structured pipeline events.  
To enable annotations, use the `--annotate-with-log` option in `benchmon-visu` and provide the corresponding events file.

The expected structure of the `events.csv` file is:

```csv
timestamp,pipeline,stage,event,node,process,source,message,core
```

## Example Script for INST Pipeline

This section provides an example of how to run the `INST` pipeline using `batchlet`.
It demonstrates how to enable both the generation of the `events.csv` file and `level 0` monitoring,
allowing `benchmon-visu` to produce annotated plots alongside the standard performance visualizations.


<!-- The following script provides a minimal example for running the `INST` pipeline on AWS with `batchlet` and enabling annotation support: -->

```bash
#!/usr/bin/env bash

set -euo pipefail

SCENARIO="example"
SUBCOMMAND="run"

INST_CONFIG="/path/to/config.yml"
INPUT_MS="/path/to/input.ms"

OUTPUT_DIR="$(pwd)/batchlet_inst_${SUBCOMMAND}_${SCENARIO}"
mkdir -p "$OUTPUT_DIR"

BATCHLET_CONFIG="$OUTPUT_DIR/batchlet_config.json"

MONITOR_OUTPUT_DIR="${OUTPUT_DIR}/monitor"
mkdir -p "$MONITOR_OUTPUT_DIR"

### SOFTWARE ENVIRONMENT ########################################################
# Load the required modules
################################################################################
module load ska-sdp-spack
module load py-ska-sdp-exec-batchlet
module load py-ska-sdp-instrumental-calibration
module load py-ska-sdp-benchmark-monitor

### BATCHLET CONFIGURATION ######################################################
# Generate the batchlet configuration file
################################################################################
cat <<EOF > $BATCHLET_CONFIG
{
  "command": [
    "ska-sdp-instrumental-calibration",
    "$SUBCOMMAND",
    "--input",
    "$INPUT_MS",
    "--config",
    "$INST_CONFIG",
    "--output",
    "$OUTPUT_DIR",
    "--no-unique-output-subdir"
  ],
  "dask_params": {
    "workers_per_node": 4,
    "threads_per_worker": 4,
    "resources_per_worker": "process=1",
    "use_entry_node": true,
    "dask_cli_option": "--dask-scheduler",
    "dask_report_dir": "$OUTPUT_DIR"
  },
  "monitor": {
    "resources": {
      "level": 0,
      "save_dir": "$MONITOR_OUTPUT_DIR"
    },
    "logs": {
      "filter_plugins": [
        {
          "name": "SKASDPFilter",
          "kwargs": {"pipeline": "INST"}
        }
      ],
      "consumer_plugins": [
        {
          "name": "CSVFile",
          "kwargs": {"file_path": "$OUTPUT_DIR/events.csv"}
        }
      ]
    }
  }
}
EOF

### EXECUTION ###################################################################
# Run the pipeline via batchlet
################################################################################
batchlet run $BATCHLET_CONFIG |& tee "$OUTPUT_DIR/batchlet.run.log"
```

## Workflow Overview
`Batchlet` is configured to monitor the pipeline at the specified `level` and produce the `events.csv` file. 
This CSV file is then used by `benchmon-visu` to add timeline annotations to the system metrics plots.

The corresponding monitoring section in the batchlet configuration is shown below:

```json
  "monitor": {
    "resources": {
      "level": 0,
      "save_dir": "$MONITOR_OUTPUT_DIR"
    },
    "logs": {
      "filter_plugins": [
        {
          "name": "SKASDPFilter",
          "kwargs": {"pipeline": "INST"}
        }
      ],
      "consumer_plugins": [
        {
          "name": "CSVFile",
          "kwargs": {"file_path": "$OUTPUT_DIR/events.csv"}
        }
      ]
    }
  }
```

## Results

The example below shows the output generated from running the INST pipeline on an AWS machine (`any-7i-24xl-spt-dy-compute-1`):

- **Partition:** any-7i-24xl-spt (Default Partition)  
- **vCPUs:** 96  
- **RAM:** ≥ 192 GB  

**Note:** The purpose of this example is **not to demonstrate performance**, but to illustrate how `Benchmark Monitor` generates timeline annotations alongside system metrics.

### Generated events.csv

An excerpt of the `events.csv` file produced by the pipeline:

```csv
timestamp,pipeline,stage,event,node,process,source,message,core
1772027227.014,INST,LOAD_DATA,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting load_data,
1772027243.313,INST,LOAD_DATA,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished load_data,
1772027243.313,INST,PREDICT_VIS,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting predict_vis,
1772027501.55,INST,PREDICT_VIS,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished predict_vis,
1772027501.55,INST,BANDPASS_INITIALISATION,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting bandpass_initialisation,
1772027569.221,INST,BANDPASS_INITIALISATION,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished bandpass_initialisation,
1772027569.221,INST,BANDPASS_CALIBRATION,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting bandpass_calibration,
1772027812.037,INST,BANDPASS_CALIBRATION,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished bandpass_calibration,
1772027812.037,INST,DELAY_CALIBRATION,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting delay_calibration,
1772027849.135,INST,DELAY_CALIBRATION,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished delay_calibration,
1772027849.135,INST,EXPORT_GAIN_TABLE,START,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#255,Starting export_gain_table,
1772027850.428,INST,EXPORT_GAIN_TABLE,FINISHED,any-7i-24xl-spt-dy-compute-1,MainThread,scheduler.py#280,Finished export_gain_table,
```
### Annotated Plot

The following figure shows the system metrics with timeline annotations generated from the `events.csv` file:
![tutorial_ical_figure](../images/tutorial_inst_annotation.png)