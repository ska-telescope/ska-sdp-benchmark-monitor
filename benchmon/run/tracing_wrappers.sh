#!/usr/bin/bash

# For each of the executables passed as argument create a wrapper script allowing to prefix
# each call to the executable with hpcrun (and corresponding options) to collect execution
# traces. For this to work, 1) this script needs to find the executables, so must be called after
# the corresponding modules have been loaded, 2) the path to script_dir will need to be prepended
# to PATH at the calling script's level so the wrappers are found first.

# Default directories for scripts and traces
hpc_save_dir="./hpctoolkit_traces"
index=0

while [[ $# -gt 0 ]]; do
    case $1 in
        "-d" | "--save-dir")
            hpc_save_dir=$2
            shift 2
            ;;
        "-f" | "--hpc-flags")
# Pass hpcrun arguments as a single string (assumes arguments are the same for all wrapped
# executables hence do not pass -o)
            hpcrun_flags=$2
            shift 2
            ;;
        "-e" | "--hpc-exe")
            while [[ $2 != "-"* && -n $2 ]]; do
                exe[((index++))]=$2
                shift 1
            done
            shift 1
            ;;
        *)
            echo "[ERROR] benchmon: Unsupported argument in \"${BASH_SOURCE[0]} $@\" Use either"
            echo "${BASH_SOURCE[0]} -f \"-e CYCLES -t\" -e DP3 python3 -d ./traces"
            echo "${BASH_SOURCE[0]} --hpc-flags \"-e CYCLES -t\" --hpc-exe DP3 python3 --save-dir ./traces"
            exit 2
            ;;
    esac
done

# Make path absolute for robustness
hpc_save_dir=$(realpath $hpc_save_dir)

# Test the number of executables passed, if none report no trace collection will be happening
if [[ $index == 0 ]]; then
    echo "[WARNING] benchmon: no executable passed as argument, execution tracing is disabled."
else

# Now write the wrapper scripts to the save-dir
# - have the wrappers call the executable with absolute paths to avoid recursion
# - cause the wrapper to log a message (now in stdout) to associate each
#   hpctoolkit_* directory to the corresponding call
# - append a fine time tag to hpctoolkit_* directories to have a separate directory for each
#   hpcrun call

    if [ ! -d $hpc_save_dir ]; then
        mkdir $hpc_save_dir
    fi

    while [[ $index > 0 ]]; do

# Check that the executable can be found
        which ${exe[--index]} &> /dev/null
        if [ $? -ne 0 ];then
            echo "[WARNING] benchmon: ${exe[index]} not found, will not be traced (modules should be loaded first)."
        else
            hpcdir="${hpc_save_dir}/hpctoolkit_$(basename ${exe[index]})_\$(date +'%s.%N')"
            script_string="#!/usr/bin/bash\necho \"[INFO] hpcrun $hpcrun_flags -o $hpcdir $(which ${exe[index]}) \$@ \"\nhpcrun $hpcrun_flags -o $hpcdir $(which ${exe[index]}) \$@"
	    echo -e "$script_string" > $hpc_save_dir/$(basename ${exe[index]})
	    chmod u+x $hpc_save_dir/$(basename ${exe[index]})
        fi
    done

    echo "[INFO] benchmon: wrapper scripts created. If this script was not sourced, prepend directory to PATH to ensure they are found before the executables: export PATH=\"$hpc_save_dir:\$PATH\""
# In case this script was sourced, prepend hpc_save_dir to PATH
    export PATH="$hpc_save_dir:$PATH"
fi

# In case this script was sourced, unset all local variables
unset hpc_save_dir index hpcrun_flags exe script_string
