#!/usr/bin/bash

# High-performance network monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular net_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
enable_grafana=$3
influxdb_pipe=$4

# Function to send data to InfluxDB via HP processor
send_to_influxdb() {
    local timestamp=$1
    local interface=$2
    local rx_bytes=$3
    local rx_packets=$4
    local rx_errs=$5
    local rx_drop=$6
    local rx_fifo=$7
    local rx_frame=$8
    local rx_compressed=$9
    local rx_multicast=${10}
    local tx_bytes=${11}
    local tx_packets=${12}
    local tx_errs=${13}
    local tx_drop=${14}
    local tx_fifo=${15}
    local tx_colls=${16}
    local tx_carrier=${17}
    local tx_compressed=${18}
    
    # HP processor format: NETWORK|timestamp|interface rx_bytes rx_packets ... tx_bytes tx_packets ...
    echo "NETWORK|$timestamp|$interface $rx_bytes $rx_packets $rx_errs $rx_drop $rx_fifo $rx_frame $rx_compressed $rx_multicast $tx_bytes $tx_packets $tx_errs $tx_drop $tx_fifo $tx_colls $tx_carrier $tx_compressed" > "$influxdb_pipe"
}

while true
do
    timestamp="$(date +'%s.%N')"
    
    # Send data to InfluxDB if Grafana is enabled
    if [[ "$enable_grafana" == "true" && -n "$influxdb_pipe" ]]; then
        while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                # Parse the line from /proc/net/dev
                interface=$(echo "$line" | awk '{gsub(/:/, "", $1); print $1}')
                rx_bytes=$(echo "$line" | awk '{print $2}')
                rx_packets=$(echo "$line" | awk '{print $3}')
                rx_errs=$(echo "$line" | awk '{print $4}')
                rx_drop=$(echo "$line" | awk '{print $5}')
                rx_fifo=$(echo "$line" | awk '{print $6}')
                rx_frame=$(echo "$line" | awk '{print $7}')
                rx_compressed=$(echo "$line" | awk '{print $8}')
                rx_multicast=$(echo "$line" | awk '{print $9}')
                tx_bytes=$(echo "$line" | awk '{print $10}')
                tx_packets=$(echo "$line" | awk '{print $11}')
                tx_errs=$(echo "$line" | awk '{print $12}')
                tx_drop=$(echo "$line" | awk '{print $13}')
                tx_fifo=$(echo "$line" | awk '{print $14}')
                tx_colls=$(echo "$line" | awk '{print $15}')
                tx_carrier=$(echo "$line" | awk '{print $16}')
                tx_compressed=$(echo "$line" | awk '{print $17}')
                
                send_to_influxdb "$timestamp" "$interface" "$rx_bytes" "$rx_packets" "$rx_errs" "$rx_drop" "$rx_fifo" "$rx_frame" "$rx_compressed" "$rx_multicast" "$tx_bytes" "$tx_packets" "$tx_errs" "$tx_drop" "$tx_fifo" "$tx_colls" "$tx_carrier" "$tx_compressed"
            fi
        done < <(awk 'NR>2 {print}' /proc/net/dev)
    fi

    sleep $delay
done
