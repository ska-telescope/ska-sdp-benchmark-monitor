#!/usr/bin/bash -x

# Parameters
APP=$HOME/BENCHMARKS/NAS/NPB3.4.2/NPB3.4-MPI/bin_openmpi-4.1.4_gcc-10.4.0/lu.A.x # /usr/bin/hostname
TRACES_REPO=./my_traces_repo_mn

# MPI module
module load openmpi/4.1.4_gcc-10.4.0

# Get nodes name
HOSTS=$(oarprint host | tr "\n" "," | sed "s/,$/\n/") # is OAR the scheduler?
# HOSTS=$(echo $(scontrol show hostname $SLURM_JOB_NODELIST) | tr -s " " ",") # is SLURM the scheduler?

# Create hostfile
HOSTFILE=./hostfile.txt
echo $HOSTS | tr "," "\n" > $HOSTFILE

# Run benchmonspc (distributed)
mpirun -host $HOSTS ./benchmonspc.sh --multi-node --sys --pow --sudo-perf-cmd sudo-g5k --traces-repo $TRACES_REPO &

# Run App (distributed)
sleep 5
mpirun --use-hwthread-cpus --machinefile $HOSTFILE $APP
sleep 5

# Kill benchmonspc (distributed)
mpirun -host $HOSTS ./benchmonspc_kill.sh --sudo-perf-cmd sudo-g5k

# Create visualization figures
for traces_repo in $TRACES_REPO/*
do
    ./benchmonspc_visu.py --cpu --cpu-all --mem --io --net --pow --fig-fmt svg,png --traces-repo $traces_repo
done
