#!/usr/bin/bash

# [-tr|--tr|--traces-repo]
# [-s|--sys]
# [-sd|--sd|--sys-delay]
# [-p|--pow]
# [-pb|--pb|--pow-bin]
# [-pd|--pd|--pow-delay]
# [-c|--call]
# [-cm|--cm|--call-mode]
# [-cf|--cf|--call-freq]
# [-ws|--ws|--wait]
# [--sudo-perf]
# [--sudo-perf-command]

# echo '$#=' "$#"
# echo '$*=' "$*"
# echo '$1' "$1"
HOSTNAME=$(hostname | cut -d '.' -f 1)
trace_repo=./benchmonspc_traces_${OAR_JOB_ID}${SLURM_JOB_ID} #_$(date "+%s")

# Init system tracing
is_sys=0
sys_bin=$HOME/bin/dool
sys_delay=1

# Perf requires sudo?
is_sudo_perf=""
sudo_perf_cmd=""

# Init power profiling
is_pow=0
pow_bin=perf
pow_delay=500

# Init callstack tracking
is_call=0
call_mode="dwarf"
call_freq=10

# Init wait seconds
wait_seconds=0

# Multinode
is_multi_node=0

# Application
app=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -tr|--tr|--traces-repo)
            if [[ -n $2 && $2 != -* ]]
            then
                trace_repo=$2
                shift 2
            else
                echo "Error: -tr, --tr, --traces-repo requires a value"
                # usage
                exit 1
            fi
            ;;
        -s|--sys)
            is_sys=1
            shift
            ;;
        -sb|--sb|--sys-bin)
            if [[ -n $2 && $2 != -* ]]
            then
                sys_bin=$2
                shift 2
            else
                echo "Error: -sb, --sb, --sys-bien requires a value"
                # usage
                exit 1
            fi
            ;;
        -sd|--sd|--sys-delay)
            if [[ -n $2 && $2 != -* ]]
            then
                sys_delay=$2
                shift 2
            else
                echo "Error: -sd, --sd, --sys-delay requires a value"
                # usage
                exit 1
            fi
            ;;
        --sudo-perf)
            is_sudo_perf="sudo"
            shift
            ;;
        --sudo-perf-cmd)
            sudo_perf_cmd=$2
            shift 2
            ;;
        -p|--pow)
            is_pow=1
            shift
            ;;
        -pb|--pb|--pow-bin)
            if [[ -n $2 && $2 != -* ]]
            then
                pow_bin=$2
                shift 2
            else
                echo "Error: -sb, --sb, --sys-bien requires a value"
                # usage
                exit 1
            fi
            ;;
        -pd|--pd|--pow-delay)
            if [[ -n $2 && $2 != -* ]]
            then
                pow_delay=$2
                shift 2
            else
                echo "Error: -pd, --pd, --pow-delay requires a value"
                # usage
                exit 1
            fi
            ;;
        -c|--call)
            is_call=1
            shift
            ;;
        -cm|--cm|--call-mode)
            if [[ -n $2 && $2 != -* ]]
            then
                call_mode=$2
                shift 2
            else
                echo "Error: -cm, --cm, --call-mode requires a value"
                # usage
                exit 1
            fi
            ;;
        -cf|--cf|--call-freq)
            if [[ -n $2 && $2 != -* ]]
            then
                call_freq=$2
                shift 2
            else
                echo "Error: -cf, --cf, --call-freq requires a value"
                # usage
                exit 1
            fi
            ;;
        -ws|--ws|--wait)
            if [[ -n $2 && $2 != -* ]]
            then
                wait_seconds=$2
                shift 2
            else
                echo "Error: -ws, --ws, --wait requires a value"
                # usage
                exit 1
            fi
            ;;
        -mn|--multi-node)
            is_multi_node=1
            shift
            ;;
        *)
            app=$@
            break
            ;;
    esac
done

# Reports
if [[ $is_multi_node = 1 ]]
then
    trace_repo=$trace_repo/${HOSTNAME}
