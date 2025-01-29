#!/usr/bin/bash

freq=$1
sampl=$(bc <<< "scale=6; 1/$freq")

report_cpu_stat=$2
echo -n "" > $report_cpu_stat

report_cpu_freq=$3
echo -n "" > $report_cpu_freq

while true
do
    cat /proc/stat | grep cpu | awk -v timestamp="$(date +'%s.%N')" '{ $1 = timestamp "," $1; print }' OFS="," >> $report_cpu_stat

    cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq | awk -F'/' -v timestamp="$(date +'%s.%N')" '{split(FILENAME, a, "/"); print timestamp "," a[6] "," $0}' /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq >> $report_cpu_freq

    sleep $sampl
done
