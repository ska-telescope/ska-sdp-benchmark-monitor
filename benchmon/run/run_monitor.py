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
        self.should_run = True

        self.save_dir = args.save_dir
        self.prefix = args.prefix

        self.filename = "sys_report.csv"
        self.sampling_freq = args.sampling_freq
        self.verbose = args.verbose

        self.is_system = args.system
        self.system_sampling_interval = args.system_sampling_interval

        self.pow_filename = "pow_report.csv"
        self.is_power = args.power
        self.power_sampling_interval = args.power_sampling_interval


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

        self.filename = self.filename.replace("%j", os.environ.get("SLURM_JOB_ID") if "SLURM_JOB_ID" in os.environ else "noslurm")
        self.filename = self.filename.replace("%n", HOSTNAME)
        if not self.filename.endswith(".csv"):
            self.filename = f"{self.filename}.csv"

        # Remove possible trailing slashes in save_dir path
        if self.save_dir[-1] == os.path.sep:
            self.save_dir = self.save_dir[:-1]

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
        perf_pow_cmd = ["sudo-g5k", "perf", "stat", "-A", "-a"] + event_flags + ["-I", f"{sampl_intv}"] + ["-x", ",", "--append", "-o", f"{filename}"]

        if self.verbose:
            print(f"Starting perf-pow with command \"{' '.join(perf_pow_cmd)}\"")

        # Run perf
        self.perfpow_process = subprocess.Popen(perf_pow_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def terminate(self, signum=None, frame=None):
        # kill dool process gracefully
        if self.dool_process and self.dool_process.poll() is None:
            self.dool_process.terminate()
            if self.verbose:
                print(f"Terminated dool process on node \"{HOSTNAME}\".\nOutput: {self.dool_process.stdout.read()}")
            self.dool_process = None

        # kill perf (power)
        if self.perfpow_process:
            perfpow_children = [f"{child.pid}" for child in psutil.Process(self.perfpow_process.pid).children()]
            kill_perf_pow_cmd = ["sudo-g5k", "kill", "-15", f"{self.perfpow_process.pid}"] + perfpow_children
            subprocess.run(kill_perf_pow_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if self.verbose:
                print(f"Terminated perf (pow) process on node \"{HOSTNAME}\".\nOutput: {self.perfpow_process.stdout.read()}")

        if self.is_benchmon_control_node:
            print("Dool Control Node: Merging output...")
            pass
            # todo scoop-315: ensure all dool processes of all nodes are terminated
            # todo scoop-315: merge all dool outputs of all nodes

        print("Benchmon-Run (dool) done. Exiting...")
        sys.exit(0)
