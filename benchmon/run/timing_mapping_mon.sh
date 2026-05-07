#!/usr/bin/bash

# Pass frequency as first argument, output filename as second, no-mapping as third to skipping mapping 
freq=$1
output=$2
journal=""
node=$(hostname)
ultimate=false
terminate=false

if [ "$3" = 'no-mapping' ]; then
    mapping=false
    ps_fields="ppid,pid,tid,etimes,lstart,cmd"
    awk_fields='$1, $2, $3'
    lst_start=5
    cmd_start=6
else
    mapping=true
    ps_fields="ppid,pid,tid,cpuid,etimes,lstart,cmd"
    awk_fields='$1, $2, $3, $4'
    lst_start=6
    cmd_start=7
fi

# Use a wrapper function to format ps's output: change lstart to seconds since the Epoch
# (1970-01-01 00:00 UTC) since the "-D %s" argument is not standard across systems
ps_reformat () {
   local ps_in ps_out lstart_iso lstart_s
   ps_in=$(eval ps "$@")
   ps_out=$(awk -vlst_start=$lst_start '{for (i=1; i<=NF; i++) if (i==lst_start) {date_cmd="date --date=\"" $i" "$(i+1)" "$(i+2)" "$(i+3)" "$(i+4) "\" '\''+%s'\''"; date_cmd | getline date_res; close(date_cmd); printf "%s ", date_res; i=lst_start+4;} else {if (i!=NF) printf "%s ", $i;else printf "%s\n", $i}}' <(echo "$ps_in"))
   echo "$ps_out"   
}

# Manage termination with one last iteration of the loop
trap 'ultimate=true' SIGTERM SIGUSR1

# Determine sampling period
sampl=$(bc <<< "scale=6; 1/$freq")

# We assume we want to measure processes running under the same parent process
root_pid=${PPID}
# and want to skip the measuring process itself
skip_pid=$$

# Get all info from ps to have coherent time stamps
# Identify what to save to journal with diff (without etime)
# then save the complete record to have the elapsed time too
# (note that this is the total time the thread has existed since
# its creation, not the time it spent on a given core)

# Collect all data with ps to then process it: e all processes, T including threads, o to define output
# processes have tid matching pid, with -T threads have their parent PID shown, use ww and place cmd
# last to have them untruncated
# ps's native sorting does not seem compatible with listing threads: revert to sort on tid
psfull="ps_reformat --no-header -eTwwo $ps_fields | sort -nk3"

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
    # (sort based on tid: all records except for the last correspond to mapping to different cores,
    # and the last to completion).
    
    newlines=$(awk 'BEGIN{i=1; j=1} (FILENAME==ARGV[1] && /^[0-9,]+[cd][0-9,]+/) {split($0, a, "[cd]"); n=split(a[1], b, ","); if(n==1) {b[2]=b[1]}; for(k=b[1];k<=b[2];k++) {line[i++]=k}; next} FILENAME==ARGV[2]{psfull[j++]=$0; next} END{for(k=1;k<i;k++) {print psfull[line[k]]}}' <(echo "$difflines") <(echo "$psold_full"))

    # If something is returned by awk, append to the journal variable with a final new line
    if [ "$newlines" != '' ]; then
	    stages=$(awk -vcmd_start="$cmd_start" '{for (i=cmd_start; i<=NF; i++) if (i!=NF) {printf "%s ", $i;} else {printf "%s\n", $i;}}' <(echo "$newlines"))

	    # START line
            if [ "$mapping" = true ]; then
 		    events=$(awk -vNODE=$node 'NR==FNR {stage_line[FNR]=$0} NR!=FNR {printf "%d,THREAD,%s,START,%s,%d,ps,PPID:%d PID:%d,%d\n", $6, stage_line[FNR], NODE, $3, $1, $2, $4}' <(echo "$stages") <(echo "$newlines"))
            else
		    events=$(awk -vNODE=$node 'NR==FNR {stage_line[FNR]=$0} NR!=FNR {printf "%d,THREAD,%s,START,%s,%d,ps,PPID:%d PID:%d,\n", $5, stage_line[FNR], NODE, $3, $1, $2}' <(echo "$stages") <(echo "$newlines"))
	    fi
	    journal+="$events"; journal+=$'\n'

	    # STOP line
	    if [ "$mapping" = true ]; then
		    events=$(awk -vNODE=$node 'NR==FNR {stage_line[FNR]=$0} NR!=FNR {printf "%d,THREAD,%s,FINISHED,%s,%d,ps,PPID:%d PID:%d elapsed:%d,%d\n", $6+$5+1, stage_line[FNR], NODE, $3, $1, $2, $5+1, $4}' <(echo "$stages") <(echo "$newlines"))
	    else
		    events=$(awk -vNODE=$node 'NR==FNR {stage_line[FNR]=$0} NR!=FNR {printf "%d,THREAD,%s,FINISHED,%s,%d,ps,PPID:%d PID:%d elapsed:%d,\n", $5+$4+1, stage_line[FNR], NODE, $3, $1, $2, $4+1}' <(echo "$stages") <(echo "$newlines"))
            fi
	    journal+="$events"; journal+=$'\n'
    fi

    # Exchange psold and psnew and full entries
    psold=$psnew
    psold_full=$psnew_full

    # Handle termination with one last iteration of the while loop to report the end of subprocesses
    if [ $terminate = true ]; then
            printf "%s\n%s" "timestamp,pipeline,stage,event,node,process,source,message,core" "$journal" > ${output}
	    exit 0
    fi
    if [ $ultimate = true ]; then
	    terminate=true
    fi

done
