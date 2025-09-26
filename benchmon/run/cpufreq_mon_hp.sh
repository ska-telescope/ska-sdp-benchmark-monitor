#!/bin/bash

# High-performance CPU frequency monitoring for InfluxDB.

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
influxdb_pipe=$2

# Use a pipe as the record separator for consistency
RS="|"

# Find all scaling_cur_freq files. This is a robust way to get all cores.
CPU_FREQ_FILES=$(find /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq 2>/dev/null)

while true
do
    if [[ -n "$influxdb_pipe" ]]; then
        payload=""
        for file in $CPU_FREQ_FILES; do
            if [[ -r "$file" ]]; then
                # Extract cpu core from path, e.g. /sys/devices/system/cpu/cpu12/... -> cpu12
                cpu_core=$(echo "$file" | sed -n 's;^/sys/devices/system/cpu/\(cpu[0-9]*\)/.*$;\1;p')
                frequency=$(cat "$file")
                
                if [[ -n "$cpu_core" && -n "$frequency" ]]; then
                    # Append "cpu_core frequency<RS>" to the payload
                    payload+="$cpu_core $frequency$RS"
                fi
            fi
        done
        
        # Send the entire aggregated payload in one line
        # New Format: CPUFREQ|cpu0 freq0|cpu1 freq1|...
        if [[ -n "$payload" ]]; then
            echo "CPUFREQ|$payload" > "$influxdb_pipe"
        fi
    fi
    
    sleep $delay
done
