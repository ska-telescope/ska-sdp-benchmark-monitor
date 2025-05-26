"""
Visualization manager
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

from .call_profile import PerfCallData
from .call_profile import PerfCallRawData
from .power_metrics import G5KPowerData
from .power_metrics import PerfPowerData
from .system_metrics import SystemData
from .utils import read_ical_log_file, plot_ical_stages


class BenchmonVisualizer:
    """
    Benchmon visualizer class to read and plot monitoring metrics

    Attributes:
        args                    (argparse.Namespace): Arguments namespace
        logger                  (logging.Logger)    : Logging object
        traces_repo             (str)               : Traces repository
        hostname                (str)               : Hostname
        system_metrics          (SystemData)        : Object of system metrics
        power_g5k_metrics       (G5KPowerData)      : Object of g5k power metrics
        power_perf_metrics      (PerfPowerData)     : Object of perf power metrics
        call_traces             (PerfCallData)      : Object of callstack recorded by perf
        n_subplots              (int)               : Number of subplots
        xlim                    (list)              :
        xticks                  (list)              :
        is_any_sys              (bool)              :
        call_depths             (list)              : List of depths (int) for the callstack visualization
        call_chosen_cmd         (str)               : The chosen command to plot for the callstack visualization
        call_recorded_cmds      (list)              : List of the recorded commands
        call_monotonic_to_real  (float)             : Convert monotonic time (of perf record) to posix time
        inline_calls_prof       (dict)              : Profile of {cmd: [list-of-timestamps]} to annotate plots
    """

    def __init__(self, args: argparse.Namespace, logger: logging.Logger, traces_repo: str) -> None:
        """
        Initialize BenchmonVisualizer

        Args:
            args        (argparse.Namespace): Arguments namespace
            logger      (logging.Logger)    : Logging object
            traces_repo (str)               : Traces repository
        """
        self.args = args
        self.logger = logger

        self.traces_repo = traces_repo
        os.makedirs(name=f"{self.traces_repo}/pkl_dir", exist_ok=True)

        self.hostname = os.path.basename(os.path.realpath(traces_repo))[16:]
        self.system_metrics = None
        self.power_g5k_metrics = None
        self.power_perf_metrics = None
        self.call_traces = None

        self.n_subplots = 0
        self.xlim = []
        self.xticks = []

        self.is_any_sys = False
        self.call_depths = []
        self.call_chosen_cmd = ""
        self.call_recorded_cmds = []
        self.call_monotonic_to_real = 0
        self.inline_calls_prof = None

        self.ical_stages = {}
        if self.args.annotate_with_log == "ical":
            self.ical_stages = read_ical_log_file(self.traces_repo)

        self.load_system_metrics()
        self.load_power_metrics()
        self.load_call_metrics()

        self.get_xaxis_params(xmargin=0)
        self.apply_xaxis_params()

        if "grid5000.fr" in self.hostname:
            self.hostname = self.hostname.split(".")[0]

    def load_system_metrics(self) -> None:
        """
        Load system metrics
        """
        is_cores_full = bool(self.args.cpu_cores_full)
        is_net = self.args.net or self.args.net_all or self.args.net_data
        is_disk = self.args.disk or self.args.disk_iops or self.args.disk_iops

        _n_cores_full = len(self.args.cpu_cores_full.split(",")) if is_cores_full else 0

        self.is_any_sys = self.args.cpu or self.args.cpu_all or self.args.cpu_freq or \
            is_cores_full or self.args.mem or is_net or is_disk or self.args.ib

        csv_reports = {}
        conds = {
            "mem": self.args.mem,
            "cpu": self.args.cpu or self.args.cpu_all or is_cores_full,
            "cpufreq": self.args.cpu_freq,
            "net": is_net,
            "disk": is_disk,
            "ib": self.args.ib
        }
        for key in conds.keys():
            csv_reports[f"csv_{key}_report"] = f"{self.traces_repo}/{key}_report.csv" if conds[key] else None

        if self.is_any_sys:
            self.system_metrics = SystemData(logger=self.logger,
                                             traces_repo=self.traces_repo,
                                             **csv_reports)

        self.n_subplots += self.args.cpu + self.args.cpu_all + self.args.cpu_freq + _n_cores_full \
            + self.args.mem + is_net + is_disk + self.args.ib

    def load_power_metrics(self) -> None:
        """
        Load power metrics recorded with perf (rapl) and grid5000 tools
        """
        if self.args.pow:
            self.power_perf_metrics = PerfPowerData(logger=self.logger,
                                                    csv_filename=f"{self.traces_repo}/pow_report.csv")

        if self.args.pow_g5k:
            self.power_g5k_metrics = G5KPowerData(traces_dir=self.traces_repo)

        self.n_subplots += (self.args.pow or self.args.pow_g5k)

    def load_call_metrics(self) -> None:
        """
        Load perf callstack traces
        """
        if self.args.call or self.args.inline_call or self.args.inline_call_cmd:
            with open(f"{self.traces_repo}/mono_to_real_file.txt", "r") as file:
                self.call_monotonic_to_real = float(file.readline())
            call_raw = PerfCallRawData(logger=self.logger,
                                       filename=f"{self.traces_repo}/call_report.txt")
            samples, self.call_recorded_cmds = call_raw.cmds_list()

            if self.args.call_cmd:
                self.call_chosen_cmd = self.args.call_cmd
            else:
                self.call_chosen_cmd = list(self.call_recorded_cmds.keys())[0]

            self.call_traces = PerfCallData(logger=self.logger,
                                            cmd=self.call_chosen_cmd,
                                            samples=samples,
                                            m2r=self.call_monotonic_to_real,
                                            traces_repo=self.traces_repo)
            if self.args.call_depth:
                self.call_depths = [depth for depth in range(self.args.call_depth)]
            elif self.args.call_depths:
                self.call_depths = [int(depth) for depth in self.args.call_depths.split(",")]
            self.n_subplots += self.args.call * (2 if len(self.call_depths) > 2 else 1)

            self.inline_calls_prof = self.get_inline_calls_prof(samples)

    def get_inline_calls_prof(self, samples: list) -> dict:
        """
        Get commands recorded by perf to annotate plots

        Args:
            samples (list): list of raw perf samples

        Returns:
            dict: command as key and value is a list of timestamps
        """
        self.logger.debug("Create PerfPower inline profile...")
        t0 = time.time()

        # Hard-coded system command to remove
        kernel_calls = [
            "swapper", "bash", "awk", "cat", "date", "grep", "sleep", "perf_5.10", "perf", "prometheus-node",
            "htop", "kworker", "dbus-daemon", "ipmitool", "slurmstepd", "rcu_sched", "ldlm_bl", "socknal",
            "systemd", "snapd", "apparmor", "sed", "kswap", "queue", "ps", "sort", "diff", "kipmi", "orted",
            "nvidia-modprobe", "async"
        ]

        # Create list of keys for user calls (remove command if less thant 5% of the larger command)
        if self.args.inline_call_cmd:
            user_calls_keys = self.args.inline_call_cmd.split(",")

        else:
            _inline_cmds_threshold = 0.01
            user_calls_keys = []
            for key in self.call_recorded_cmds:
                if (
                    self.call_recorded_cmds[key] / self.call_recorded_cmds[self.call_chosen_cmd]
                    > _inline_cmds_threshold
                ):
                    user_calls_keys += [key]

            self.logger.debug(f"{user_calls_keys=}")
            user_calls_keys_raw = user_calls_keys.copy()
            for command in user_calls_keys_raw:
                for kcall in kernel_calls:
                    if kcall in command:
                        user_calls_keys.remove(command)
                        break

        inline_calls_prof = {key: [] for key in user_calls_keys}

        msg = "\tInline commands: "
        for cmd in user_calls_keys:
            msg += f"{{{cmd}: {self.call_recorded_cmds[cmd]} samples}} "
        self.logger.debug(msg)

        for sample in samples:
            if sample["cmd"] in user_calls_keys:  # and  sample["cpu"] == "[000]":
                inline_calls_prof[sample["cmd"]] += [sample["timestamp"] + self.call_monotonic_to_real]

        # Remove duplicated wrt decimal
        _round_val = 2
        msg = "\tInline commands (Lightened): "
        for cmd in user_calls_keys:
            inline_calls_prof[cmd] = np.unique(np.array(inline_calls_prof[cmd]).round(_round_val))
            msg += f"{{{cmd}: {len(inline_calls_prof[cmd])} samples}} "
        self.logger.debug(msg)

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return inline_calls_prof

    def get_xaxis_params(self, xmargin=0.02) -> None:
        """
        Get x-axis params: limits and ticks

        Args:
            xmargin (float): xmaring percent
        """
        # @hc
        try:
            t0, tf = self.system_metrics.cpu_stamps[0], self.system_metrics.cpu_stamps[-1]
        except AttributeError:
            try:
                t0, tf = self.system_metrics.cpufreq_stamps[0], self.system_metrics.cpufreq_stamps[-1]
            except AttributeError:
                try:
                    t0, tf = self.system_metrics.mem_stamps[0], self.system_metrics.mem_stamps[-1]
                except AttributeError:
                    try:
                        t0, tf = self.system_metrics.net_stamps[0], self.system_metrics.net_stamps[-1]
                    except AttributeError:
                        try:
                            t0, tf = self.system_metrics.disk_stamps[0], self.system_metrics.disk_stamps[-1]
                        except AttributeError:
                            try:
                                t0, tf = self.system_metrics.ib_stamps[0], self.system_metrics.ib_stamps[-1]
                            except AttributeError:
                                sys.exit(1)

        fmt = "%Y-%m-%dT%H:%M:%S"
        if self.args.start_time:
            t0 = datetime.strptime(self.args.start_time, fmt).timestamp()
        if self.args.end_time:
            tf = datetime.strptime(self.args.end_time, fmt).timestamp()

        xticks_val = np.linspace(t0, tf, self.args.fig_xrange)

        t0_fmt = time.strftime("%H:%M:%S\n%b-%d", time.localtime(t0))
        tf_fmt = time.strftime("%H:%M:%S\n%b-%d", time.localtime(tf))

        inbetween_labels = []
        _days = [t0_fmt.split("\n")[1].split("-")[1]]
        for st in xticks_val[1:-1]:
            inbetween_labels += [time.strftime('%H:%M:%S', time.localtime(st))]
            _days += [time.strftime('%d', time.localtime(st))]
            if _days[-1] != _days[-2]:
                inbetween_labels[-1] += "\n" + time.strftime('%b-%d', time.localtime(st))
        xticks_label = [t0_fmt] + inbetween_labels + [tf_fmt]

        self.xticks = (xticks_val, xticks_label)

        dx = (tf - t0) * xmargin
        self.xlim = [t0 - dx, tf + dx]

    def apply_xaxis_params(self) -> None:
        """
        Apply x-axis params to objects
        """
        if self.is_any_sys:
            self.system_metrics.xlim = self.xlim
            self.system_metrics.xticks = self.xticks
            self.system_metrics.yrange = self.args.fig_yrange

    def run_plots(self) -> None:
        """
        Run plotting
        """
        fig, _ = plt.subplots(self.n_subplots, sharex=True)
        fig.set_size_inches(self.args.fig_width, self.n_subplots * self.args.fig_height_unit)
        fig.add_gridspec(self.n_subplots, hspace=0)

        sbp = 1
        annotate_with_cmds = self.annotate_with_cmds if self.inline_calls_prof else None

        # CPU plot
        if self.args.cpu:
            self.logger.debug("Plotting  cpu")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            self.system_metrics.plot_cpu(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # Full individual core plot
        if bool(self.args.cpu_cores_full):
            for core_number in self.args.cpu_cores_full.split(","):
                self.logger.debug(f"Plotting  full cpu core {core_number}")
                ax = plt.subplot(self.n_subplots, 1, sbp)
                sbp += 1
                self.system_metrics.plot_cpu(number=core_number,
                                             annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # CPU per core plot
        if self.args.cpu_all:
            self.logger.debug("Plotting  cpu per core")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            self.system_metrics.plot_cpu_per_core(cores_in=self.args.cpu_cores_in,
                                                  cores_out=self.args.cpu_cores_out,
                                                  annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # CPU cores frequency plot
        if self.args.cpu_freq:
            self.logger.debug("Plotting  cpu cores frequency")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            freqmax = self.system_metrics.plot_cpufreq(cores_in=self.args.cpu_cores_in,
                                                       cores_out=self.args.cpu_cores_out,
                                                       annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=freqmax)

        # Memory/swap plot
        if self.args.mem:
            self.logger.debug("Plotting  memory/swap")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            memmax = self.system_metrics.plot_memory_usage(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=memmax)

        # Network plot
        if self.args.net or self.args.net_all or self.args.net_data:
            self.logger.debug("Plotting  network")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            netmax = self.system_metrics.plot_network(all_interfaces=self.args.net_all,
                                                      is_rx_only=self.args.net_rx_only,
                                                      is_tx_only=self.args.net_tx_only,
                                                      is_netdata_label=self.args.net_data,
                                                      annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=netmax)

        # Infiniband plot
        if self.args.ib:
            self.logger.debug("Plotting  infiniband")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            ibmax = self.system_metrics.plot_ib(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=ibmax)

        # Disk plot
        if self.args.disk:
            self.logger.debug("Plotting  disk")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            diskmax = self.system_metrics.plot_disk(is_with_iops=self.args.disk_iops,
                                                    is_rd_only=self.args.disk_rd_only,
                                                    is_wr_only=self.args.disk_wr_only,
                                                    is_diskdata_label=self.args.disk_data,
                                                    annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=diskmax)

        # (perf+g5k) Power plot
        if self.args.pow or self.args.pow_g5k:
            self.logger.debug("Plotting perf power")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            powmax = [0]
            if self.args.pow:
                powmax += [self.power_perf_metrics.plot_events()]
            if self.args.pow_g5k:
                powmax += [self.power_g5k_metrics.plot_g5k_pow_profiles()]
            if annotate_with_cmds:
                annotate_with_cmds(ymax=max(powmax))
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=max(powmax))

            plt.xticks(*self.xticks)
            plt.xlim(self.xlim)
            plt.ylabel("Power (W)")
            plt.legend(loc=1)
            plt.grid()

        # (perf) Calltrace plot
        if self.args.call:
            self.logger.debug("Plotting perf call graph")
            plt.subplot(self.n_subplots, 1, (sbp, sbp + 1), sharex=ax)
            self.call_traces.plot(self.call_depths,
                                  xticks=self.xticks,
                                  xlim=self.xlim,
                                  legend_ncol=self.args.fig_call_legend_ncol)

        fig.suptitle(f"{os.path.basename(os.path.realpath(self.traces_repo))[16:]}")
        plt.subplots_adjust(hspace=.5)
        plt.tight_layout()

        # Enable interactive plot
        if self.args.interactive:
            self.logger.debug("Start interactive session with matplotlib")
            plt.show()

        # Figure saving parameters
        dpi = {"unset": "figure", "low": 200, "medium": 600, "high": 1200}
        figpath = f"{self.traces_repo}" if self.args.fig_path is None else self.args.fig_path
        for fmt in self.args.fig_fmt.split(","):
            figname = f"{figpath}/{self.args.fig_name}.{fmt}"
            fig.savefig(figname, format=fmt, dpi=dpi[self.args.fig_dpi])
            self.logger.info(f"Figure saved: {os.path.realpath(figname)}")

    def annotate_with_cmds(self, ymax: float = 100.) -> None:
        """
        Annotate plots with perf cmds

        Args:
            ymax (float): max value of y-axis
            xlim (list) : limits of x-axis
        """
        cm = plt.cm.gist_earth(np.linspace(0, 1, len(self.inline_calls_prof) + 1))

        ypos = lambda idx: - 0.03 * ymax - 0.03 * idx * ymax
        ylim = lambda idx: (- 0.15 * ymax - 0.03 * idx * ymax, 1.1 * ymax)
        for idx, call in enumerate(self.inline_calls_prof):
            call_ts_limited = self.inline_calls_prof[call][
                np.logical_and(self.inline_calls_prof[call] > self.xlim[0],
                               self.inline_calls_prof[call] < self.xlim[1])
            ]

            if len(call_ts_limited) == 0:
                continue

            plt.plot(call_ts_limited,
                     ypos(idx) * np.ones(len(call_ts_limited)),
                     ".", ms=4, c=cm[idx])

            plt.text(np.mean(call_ts_limited),
                     ypos(idx) * 1.5,
                     call,
                     va="top",
                     ha="center",
                     c=cm[idx],
                     weight="bold")

        plt.ylim(ylim(idx))
