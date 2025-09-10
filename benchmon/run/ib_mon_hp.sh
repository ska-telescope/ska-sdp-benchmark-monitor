#!/usr/bin/bash

# High-performance InfiniBand monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular ib_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

# Check if Infiband is available
cat /sys/class/infiniband/*/ports/1/counters/port*data >/dev/null 2>&1
retval=$?
if [ $retval != 0 ]; then
    echo "Infiniband is not available"
    exit 0
fi

csv_file=$2  # Not used, always /dev/null
enable_grafana=$3
influxdb_pipe=$4

# Function to send data to InfluxDB
send_to_influxdb() {
    local timestamp_ns=$1
    local interface=$2
    local port=$3
    local metric_key=$4
    local metric_value=$5
    local hostname=$(hostname)
    
    # Convert timestamp to nanoseconds if needed
    if [[ $timestamp_ns == *.* ]]; then
        timestamp_ns=$(echo "$timestamp_ns * 1000000000" | bc | cut -d. -f1)
    else
        timestamp_ns="${timestamp_ns}000000000"
    fi
    
    # InfluxDB Line Protocol format
    echo "infiniband_stats,host=$hostname,interface=$interface,port=$port,metric=$metric_key value=$metric_value $timestamp_ns" > "$influxdb_pipe"
}

while true
do
    timestamp="$(date +'%s.%N')"
    
    # Send data to InfluxDB only
    if [[ "$enable_grafana" == "true" && -n "$influxdb_pipe" ]]; then
        for file in /sys/class/infiniband/*/ports/1/counters/port*data; do
            if [[ -r "$file" ]]; then
                interface=$(echo $file | awk -F'/' '{print $5}')
                port=$(echo $file | awk -F'/' '{print $7}')
                metric_key=$(echo $file | awk -F'/' '{print $9}')
                metric_value=$(cat $file)
                send_to_influxdb "$timestamp" "$interface" "$port" "$metric_key" "$metric_value"
            fi
        done
    fi

    sleep $delay
done
