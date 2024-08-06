import os
import shutil
import signal
import socket
import subprocess
import sys

from benchmon.common.utils import execute_cmd


class RunMonitor:
    def __init__(self, args):
        self.should_run = True
        self.save_dir = args.save_dir
        self.filename = args.filename
        self.sampling_freq = args.sampling_freq
        # self.checkpoint = args.checkpoint
        self.verbose = args.verbose

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
        self.filename = self.filename.replace("%n", socket.gethostname())
        if not self.filename.endswith(".csv"):
            self.filename = f"{self.filename}.csv"

        # Remove possible trailing slashes in save_dir path
        if self.save_dir[-1] == os.path.sep:
            self.save_dir = self.save_dir[:-1]

        # handle for the dool process
        self.process = None

    def run(self):
        # The constructor made sure we have a correct dool executable at self.dool
        # dool --time --mem --swap --io --aio --disk --fs --net --cpu --cpu-use --output ./dool-report-$SLURM_JOB_ID-$(hostname).csv 1&
        dool_cmd = [self.dool, "--time", "--mem", "--swap", "--io", "--aio", "--disk", "--fs", "--net", "--cpu",
                    "--cpu-use", "--output", f"{self.save_dir}{os.path.sep}{self.filename}", f"{self.sampling_freq}"]
        if self.verbose:
            print(f"Starting dool with command \"{' '.join(dool_cmd)}\"")
        self.process = subprocess.Popen(dool_cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.process.wait()
        print("Dool exited unexpectedly!")
        print(f"Terminated dool process on node \"{socket.gethostname()}\".\nOutput: {self.process.stdout.read()}")
        self.terminate("", "")

    def terminate(self, signum=None, frame=None):
        # kill dool process gracefully
        if self.process and self.process.poll() is None:
            self.process.terminate()
            if self.verbose:
                print(f"Terminated dool process on node \"{socket.gethostname()}\".\nOutput: {self.process.stdout.read()}")
            self.process = None

        if self.is_benchmon_control_node:
            print("Dool Control Node: Merging output...")
            pass
            # todo scoop-315: ensure all dool processes of all nodes are terminated
            # todo scoop-315: merge all dool outputs of all nodes

        print("Benchmon-Run done. Exiting...")
        sys.exit(0)
