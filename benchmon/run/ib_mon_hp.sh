#!/bin/bash

# High-performance InfiniBand monitoring by reading /sys filesystem directly

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2 # Not used
grafana_enabled=$3
influxdb_pipe=$4

# The directory where IB devices are exposed
IB_SYSFS_PATH="/sys/class/infiniband"

# Check if the IB sysfs path exists
if [ ! -d "$IB_SYSFS_PATH" ]; then
    exit 0
fi

# Define the metrics we want to capture
IB_METRICS="port_xmit_data port_rcv_data port_xmit_pkts port_rcv_pkts"

while true; do
    timestamp=$(date +'%s.%N')

    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        # Loop through each InfiniBand device (e.g., mlx5_0)
        for device_path in "$IB_SYSFS_PATH"/*; do
            if [ ! -d "$device_path/ports" ]; then
                continue
            fi
            device_name=$(basename "$device_path")

            # Loop through each port for the device
            for port_path in "$device_path/ports"/*; do
                port_num=$(basename "$port_path")
                
                # Check if the port is active
                if [[ -r "$port_path/state" ]] && grep -q "4: ACTIVE" "$port_path/state"; then
                    # Loop through the metrics we want to collect
                    for metric in $IB_METRICS; do
                        counter_file="$port_path/counters/$metric"
                        if [[ -r "$counter_file" ]]; then
                            value=$(cat "$counter_file")
                            # Use a combined device_port identifier
                            device_id="${device_name}_${port_num}"
                            
                            # Format: IB|timestamp|value device=<device_id> metric=<metric_name>
                            echo "IB|$timestamp|$value device=$device_id metric=$metric" > "$influxdb_pipe"
                        fi
                    done
                fi
            done
        done
    fi

    sleep "$delay"
done
