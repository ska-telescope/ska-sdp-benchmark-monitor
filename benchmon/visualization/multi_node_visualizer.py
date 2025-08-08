"""
Muti-node visualizatinon synchronizer
"""


import os

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d


class BenchmonMNSyncVisualizer:
    """
    Benchmon class to synchronise multi-node visualization
    """

    def __init__(self, args, logger, nodes_data):
        """
        Initialize BenchmonMNSyncVisualizer

        Args:
            args        (argparse.Namespace)    Arguments namespace
            logger      (logging.Logger)        Logging object
            nodes_data  (list)                  List of nodes data of type: visualizer.BenchmonVisualizer
        """
        self.xticks = nodes_data[0].xticks
        self.xlim = nodes_data[0].xlim

        self.args = args
        self.logger = logger

        self.run_sync_plots(nodes_data=nodes_data)


    def set_frame(self, label: str = "") -> None:
        """
        Set frame for a plot

        Args:
            label (str): Set the label
        """
        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.ylabel(label)
        plt.legend(loc=1)
        plt.grid(True)


    def run_sync_plots(self, nodes_data: list) -> None:
        """
        Run multi-node sync plots

        Args:
            nodes_data (list): list of nodes data
        """
        nsbp = self.args.cpu + self.args.cpu_freq + self.args.mem + self.args.net \
            + self.args.ib + self.args.disk + (self.args.pow or self.args.pow_g5k)

        fig, _ = plt.subplots(nsbp, sharex=True)
        fig.set_size_inches(self.args.fig_width, nsbp * self.args.fig_height_unit)
        fig.add_gridspec(nsbp, hspace=0)

        sbp = 1

        if self.args.cpu:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_cpu(nodes_data=nodes_data)

        if self.args.cpu_freq:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_cpufreq(nodes_data=nodes_data)

        if self.args.mem:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_mem(nodes_data=nodes_data)

        if self.args.net:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_net(nodes_data=nodes_data)

        if self.args.ib:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_ib(nodes_data=nodes_data)

        if self.args.disk:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_disk(nodes_data=nodes_data)

        if self.args.pow or self.args.pow_g5k:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_pow(nodes_data=nodes_data)

        plt.subplots_adjust(hspace=0.5)
        plt.tight_layout()

        if self.args.interactive:
            self.logger.debug("Start interactive session with matplotlib")
            plt.show()

        dpi = {"unset": "figure", "low": 200, "medium": 600, "high": 1200}
        for fmt in self.args.fig_fmt.split(","):
            figname = f"{self.args.traces_repo}/multi-node_sync.{fmt}"
            fig.savefig(figname, format=fmt, dpi=dpi[self.args.fig_dpi])
            self.logger.info(f"Multi-node sync figure saved in: {os.path.realpath(figname)}")


    def plot_sync_cpu(self, nodes_data: list) -> None:
        """
        Plot cpu sync

        Args:
            nodes_data (list): list of nodes data
        """
        ts_sync = []
        cpu_sync = []
        for data in nodes_data:
            if not data.system_metrics.cpu_profile_valid:
                self.logger.warning(f"CPU profile data not available  on {data.hostname}, will not be plotted.")
                continue
            ts = data.system_metrics.cpu_stamps
            spaces = ["user", "nice", "system", "iowait", "irq", "softirq", "steal", "guest", "guestnice"]
            cpu = sum([data.system_metrics.cpu_prof[np.iinfo(np.uint32).max][space] for space in spaces])
            plt.plot(ts, cpu, label=data.hostname)

            ts_sync += [ts]
            cpu_sync += [cpu]

        if len(ts_sync) == 0:
            self.logger.warning("No CPU profile data available, no plot will be produced.")
            return

        self.sync_metrics(ts_list=ts_sync, dev_list=cpu_sync, opt="avg", label="average", color="k")

        yrng = 10
        plt.yticks(100 / yrng * np.arange(yrng + 1))
        self.set_frame(label="Total CPU usage (%)")


    def plot_sync_cpufreq(self, nodes_data: list) -> None:
        """
        Plot cpufreq sync

        Args:
            nodes_data (list): list of nodes data
        """
        ts_sync = []
        cpufreq_sync = []
        for data in nodes_data:
            if not data.system_metrics.cpufreq_profile_valid:
                self.logger.warning(f"CPU frequency profile data not available on {data.hostname}, will not be"
                                    + " plotted.")
                continue
            ts = data.system_metrics.cpufreq_stamps
            cpufreq = data.system_metrics.cpufreq_vals["mean"]
            plt.plot(ts, cpufreq, label=data.hostname)

            ts_sync += [ts]
            cpufreq_sync += [cpufreq]

        if len(ts_sync) == 0:
            self.logger.warning("No CPU frequency profile data available, no plot will be produced.")
            return

        self.sync_metrics(ts_list=ts_sync, dev_list=cpufreq_sync, opt="avg", label="average", color="k")
        self.set_frame(label="Mean CPU frequency (GHz)")


    def plot_sync_mem(self, nodes_data: list) -> None:
        """
        Plot mem sync

        Args:
            nodes_data (list): list of nodes data
        """
        memtotal = [0]
        ts_sync = []
        mem_sync = []
        for data in nodes_data:
            if not data.system_metrics.mem_profile_valid:
                self.logger.warning(f"Memory profile data not available on {data.hostname}, will not be plotted.")
                continue
            memunit = 1024**2
            ts = data.system_metrics.mem_stamps
            mem = (data.system_metrics.mem_prof["MemTotal"] - data.system_metrics.mem_prof["MemFree"]) / memunit
            plt.fill_between(ts, sum(memtotal), sum(memtotal) + mem, label=data.hostname)

            plt.plot(ts, sum(memtotal) * np.ones_like(ts), color="grey", lw=1)
            memtotal += [data.system_metrics.mem_prof["MemTotal"][0] / memunit]

            ts_sync += [ts]
            mem_sync += [mem]

        if len(ts_sync) == 0:
            self.logger.warning("No memory profile data available, no plot will be produced.")
            return

        plt.plot(ts, sum(memtotal) * np.ones_like(ts), color="grey", lw=1)
        self.sync_metrics(ts_list=ts_sync, dev_list=mem_sync, label="sum", color="k", ls="-.")

        for powtwo in range(25):
            yticks = np.arange(0, sum(memtotal) + 2**powtwo, 2**powtwo, dtype="i")
            if len(yticks) < self.args.fig_yrange:
                break
        plt.yticks(yticks)
        self.set_frame(label="Memory (GB)")


    def plot_sync_net(self, nodes_data: list) -> None:
        """
        Plot network sync

        Args:
            nodes_data (list): list of nodes data
        """
        ts_sync = []
        net_rx_sync = []
        rx_data = 0
        for data in nodes_data:
            if not data.system_metrics.net_profile_valid:
                self.logger.warning(f"Network profile data not available on {data.hostname}, will not be plotted.")
                continue
            ts = data.system_metrics.net_stamps
            net_rx = data.system_metrics.net_rx_total
            plt.plot(ts, net_rx, marker="v", label=f"rx:{data.hostname} ({int(data.system_metrics.net_rx_data)} MB)")

            ts_sync += [ts]
            net_rx_sync += [net_rx]
            rx_data += data.system_metrics.net_rx_data

        if len(ts_sync) == 0:
            self.logger.warning("No network frequency profile data available, no plot will be produced.")
            return

        self.sync_metrics(ts_list=ts_sync,
                          dev_list=net_rx_sync,
                          label=f"rx:sum ({int(rx_data)} MB)",
                          marker="v",
                          ls="--")

        ts_sync = []
        net_tx_sync = []
        tx_data = 0
        for data in nodes_data:
            ts = data.system_metrics.net_stamps
            net_tx = data.system_metrics.net_tx_total
            plt.plot(ts, net_tx, marker="^", label=f"tx:{data.hostname} ({int(data.system_metrics.net_tx_data)} MB)")

            ts_sync += [ts]
            net_tx_sync += [net_tx]
            tx_data += data.system_metrics.net_tx_data

        self.sync_metrics(ts_list=ts_sync,
                          dev_list=net_tx_sync,
                          label=f"tx:sum ({int(tx_data)} MB)",
                          marker="^",
                          ls="--",
                          with_yrange=(tx_data > rx_data))

        self.set_frame(label="Network Activity (MB/s)")


    def plot_sync_disk(self, nodes_data: list) -> None:
        """
        Plot disk sync

        Args:
            nodes_data (list): list of nodes data
        """
        ts_sync = []
        rd_sync = []
        rd_data = 0
        for data in nodes_data:
            if not data.system_metrics.disk_profile_valid:
                self.logger.warning(f"Disk read profile data not available on {data.hostname}, will not be plotted.")
                continue
            ts = data.system_metrics.disk_stamps
            disk_rd = data.system_metrics.disk_rd_total
            plt.plot(ts, disk_rd, marker="v", label=f"rd:{data.hostname} ({int(data.system_metrics.disk_rd_data)} MB)")

            ts_sync += [ts]
            rd_sync += [disk_rd]
            rd_data += data.system_metrics.disk_rd_data
        self.sync_metrics(ts_list=ts_sync, dev_list=rd_sync, label=f"rd:sum ({int(rd_data)} MB)", marker="v", ls="--")

        if len(ts_sync) == 0:
            self.logger.warning("No disk read profile data available, no plot will be produced.")
            return

        ts_sync = []
        wr_sync = []
        wr_data = 0
        for data in nodes_data:
            if not data.system_metrics.disk_profile_valid:
                self.logger.warning(f"Disk write profile data not available on {data.hostname}, will not be plotted.")
                continue
            ts = data.system_metrics.disk_stamps
            disk_wr = data.system_metrics.disk_wr_total
            plt.plot(ts, disk_wr, marker="^", label=f"wr:{data.hostname} ({int(data.system_metrics.disk_wr_data)} MB)")

            ts_sync += [ts]
            wr_sync += [disk_wr]
            wr_data += data.system_metrics.disk_wr_data

        if len(ts_sync) == 0:
            self.logger.warning("No disk write profile data available, no plot will be produced.")
            return

        self.sync_metrics(ts_list=ts_sync,
                          dev_list=wr_sync,
                          label=f"wr:sum ({int(wr_data)} MB)",
                          marker="^",
                          ls="--",
                          with_yrange=(wr_data > rd_data))

        self.set_frame(label="Disk Activity (MB/s)")


    def plot_sync_ib(self, nodes_data: list) -> None:
        """
        Plot infiniband sync

        Args:
            nodes_data (list): list of nodes data
        """
        ts_sync = []
        ib_rx_sync = []
        rx_data = 0
        for data in nodes_data:
            if not data.system_metrics.ib_profile_valid:
                self.logger.warning(f"Infiniband read profile data not available on {data.hostname}, will not be "
                                    + "plotted.")
                continue
            ts = data.system_metrics.ib_stamps
            ib_rx = data.system_metrics.ib_rx_total
            plt.plot(ts, ib_rx, marker="v", label=f"rx:{data.hostname} ({int(data.system_metrics.ib_rx_data)} MB)")

            ts_sync += [ts]
            ib_rx_sync += [ib_rx]
            rx_data += data.system_metrics.ib_rx_data

        self.sync_metrics(ts_list=ts_sync,
                          dev_list=ib_rx_sync,
                          label=f"rx:sum ({int(rx_data)} MB)",
                          marker="v",
                          ls="--",
                          with_yrange=True)

        if len(ts_sync) == 0:
            self.logger.warning("No Infiniband write profile data available, no plot will be produced.")
            return

        ts_sync = []
        ib_tx_sync = []
        tx_data = 0
        for data in nodes_data:
            if not data.system_metrics.ib_profile_valid:
                self.logger.warning(f"Infiniband write profile data not available on {data.hostname}, will not be "
                                    + "plotted.")
                continue
            ts = data.system_metrics.ib_stamps
            ib_tx = data.system_metrics.ib_tx_total
            plt.plot(ts, ib_tx, marker="^", label=f"tx:{data.hostname} ({int(data.system_metrics.ib_tx_data)} MB)")

            ts_sync += [ts]
            ib_tx_sync += [ib_tx]
            tx_data += data.system_metrics.ib_tx_data

        if len(ts_sync) == 0:
            self.logger.warning("No Infiniband read profile data available, no plot will be produced.")
            return

        self.sync_metrics(ts_list=ts_sync,
                          dev_list=ib_tx_sync,
                          label=f"tx:sum ({int(tx_data)} MB)",
                          marker="^",
                          ls="--",
                          with_yrange=(tx_data > rx_data))

        self.set_frame(label="Infiniband Activity (MB/s)")


    def plot_sync_pow(self, nodes_data: list) -> None:
        """
        Plot power sync

        Args:
            nodes_data (list): list of nodes data
        """
        if self.args.pow:
            for data in nodes_data:
                data.power_perf_metrics.plot_events(pre_label=f"{data.hostname}:")

        if self.args.pow_g5k:
            for data in nodes_data:
                data.power_g5k_metrics.plot_g5k_pow_profiles(pre_label=f"{data.hostname}:")

        self.set_frame(label="Power (W)")


    def sync_metrics(self,
                     ts_list: list, dev_list: list, opt: str = "sum",
                     label: str = "", ls: str = "-", marker: str = "",
                     color=None, with_yrange: bool = False) -> None:
        """
        Sync multi-node metrics

        Args:
            ts_list     (list)  timestamps list
            dev_list    (list)  devices metric list
            opt         (str)   sync operation
            label       (str)   sync plot label
            ls          (str)   sync plot line style
            marker      (str)   sync plot marker
            color       (str)   sync plot line color
        """
        SYNC_FREQ = 1  # noqa: N806
        ts_sync = np.unique(np.round(np.concatenate(ts_list), SYNC_FREQ))
        dev_sync = np.zeros_like(ts_sync)

        for ts, dev in zip(ts_list, dev_list):
            interpolator = interp1d(ts, dev, kind="linear", fill_value="extrapolate", bounds_error=False)
            dev_sync += interpolator(ts_sync)

        divider = len(ts_list) if opt == "avg" else 1

        plt.plot(ts_sync, dev_sync / divider, label=label, color=color, ls=ls, marker=marker)

        if with_yrange:
            maxval = max(dev_sync / divider)
            for powtwo in range(25):
                yticks = np.arange(0, maxval + 2**powtwo, 2**powtwo, dtype="i")
                if len(yticks) < self.args.fig_yrange:
                    break
            plt.yticks(yticks)
