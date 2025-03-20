#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_net_stat=$2
echo -n "" > $report_net_stat

echo "$(ls /sys/class/net | wc -l)" > $report_net_stat

while true
do
    awk -v timestamp="$(date +'%s.%N')" 'NR>2 {
        $1 = $1;
        printf "%s", timestamp;
        for (i=1; i<=NF; i++) {
            printf ",%s", $i;
        }
        print "";
    }' /proc/net/dev >> $report_net_stat

    sleep $delay
done