fi
mkdir -p ${trace_repo}
trace_repo=$(realpath ${trace_repo})
sys_report=${trace_repo}/sys_report.csv
pow_report=${trace_repo}/pow_report.csv
call_report=${trace_repo}/call_report.txt
mono_to_real_file=${trace_repo}/mono_to_real_file.txt

# Print traces repo if app is not given
if [[ -z $app ]]
then
    echo "BENCHMARK MONITOR (sys+pow+call) -----------------"
    echo "Traces repo: $trace_repo"
    echo "--------------------------------------------------"
fi

# System resources tracing
if [[ $is_sys = 1 ]]
then
    mkdir -p $(dirname $sys_report)
    echo -n "" > $sys_report
    $sys_bin --epoch --mem --swap --io --aio --disk --fs --net --cpu --cpu-use --output $sys_report $sys_delay &
    _SYS_PID=$!
fi

# Power events detection
if [[ $is_pow = 1 ]]
then
    _perf_power_events=$(perf list | grep -i power/energy | awk '{print $1}')
    _perf_events_flag=""
    for _event in $_perf_power_events
    do
        _perf_events_flag="$_perf_events_flag -e $_event"
    done
fi

# Power profiling
if [[ $is_pow = 1 ]]
then
    mkdir -p $(dirname $pow_report)
    echo -n "" > $pow_report
    $sudo_perf_cmd perf stat -A -a $_perf_events_flag -I $pow_delay -x , -o $pow_report &
    _POW_PID=$!
fi

sleep $wait_seconds

# Callstack tracking
if [[ $is_call = 1 ]]
then
    if [[ -z $app ]]
    then
        echo "Error: Application is required"
        exit 1
    fi
    _temp_perf_date_file=${trace_repo}/_temp_perf.data
    $(dirname $0)/mono_to_real -o ${mono_to_real_file}
    $sudo_perf_cmd perf record --running-time -T -a -F $call_freq --call-graph=$call_mode -o $_temp_perf_date_file $app
else
    eval $app
fi

sleep $wait_seconds

# Stop power profiling
if [[ $is_pow = 1 && -n $app ]]
then
    $sudo_perf_cmd kill -15 $(ps -o pid= --ppid $_POW_PID) $_POW_PID
fi &> /dev/null

# Stop system resources tracing
if [[ $is_sys = 1 && -n $app ]]
then
    kill -15 $_SYS_PID &> /dev/null
fi

# Create callgraph file
if [[ $is_call = 1 ]]
then
    perf script -F trace:comm,pid,tid,cpu,time,event -i ${_temp_perf_date_file} > ${call_report}
    rm ${_temp_perf_date_file}
fi

# Output
if [[ -z $app ]]
then
    if [[ $is_sys = 1 ]]
    then
        echo $_SYS_PID >> ./.benchmonspc_sys_pid_${HOSTNAME}
    fi

    if [[ $is_pow = 1 ]]
    then
        echo $_POW_PID >> ./.benchmonspc_pow_pid_${HOSTNAME}
    fi
else
    echo "BENCHMARK MONITOR (sys+pow+call) -----------------"
    echo -e "\tApplication: $app"
    echo -e "\tTraces repo: $trace_repo\n"
    if [[ $is_sys = 1 ]]
    then
        echo -e "\tSys tracing: True"
        echo -e "\tSys bin    : $sys_bin"
        echo -e "\tSys delay  : $sys_delay Seconds"
    else
        echo -e "\tSys tracing:   False"
    fi
    echo ""
    if [[ $is_pow = 1 ]]
    then
        echo -e "\tPow profiling: True"
        echo -e "\tPow bin      : $pow_bin"
        echo -e "\tPow delay    : $pow_delay Milliseconds"
        echo -e "\tPow events   :" $_perf_power_events
    else
        echo -e "\tPow tracing:   False"
    fi
    echo ""
    if [[ $is_call = 1 ]]
    then
        echo -e "\tCall tracing: True"
        echo -e "\tCall mode   : $call_mode"
        echo -e "\tCall freq   : $call_freq Hz"
    else
        echo -e "\tCall tracing: False"
    fi
    echo -e ""
    echo -e "\tWait seconds: $wait_seconds" Seconds
    echo "--------------------------------------------------"
fi
