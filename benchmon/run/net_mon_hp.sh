#!/bin/bash

# High-performance Network monitoring with direct InfluxDB output

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2 # Not used
grafana_enabled=$3
influxdb_pipe=$4

while true; do
    timestamp=$(date +'%s.%N')

    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        # Read all interface lines from /proc/net/dev, skipping the header
        # and send one line per interface in the original format
        tail -n +3 /proc/net/dev | while IFS=':' read -r iface data; do
            # Clean up interface name and format the data payload
            iface=$(echo "$iface" | xargs)
            payload=$(echo "$data" | xargs)
            
            # Original Format: NETWORK|timestamp|interface_name value1 value2 ...
            echo "NETWORK|$timestamp|$iface $payload" > "$influxdb_pipe"
        done
    fi

    sleep "$delay"
done
            read -r -a values <<< "$data"
            
            for i in "${!all_headers[@]}"; do
                measurement="net"
                field_key="${all_headers[$i]}"
                value="${values[$i]}"
                # InfluxDB Line Protocol: measurement,tag_set field_key=value timestamp
                echo "$measurement,host=$HOST_FQDN,interface=$iface ${field_key}=${value}i $timestamp_ns" > "$influxdb_pipe"
            done
        done < <(grep ":" /proc/net/dev)
    fi

    sleep "$delay"
done
