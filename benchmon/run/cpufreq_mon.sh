#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_cpu_freq=$2
cpu0_repo=/sys/devices/system/cpu/cpu0
cpu_freq_min=$(cat ${cpu0_repo}/cpufreq/cpuinfo_min_freq)
cpu_freq_max=$(cat ${cpu0_repo}/cpufreq/cpuinfo_max_freq)
echo "timestamp,cpu_core,frequency[$cpu_freq_min-$cpu_freq_max]" > $report_cpu_freq

online_cpu_curfreq=$(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat $file) = 1 ]]; then echo $(dirname $file)/cpufreq/scaling_cur_freq; fi; done)

test -e ${cpu0_repo}/online || online_cpu_curfreq="${cpu0_repo}/cpufreq/scaling_cur_freq $online_cpu_curfreq"

while true
do
    cat $online_cpu_curfreq | awk -F'/' -v timestamp="$(date +'%s.%N')" '{split(FILENAME, a, "/"); print timestamp "," a[6] "," $0}' $online_cpu_curfreq >> $report_cpu_freq

    sleep $delay
done
