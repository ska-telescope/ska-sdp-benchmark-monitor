#!/bin/bash

# High-performance Memory monitoring with direct InfluxDB output

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2 # Not used
grafana_enabled=$3
influxdb_pipe=$4

# These fields MUST match the order in hp_processor.py's _process_memory_data
MEMORY_FIELDS="MemTotal MemFree MemAvailable Buffers Cached SwapCached Active Inactive SwapTotal SwapFree"

while true; do
    timestamp=$(date +'%s.%N')

    if [[ "$grafana_enabled" == "true" && -n "$influxdb_pipe" ]]; then
        # Read all required values from /proc/meminfo
        values_line=$(grep -E "^($(echo $MEMORY_FIELDS | sed 's/ /|/g')):" /proc/meminfo | awk '{print $2}' | paste -sd, -)
        
        # Format: MEMORY|timestamp|value1,value2,value3...
        echo "MEMORY|$timestamp|$values_line" > "$influxdb_pipe"
    fi

    sleep "$delay"
done
            
            if [[ -n "$value" ]]; then
                # Format: MEMORY|timestamp|value metric=<metric_name> hostname=<fqdn>
                echo "MEMORY|$timestamp|$value metric=$metric hostname=$HOST_FQDN" > "$influxdb_pipe"
            fi
        done
    fi

    sleep "$delay"
done
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
