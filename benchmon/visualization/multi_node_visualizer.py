"""
Muti-node visualizatinon synchronizer
"""


import os

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d
from .utils import plot_stage_markers, get_stage_color, add_stage_legend


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
        # Collect annotation stages from all nodes
        nodes_annotations = [
            (nd.hostname, nd.annotation_stages)
            for nd in nodes_data
            if getattr(nd, "annotation_stages", None)
        ]
        has_annotations = len(nodes_annotations) > 0

        # Interleaved color mapping: (hostname, label) → color index
        color_map = {}
        if has_annotations:
            node_hostnames = [h for h, _ in nodes_annotations]
            n_nodes = len(node_hostnames)
            stage_labels_ordered = []
            seen_labels = set()
            for _, stages in nodes_annotations:
                for s in stages:
                    if s["label"] not in seen_labels:
                        stage_labels_ordered.append(s["label"])
                        seen_labels.add(s["label"])
            for stage_idx, label in enumerate(stage_labels_ordered):
                for node_idx, hostname in enumerate(node_hostnames):
                    color_map[(hostname, label)] = stage_idx * n_nodes + node_idx

        n_annotation_subplots = len(nodes_annotations) if has_annotations else 0
        nsbp = self.args.cpu + self.args.cpu_freq + self.args.mem + self.args.net \
            + self.args.ib + self.args.disk + n_annotation_subplots

        fig, _ = plt.subplots(nsbp, sharex=True)
        fig.set_size_inches(self.args.fig_width, nsbp * self.args.fig_height_unit)

        sbp = 1
        ax_pipeline = None
        ax_last = None

        # --- One annotation subplot per node ---
        if has_annotations:
            for hostname, stages in nodes_annotations:
                ax = plt.subplot(nsbp, 1, sbp)
                sbp += 1
                self.plot_node_annotation(hostname, stages, ax, color_map)
                if ax_pipeline is None:
                    ax_pipeline = ax

        # --- Metric subplots ---
        if self.args.cpu:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_cpu(nodes_data=nodes_data)
            ax_last = plt.gca()

        if self.args.cpu_freq:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_cpufreq(nodes_data=nodes_data)
            ax_last = plt.gca()

        if self.args.mem:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_mem(nodes_data=nodes_data)
            ax_last = plt.gca()

        if self.args.net:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_net(nodes_data=nodes_data)
            ax_last = plt.gca()

        if self.args.ib:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_ib(nodes_data=nodes_data)
            ax_last = plt.gca()

        if self.args.disk:
            plt.subplot(nsbp, 1, sbp)
            sbp += 1
            self.plot_sync_disk(nodes_data=nodes_data)
            ax_last = plt.gca()

        # Single plot_stage_markers call after ALL subplots are created
        if has_annotations and ax_pipeline is not None and ax_last is not None:
            all_stages = [
                {**s, "_hostname": hostname}
                for hostname, stages in nodes_annotations
                for s in stages
            ]
            plot_stage_markers(
                all_stages,
                ax_top=ax_pipeline,
                ax_bottom=ax_last,
                xlim=self.xlim,
                color_map=color_map,
                linewidth=1.6,
                linestyle_start=(0, (4, 3)),
                linestyle_stop=(0, (4, 3)),
                stop_as_markers=True,
                show_legend=True,
                legend_loc="upper center",
            )

        plt.tight_layout(h_pad=1.5)

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
            # Check if CPU data is available
            if not hasattr(data.system_metrics, 'cpu_stamps') or len(data.system_metrics.cpu_stamps) == 0:
                self.logger.warning(f"No CPU data available for node {data.hostname}")
                continue

            if not hasattr(data.system_metrics, 'cpu_prof') or 'cpu' not in data.system_metrics.cpu_prof:
                self.logger.warning(f"No CPU profile data available for node {data.hostname}")
                continue

            ts = data.system_metrics.cpu_stamps
            spaces = ["user", "nice", "system", "iowait", "irq", "softirq", "steal", "guest", "guestnice"]

            # Check if all required spaces exist in cpu_prof
            cpu_data = []
            for space in spaces:
                if space in data.system_metrics.cpu_prof["cpu"]:
                    cpu_data.append(data.system_metrics.cpu_prof["cpu"][space])
                else:
                    self.logger.warning(f"Missing CPU space '{space}' for node {data.hostname}")

            if not cpu_data:
                self.logger.warning(f"No valid CPU spaces found for node {data.hostname}")
                continue

            cpu = sum(cpu_data)
            plt.plot(ts, cpu, label=data.hostname)

            ts_sync += [ts]
            cpu_sync += [cpu]

        # Only sync if we have data
        if ts_sync and cpu_sync:
            self.sync_metrics(ts_list=ts_sync, dev_list=cpu_sync, opt="avg", label="average", color="k")

        yrng = 10
        plt.yticks(100 / yrng * np.arange(yrng + 1))
        self.set_frame(label="Total CPU usage (%)")


    def plot_sync_cpu_binary(self, nodes_data: list) -> None:
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
            # Check if CPU frequency data is available
            if not hasattr(data.system_metrics, 'cpufreq_stamps') or len(data.system_metrics.cpufreq_stamps) == 0:
                self.logger.warning(f"No CPU frequency timestamps available for node {data.hostname}")
                continue

            if not hasattr(data.system_metrics, 'cpufreq_vals') or 'mean' not in data.system_metrics.cpufreq_vals:
                self.logger.warning(f"No CPU frequency data available for node {data.hostname}")
                continue

            ts = data.system_metrics.cpufreq_stamps
            cpufreq = data.system_metrics.cpufreq_vals["mean"]

            # Check if arrays have same length
            if len(ts) != len(cpufreq):
                self.logger.warning(f"Timestamp and frequency data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, cpufreq, label=data.hostname)

            ts_sync += [ts]
            cpufreq_sync += [cpufreq]

        # Only sync if we have data
        if ts_sync and cpufreq_sync:
            self.sync_metrics(ts_list=ts_sync, dev_list=cpufreq_sync, opt="avg", label="average", color="k")
        self.set_frame(label="Mean CPU frequency (GHz)")


    def plot_sync_cpufreq_binary(self, nodes_data: list) -> None:
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
            # Check if memory data is available
            if not hasattr(data.system_metrics, 'mem_stamps') or len(data.system_metrics.mem_stamps) == 0:
                self.logger.warning(f"No memory timestamps available for node {data.hostname}")
                continue

            if not hasattr(data.system_metrics, 'mem_prof') or not data.system_metrics.mem_prof:
                self.logger.warning(f"No memory profile data available for node {data.hostname}")
                continue

            # Check if required memory fields exist
            if 'MemTotal' not in data.system_metrics.mem_prof or 'MemFree' not in data.system_metrics.mem_prof:
                self.logger.warning(f"Missing MemTotal or MemFree data for node {data.hostname}")
                continue

            if (len(data.system_metrics.mem_prof["MemTotal"]) == 0
                    or len(data.system_metrics.mem_prof["MemFree"]) == 0):
                self.logger.warning(f"Empty memory data arrays for node {data.hostname}")
                continue

            memunit = 1024**2
            ts = data.system_metrics.mem_stamps
            mem = (data.system_metrics.mem_prof["MemTotal"] - data.system_metrics.mem_prof["MemFree"]) / memunit

            # Check if arrays have same length
            if len(ts) != len(mem):
                self.logger.warning(f"Timestamp and memory data length mismatch for node {data.hostname}")
                continue

            plt.fill_between(ts, sum(memtotal), sum(memtotal) + mem, label=data.hostname)

            plt.plot(ts, sum(memtotal) * np.ones_like(ts), color="grey", lw=1)
            memtotal += [data.system_metrics.mem_prof["MemTotal"][0] / memunit]

            ts_sync += [ts]
            mem_sync += [mem]

        if memtotal and len(memtotal) > 1:  # Check if we have any memory data
            if ts_sync and mem_sync:
                plt.plot(ts, sum(memtotal) * np.ones_like(ts), color="grey", lw=1)
                self.sync_metrics(ts_list=ts_sync, dev_list=mem_sync, label="sum", color="k", ls="-.")

            for powtwo in range(25):
                yticks = np.arange(0, sum(memtotal) + 2**powtwo, 2**powtwo, dtype="i")
                if len(yticks) < self.args.fig_yrange:
                    break
            plt.yticks(yticks)
        self.set_frame(label="Memory (GiB)")


    def plot_sync_mem_binary(self, nodes_data: list) -> None:
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
        self.set_frame(label="Memory (GiB)")


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
            # Check if network data is available
            if not hasattr(data.system_metrics, 'net_stamps') or len(data.system_metrics.net_stamps) == 0:
                self.logger.warning(f"No network timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'net_rx_total')
                    or not hasattr(data.system_metrics, 'net_rx_data')):
                self.logger.warning(f"No network RX data available for node {data.hostname}")
                continue

            ts = data.system_metrics.net_stamps
            net_rx = data.system_metrics.net_rx_total

            # Check if arrays have same length
            if len(ts) != len(net_rx):
                self.logger.warning(f"Timestamp and network RX data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, net_rx, marker="v", label=f"rx:{data.hostname} ({int(data.system_metrics.net_rx_data)} MB)")

            ts_sync += [ts]
            net_rx_sync += [net_rx]
            rx_data += data.system_metrics.net_rx_data

        if ts_sync and net_rx_sync:
            self.sync_metrics(ts_list=ts_sync,
                              dev_list=net_rx_sync,
                              label=f"rx:sum ({int(rx_data)} MB)",
                              marker="v",
                              ls="--")

        ts_sync = []
        net_tx_sync = []
        tx_data = 0
        for data in nodes_data:
            # Check if network TX data is available
            if not hasattr(data.system_metrics, 'net_stamps') or len(data.system_metrics.net_stamps) == 0:
                self.logger.warning(f"No network timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'net_tx_total')
                    or not hasattr(data.system_metrics, 'net_tx_data')):
                self.logger.warning(f"No network TX data available for node {data.hostname}")
                continue

            ts = data.system_metrics.net_stamps
            net_tx = data.system_metrics.net_tx_total

            # Check if arrays have same length
            if len(ts) != len(net_tx):
                self.logger.warning(f"Timestamp and network TX data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, net_tx, marker="^", label=f"tx:{data.hostname} ({int(data.system_metrics.net_tx_data)} MB)")

            ts_sync += [ts]
            net_tx_sync += [net_tx]
            tx_data += data.system_metrics.net_tx_data

        if ts_sync and net_tx_sync:
            self.sync_metrics(ts_list=ts_sync,
                              dev_list=net_tx_sync,
                              label=f"tx:sum ({int(tx_data)} MB)",
                              marker="^",
                              ls="--",
                              with_yrange=(tx_data > rx_data))

        self.set_frame(label="Network Activity (MB/s)")


    def plot_sync_net_binary(self, nodes_data: list) -> None:
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
            # Check if disk read data is available
            if not hasattr(data.system_metrics, 'disk_stamps') or len(data.system_metrics.disk_stamps) == 0:
                self.logger.warning(f"No disk timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'disk_rd_total')
                    or not hasattr(data.system_metrics, 'disk_rd_data')):
                self.logger.warning(f"No disk read data available for node {data.hostname}")
                continue

            ts = data.system_metrics.disk_stamps
            disk_rd = data.system_metrics.disk_rd_total

            # Check if arrays have same length
            if len(ts) != len(disk_rd):
                self.logger.warning(f"Timestamp and disk read data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, disk_rd, marker="v", label=f"rd:{data.hostname} ({int(data.system_metrics.disk_rd_data)} MB)")

            ts_sync += [ts]
            rd_sync += [disk_rd]
            rd_data += data.system_metrics.disk_rd_data

        if ts_sync and rd_sync:
            self.sync_metrics(ts_list=ts_sync, dev_list=rd_sync,
                              label=f"rd:sum ({int(rd_data)} MB)", marker="v", ls="--")

        ts_sync = []
        wr_sync = []
        wr_data = 0
        for data in nodes_data:
            # Check if disk write data is available
            if not hasattr(data.system_metrics, 'disk_stamps') or len(data.system_metrics.disk_stamps) == 0:
                self.logger.warning(f"No disk timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'disk_wr_total')
                    or not hasattr(data.system_metrics, 'disk_wr_data')):
                self.logger.warning(f"No disk write data available for node {data.hostname}")
                continue

            ts = data.system_metrics.disk_stamps
            disk_wr = data.system_metrics.disk_wr_total

            # Check if arrays have same length
            if len(ts) != len(disk_wr):
                self.logger.warning(f"Timestamp and disk write data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, disk_wr, marker="^", label=f"wr:{data.hostname} ({int(data.system_metrics.disk_wr_data)} MB)")

            ts_sync += [ts]
            wr_sync += [disk_wr]
            wr_data += data.system_metrics.disk_wr_data

        if ts_sync and wr_sync:
            self.sync_metrics(ts_list=ts_sync,
                              dev_list=wr_sync,
                              label=f"wr:sum ({int(wr_data)} MB)",
                              marker="^",
                              ls="--",
                              with_yrange=(wr_data > rd_data))

        self.set_frame(label="Disk Activity (MB/s)")


    def plot_sync_disk_binary(self, nodes_data: list) -> None:
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
            # Check if InfiniBand RX data is available
            if not hasattr(data.system_metrics, 'ib_stamps') or len(data.system_metrics.ib_stamps) == 0:
                self.logger.warning(f"No InfiniBand timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'ib_rx_total')
                    or not hasattr(data.system_metrics, 'ib_rx_data')):
                self.logger.warning(f"No InfiniBand RX data available for node {data.hostname}")
                continue

            ts = data.system_metrics.ib_stamps
            ib_rx = data.system_metrics.ib_rx_total

            # Check if arrays have same length
            if len(ts) != len(ib_rx):
                self.logger.warning(f"Timestamp and InfiniBand RX data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, ib_rx, marker="v", label=f"rx:{data.hostname} ({int(data.system_metrics.ib_rx_data)} MB)")

            ts_sync += [ts]
            ib_rx_sync += [ib_rx]
            rx_data += data.system_metrics.ib_rx_data

        if ts_sync and ib_rx_sync:
            self.sync_metrics(ts_list=ts_sync,
                              dev_list=ib_rx_sync,
                              label=f"rx:sum ({int(rx_data)} MB)",
                              marker="v",
                              ls="--",
                              with_yrange=True)

        ts_sync = []
        ib_tx_sync = []
        tx_data = 0
        for data in nodes_data:
            # Check if InfiniBand TX data is available
            if not hasattr(data.system_metrics, 'ib_stamps') or len(data.system_metrics.ib_stamps) == 0:
                self.logger.warning(f"No InfiniBand timestamps available for node {data.hostname}")
                continue

            if (not hasattr(data.system_metrics, 'ib_tx_total')
                    or not hasattr(data.system_metrics, 'ib_tx_data')):
                self.logger.warning(f"No InfiniBand TX data available for node {data.hostname}")
                continue

            ts = data.system_metrics.ib_stamps
            ib_tx = data.system_metrics.ib_tx_total

            # Check if arrays have same length
            if len(ts) != len(ib_tx):
                self.logger.warning(f"Timestamp and InfiniBand TX data length mismatch for node {data.hostname}")
                continue

            plt.plot(ts, ib_tx, marker="^", label=f"tx:{data.hostname} ({int(data.system_metrics.ib_tx_data)} MB)")

            ts_sync += [ts]
            ib_tx_sync += [ib_tx]
            tx_data += data.system_metrics.ib_tx_data

        if ts_sync and ib_tx_sync:
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
                # Check if power performance metrics are available
                if not hasattr(data, 'power_perf_metrics'):
                    self.logger.warning(f"No power performance metrics available for node {data.hostname}")
                    continue

                data.power_perf_metrics.plot_events(pre_label=f"{data.hostname}:")

        if self.args.pow_g5k:
            for data in nodes_data:
                # Check if G5K power metrics are available
                if not hasattr(data, 'power_g5k_metrics'):
                    self.logger.warning(f"No G5K power metrics available for node {data.hostname}")
                    continue

                data.power_g5k_metrics.plot_g5k_pow_profiles(pre_label=f"{data.hostname}:")

        self.set_frame(label="Power (W)")

    def plot_sync_annotations(self, nodes_annotations: list, ax) -> None:
        """
        Plot superposed/stacked annotation timelines for all nodes.

        Each node gets its own row in the subplot, stages drawn as horizontal segments.

        Args:
            nodes_annotations (list): list of (hostname, annotation_stages) tuples
            ax: matplotlib axis to draw on
        """
        if not nodes_annotations:
            return

        n_nodes = len(nodes_annotations)
        # One row per node, y in [0, n_nodes]
        ax.set_ylim(0, n_nodes)
        ax.set_yticks(np.arange(n_nodes) + 0.5)
        ax.set_yticklabels([hostname for hostname, _ in nodes_annotations], fontsize=8)
        ax.set_ylabel("Pipeline Events", fontsize=9)

        if self.xlim:
            ax.set_xlim(self.xlim)

        cap_height = 0.06

        for row_idx, (hostname, stages) in enumerate(nodes_annotations):
            y_center = row_idx + 0.5
            for stage in stages:
                color = get_stage_color(stage["label"])
                start = stage["start"]
                stop = stage["stop"]

                # Horizontal segment
                ax.hlines(y=y_center, xmin=start, xmax=stop,
                          linewidth=2.0, color=color)
                # Start cap
                ax.vlines(x=start,
                          ymin=y_center - cap_height,
                          ymax=y_center + cap_height,
                          linewidth=2.0, color=color)
                # Stop cap
                ax.vlines(x=stop,
                          ymin=y_center - cap_height,
                          ymax=y_center + cap_height,
                          linewidth=2.0, color=color)
                # Label above segment
                ax.text(
                    (start + stop) / 2,
                    y_center + cap_height * 1.5,
                    stage["label"],
                    ha="center", va="bottom",
                    fontsize=7, fontweight="bold",
                    color=color,
                )

        ax.grid(True, axis="x")
        add_stage_legend(ax)

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
        # Check if we have data to sync
        if not ts_list or not dev_list:
            self.logger.warning("No data available for sync operation")
            return

        if len(ts_list) != len(dev_list):
            self.logger.warning("Timestamp and device lists have different lengths")
            return

        # Check if all arrays are non-empty
        valid_pairs = []
        for ts, dev in zip(ts_list, dev_list):
            if len(ts) > 0 and len(dev) > 0 and len(ts) == len(dev):
                valid_pairs.append((ts, dev))
            else:
                self.logger.warning("Skipping invalid timestamp/device pair in sync")

        if not valid_pairs:
            self.logger.warning("No valid data pairs for sync operation")
            return

        SYNC_FREQ = 1  # noqa: N806
        all_ts = [ts for ts, _ in valid_pairs]
        ts_sync = np.unique(np.round(np.concatenate(all_ts), SYNC_FREQ))
        dev_sync = np.zeros_like(ts_sync)

        for ts, dev in valid_pairs:
            interpolator = interp1d(ts, dev, kind="linear", fill_value="extrapolate", bounds_error=False)
            dev_sync += interpolator(ts_sync)

        divider = len(valid_pairs) if opt == "avg" else 1

        plt.plot(ts_sync, dev_sync / divider, label=label, color=color, ls=ls, marker=marker)

        if with_yrange and len(dev_sync) > 0:
            maxval = max(dev_sync / divider)
            for powtwo in range(25):
                yticks = np.arange(0, maxval + 2**powtwo, 2**powtwo, dtype="i")
                if len(yticks) < self.args.fig_yrange:
                    break
            plt.yticks(yticks)


    def plot_node_annotation(self, hostname: str, stages: list, ax,
                             color_map: dict) -> None:
        """
        Draw the annotation timeline for a single node — staircase layout.

        Color is resolved from color_map[(hostname, label)] so that
        node1/stageA and node2/stageA always get different colors.

        Args:
            hostname    : Node hostname — used as y-axis label
            stages      : List of stage dicts {label, start, stop}
            ax          : Matplotlib axis
            color_map   : (hostname, label) → color index
        """
        if self.xlim:
            ax.set_xlim(self.xlim)

        ax.set_yticks([])
        ax.set_ylim(0, 1)
        ax.set_ylabel(hostname, fontsize=8, rotation=0, labelpad=60, va="center")
        ax.grid(True, axis="x")

        if not stages:
            return

        # Staircase layout — identical to plot_stage_timeline
        y_base = 0.2
        y_step = 0.6 / max(len(stages), 1)
        cap_height = 0.03

        for i, stage in enumerate(stages):
            # Interleaved color: (hostname, label) → index
            color = get_stage_color(color_map.get((hostname, stage["label"]), i))
            y = y_base + i * y_step
            start = stage["start"]
            stop = stage["stop"]

            ax.hlines(y=y, xmin=start, xmax=stop, linewidth=1.6, color=color,
                      transform=ax.get_xaxis_transform())
            ax.axvline(x=start, ymin=y - cap_height, ymax=y + cap_height,
                       linewidth=1.6, color=color)
            ax.axvline(x=stop, ymin=y - cap_height, ymax=y + cap_height,
                       linewidth=1.6, color=color)
            ax.text(
                (start + stop) / 2, y + cap_height * 1.5, stage["label"],
                ha="center", va="bottom", fontsize=7, fontweight="bold",
                color=color, transform=ax.get_xaxis_transform(),
            )
