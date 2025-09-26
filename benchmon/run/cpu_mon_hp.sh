#!/bin/bash

# High-performance CPU monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Use a pipe as the record separator for consistency
RS="|"

while true
do
    if [[ -n "$influxdb_pipe" ]]; then
        # Aggregate all cpu lines from /proc/stat into a single payload, separated by RS
        payload=$(grep '^cpu' /proc/stat | tr '\n' "$RS")
        
        # New Format: CPU|line1|line2|...
        echo "CPU|$payload" > "$influxdb_pipe"
    fi
    
    sleep $delay
done
