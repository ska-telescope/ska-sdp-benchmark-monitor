#!/bin/bash

# High-performance Memory monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Define the memory fields we are interested in
MEM_FIELDS="MemTotal MemFree MemAvailable Buffers Cached Slab"

while true; do
    if [[ -n "$influxdb_pipe" ]]; then
        values=""
        for field in $MEM_FIELDS; do
            # Extract the value for each field from /proc/meminfo
            value=$(grep "^${field}:" /proc/meminfo | awk '{print $2}')
            values+="${value},"
        done
        # Remove trailing comma
        values=${values%,}
        
        # New Format: MEMORY|value1,value2,value3...
        echo "MEMORY|$values" > "$influxdb_pipe"
    fi
    sleep "$delay"
done
