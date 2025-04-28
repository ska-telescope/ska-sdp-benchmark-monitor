#!/usr/bin/bash

freq=$1
delay=$(bc <<< "scale=6; 1/$freq")

report_disk_stat=$2

echo $(lsblk -d -o NAME --noheadings | grep -v loop | wc -l) > $report_disk_stat # Number of major blocks
echo $(lsblk -o NAME --noheadings | grep -v loop | wc -l) >> $report_disk_stat   # Number of all blocks
echo $(lsblk -d -o NAME,PHY-SEC --noheadings | grep -v loop | awk '{printf "%s,%s,", $1, $2}' | sed 's/,$/\n/') >> $report_disk_stat # Sector size by major block

echo "timestamp,major,minor,device,#rd-cd,#rd-md,sect-rd,time-rd,#wr-cd,#wr-md,sect-wr,time-wr,#io-ip,time-io,time-wei-io,#disc-cd,#disc-md,sect-disc,time-disc,#flush-req,time-flush" >> $report_disk_stat

while true
do
    awk -v timestamp="$(date +'%s.%N')" '{
        $1 = $1;
        printf "%s", timestamp;
        for (i=1; i<=NF; i++) {
            printf ",%s", $i;
        }
        print "";
    }' /proc/diskstats | grep -v loop >> $report_disk_stat

    sleep $delay
done
