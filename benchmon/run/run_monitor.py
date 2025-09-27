"""Run monitor module"""

import glob
import json
import math
import os
import signal
import subprocess
import time

import psutil
import requests

from .hp_collector import HighPerformanceCollector


HOSTNAME = os.uname()[1]
PID = (os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID")) or "nosched"

# 简化InfluxDB3配置，移除Docker依赖
INFLUXDB3_DEFAULT_CONFIG = {
    'url': 'http://localhost:8086',
    'database': 'metrics',
    'token': '',  # InfluxDB3 may not require token for local instance
    'org': 'benchmon',
}


class RunMonitor:
    """
    Run monitor class starting, stoping, post-processing monitoring processes
    """

    def __init__(self, args, logger):
        """Docstring @todo."""

        self.args = args
        self.logger = logger
        self.should_run = True
        self.is_shutting_down = False

        self.save_dir_base = args.save_dir
        self.save_dir = f"{self.save_dir_base}/benchmon_traces_{HOSTNAME}"

        self.verbose = args.verbose

        # System monitoring
        self.sys_filename = lambda device: f"{device}_report.csv"  # @nc
        self.is_system = args.system
        self.sys_freq = args.sys_freq

        # Power monitoring parameters
        self.pow_filename = "pow_report.csv"
        self.is_power = args.power
        self.power_sampling_interval = args.power_sampling_interval

        # G5K Power monitoring
        self.pow_filename_base = "pow_g5k_.csv"
        self.is_power_g5k = args.power_g5k

        # CSV file output control
        self.is_csv = args.csv

        # InfluxDB integration
        self.is_grafana = args.grafana

        # --- REFACTOR: Use the new HighPerformanceCollector ---
        self.hp_collector = None
        if self.is_grafana:
            self.influxdb_config = {
                'url': args.grafana_url,
                'token': args.grafana_token,
                'org': args.grafana_org,
                'database': args.grafana_bucket,
            }

        # Profiling and callstack parameters
        self.call_filename = "call_report.txt"
        self.is_call = args.call
        self.call_mode = args.call_mode
        self.call_profiling_frequency = args.call_profiling_frequency
        self.temp_perf_file = "_temp_perf.data"
        self.is_perf_datafile_kept = args.call_keep_datafile

        # Enable sudo-g5k (for Grid5000 clusters)
        self.sudo_g5k = "sudo-g5k" if "grid5000" in HOSTNAME else ""

        # Defer node check to the run method
        self.is_benchmon_control_node = False

        # Setup SIGTERM handler for graceful termination
        signal.signal(signal.SIGTERM, self.terminate)

        # Init process variables
        self.sys_process = []
        self.perfpow_process = None
        self.perfcall_process = None

    def _check_control_node(self):
        """Checks if the current node is the control node for post-processing."""
        oar_check = subprocess.run(args=["oarprint", "host"],
                                   capture_output=True,
                                   shell=True,
                                   text=True,
                                   check=False).stdout.split("\n")[0] == HOSTNAME
        slurm_check = os.environ.get("SLURM_NODEID") == "0"
        self.is_benchmon_control_node = oar_check or slurm_check

    def run(self, timeout: int = None):
        """
        Run, terminate, post-process processes
        (Wrapper of monitoring functions)

        Args:
            timeout (int)   Timeout for testing purpose
        """
        self.t0 = time.time()

        os.makedirs(self.save_dir, exist_ok=True)

        # Check if this is the control node
        self._check_control_node()

        # --- REFACTOR: Initialize and start the new HP Collector ---
        if self.is_grafana:
            self.hp_collector = HighPerformanceCollector(
                self.logger,
                self.influxdb_config,
                self.args.grafana_sample_interval
            )
            self.hp_collector.start()

        # Start writer processes (Only for CSV now)
        if self.is_system:
            self.run_sys_monitoring()

        if self.is_power:
            self.run_perf_pow()

        if self.is_call:
            self.run_perf_call()

        # --- FIX: Replace blocking wait() with a main loop ---
        if timeout:
            self.logger.info(f"Running for a fixed duration of {timeout} seconds.")
            time.sleep(timeout)
        else:
            self.logger.info("Monitoring started. Press Ctrl+C to stop.")
            try:
                while self.should_run:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("Ctrl+C received, initiating termination.")
                self.should_run = False

        self._shutdown()

    def run_sys_monitoring(self):
        """
        Run system monitoring
        """
        freq = self.sys_freq

        self.logger.debug("Starting system monitoring")

        sh_repo = os.path.dirname(os.path.realpath(__file__))

        # --- REFACTOR: This loop now only handles CSV monitoring ---
        for device in ("cpu", "cpufreq", "mem", "net", "disk", "ib"):

            # Start CSV monitoring if enabled
            if self.is_csv:
                script_path = f"{sh_repo}/{device}_mon.sh"
                csv_file = f"{self.save_dir}/{self.sys_filename(device)}"
                args = ["bash", script_path, f"{freq}", csv_file]
                msg = f"CSV script: {script_path} → {csv_file}"

                self.logger.debug(f"Starting: {msg}")
                self.sys_process += [
                    subprocess.Popen(
                        args=args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                ]

            # The 'if self.is_grafana:' block is no longer needed here.

    def run_perf_pow(self):
        """
        Get and run (as subprocess) perf power events
        """
        # Get Perf Power event
        get_events_cmd = "perf list | grep -i power/energy | awk '{print $1}'"
        events = subprocess.run(args=get_events_cmd,
                                capture_output=True,
                                shell=True,
                                text=True,
                                check=False).stdout.split("\n")[:-1]

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
        perf_pow_cmd = ["perf", "stat", "-A", "-a"] + event_flags + \
                       ["-I", f"{sampl_intv}"] + ["-x", ",", "--append", "-o", f"{filename}"]

        if self.sudo_g5k:
            perf_pow_cmd.insert(0, self.sudo_g5k)

        self.logger.debug(f"Starting perf (power):\n\t{' '.join(perf_pow_cmd)}")

        # Run perf (power)
        self.perfpow_process = subprocess.Popen(args=perf_pow_cmd,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT,
                                                text=True)


    def run_perf_call(self):
        """
        Profile and get the call graph
        """
        perf_call_cmd = ["perf", "record",
                         "--running-time", "-T", "-a",
                         "-F", f"{self.call_profiling_frequency}",
                         "--call-graph", f"{self.call_mode}",
                         "-o", f"{self.save_dir}/{self.temp_perf_file}"
                         ]

        if self.sudo_g5k:
            perf_call_cmd.insert(0, self.sudo_g5k)

        self.logger.debug(f"Starting perf (call graph):\n\t{' '.join(perf_call_cmd)}")

        # Get the conversion from monotonic to real time
        monotonic = time.clock_gettime(time.CLOCK_MONOTONIC)
        real = time.clock_gettime(time.CLOCK_REALTIME)
        with open(f"{self.save_dir}/mono_to_real_file.txt", "w") as file:
            file.write(f"{real - monotonic}\n")

        # Run perf (call)
        self.perfcall_process = subprocess.Popen(args=perf_call_cmd,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.DEVNULL,
                                                 shell=False,
                                                 text=True)


    def download_g5k_pow(self):
        """
        Download grid5000 power consumption report
        """
        # Check if hostname is in Grid5000 format
        hostname_parts = HOSTNAME.split(".")
        if len(hostname_parts) < 2 or "grid5000" not in HOSTNAME:
            self.logger.info(f"Hostname {HOSTNAME} is not a Grid5000 node, skipping G5K power download")
            return

        _site = hostname_parts[1]
        _cluster = hostname_parts[0]

        requests.packages.urllib3.disable_warnings(
            requests.packages.urllib3.exceptions.InsecureRequestWarning
        )

        self.t1 = time.time()

        metrics = ["wattmetre_power_watt", "bmc_node_power_watt"]

        for metric in metrics:

            suffix = f"stable/sites/{_site}/metrics?metrics={metric}&" + \
                     f"nodes={_cluster}&start_time={math.floor(self.t0)}&" + \
                     f"end_time={math.ceil(self.t1)}"
            url = f"https://api.grid5000.fr/{suffix}"

            self.logger.debug(f"Downloading ...: {url}")

            req = requests.get(url, verify=False)
            filepath = f"{self.save_dir}/g5k_pow_report_{metric}.json"
            with open(filepath, "w") as jsfile:
                json.dump(req.json(), jsfile)

            self.logger.debug(f"File saved in: {filepath}")


    def terminate(self, signum=None, frame=None):
        """
        Terminate background process after catching term signal
        """
        # This method is now only for signal handling
        self.logger.info(f"Signal {signum} received, initiating termination.")
        self.should_run = False

    def _shutdown(self):
        """
        Internal method to perform all shutdown operations once.
        """
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.logger.info("Shutting down monitoring processes...")

        # --- REFACTOR: Stop the new HP Collector ---
        if self.is_grafana and self.hp_collector:
            self.hp_collector.stop()

        # kill perf (call)
        if self.perfcall_process:
            perfcall_children = [
                f"{child.pid}" for child in psutil.Process(self.perfcall_process.pid).children()
            ]
            kill_perf_pow_cmd = ["kill", "-15", f"{self.perfcall_process.pid}"] + perfcall_children

            if self.sudo_g5k:
                kill_perf_pow_cmd.insert(0, self.sudo_g5k)

            subprocess.run(args=kill_perf_pow_cmd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           text=True,
                           check=False)

            process_stdout = self.perfcall_process.stdout.read()
            # @hc must be kept, otherwise, it doesnt terminate properly

            self.logger.debug(f"Terminated perf (call graph) with stdout: {process_stdout}")

        # kill perf (power)
        if self.perfpow_process:
            perfpow_children = [
                f"{child.pid}" for child in psutil.Process(self.perfpow_process.pid).children()
            ]
            kill_perf_pow_cmd = ["kill", "-15", f"{self.perfpow_process.pid}"] + perfpow_children

            if self.sudo_g5k:
                kill_perf_pow_cmd.insert(0, self.sudo_g5k)

            subprocess.run(args=kill_perf_pow_cmd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           text=True,
                           check=False)

            process_stdout = self.perfpow_process.stdout.read()  # @hc

            self.logger.debug(f"Terminated perf (power) with stdout: {process_stdout}")

        # Kill sys processes
        for process in self.sys_process:
            process.terminate()
            process_stdout = process.stdout.read()

            self.logger.debug(f"Terminated system monitoring with stdout: {process_stdout}")

        # Perform post-processing after all processes are terminated
        self.post_process()

    def post_process(self):
        """
        Post-process data
        """
        if self.is_power_g5k:
            self.download_g5k_pow()

        # Create callgraph file
        if self.is_call:
            self.logger.debug("Post-processing perf.data file ...")
            perf_data_file = f"{self.save_dir}/{self.temp_perf_file}"
            create_callgraph_cmd = ["perf", "script",
                                    "-F", "trace:comm,pid,tid,cpu,time,event",
                                    "-i", perf_data_file]
            # @dev "-F comm,pid,tid,cpu,time,event" could be used to lighten the file

            with open(f"{self.save_dir}/{self.call_filename}", "w") as redirect_stdout:
                subprocess.run(args=create_callgraph_cmd,
                               stdout=redirect_stdout,
                               stderr=subprocess.STDOUT,
                               text=True,
                               check=False)

            if not self.is_perf_datafile_kept:
                self.logger.debug(f"Removing perf binany file: {perf_data_file}...")
                os.remove(perf_data_file)
                self.logger.debug("...done")

            self.logger.debug("...done")

        if self.is_benchmon_control_node:
            self.logger.debug("Control Node: Merging output...")

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

            # merge swmon-files if any:
            if len(swmon_files) > 0:
                swmon_data = {}
                for file in swmon_files:
                    filename = file.split("/")[-1][6:-4]
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
                    filename = file.split("/")[-1][6:-4]
                    with open(file, "r") as f:
                        hwmon_data[filename] = json.load(f)

                with open(f"{self.save_dir_base}/hwmon_merged.json", "w") as f:
                    json.dump(hwmon_data, f)

                for file in hwmon_files:
                    os.remove(file)

            self.logger.debug("Control Node: Output Merged.")

        return 0
