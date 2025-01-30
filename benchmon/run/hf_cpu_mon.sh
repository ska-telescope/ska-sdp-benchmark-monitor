#!/usr/bin/bash

freq=$1
sampl=$(bc <<< "scale=6; 1/$freq")

report_cpu_stat=$2
echo -n "" > $report_cpu_stat

report_cpu_freq=$3
echo -n "" > $report_cpu_freq

online_cpu_curfreq=$(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat $file) = 1 ]]; then echo $(dirname $file)/cpufreq/scaling_cur_freq; fi; done)
online_cpu_curfreq="/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq $online_cpu_curfreq"


while true
do
    cat /proc/stat | grep cpu | awk -v timestamp="$(date +'%s.%N')" '{ $1 = timestamp "," $1; print }' OFS="," >> $report_cpu_stat

    cat $online_cpu_curfreq | awk -F'/' -v timestamp="$(date +'%s.%N')" '{split(FILENAME, a, "/"); print timestamp "," a[6] "," $0}' $online_cpu_curfreq >> $report_cpu_freq

    sleep $sampl
done
