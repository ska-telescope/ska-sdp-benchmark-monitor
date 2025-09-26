#!/bin/bash

# High-performance Disk monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Use a pipe as the record separator for consistency
RS="|"

while true; do
    if [[ -n "$influxdb_pipe" ]]; then
        # Read all disk lines from /proc/diskstats and send them
        # We filter for common disk types like sd, nvme, vd, xvd
        payload=$(grep -E ' (sd|nvme|vd|xvd)[a-z]+ ' /proc/diskstats | tr '\n' "$RS")
        
        # New Format: DISK|line1|line2|...
        if [[ -n "$payload" ]]; then
            echo "DISK|$payload" > "$influxdb_pipe"
        fi
    fi
    sleep "$delay"
done

