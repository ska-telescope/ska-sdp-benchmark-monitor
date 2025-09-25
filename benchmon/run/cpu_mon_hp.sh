#!/bin/bash

# High-performance CPU monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular cpu_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
grafana_enabled=$3
influxdb_pipe=$4

# Function to send CPU data in the original format expected by hp_processor.py
send_to_influxdb() {
    local timestamp=$1
    local cpu_core=$2
    local user=$3
    local nice=$4
    local system=$5
    local idle=$6
    local iowait=$7
    local irq=$8
    local softirq=$9
    local steal=${10}
    local guest=${11}
    local guestnice=${12}
    
    # Original Format: CPU|timestamp|cpu_core user nice system idle iowait irq softirq steal guest guestnice
    echo "CPU|$timestamp|$cpu_core $user $nice $system $idle $iowait $irq $softirq $steal $guest $guestnice" > "$influxdb_pipe"
}

while true
do
    timestamp=$(date +'%s.%N')
    
    # Process CPU data and send to InfluxDB only
    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        while read -r line; do
            read -r cpu_core user nice system idle iowait irq softirq steal guest guestnice <<< "$line"
            send_to_influxdb "$timestamp" "$cpu_core" "$user" "$nice" "$system" "$idle" "$iowait" "$irq" "$softirq" "$steal" "$guest" "$guestnice"
        done < <(grep '^cpu' /proc/stat)
    fi
    
    sleep $delay
done
        # Use process substitution for better performance
        while read -r line; do
            # The 'read' command correctly splits the line into variables.
            read -r cpu_core user nice system idle iowait irq softirq steal guest guestnice <<< "$line"
            
            # Pass all values as a single string to be split in the function
            all_values="$user $nice $system $idle $iowait $irq $softirq $steal $guest $guestnice"
            send_to_influxdb "$timestamp_ns" "$cpu_core" "$all_values"
        done < <(grep '^cpu' /proc/stat)
    fi
    
    sleep $delay
done
