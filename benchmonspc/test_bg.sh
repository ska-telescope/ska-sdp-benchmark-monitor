#!/usr/bin/bash -x

./benchmonspc.sh --sys --pow --sudo-perf --traces-repo ./test_repo

sleep 10

sudo ./benchmonspc_kill

./benchmonspc_visu.py --cpu --cpu-all --mem --io --net --traces-repo ./test_repo
