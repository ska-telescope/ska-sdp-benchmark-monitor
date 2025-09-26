#!/bin/bash

# High-performance Network monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Use a pipe as the record separator for consistency
RS="|"

while true; do
    if [[ -n "$influxdb_pipe" ]]; then
        # Aggregate all interface data into a single payload
        payload=$(tail -n +3 /proc/net/dev | tr '\n' "$RS")

        # New Format: NETWORK|iface1: data|iface2: data|...
        echo "NETWORK|$payload" > "$influxdb_pipe"
    fi

    sleep "$delay"
done


