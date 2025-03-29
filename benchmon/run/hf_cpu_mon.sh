#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_cpu_stat=$2
echo -n "" > $report_cpu_stat

while true
do
    cat /proc/stat | grep cpu | awk -v timestamp="$(date +'%s.%N')" '{ $1 = timestamp "," $1; print }' OFS="," >> $report_cpu_stat

    sleep $delay
done
