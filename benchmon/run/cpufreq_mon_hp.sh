#!/bin/bash

# High-performance CPU frequency monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular cpufreq_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
grafana_enabled=$3
influxdb_pipe=$4

# Use a more robust method to find all scaling_cur_freq files, similar to cpufreq_mon.sh
# This is more reliable than checking the 'online' status.
CPU_FREQ_FILES=$(find /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq 2>/dev/null)

# Function to send CPU frequency data in the format expected by hp_processor.py
send_to_influxdb() {
    local timestamp=$1
    local cpu_core=$2
    local frequency=$3
    
    # Format: CPUFREQ|timestamp|cpu_core frequency
    echo "CPUFREQ|$timestamp|$cpu_core $frequency" > "$influxdb_pipe"
}

while true
do
    timestamp=$(date +'%s.%N')
    
    # Process CPU frequency data and send to InfluxDB only
    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        for file in $CPU_FREQ_FILES; do
            if [[ -r "$file" ]]; then
                # Extract cpu core from path, e.g. /sys/devices/system/cpu/cpu12/.. -> cpu12
                cpu_core=$(echo "$file" | sed -n 's;^/sys/devices/system/cpu/\(cpu[0-9]*\)/.*$;\1;p')
                frequency=$(cat "$file")
                
                if [[ -n "$cpu_core" && -n "$frequency" ]]; then
                    send_to_influxdb "$timestamp" "$cpu_core" "$frequency"
                fi
            fi
        done
    fi
    
    sleep $delay
done
