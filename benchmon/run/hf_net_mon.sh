#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_net_stat=$2

echo "timestamp,interface,rx-bytes,rx-packets,rx-errs,rx-drop,rx-fifo,rx-frame,rx-compressed,rx-multicast,tx-bytes,tx-packets,tx-errs,tx-drop,tx-fifo,tx-colls,tx-carrier,tx-compressed" > $report_net_stat

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
