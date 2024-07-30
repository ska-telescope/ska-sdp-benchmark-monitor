#!/usr/bin/bash -x

# Parameters
APP=$HOME/BENCHMARKS/NAS/NPB3.4.2/NPB3.4-OMP/bin/ft.B.x # /usr/bin/hostname
TRACES_REPO=./my_traces_repo

# Run benchmonspc
./benchmonspc.sh --sys --pow --traces-repo $TRACES_REPO --sudo-perf-cmd sudo-g5k

# Run App
sleep 5
eval $APP
sleep 5

# Kill benchmonspc
./benchmonspc_kill.sh --sudo-perf-cmd sudo-g5k

# Create visualization figure
./benchmonspc_visu.py --cpu --cpu-all --mem --io --net --pow --fig-fmt svg,png --traces-repo $TRACES_REPO
