#!/usr/bin/bash -x

# Parameters
APP=/usr/bin/hostname # $HOME/BENCHMARKS/NAS/NPB3.4.2/NPB3.4-OMP/bin/ft.B.x
TRACES_REPO=./my_traces_repo
SUB_TRACES_REPO=$TRACES_REPO/$(hostname | cut -d "." -f 1)

# Run App within benchmonspc (to record the callstack)
./benchmonspc.sh --sys --pow --call --call-freq 10 --traces-repo $TRACES_REPO --sudo-perf-cmd sudo-g5k --wait 5 $APP

./benchmonspc_visu.py --cpu --cpu-all --mem --io --net --pow --call --call-depth 3 --fig-fmt svg,png --traces-repo $SUB_TRACES_REPO
