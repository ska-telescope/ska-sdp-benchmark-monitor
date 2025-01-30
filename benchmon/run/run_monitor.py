import glob
import json
import os
import psutil
import shutil
import signal
import subprocess
import sys
import time

HOSTNAME = os.uname()[1]
PID = (os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID")) or "nosched"

class RunMonitor:
    def __init__(self, args):
        self.should_run = True

        self.save_dir = args.save_dir
        self.prefix = args.prefix

        self.sampling_freq = args.sampling_freq

        self.save_dir_base = args.save_dir
        self.save_dir = f"{self.save_dir}/benchmon_traces_{HOSTNAME}"

        self.verbose = args.verbose

        # System monitoring parameters
        self.filename = f"sys_report.csv"
        self.is_system = args.system
        self.system_sampling_interval = args.system_sampling_interval

        # Power monitoring parameters
        self.pow_filename = f'pow_report.csv'
        self.is_power = args.power
        self.power_sampling_interval = args.power_sampling_interval

        # Profiling and callstack parameters
        self.call_filename = f'call_report.txt'
        self.is_call = args.call
        self.call_mode = args.call_mode
        self.call_profiling_frequency = args.call_profiling_frequency
        self.temp_perf_file = f'_temp_perf.data'

        # Enable sudo-g5k (for Grid5000 clusters)
        self.sudo_g5k = "sudo-g5k" if args.sudo_g5k else ""

        # Mark the node with SLURM_NODEID == "0" as main node responsible for collecting all the different reports in the end
        is_slurm_control_node = os.environ.get("SLURM_NODEID") == "0" if "SLURM_NODEID" in os.environ else False
        is_oar_control_node = True if subprocess.run(["oarprint host"], capture_output=True, shell=True, text=True).stdout.split("\n")[0] == HOSTNAME else False
        self.is_benchmon_control_node = is_slurm_control_node or is_oar_control_node

        # Setup SIGTERM handler for graceful termination
        signal.signal(signal.SIGTERM, self.terminate)

        # Get dool binary
        self.dool = args.dool
        if not self.dool:
            # search for dool in the path
            dool_path = shutil.which("dool")
            if dool_path is None:
                raise Exception("Dool not found in PATH. Please specify the dool executable using --dool")
            self.dool = dool_path
        else:
            # We use shutil again to check if the passed file exists and is an executable.
            dool_path = shutil.which(self.dool, mode=os.F_OK | os.X_OK)
            if dool_path is None:
                raise Exception(f"Specified dool executable \"{self.dool}\" is not executable or not found! Please specify the correct dool executable using --dool")

        self.filename = self.filename.replace("%j", os.environ.get("SLURM_JOB_ID") if "SLURM_JOB_ID" in os.environ else "noslurm")
        self.filename = self.filename.replace("%n", HOSTNAME)
        if not self.filename.endswith(".csv"):
            self.filename = f"{self.filename}.csv"

        # # Remove possible trailing slashes in save_dir path
        # if self.save_dir[-1] == os.path.sep:
        #     self.save_dir = self.save_dir[:-1]

        # handle for the dool process
        self.dool_process = None
        self.perfpow_process = None
        self.perfcall_process = None

    def run(self):
        """
        Wrapper of monitoring functions
        """
        os.makedirs(self.save_dir, exist_ok=True)

        if self.is_system:
            self.run_dool()

        if self.is_power:
            self.run_perf_pow()

        if self.is_call:
            self.run_perf_call()

        if self.is_system:
            self.dool_process.wait()

        self.terminate("", "")
        self.post_process()

    def run_dool(self):
        # Hardcoded
        sh_file = f"{os.path.dirname(os.path.realpath(__file__))}/pre_dool_hc.sh"
        subprocess.run(["bash", f"{sh_file}", f"{self.save_dir}"])

        # The constructor made sure we have a correct dool executable at self.dool
        # dool --time --mem --swap --io --aio --disk --fs --net --cpu --cpu-use --output save_dir/sys_report.csv
        dool_cmd = [self.dool, "--epoch", "--mem", "--swap", "--io", "--aio", "--disk", "--fs", "--net", "--cpu", "--cpu-use", "--cpufreq", "--bytes", "--output", f"{self.save_dir}{os.path.sep}{self.filename}", f"{self.system_sampling_interval}"]

        if self.verbose:
            print(f"Starting dool with command \"{' '.join(dool_cmd)}\"")

        self.dool_process = subprocess.Popen(dool_cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def run_perf_pow(self):
        """
        Get and run (as subprocess) perf power events
        """
        # Get Perf Power event
        get_events_cmd = "perf list | grep -i power/energy | awk '{print $1}'"
        events = subprocess.run(get_events_cmd, capture_output=True, shell=True, text=True).stdout.split("\n")[:-1]
        event_flags = []
        for event in events:
            event_flags += ["-e"] + [event]

        # Reporting in/ouput
        sampl_intv = self.power_sampling_interval
        filename = f"{self.save_dir}{os.path.sep}{self.pow_filename}"

        # Get start time for
        with open(filename, "w") as fn:
            fn.write(f"# {time.time()}\n")

        # Perf power command
        perf_pow_cmd = [self.sudo_g5k, "perf", "stat", "-A", "-a"] + event_flags + ["-I", f"{sampl_intv}"] + ["-x", ",", "--append", "-o", f"{filename}"]

        if self.verbose:
            print(f"Starting perf-pow with command \"{' '.join(perf_pow_cmd)}\"")

        # Run perf (power)
        self.perfpow_process = subprocess.Popen(perf_pow_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def run_perf_call(self):
        """
        Profile and get the call graph
        """
        perf_call_cmd = [self.sudo_g5k, "perf", "record", "--running-time", "-T", "-a", "-F", f"{self.call_profiling_frequency}", "--call-graph", f"{self.call_mode}", "-o", f"{self.save_dir}/{self.temp_perf_file}"]

        if self.verbose:
            print(f"Starting perf-call with command \"{' '.join(perf_call_cmd)}\"")

        # Get the conversion from monotonic to real time
        monotonic = time.clock_gettime(time.CLOCK_MONOTONIC)
        real = time.clock_gettime(time.CLOCK_REALTIME)
        with open(f"{self.save_dir}/mono_to_real_file.txt", "w") as file:
            file.write(f"{real - monotonic}\n")

        # Run perf (call)
        self.perfcall_process = subprocess.Popen(perf_call_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def terminate(self, signum=None, frame=None):
        # kill perf (call)
        if self.perfcall_process:
            perfcall_children = [f"{child.pid}" for child in psutil.Process(self.perfcall_process.pid).children()]
            kill_perf_pow_cmd = [self.sudo_g5k, "kill", "-15", f"{self.perfcall_process.pid}"] + perfcall_children
            subprocess.run(kill_perf_pow_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if self.verbose:
                print(f"Terminated perf (call) process on node \"{HOSTNAME}\".\nOutput: {self.perfcall_process.stdout.read()}")

        # kill perf (power)
        if self.perfpow_process:
            perfpow_children = [f"{child.pid}" for child in psutil.Process(self.perfpow_process.pid).children()]
            kill_perf_pow_cmd = [self.sudo_g5k, "kill", "-15", f"{self.perfpow_process.pid}"] + perfpow_children
            subprocess.run(kill_perf_pow_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if self.verbose:
                print(f"Terminated perf (pow) process on node \"{HOSTNAME}\".\nOutput: {self.perfpow_process.stdout.read()}")

        # kill dool process gracefully
        if self.dool_process and self.dool_process.poll() is None:
            self.dool_process.terminate()
            if self.verbose:
                print(f"Terminated dool process on node \"{HOSTNAME}\".\nOutput: {self.dool_process.stdout.read()}")
            self.dool_process = None

    def post_process(self):
        # Create callgraph file
        if self.perfcall_process:
            print("Post-processing perf.data file ...")
            create_callgraph_cmd = ["perf", "script", "-F", "trace:comm,pid,tid,cpu,time,event", "-i", f"{self.save_dir}/{self.temp_perf_file}"]
            with open(f"{self.save_dir}/{self.call_filename}", "w") as redirect_stdout:
                subprocess.run(create_callgraph_cmd, stdout=redirect_stdout, stderr=subprocess.STDOUT, text=True)
            print("...done")

        if self.is_benchmon_control_node:
            print("Control Node: Merging output...")

            """
            Files:
            ./swmon-*.json
            ./hwmon-*.json
            ./benchmon_traces_*   (directories)
                -> ./mono_to_real_file.txt
                -> ./sys_report.csv
                -> ./pow_report.csv
                -> ./call_report.txt
            """
            swmon_files = sorted(glob.glob(f"{self.save_dir_base}/swmon-*.json"))
            hwmon_files = sorted(glob.glob(f"{self.save_dir_base}/hwmon-*.json"))
            traces_dirs = sorted(glob.glob(f"{self.save_dir_base}/benchmon_traces_*"))

            # merge swmon-files if any:
            if len(swmon_files) > 0:
                swmon_data = {}
                for file in swmon_files:
                    filename = file.split("/")[-1][6:-4]  # remove "swmon-" and ".csv" - should result in the hostname
                    with open(file, "r") as f:
                        swmon_data[filename] = json.load(f)

                with open(f"{self.save_dir_base}/swmon_merged.json", "w") as f:
                    json.dump(swmon_data, f)

                for file in swmon_files:
                    os.remove(file)

            # merge hwmon-files if any:
            if len(hwmon_files) > 0:
                hwmon_data = {}

                for file in hwmon_files:
                    filename = file.split("/")[-1][6:-4]  # remove "hwmon-" and ".csv" - should result in the hostname
                    with open(file, "r") as f:
                        hwmon_data[filename] = json.load(f)

                with open(f"{self.save_dir_base}/hwmon_merged.json", "w") as f:
                    json.dump(hwmon_data, f)

                for file in hwmon_files:
                    os.remove(file)

            print("Control Node: Output Merged.")

        # print("Benchmon-Run (dool) done. Exiting...")
        # sys.exit(0)
        return 0
