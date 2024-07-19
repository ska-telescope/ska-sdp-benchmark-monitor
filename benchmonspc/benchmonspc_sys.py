#!/usr/bin/env python3

import csv
import time
import numpy as np
import matplotlib.pyplot as plt

class DoolData():
    """
    Dool database
    """
    def __init__(self, csv_filename):
        """
        Constructor
        """
        self.csv_filename = csv_filename
        self.csv_report = []

        self.prof_keys = []
        self.prof = {}

        self.ncpu = 0
        self.with_io = True

        self._stamps = np.array([])
        self._xticks = ()
        self._xlim = []

        self._plt_xrange = 20
        self._plt_xlim_coef = 0.025

        self.read_csv_report()
        self.create_profile()
        self.create_plt_params()


    def read_csv_report(self) -> int:
        """
        Parse the csv report
        """
        self.csv_report = []
        with open(self.csv_filename, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                self.csv_report.append(row)

        version = self.csv_report[0]
        host = self.csv_report[2]
        command = self.csv_report[3]

        if not ("read" in self.csv_report[5] and "writ" in self.csv_report[5]):
            self.with_io = False

        print(f"version: {''.join(version)}")
        print(f"Hostname: {host[1]}")
        print(f"Username: {host[-1]}")
        print(f"Commandline: {command[1]}")

        return 0


    def create_profile(self) -> int:
        """
        Create profiling dictionary
        """
        # Get total number of cpus
        self.ncpu = int(self.csv_report[5][-1]) + 1

        # Init dictionaries containing indices
        sys_idx = {}
        io_idx = {}
        net_idx = {}
        cpu_idx = {}

        # Corresponding indices to system columns: "--time"
        sys_idx = {"time": 0}

        # Corresponding indices to memory columns: "--mem --swap"
        mi0 = len(sys_idx)
        mem_labels = ["mem-used", "mem-free", "mem-cach", "mem-avai", "swp-used", "swp-free"]
        mem_idx = {label: mi0 + idx for idx, label in enumerate(mem_labels)}

        # Corresponding indices to io/disk columns "--io --aio --disk --fs"
        ii0 = len(sys_idx) + len(mem_idx)
        io_labels = ["io-async", "fs-file", "fs-inod"]
        if self.with_io:
            io_labels = ["io-read", "io-writ", "io-async", "dsk-read", "dsk-writ", "fs-file", "fs-inod"]
        io_idx = {label: ii0 + idx for idx, label in enumerate(io_labels)}

        # Corresponding indices to network: "--net"
        ni0 = len(sys_idx) + len(mem_idx) + len(io_idx)
        net_labels = ["net-recv", "net-send"]
        net_idx = {label: ni0 + idx for idx, label in enumerate(net_labels)}

        # Corresponding indices to CPU: "--cpu --cpu-use"
        ci0 = len(sys_idx) + len(mem_idx) + len(io_idx) + len(net_idx)
        cpu_labels = ["cpu-usr", "cpu-sys", "cpu-idl", "cpu-wai", "cpu-stl"] \
                        + [f"cpu-{i}" for i in range(self.ncpu)]
        cpu_idx = {label: ci0 + idx for idx, label in enumerate(cpu_labels)}

        # Full indices correspondance
        prof_idx = {**sys_idx, **mem_idx, **io_idx, **net_idx, **cpu_idx}
        self.prof_keys = list(prof_idx.keys())

        # Construct full profiling dictionary of list
        for key in self.prof_keys:
            self.prof[key] = []

        # Loop on timestamps (timing starts for index 6)
        for stamp in range(6, len(self.csv_report)):

            # Loop on keys
            for key in self.prof_keys:

                # Skip csv non-informative lines
                if self.csv_report[stamp] == []:
                    continue
                elif self.csv_report[stamp][0] in ("Host:", "Cmdline:", "system", "time"):
                    continue

                # Get value
                val = self.csv_report[stamp][prof_idx[key]]

                # Convert val to float (execpt time)
                if key != "time":
                    val = float(val)

                # Append value to dictonary
                self.prof[key].append(val)

        # Convert list to numpy array
        for key in self.prof_keys:
            self.prof[key] = np.array(self.prof[key])

        return 0


    def create_plt_params(self) -> int:
        """
        Create plot parameters
        """
        self._stamps = self.prof["time"].astype(np.float64)
        nstamps = len(self._stamps)
        xstride = max(1, nstamps // self._plt_xrange)
        val0 = self._stamps[0]
        vallst = self._stamps[xstride: nstamps-xstride+1: xstride]
        valf = self._stamps[-1]
        xticks_val = [val0] + vallst.tolist() + [valf]

        t0 = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[0]))
        tlst = np.round(self._stamps[xstride: nstamps-xstride+1: xstride] - self._stamps[0], 2)
        tf = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[-1]))
        xticks_label = [t0] + tlst.astype("int").tolist() + [tf]

        self._xticks = (xticks_val, xticks_label)

        dx = (valf - val0) * self._plt_xlim_coef
        self._xlim = [val0 - dx, valf + dx]

        return 0


    def plot_cpu_average(self) -> int:
        """
        Plot average cpu usage
        """
        alpha = .8

        cpu_usr = self.prof["cpu-usr"]
        cpu_sys = self.prof["cpu-sys"]
        cpu_wai = self.prof["cpu-wai"]
        cpu_stl = self.prof["cpu-stl"]
        plt.fill_between(self._stamps, 0, 100, color="C7", alpha=alpha/3, label="idle")
        plt.fill_between(self._stamps, 0, cpu_usr, color="C0", alpha=alpha, label="usr")
        plt.fill_between(self._stamps, cpu_usr, cpu_usr+cpu_sys, color="C4", alpha=alpha, label="sys")
        plt.fill_between(self._stamps, cpu_usr+cpu_sys, cpu_usr+cpu_sys+cpu_wai, color="C8", alpha=alpha, label="wait")
        plt.fill_between(self._stamps, cpu_usr+cpu_sys+cpu_wai, cpu_usr+cpu_sys+cpu_wai+cpu_stl, color="C5", alpha=alpha, label="stl")

        plt.xticks(self._xticks[0], self._xticks[1])
        plt.xlim(self._xlim)
        _yrange = 10
        plt.yticks(100 / _yrange * np.arange(_yrange + 1))
        plt.ylabel("CPU usage (%)")
        plt.xlabel("Time (s)")
        plt.grid()
        plt.legend(loc=1)

        return 0


    def plot_cpu_per_core(self, with_legend: bool = False, with_color_bar: bool = False,
                          fig=None, nsbp: int = None, sbp: int = None) -> int:
        """
        Plot cpu per core

        Args:
            with_legend (bool): Plot cores usage with legend
            with_color_bar (bool): Plot cores usage with colobar (color gardient)
            fig (obj): Figure object (matplotlib)
            nsbp (int): Total number of subplots
            sbp (int): Number of current subplots
        """
        alpha = 0.8
        cm = plt.cm.jet(np.linspace(0, 1, self.ncpu+1))
        cpu_n = 0
        for cpu in range(self.ncpu):
            if cpu > 0:
                cpu_n = cpu_nn
            cpu_nn = self.prof[f"cpu-{cpu}"] / self.ncpu + cpu_n
            plt.fill_between(self._stamps, cpu_n, cpu_nn, color=cm[cpu], alpha=alpha, label=f"cpu-{cpu}")
        plt.xticks(self._xticks[0], self._xticks[1])
        _yrange = 10
        plt.yticks(100 * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(self._xlim)
        plt.ylabel(f" CPU Cores (x{self.ncpu}) (%)")
        plt.grid()
        plt.xlabel("Time (s)")

        if with_legend:
            plt.legend(loc=1, ncol=3)

        if with_color_bar:
            cax = fig.add_axes([0.955, 1 - (sbp-.2)/nsbp, fig.get_figwidth()/1e4, .7/nsbp]) # [left, bottom, width, height]
            plt.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(vmin=1, vmax=self.ncpu), cmap=plt.cm.jet), \
                         ticks=np.linspace(1, self.ncpu, min(self.ncpu, 5), dtype="i"), cax=cax)

        return 0


    def plot_memory_usage(self) -> int:
        """
        Plot memory usage
        """
        alpha = .3
        mem_unit = 1024 ** 3 # (GB)

        # Total memory
        plt.fill_between(self._stamps, self.prof["mem-used"] / mem_unit, (self.prof["mem-used"] + self.prof["mem-cach"] + self.prof["mem-free"]) / mem_unit, alpha=alpha, label="Total memory", color="b")

        # Used memory
        plt.fill_between(self._stamps, 0, self.prof["mem-used"] / mem_unit, alpha=alpha*3, label="Used memory", color="b")

        # Total swap
        plt.fill_between(self._stamps, 0, (self.prof["swp-used"] + self.prof["swp-free"]) / mem_unit, alpha=alpha, label="Total swap", color="r")

        # Used swap
        plt.fill_between(self._stamps, 0, self.prof["swp-used"] / mem_unit, alpha=alpha*3, label="Used swap", color="r")

        plt.xticks(self._xticks[0], self._xticks[1])
        plt.xlim(self._xlim)
        plt.yticks(np.linspace(0, max((self.prof["mem-used"] + self.prof["mem-cach"] + self.prof["mem-free"]) / mem_unit), 5, dtype="i"))
        plt.ylabel("Memory (GB)")
        plt.legend(loc=1)
        plt.grid()
        plt.xlabel("Time (s)")

        return 0


    def plot_network(self) -> int:
        """
        Plot network activity
        """
        # Yplot: #opened_files - #inodes
        plt.plot(self._stamps, self.prof["fs-file"], "g-", label="# Open file")
        plt.plot(self._stamps, self.prof["fs-inod"], "y-", label="# inodes")
        plt.ylabel("Total number")
        plt.xlabel("Time (s)")
        plt.xticks(self._xticks[0], self._xticks[1])
        plt.xlim(self._xlim)
        plt.legend(loc=2)
        plt.grid()

        # YYplot: download - upload
        alpha = .5
        mem_unit = 1024 ** 2
        pltt = plt.twinx()
        pltt.fill_between(self._stamps, 0, self.prof["net-recv"] / mem_unit, alpha=alpha, color="b", label="Recv")
        pltt.fill_between(self._stamps, 0, self.prof["net-send"] / mem_unit, alpha=alpha, color="r", label="Send")
        pltt.grid()
        pltt.set_ylabel("Network (MB/s)")
        pltt.legend(loc=1)

        return 0


    def plot_io(self) -> int:
        """
        Plot IO stats
        """
        if self.with_io:
            alpha = .5
            mem_unit = 1024 ** 2

            # Yplot: #read-requests; #write-requests; #async-requests
            plt.plot(self._stamps, self.prof["io-read"], "b-", label="#read")
            plt.plot(self._stamps, self.prof["io-writ"], "r-", label="#write")
            plt.plot(self._stamps, self.prof["io-async"], "g-", label="#async")
            plt.ylabel("# Number of requests")
            plt.xticks(self._xticks[0], self._xticks[1])
            plt.xlim(self._xlim)
            plt.legend(loc=2)
            plt.xlabel("Time (s)")
            plt.grid()

            # YYplot: disk-read; disk-write
            pltt = plt.twinx()
            pltt.fill_between(self._stamps, 0, self.prof["dsk-read"] / mem_unit, color="b", alpha=alpha, label="Disk read")
            pltt.fill_between(self._stamps, 0, self.prof["dsk-writ"] / mem_unit, color="r", alpha=alpha, label="Disk write")
            pltt.set_ylabel("IO (MB)")
            pltt.legend(loc=1)
            plt.grid()

        return 0
