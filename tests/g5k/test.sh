#!/usr/bin/bash -xe


# sys_params=("'--sys --sys-freq 10'" "'--cpu --cpu-all --cpu-freq --net --net-all --net-data --mem --disk --disk-data --disk-iops'")
# pow_params=("--pow --power-sampling-interval 10" "--pow")
# pow_g5k_params=("--pow-g5k" "--pow-g5k")
# call_params=("--call --call-prof-freq 10" "--inline-call --call --call-depth 4")

benchmon_params_list=('--sys --sys-freq 10' '--pow --power-sampling-interval 10' '--pow-g5k' '--call --call-prof-freq 10')
benchmonvisu_params_list=('--cpu --cpu-all --cpu-freq --net --net-all --net-data --mem --disk --disk-data --disk-iops' '--pow' '--pow-g5k' '--inline-call --call --call-depth 4')

### benchmon params ################################################################################
benchmon=$1
savedir=$2
benchrepo=$3
savedir=$savedir
mkdir -p $savedir
benchmon_params="--save-dir $savedir"
benchmon_params+=" --sys --sys-freq 10"
benchmon_params+=" --power --pow-g5k"
benchmon_params+=" --call --call-prof-freq 10"
benchmon_params+=" --verbose"
wst=1
####################################################################################################


### benchmon start #################################################################################
$benchmon/benchmon-start $benchmon_params
sleep $wst
####################################################################################################


### run ############################################################################################
$benchrepo/ft.A.x
####################################################################################################


### benchmon stop ##################################################################################
sleep $wst
$benchmon/benchmon-stop
####################################################################################################


# benchmon visu ####################################################################################
benchmonvisu_params="--verbose --fig-fmt png --fig-name myfigg"
benchmonvisu_params+=" --cpu --cpu-all --cpu-freq"
benchmonvisu_params+=" --net --net-all --net-data"
benchmonvisu_params+=" --mem"
benchmonvisu_params+=" --disk --disk-data --disk-iops"
benchmonvisu_params+=" --pow --pow-g5k"
benchmonvisu_params+=" --inline-call"
benchmonvisu_params+=" --call --call-depth 4"
benchmonvisu_params+=" --recursive"
$benchmon/benchmon-visu $benchmonvisu_params $savedir
$benchmon/benchmon-visu $benchmonvisu_params $savedir
####################################################################################################
