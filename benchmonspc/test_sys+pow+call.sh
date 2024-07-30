#!/usr/bin/bash -x

# Parameters
APP=$HOME/BENCHMARKS/NAS/NPB3.4.2/NPB3.4-OMP/bin/ft.B.x # /usr/bin/hostname
TRACES_REPO=./my_traces_repo

# Run App within benchmonspc (to record the callstack)
./benchmonspc.sh --sys --pow --call --call-freq 10 --traces-repo $TRACES_REPO --sudo-perf-cmd sudo-g5k --wait 5 $APP

./benchmonspc_visu.py --cpu --cpu-all --mem --io --net --pow --call --call-depth 4 --fig-fmt svg,png --traces-repo $TRACES_REPO
