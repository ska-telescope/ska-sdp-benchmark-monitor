#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_net_stat=$2
echo -n "" > $report_net_stat

echo "$(ls /sys/class/net | wc -l)" > $report_net_stat # or ip link show | grep -c '^[0-9]'

while true
do
    awk 'NR>2 {gsub(/ +/, ","); print}' /proc/net/dev | sed 's/^,//' | awk -v timestamp="$(date +'%s.%N')" '{print timestamp","$0}' >> $report_net_stat
    sleep $delay
done
