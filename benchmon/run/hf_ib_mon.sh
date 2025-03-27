#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

# Check if Infiband is available
cat /sys/class/infiniband/*/ports/1/counters/port*data
retval=$?
if [ $retval != 0 ]; then
    echo "Infiniband is not available"
    exit 0
fi

# Init report file
report_ib_stat=$2
echo -n "" > $report_ib_stat

echo "timestamp,ib-interf:port,metric-key,metric-value" > $report_ib_stat

while true
do
    timestamp="$(date +'%s.%N')"
    buff=""
    for file in /sys/class/infiniband/*/ports/1/counters/port*data; do
        buff+="$timestamp,$(echo $file | awk -F'/' '{print $5":"$7","$9}'),$(cat $file)\n"
    done
    echo -ne $buff >> $report_ib_stat

    sleep $delay
done
