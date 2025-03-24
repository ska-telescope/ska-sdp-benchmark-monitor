#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_ib_stat=./hf_ib_report.csv #$2
echo -n "" > $report_ib_stat

# echo "$(ls /sys/class/net | wc -l)" > $report_ib_stat
echo "timestamp,ib-interf:port,metric-key,metric-value" > $report_ib_stat

while true
do
    timestamp="$(date +'%s.%N')"
    for file in /sys/class/infiniband/*/ports/1/counters/port*data; do
        echo $timestamp,$(echo $file | awk -F'/' '{print $5":"$7","$9}'),$(cat $file) >> $report_ib_stat
    done

    sleep $delay
done
