#!/usr/bin/bash

_HOSTNAME=$(hostname | cut -d '.' -f 1)

sudo_perf_cmd=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --sudo-perf-cmd)
            sudo_perf_cmd=$2
            shift 2
            ;;
    esac
done

_SYS_PID_FILE=./.benchmonspc_sys_pid_${_HOSTNAME}
if [[ -f ${_SYS_PID_FILE} ]]
then
    _SYS_PID=$(cat ${_SYS_PID_FILE})
    kill -15 ${_SYS_PID}
    rm -v ${_SYS_PID_FILE}
fi

_POW_PID_FILE=./.benchmonspc_pow_pid_${_HOSTNAME}
if [[ -f ${_POW_PID_FILE} ]]
then
    _POW_PID=$(cat ${_POW_PID_FILE})
    $sudo_perf_cmd kill -15 $(ps -o pid= --ppid ${_POW_PID}) ${_POW_PID}
    rm -v ${_POW_PID_FILE}
fi
