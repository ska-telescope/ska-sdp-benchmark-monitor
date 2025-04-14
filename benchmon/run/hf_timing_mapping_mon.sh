#!/usr/bin/bash

# Pass frequency as first argument, output filename as second, no-mapping as third to skipping mapping 
freq=$1
output=$2
if [ "$3" = 'no-mapping' ]; then
    ps_fields="ppid,pid,tid,etimes,lstart,cmd";
    awk_fields='$1, $2, $3'
else
    ps_fields="ppid,pid,tid,cpuid,etimes,lstart,cmd"
    awk_fields='$1, $2, $3, $4'
fi

# Manage termination
trap 'echo "#" "$(ps -o $ps_fields|head -1)" "$(sort -s -nk3 <(echo "$journal"))" > $output; exit 0' SIGTERM

# Determine sampling period
sampl=$(bc <<< "scale=6; 1/$freq")

# We assume we want to measure processes running under the same parent process
root_pid=${PPID}
# and want to skip the measuring process itself
skip_pid=$$

# Get all info from ps to have coherent time stamps
# Identify what to save to journal with diff (without etime)
# then save the complete record to have the elapsed time too

# Collect all data with ps to then process it: e all processes, T including threads, o to define output
# processes have tid matching pid, with -T threads have their parent PID shown, use ww and place cmd
# last to have them untruncated
# ps's native sorting does not seem compatible with listing threads: revert to sort on tid
psfull="ps --no-header -eTwwo $ps_fields | sort -nk3"
echo "$psfull"

# Recursively search for child processes and threads with awk
psold_full="$(eval $psfull | awk -vpp=$root_pid -vp=$skip_pid 'function r(s,e){if(s!=e) {print ps_string[s];s=child_id[s];while(s){sub(",","",s);t=s;sub(",.*","",t);sub("[0-9]+","",s);r(t,e)}}}{child_id[$1]=child_id[$1]","$3;ps_string[$3]=$0}END{r(pp,p)}')"

# Retain only ppid, pid, tid and cpuid (except for no-mapping where cpuid is skipped)
psold="$(echo "$psold_full" | awk '{print '"$awk_fields"'}')"

# Now do this at every new time step and save only lines corresponding to processes and threads
# that have finished or that have moved to a new cpuid

while true
do
    sleep $sampl
    psnew_full="$(eval $psfull | awk -vpp=$root_pid -vp=$skip_pid 'function r(s,e){if(s!=e) {print ps_string[s];s=child_id[s];while(s){sub(",","",s);t=s;sub(",.*","",t);sub("[0-9]+","",s);r(t,e)}}}{child_id[$1]=child_id[$1]","$3;ps_string[$3]=$0}END{r(pp,p)}')"
    psnew="$(echo "$psnew_full" | awk '{print '"$awk_fields"'}')"

    # Compare psold and psnew with diff
    difflines="$(diff <(echo "$psold") <(echo "$psnew"))"

    # Extract line numbers of deletions/changes in psold and print the correspondine lines of
    # psold_full with awk. Depending on the sequence, line suppression corresponding
    # to completed processes/threads can appear as deletions or changes. Deletions will have to
    # be identified based on the fact that this is the last change recorded for this process/thread
    # (sort based on tid: all records execpt for the last correspond to mapping to different cores,
    # and the last to completion).
    newlines=$(awk 'BEGIN{i=1; j=1} (FILENAME==ARGV[1] && /^[0-9,]+[cd][0-9,]+/) {split($0, a, "[cd]"); n=split(a[1], b, ","); if(n==1) {b[2]=b[1]}; for(k=b[1];k<=b[2];k++) {line[i++]=k}; next} FILENAME==ARGV[2]{psfull[j++]=$0; next} END{for(k=1;k<i;k++) {print psfull[line[k]]}}' <(echo "$difflines") <(echo "$psold_full"))

    # If something is returned by awk, append to the journal variable with a final new line
    if [ "$newlines" != '' ]; then journal+="$newlines"; journal+=$'\n'; fi

    # Exchange psold and psnew and full entries
    psold=$psnew
    psold_full=$psnew_full
done
