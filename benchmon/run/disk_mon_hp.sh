#!/bin/bash

# High-performance Disk monitoring with direct InfluxDB output

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2 # Not used
grafana_enabled=$3
influxdb_pipe=$4

while true; do
    timestamp=$(date +'%s.%N')

    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        # hp_processor.py expects the raw line from /proc/diskstats
        while read -r line; do
            # Format: DISK|timestamp|raw_line_from_diskstats
            echo "DISK|$timestamp|$line" > "$influxdb_pipe"
        done < <(grep -v -e loop -e dm- /proc/diskstats)
    fi

    sleep "$delay"
done

