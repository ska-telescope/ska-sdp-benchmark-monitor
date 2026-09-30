#!/bin/bash

# High-performance memory monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular mem_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
grafana_enabled=${3:-"false"}
influxdb_pipe=${4:-""}

# Function to send data to InfluxDB via HP processor
send_to_influxdb() {
    local timestamp=$1
    
    # Parse memory data into comma-separated values for HP processor
    local meminfo_values=""
    local memory_fields=(
        "MemTotal" "MemFree" "MemAvailable" "Buffers" "Cached"
        "SwapCached" "Active" "Inactive" "SwapTotal" "SwapFree"
    )
    
    for field in "${memory_fields[@]}"; do
        local value=$(grep "^${field}:" /proc/meminfo | awk '{print $2}')
        if [[ -n "$value" ]]; then
            if [[ -n "$meminfo_values" ]]; then
                meminfo_values="${meminfo_values},${value}"
            else
                meminfo_values="$value"
            fi
        else
            meminfo_values="${meminfo_values},0"
        fi
    done
    
    # HP processor format: MEMORY|timestamp|value1,value2,value3...
    echo "MEMORY|$timestamp|$meminfo_values" > "$influxdb_pipe"
}

while true
do
    timestamp=$(date +'%s.%N')
    
    # Send data to InfluxDB only
    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        send_to_influxdb "$timestamp"
    fi
    
    sleep $delay
done
