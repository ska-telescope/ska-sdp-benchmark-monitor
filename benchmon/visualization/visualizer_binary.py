"""
Visualization manager
"""

import argparse
import logging
import matplotlib.pyplot as plt
import os

from .system_metrics_binary import SystemDataBinary
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

        self.system_metrics_loaded = self.load_system_metrics()
        self.power_metrics_loaded = self.load_power_metrics()
        self.call_metrics_loaded = self.load_call_metrics()

        self.get_xaxis_params(xmargin=0)
        self.apply_xaxis_params()


    def load_system_metrics_binary(self) -> bool:
        """
        Load system metrics

        Returns:
            bool: True if loading was successful, False otherwise
        """
        try:
            is_cores_full = bool(self.args.cpu_cores_full)
            is_net = self.args.net or self.args.net_all or self.args.net_data
            is_disk = self.args.disk or self.args.disk_iops or self.args.disk_iops

            _n_cores_full = len(self.args.cpu_cores_full.split(",")) if is_cores_full else 0

            self.is_any_sys = self.args.cpu or self.args.cpu_all or self.args.cpu_freq or \
                is_cores_full or self.args.mem or is_net or is_disk or self.args.ib

            conds = {
                "mem": self.args.mem,
                "cpu": self.args.cpu or self.args.cpu_all or is_cores_full,
                "cpufreq": self.args.cpu_freq,
                "net": is_net,
                "disk": is_disk,
                "ib": self.args.ib
            }

            bin_reports = {}
            for key in conds.keys():
                if key == "ib":
                    continue
                bin_reports[f"bin_{key}_report"] = f"{self.traces_repo}/{key}_report.bin" if conds[key] else None
            if self.is_any_sys:
                self.system_metrics = SystemDataBinary(logger=self.logger,
                                                       traces_repo=self.traces_repo,
                                                       **bin_reports)

            self.n_subplots += self.args.cpu + self.args.cpu_all + self.args.cpu_freq + _n_cores_full \
                + self.args.mem + is_net + is_disk + self.args.ib

            return True
        except Exception as e:
            self.logger.error(f"Failed to load system metrics: {e}")
            self.system_metrics = None
            return False


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
        if self.args.cpu and self.system_metrics_loaded:
            self.logger.debug("Plotting  cpu")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            self.system_metrics.plot_cpu(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # Full individual core plot
        if bool(self.args.cpu_cores_full) and self.system_metrics_loaded:
            for core_number in self.args.cpu_cores_full.split(","):
                self.logger.debug(f"Plotting  full cpu core {core_number}")
                ax = plt.subplot(self.n_subplots, 1, sbp)
                sbp += 1
                self.system_metrics.plot_cpu(number=core_number,
                                             annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # CPU per core plot
        if self.args.cpu_all and self.system_metrics_loaded:
            self.logger.debug("Plotting  cpu per core")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            self.system_metrics.plot_cpu_per_core(cores_in=self.args.cpu_cores_in,
                                                  cores_out=self.args.cpu_cores_out,
                                                  annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages)

        # CPU cores frequency plot
        if self.args.cpu_freq and self.system_metrics_loaded:
            self.logger.debug("Plotting  cpu cores frequency")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            freqmax = self.system_metrics.plot_cpufreq(cores_in=self.args.cpu_cores_in,
                                                       cores_out=self.args.cpu_cores_out,
                                                       annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=freqmax)

        # Memory/swap plot
        if self.args.mem and self.system_metrics_loaded:
            self.logger.debug("Plotting  memory/swap")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            memmax = self.system_metrics.plot_memory_usage(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=memmax)

        # Network plot
        if self.system_metrics_loaded and self.args.net or self.args.net_all or self.args.net_data:
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
        if self.args.ib and self.system_metrics_loaded:
            self.logger.debug("Plotting  infiniband")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            ibmax = self.system_metrics.plot_ib(annotate_with_cmds=annotate_with_cmds)
            if self.ical_stages:
                plot_ical_stages(self.ical_stages, ymax=ibmax)

        # Disk plot
        if self.args.disk and self.system_metrics_loaded:
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

        # (perf) Power plot
        if self.power_metrics_loaded and self.args.pow:
            self.logger.debug("Plotting perf power")
            ax = plt.subplot(self.n_subplots, 1, sbp)
            sbp += 1
            powmax = [0]
            if self.args.pow:
                powmax += [self.power_perf_metrics.plot_events()]
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
        if self.call_metrics_loaded and self.args.call:
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
