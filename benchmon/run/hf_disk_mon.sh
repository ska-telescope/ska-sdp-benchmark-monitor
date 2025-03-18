#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_disk_stat=$2
echo -n "" > $report_disk_stat

echo $(lsblk -d -o NAME --noheadings | wc -l) > $report_disk_stat # Number of major blocks
echo $(lsblk -o NAME --noheadings | wc -l) >> $report_disk_stat   # Number of all blocks
echo $(lsblk -d -o NAME,PHY-SEC --noheadings | awk '{printf "%s,%s,", $1, $2}' | sed 's/,$/\n/') >> $report_disk_stat # Sector size by major block

while true
do
    awk -v timestamp="$(date +'%s.%N')" '{
        $1 = $1;
        printf "%s", timestamp;
        for (i=1; i<=NF; i++) {
            printf ",%s", $i;
        }
        print "";
    }' /proc/diskstats >> $report_disk_stat

    sleep $delay
done
