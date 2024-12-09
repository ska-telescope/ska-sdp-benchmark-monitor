import os
import psutil
import shutil
import signal
import subprocess
import sys
import time

HOSTNAME = os.uname()[1]

class RunMonitor:
    def __init__(self, args):
        self.JOBID = os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID")
        self.HOSTNAME = os.uname()[1]

        self.should_run = True

        self.save_dir = f"{args.save_dir}{os.sep}benchmon_traces_{self.JOBID}_{self.HOSTNAME}"

        self.sampling_freq = args.sampling_freq
        self.verbose = args.verbose

        # System monitoring parameters
        self.filename = f"sys_report_{self.HOSTNAME}.csv"
        self.is_system = args.system
        self.system_sampling_interval = args.system_sampling_interval

        # Power monitoring parameters
        self.pow_filename = f'pow_report_{self.HOSTNAME}.csv'
        self.is_power = args.power
        self.power_sampling_interval = args.power_sampling_interval

        # Profiling and callstack parameters
        self.call_filename = f'call_report_{self.HOSTNAME}.txt'
        self.is_call = args.call
        self.call_mode = args.call_mode
        self.call_profiling_frequency = args.call_profiling_frequency
        self.temp_perf_file = f'_temp_perf_{self.HOSTNAME}.data'

        # Enable sudo-g5k (for Grid5000 clusters)
        self.sudo_g5k = "sudo-g5k" if args.sudo_g5k else ""

        # Mark the node with SLURM_NODEID == "0" as main node responsible for collecting all the different reports in the end
        self.is_benchmon_control_node = os.environ.get("SLURM_NODEID") == "0" if "SLURM_NODEID" in os.environ else False

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

        if not self.filename.endswith(".csv"):
            self.filename = f"{self.filename}.csv"

        # handle for the dool process
        self.dool_process = None
        self.perfpow_process = None


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
            print("Dool exited unexpectedly!")
            print(f"Terminated dool process on node \"{HOSTNAME}\".\nOutput: {self.dool_process.stdout.read()}")

        self.terminate("", "")

    def run_dool(self):
        # Hardcoded
        sh_file = f"{os.path.dirname(os.path.realpath(__file__))}/pre_dool_hc.sh"
        subprocess.run(["bash", f"{sh_file}", f"{self.save_dir}"])

        # The constructor made sure we have a correct dool executable at self.dool
        # dool --time --mem --swap --io --aio --disk --fs --net --cpu --cpu-use --output save_dir/sys_report.csv
        dool_cmd = [self.dool, "--epoch", "--mem", "--swap", "--io", "--aio", "--disk", "--fs", "--net", "--cpu", "--cpu-use", "--cpufreq", "--output", f"{self.save_dir}{os.path.sep}{self.filename}", f"{self.system_sampling_interval}"]

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

        # Create callgraph file
        if self.perfcall_process:
            create_callgraph_cmd = ["perf", "script", "-F", "trace:comm,pid,tid,cpu,time,event", "-i", f"{self.save_dir}/{self.temp_perf_file}"]
            with open(f"{self.save_dir}/{self.call_filename}", "w") as redirect_stdout:
                subprocess.run(create_callgraph_cmd, stdout=redirect_stdout, stderr=subprocess.STDOUT, text=True)

        if self.is_benchmon_control_node:
            print("Dool Control Node: Merging output...")
            base_directory = self.save_dir
            pass
            # todo scoop-315: ensure all dool processes of all nodes are terminated
            # todo scoop-315: merge all dool outputs of all nodes

        print("Benchmon-Run (dool) done. Exiting...")
        sys.exit(0)
