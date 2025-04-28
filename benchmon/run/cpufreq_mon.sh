#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_cpu_freq=$2
cpu_freq_min=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq)
cpu_freq_max=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
echo "timestamp,cpu_core,frequency[$cpu_freq_min-$cpu_freq_max]" > $report_cpu_freq

online_cpu_curfreq=$(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat $file) = 1 ]]; then echo $(dirname $file)/cpufreq/scaling_cur_freq; fi; done)
online_cpu_curfreq="/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq $online_cpu_curfreq"

while true
do
    cat $online_cpu_curfreq | awk -F'/' -v timestamp="$(date +'%s.%N')" '{split(FILENAME, a, "/"); print timestamp "," a[6] "," $0}' $online_cpu_curfreq >> $report_cpu_freq

    sleep $delay
done
