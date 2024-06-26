#!/usr/bin/bash

_SYS_PID=$(cat ./.benchmonspc_sys_pid)
_POW_PID=$(cat ./.benchmonspc_pow_pid)

kill -15 $_SYS_PID
kill -15 $(ps -o pid= --ppid $_POW_PID) $_POW_PID
