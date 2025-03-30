#!/usr/bin/bash

freq=$1
sampl=$(bc <<< "scale=6; 1/$freq")

report=$2
echo 'timestamp,'$(cat /proc/meminfo | awk -F: '{printf "%s%s", $1, (NR==NR_END ? "" : ",")}' | sed 's/,$/\n/') > $report

while true
do
    echo $(date +'%s.%N'),$(cat /proc/meminfo | awk '{printf (NR==1 ? "%s" : ",%s", $2)} END {print ""}') >> $report
    sleep $sampl
done
