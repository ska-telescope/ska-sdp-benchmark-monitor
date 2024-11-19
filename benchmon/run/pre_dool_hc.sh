#!/usr/bin/bash

trace_repo=$1

echo "cpu_freq_min: $(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq)" > ${trace_repo}/sys_info.txt
echo "cpu_freq_max: $(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)" >> ${trace_repo}/sys_info.txt

_online_cores=$(echo $(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat $file) = 1 ]]; then echo $(basename $(dirname $file)); fi; done) | sed 's/cpu//g')
_offline_cores=$(echo $(for file in /sys/devices/system/cpu/cpu*/online; do  if [[ $(cat    $file) = 0 ]]; then echo $(basename $(dirname $file)); fi; done) | sed 's/cpu//g')
echo "online_cores: -1 0 $_online_cores" >> ${trace_repo}/sys_info.txt
echo "offline_cores: -1 $_offline_cores" >> ${trace_repo}/sys_info.txt
