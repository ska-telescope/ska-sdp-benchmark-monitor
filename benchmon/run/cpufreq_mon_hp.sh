#!/bin/bash

# High-performance CPU frequency monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular cpufreq_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
grafana_enabled=$3
influxdb_pipe=$4

cpu0_repo=/sys/devices/system/cpu/cpu0
cpu_freq_min=$(cat ${cpu0_repo}/cpufreq/cpuinfo_min_freq)
cpu_freq_max=$(cat ${cpu0_repo}/cpufreq/cpuinfo_max_freq)

online_cpu_curfreq=$(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat $file) = 1 ]]; then echo $(dirname $file)/cpufreq/scaling_cur_freq; fi; done)

test -e ${cpu0_repo}/online || online_cpu_curfreq="${cpu0_repo}/cpufreq/scaling_cur_freq $online_cpu_curfreq"

# Function to send CPU frequency data to HP processor
send_to_influxdb() {
    local timestamp=$1
    local cpu_core=$2
    local frequency=$3
    
    # HP processor format: CPUFREQ|timestamp|cpu_core frequency
    echo "CPUFREQ|$timestamp|$cpu_core $frequency" > "$influxdb_pipe"
}

while true
do
    timestamp=$(date +'%s.%N')
    
    # Process CPU frequency data and send to InfluxDB only
    for file in $online_cpu_curfreq; do
        if [[ -r "$file" ]]; then
            cpu_core=$(echo "$file" | awk -F'/' '{print $6}')
            frequency=$(cat "$file")
            
            # Send to InfluxDB only
            if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
                send_to_influxdb "$timestamp" "$cpu_core" "$frequency"
            fi
        fi
    done
    
    sleep $delay
done
