#!/usr/bin/bash

# High-performance disk monitoring with direct InfluxDB output
# This script only handles InfluxDB output, CSV is handled by regular disk_mon.sh

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")
csv_file=$2  # Not used, always /dev/null
enable_grafana=$3
influxdb_pipe=$4

# Function to send data to InfluxDB via HP processor
send_to_influxdb() {
    local timestamp=$1
    local major=$2
    local minor=$3
    local device=$4
    local rd_cd=$5
    local rd_md=$6
    local sect_rd=$7
    local time_rd=$8
    local wr_cd=$9
    local wr_md=${10}
    local sect_wr=${11}
    local time_wr=${12}
    local io_ip=${13}
    local time_io=${14}
    local time_wei_io=${15}
    local disc_cd=${16}
    local disc_md=${17}
    local sect_disc=${18}
    local time_disc=${19}
    local flush_req=${20}
    local time_flush=${21}
    
    # HP processor format: DISK|timestamp|major minor device rd_cd rd_md sect_rd ... (following /proc/diskstats format)
    echo "DISK|$timestamp|$major $minor $device $rd_cd $rd_md $sect_rd $time_rd $wr_cd $wr_md $sect_wr $time_wr $io_ip $time_io $time_wei_io" > "$influxdb_pipe"
}

while true
do
    timestamp="$(date +'%s.%N')"
    
    # Send data to InfluxDB only
    if [[ "$enable_grafana" == "true" && -n "$influxdb_pipe" ]]; then
        while read -r line; do
            if [[ -n "$line" ]]; then
                read -r major minor device rd_cd rd_md sect_rd time_rd wr_cd wr_md sect_wr time_wr io_ip time_io time_wei_io disc_cd disc_md sect_disc time_disc flush_req time_flush <<< "$line"
                send_to_influxdb "$timestamp" "$major" "$minor" "$device" "$rd_cd" "$rd_md" "$sect_rd" "$time_rd" "$wr_cd" "$wr_md" "$sect_wr" "$time_wr" "$io_ip" "$time_io" "$time_wei_io" "$disc_cd" "$disc_md" "$sect_disc" "$time_disc" "$flush_req" "$time_flush"
            fi
        done < <(grep -v loop /proc/diskstats | grep -v dm)
    fi

    sleep $delay
done
