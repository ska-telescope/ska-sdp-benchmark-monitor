#!/bin/bash

# High-performance InfiniBand monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Use a pipe as the record separator for consistency
RS="|"

# Find all InfiniBand ports
IB_PORTS=$(find /sys/class/infiniband/*/ports/*/counters -type f -name 'port_xmit_data' | sed -e 's;/sys/class/infiniband/\(.*\)/ports/.*/counters/.*$;\1;')

while true; do
    if [[ -n "$influxdb_pipe" ]]; then
        payload=""
        for port in $IB_PORTS; do
            # Transmitted data
            xmit_data=$(cat "/sys/class/infiniband/${port}/ports/1/counters/port_xmit_data")
            
            # Received data
            rcv_data=$(cat "/sys/class/infiniband/${port}/ports/1/counters/port_rcv_data")

            # Append "port_name rcv_data xmit_data<RS>" to the payload
            payload+="$port $rcv_data $xmit_data$RS"
        done

        # Send the entire aggregated payload in one line
        # New Format: IB|port0 rcv0 xmit0|port1 rcv1 xmit1|...
        if [[ -n "$payload" ]]; then
            echo "IB|$payload" > "$influxdb_pipe"
        fi
    fi
    sleep "$delay"
done
