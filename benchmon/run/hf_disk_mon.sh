#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_disk_stat=$2

# echo "$(cat /proc/diskstats | wc -l)" > $report_disk_stat # or ip link show | grep -c '^[0-9]'

echo $(lsblk -d -o NAME --noheadings | wc -l) > $report_disk_stat # Number of major blocks
echo $(lsblk -o NAME --noheadings | wc -l) >> $report_disk_stat   # Number of all blocks
echo $(lsblk -d -o NAME,PHY-SEC --noheadings | awk '{printf "%s,%s,", $1, $2}' | sed 's/,$/\n/') >> $report_disk_stat # Sector size by major block

while true
do
    awk '{gsub(/ +/, ","); print}' /proc/diskstats | sed 's/^,//' | awk -v timestamp="$(date +'%s.%N')" '{print timestamp","$0}' >> $report_disk_stat
    sleep $delay
done
