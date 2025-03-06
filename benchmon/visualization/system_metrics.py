#!/usr/bin/env python3

import csv
import time
import numpy as np
import matplotlib.pyplot as plt
from math import ceil

PLT_XLIM_COEF = 0.025
PLT_XRANGE = 20

def read_sys_info(any_reportpath) -> int:
    """
    Parse and read sys_info.txt file
    """
    import os
    sys_info_txtfile = os.path.dirname(any_reportpath) + "/sys_info.txt"
    sys_info = {}
    with open(sys_info_txtfile, "r") as file:
        for line in file:
            _key, _val = line.strip().split(": ")
            sys_info[_key] = _val

    for _key in ["cpu_freq_max", "cpu_freq_min"]:
        sys_info[_key] = float(sys_info[_key])

    for _key in ["online_cores", "offline_cores"]:
        sys_info[_key] = [int(lcore) for lcore in sys_info[_key].split(" ")][1:]

    return sys_info


def plot_inline_calls(calls: dict, ymax: float = 100., xlim: list = []):
    """
    Generic plot of call inline
    """
    cm = plt.cm.gist_earth(np.linspace(0, 1, len(calls)+1))

    ypos = lambda idx: - 0.03 * ymax - 0.03 * idx * ymax
    ylim = lambda idx: (- 0.15 * ymax - 0.03 * idx * ymax, 1.1 * ymax)
    for idx, call in enumerate(calls):
        plt.plot(calls[call], ypos(idx) * np.ones(len(calls[call])), ".", ms=4, c=cm[idx])
        plt.text(np.mean(calls[call]), ypos(idx)*1.5, call, va="top", ha="center", c=cm[idx], weight="bold")
    plt.ylim(ylim(idx))


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

        self.sys_info = read_sys_info(self.csv_filename)
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
        # Get total number of active cpus (by looking for number just before freq column)
        self.ncpu = len(self.sys_info["online_cores"])
        self.ncpu_all = self.ncpu + len(self.sys_info["offline_cores"])

        self.is_mono_threaded = False
        if self.ncpu < self.ncpu_all:
            self.is_mono_threaded = True

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
                        + [f"cpu-{i}" for i in range(self.ncpu)] \
                        + [f"freq-{i}" for i in range(self.ncpu_all)]
        cpu_idx = {label: ci0 + idx for idx, label in enumerate(cpu_labels)}

        # Omit logical core freq when monothreaded
        if self.is_mono_threaded:
            for lcore in self.sys_info["offline_cores"]:
                cpu_idx.pop(f"freq-{lcore}")

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
                elif self.csv_report[stamp][0] in ("Host:", "Cmdline:", "system", "time", "epoch"):
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
        xstride = max(1, nstamps // PLT_XRANGE)
        val0 = self._stamps[0]
        vallst = self._stamps[xstride: nstamps-xstride+1: xstride]
        valf = self._stamps[-1]
        xticks_val = [val0] + vallst.tolist() + [valf]

        t0 = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[0]))
        tlst = np.round(self._stamps[xstride: nstamps-xstride+1: xstride] - self._stamps[0], 2)
        tf = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[-1]))
        xticks_label = [t0] + tlst.astype("int").tolist() + [tf]

        self._xticks = (xticks_val, xticks_label)

        dx = (valf - val0) * PLT_XLIM_COEF
        self._xlim = [val0 - dx, valf + dx]

        return 0


    def plot_cpu_average(self, xticks, xlim, calls: dict = None) -> int:
        """
        Plot average cpu usage
        """
        alpha = .8

        cpu_usr = self.prof["cpu-usr"]
        cpu_sys = self.prof["cpu-sys"]
        cpu_wai = self.prof["cpu-wai"]
        cpu_stl = self.prof["cpu-stl"]
        plt.fill_between(self._stamps, 0, 100, color="C7", alpha=alpha/3, label="dool: idle")
        plt.fill_between(self._stamps, 0, cpu_stl, color="C5", alpha=alpha, label="dool: virt")
        plt.fill_between(self._stamps, cpu_stl, cpu_stl+cpu_wai, color="C8", alpha=alpha, label="dool: wait")
        plt.fill_between(self._stamps, cpu_stl+cpu_wai, cpu_stl+cpu_wai+cpu_sys, color="C4", alpha=alpha, label="dool: sys")
        plt.fill_between(self._stamps, cpu_stl+cpu_wai+cpu_sys, cpu_stl+cpu_wai+cpu_sys+cpu_usr, color="C0", alpha=alpha, label="dool: usr")

        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)
        _yrange = 10
        plt.yticks(100 / _yrange * np.arange(_yrange + 1))
        plt.ylabel("CPU average usage (%)")
        plt.grid()
        # plt.title("dool: cpu average usage")

        # Order legend
        _order = [0, 4, 3, 2, 1]
        _handles, _labels = plt.gca().get_legend_handles_labels()
        plt.legend([_handles[idx] for idx in _order],[_labels[idx] for idx in _order], loc=1)

        if calls:
            plot_inline_calls(calls=calls)

        return 0


    def plot_cpu_per_core(self, xticks, xlim, cores_in: str = "", cores_out: str = "", calls: dict = None) -> int:
        """
        Plot cpu per core
        """

        cores = [core for core in range(self.ncpu)]
        if len(cores_in) > 0:
            cores = [int(core) for core in cores_in.split(",")]
        elif len(cores_in) == 0 and len(cores_out) > 0:
            for core_ex in cores_out.split(","):
                cores.remove(int(core_ex))
        _ncpu = len(cores)

        cm = plt.cm.jet(np.linspace(0, 1, _ncpu+1))
        for idx, core in enumerate(cores):
            plt.plot(self._stamps, self.prof[f"cpu-{core}"], color=cm[idx], label=f"dool: core-{core}")
        plt.xticks(xticks[0], xticks[1])
        _yrange = 10
        plt.yticks(100 * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(xlim)
        plt.ylabel(f"(Dool) CPU Cores (%)")
        plt.grid()

        plt.legend(loc=0, ncol=_ncpu // ceil(_ncpu/16) , fontsize="6")

        if calls:
            plot_inline_calls(calls=calls)

        return 0


    def plot_cpu_per_core_acc(self, xticks, xlim, with_legend: bool = False, with_color_bar: bool = False,
                          fig=None, nsbp: int = None, sbp: int = None) -> int:
        """
        Plot cpu per core in an accumulated way

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
        plt.xticks(xticks[0], xticks[1])
        _yrange = 10
        plt.yticks(100 * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(xlim)
        plt.ylabel(f" CPU Cores (x{self.ncpu}) (%)")
        plt.grid()

        if with_legend:
            plt.legend(loc=1, ncol=3)

        if with_color_bar:
            cax = fig.add_axes([0.955, 1 - (sbp-.2)/nsbp, fig.get_figwidth()/1e4, .7/nsbp]) # [left, bottom, width, height]
            plt.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(vmin=1, vmax=self.ncpu), cmap=plt.cm.jet), \
                         ticks=np.linspace(1, self.ncpu, min(self.ncpu, 5), dtype="i"), cax=cax)

        return 0


    def plot_cpu_freq(self, xticks, xlim, cores_in: str = "", cores_out: str = "", calls: dict = None) -> int:
        """
        Plot cpu per core
        """
        cpu_freq_min = self.sys_info["cpu_freq_min"] / 1e6 # GHz
        cpu_freq_max = self.sys_info["cpu_freq_max"] / 1e6 # GHz

        cores = [core for core in range(self.ncpu)]
        if len(cores_in) > 0:
            cores = [int(core) for core in cores_in.split(",")]
        elif len(cores_in) == 0 and len(cores_out) > 0:
            for core_ex in cores_out.split(","):
                cores.remove(int(core_ex))
        _ncpu = len(cores)


        cm = plt.cm.jet(np.linspace(0, 1, _ncpu+1))

        _nstamps = len(self._stamps)
        freq_mean = np.zeros(_nstamps)

        for idx, core in enumerate(cores):
            plt.plot(self._stamps, self.prof[f"freq-{core}"] * (cpu_freq_max / 100), color=cm[idx], label=f"dool: core-{core}")

        for cpu in range(self.ncpu):
            freq_mean += self.prof[f"freq-{cpu}"] / self.ncpu * (cpu_freq_max / 100)
        plt.plot(self._stamps, freq_mean, "k.-", label=f"mean")

        plt.plot(self._stamps, cpu_freq_max * np.ones(_nstamps), "gray", linestyle="--", label=f"hw max/min")
        plt.plot(self._stamps, cpu_freq_min * np.ones(_nstamps), "gray", linestyle="--")

        plt.xticks(xticks[0], xticks[1])
        _yrange = 10
        plt.yticks(cpu_freq_max * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(xlim)
        plt.ylabel(f" CPU frequencies (GHz)")
        plt.grid()

        plt.legend(loc=0, ncol=self.ncpu // ceil(self.ncpu/16) , fontsize="6")

        if calls:
            plot_inline_calls(calls=calls, ymax=cpu_freq_max)

        return 0


    def plot_memory_usage(self, xticks, xlim, calls: dict = None) -> int:
        """
        Plot memory usage
        """
        alpha = .3
        mem_unit = 1024 ** 3 # (GB)

        # Total memory
        memtotal = (self.prof["mem-used"] + self.prof["mem-cach"] + self.prof["mem-free"]) / mem_unit
        plt.fill_between(self._stamps, memtotal, alpha=alpha, label="dool: MemTotal", color="b")

        # Used memory
        memused =  self.prof["mem-used"] / mem_unit
        plt.fill_between(self._stamps, memused, alpha=alpha*3, label="dool: MemUsed", color="b")

        # Cache memory
        memcach = self.prof["mem-cach"] / mem_unit
        plt.fill_between(self._stamps, memused, memused + memcach, alpha=alpha*2, label="dool: MemCach", color="g")

        # Total swap
        swaptotal = (self.prof["swp-used"] + self.prof["swp-free"]) / mem_unit
        plt.fill_between(self._stamps, swaptotal, alpha=alpha, label="dool: SwapTotal", color="r")

        # Used swap
        swapused = self.prof["swp-used"] / mem_unit
        plt.fill_between(self._stamps, swapused, alpha=alpha*3, label="dool: SwapUsed", color="r")

        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)
        plt.yticks(np.linspace(0, max(memtotal), 8, dtype="i"))
        plt.ylabel("Memory (GB)")
        plt.legend(loc=1)
        plt.grid()

        if calls:
            plot_inline_calls(calls=calls, ymax=max(memtotal))

        return 0


    def plot_network(self) -> int:
        """
        Plot network activity
        """
        # Yplot: #opened_files - #inodes
        plt.plot(self._stamps, self.prof["fs-file"], "g-", label="# Open file")
        plt.plot(self._stamps, self.prof["fs-inod"], "y-", label="# inodes")
        plt.ylabel("Total number")
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
            plt.grid()

            # YYplot: disk-read; disk-write
            pltt = plt.twinx()
            pltt.fill_between(self._stamps, 0, self.prof["dsk-read"] / mem_unit, color="b", alpha=alpha, label="Disk read")
            pltt.fill_between(self._stamps, 0, self.prof["dsk-writ"] / mem_unit, color="r", alpha=alpha, label="Disk write")
            pltt.set_ylabel("IO (MB)")
            pltt.legend(loc=1)
            plt.grid()

        return 0


class HighFreqData():
    """
    High-frequency monitoring database
    """
    def __init__(self, csv_mem_report, csv_cpu_report, csv_cpufreq_report):
        """
        Constructor
        """
        self.csv_mem_report = csv_mem_report
        self.csv_cpu_report = csv_cpu_report
        self.csv_cpufreq_report = csv_cpufreq_report

        self.sys_info = read_sys_info(self.csv_cpu_report)

        self.hf_cpu_prof = {}
        self.hf_cpu_stamps = np.array([])
        self.get_hf_cpu_profile()

        self.hf_mem_prof = {}
        self.hf_mem_stamps = np.array([])
        self.get_hf_mem_profile()

        self.hf_cpufreq_prof = {}
        self.hf_cpufreq_stamps = np.array([])

        self.get_hf_cpufreq_prof()

        self.create_plt_params()


    def create_plt_params(self) -> int:
        """
        Create plot parameters
        """
        nstamps = len(self.hf_cpu_stamps)
        xstride = max(1, nstamps // PLT_XRANGE)
        val0 = self.hf_cpu_stamps[0]
        vallst = self.hf_cpu_stamps[xstride: nstamps-xstride+1: xstride]
        valf = self.hf_cpu_stamps[-1]
        xticks_val = [val0] + vallst.tolist() + [valf]

        t0 = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self.hf_cpu_stamps[0]))
        tlst = np.round(self.hf_cpu_stamps[xstride: nstamps-xstride+1: xstride] - self.hf_cpu_stamps[0], 2)
        tf = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self.hf_cpu_stamps[-1]))
        xticks_label = [t0] + tlst.astype("int").tolist() + [tf]

        self._xticks = (xticks_val, xticks_label)

        dx = (valf - val0) * PLT_XLIM_COEF
        self._xlim = [val0 - dx, valf + dx]

        return 0

    def read_hf_cpu_csv_report(self):
        """
        Read high-frequency cpu report
        """
        # Read line of cpu csv report
        cpu_report_lines = []
        with open(self.csv_cpu_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                cpu_report_lines.append(row)

        # Number of CPU cores + global @hc
        self.ncpu = 0
        cnt = 0
        for line in cpu_report_lines:
            nb = line[1][3:]
            self.ncpu = max(int(nb) if len(nb) > 1 else 0, self.ncpu)
            cnt +=1
            if cnt > 10000: break
        self.ncpu += 1
        self.ncpu_glob = self.ncpu + 1

        # Number of reported samples
        nsamples = len(cpu_report_lines)

        # Number of timestamp
        ntimestamps_raw = nsamples // self.ncpu_glob

        # CPU metric keys (to read lines)
        cpu_metric_keys = {"User": 2, "Nice": 3, "System": 4, "Idle": 5, "IOwait": 6, "Irq": 7, "Sotfirq": 8, "Steal": 9, "Guest": 10, "GuestNice": 11}

        # Init cpu time series
        cpu_ts_raw = {}
        for cpu_nb in range(self.ncpu_glob):
            cpu_ts_raw[f"cpu{cpu_nb}"] = {key: [] for key in cpu_metric_keys.keys()}
        cpu_ts_raw["cpu"] = cpu_ts_raw[f"cpu{self.ncpu_glob-1}"]
        del cpu_ts_raw[f"cpu{self.ncpu_glob-1}"]

        # Read lines
        time_index = 0
        cpu_index = 1
        timestamps_raw = []
        for line in cpu_report_lines:
            for key in cpu_metric_keys:
                cpu_ts_raw[line[cpu_index]][key] += [float(line[cpu_metric_keys[key]])]
            timestamps_raw += [line[time_index]]

        timestamps_raw = np.sort(np.array(list(set(timestamps_raw))).astype(np.float64))

        return cpu_ts_raw, timestamps_raw


    def get_hf_cpu_profile(self) -> int:
        """
        Get high-frequency cpu profile
        """
        cpu_ts_raw, timestamps_raw = self.read_hf_cpu_csv_report()

        nstamps = len(timestamps_raw) - 1

        timestamps = np.zeros(nstamps)
        for stamp in range(nstamps):
            timestamps[stamp] = (timestamps_raw[stamp+1] + timestamps_raw[stamp]) / 2

        cpu_ts = {}
        for key in cpu_ts_raw.keys():
            cpu_ts[key] = {metric_key: np.zeros(nstamps) for metric_key in cpu_ts_raw["cpu"].keys()}

        for key in cpu_ts_raw.keys():
            for metric_key in cpu_ts_raw["cpu"].keys():
                for stamp in range(nstamps):
                    cpu_ts[key][metric_key][stamp] = cpu_ts_raw[key][metric_key][stamp+1] - cpu_ts_raw[key][metric_key][stamp]

        for key in cpu_ts.keys():
            for stamp in range(nstamps):
                cpu_total = 0
                for metric_key in cpu_ts["cpu"].keys():
                    cpu_total += cpu_ts[key][metric_key][stamp]

                for metric_key in cpu_ts["cpu"].keys():
                    cpu_ts[key][metric_key][stamp] = cpu_ts[key][metric_key][stamp] / cpu_total * 100

        self.hf_cpu_prof = cpu_ts
        self.hf_cpu_stamps = timestamps

        return 0


    def plot_hf_cpu(self, number="", calls: dict = None) -> int:
        core = f"cpu{number}"
        alpha = .8
        prefix = f"{number}: " if number else ""

        cpu_usr = self.hf_cpu_prof[core]["User"] + self.hf_cpu_prof[core]["Nice"]
        cpu_sys = self.hf_cpu_prof[core]["System"] + self.hf_cpu_prof[core]["Irq"] + self.hf_cpu_prof[core]["Sotfirq"]
        cpu_wai = self.hf_cpu_prof[core]["IOwait"]
        cpu_stl = self.hf_cpu_prof[core]["Steal"] + self.hf_cpu_prof[core]["Guest"] + self.hf_cpu_prof[core]["GuestNice"]

        plt.fill_between(self.hf_cpu_stamps, 100, color="C7", alpha=alpha/3, label=f"{prefix}idle")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl, color="C5", alpha=alpha, label=f"{prefix}virt")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl, cpu_stl+cpu_wai, color="C8", alpha=alpha, label=f"{prefix}wait")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl+cpu_wai, cpu_stl+cpu_wai+cpu_sys, color="C4", alpha=alpha, label=f"{prefix}sys")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl+cpu_wai+cpu_sys, cpu_stl+cpu_wai+cpu_sys+cpu_usr, color="C0", alpha=alpha, label=f"{prefix}usr")

        plt.xticks(self._xticks[0], self._xticks[1])
        plt.xlim(self._xlim)
        _yrange = 10
        plt.yticks(100 / _yrange * np.arange(_yrange + 1))
        plt.grid()

        if number:
            plt.ylabel(f"CPU Core-{number} usage (%)")
        else:
            plt.ylabel("CPU average usage (%)")

        # Order legend
        _order = [0, 4, 3, 2, 1]
        _handles, _labels = plt.gca().get_legend_handles_labels()
        plt.legend([_handles[idx] for idx in _order],[_labels[idx] for idx in _order], loc=1)

        if calls:
            plot_inline_calls(calls=calls)

        return 0


    def plot_hf_cpu_per_core(self, cores_in: str = "", cores_out: str = "", calls: dict = None) -> int:
        """
        Plot cpu per core
        """
        cores = [core for core in range(self.ncpu)]
        if len(cores_in) > 0:
            cores = [int(core) for core in cores_in.split(",")]
        elif len(cores_in) == 0 and len(cores_out) > 0:
            for core_ex in cores_out.split(","):
                cores.remove(int(core_ex))
        _ncpu = len(cores)

        cm = plt.cm.jet(np.linspace(0, 1, _ncpu+1))
        for idx, core in enumerate(cores):
            core_name = f"cpu{core}"
            cpu_usr = self.hf_cpu_prof[core_name]["User"] + self.hf_cpu_prof[core_name]["Nice"]
            cpu_sys = self.hf_cpu_prof[core_name]["System"] + self.hf_cpu_prof[core_name]["Irq"] + self.hf_cpu_prof[core_name]["Sotfirq"]
            cpu_wai = self.hf_cpu_prof[core_name]["IOwait"]
            plt.plot(self.hf_cpu_stamps, cpu_usr+cpu_sys+cpu_wai, color=cm[idx], label=f"core-{core}")
        plt.xticks(self._xticks[0], self._xticks[1])
        _yrange = 10
        plt.yticks(100 * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(self._xlim)
        plt.ylabel(f" CPU Cores (%)")
        plt.grid()
        plt.legend(loc=0, ncol=_ncpu // ceil(_ncpu/16) , fontsize="6")

        if calls:
            plot_inline_calls(calls=calls)
        return 0


    def read_hf_mem_csv_report(self):
        """
        Read high-frequency memory report
        """
        mem_report_lines = []
        with open(self.csv_mem_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                mem_report_lines.append(row)
        keys_full = mem_report_lines[0][:-1]

        keys_with_idx = {key: idx for idx, key in enumerate(mem_report_lines[0][:-1])}

        return mem_report_lines, keys_with_idx


    def get_hf_mem_profile(self) -> int:
        """
        Get memory profile
        """
        ALL_MEM_KEYS = "MemTotal,MemFree,MemAvailable,Buffers,Cached,SwapCached,Active,Inactive,Active(anon),Inactive(anon),Active(file),Inactive(file),Unevictable,Mlocked,SwapTotal,SwapFree,Dirty,Writeback,AnonPages,Mapped,Shmem,KReclaimable,Slab,SReclaimable,SUnreclaim,KernelStack,PageTables,NFS_Unstable,Bounce,WritebackTmp,CommitLimit,Committed_AS,VmallocTotal,VmallocUsed,VmallocChunk,Percpu,HardwareCorrupted,AnonHugePages,ShmemHugePages,ShmemPmdMapped,FileHugePages,FilePmdMapped,HugePages_Total,HugePages_Free,HugePages_Rsvd,HugePages_Surp,Hugepagesize,Hugetlb,DirectMap4k,DirectMap2M,DirectMap1G"

        _chosen_keys = ["Time", "MemTotal", "MemFree", "Buffers", "Cached", "Slab", "SwapTotal", "SwapFree", "SwapCached"]

        mem_report_lines, keys_with_idx = self.read_hf_mem_csv_report()

        memory_dict = {key: [] for key in _chosen_keys}

        for line in mem_report_lines[1:]:
            for key in memory_dict:
                memory_dict[key] += [float(line[keys_with_idx[key]])]

        for key in memory_dict:
            memory_dict[key] = np.array(memory_dict[key])

        self.hf_mem_prof = memory_dict
        self.hf_mem_stamps = memory_dict["Time"]

        return 0


    def plot_hf_memory_usage(self, xticks, xlim, calls: dict = None) -> int:
        """
        Plot memory/swap usage
        """
        alpha = 0.3
        memunit = 1024 ** 2 # (GB)

        # Memory
        total =  self.hf_mem_prof["MemTotal"] / memunit
        cached = (self.hf_mem_prof["Buffers"] + self.hf_mem_prof["Cached"] + self.hf_mem_prof["Slab"]) / memunit
        used = - cached + (self.hf_mem_prof["MemTotal"] - self.hf_mem_prof["MemFree"]) / memunit
        plt.fill_between(self.hf_mem_stamps, total, alpha=alpha, label="MemTotal", color="b")
        plt.fill_between(self.hf_mem_stamps, used, alpha=alpha*3, label="MemUsed", color="b")
        plt.fill_between(self.hf_mem_stamps, used, used + cached, alpha=alpha*2, label="Cach/Buff", color="g")

        # Swap
        swap_total = self.hf_mem_prof["SwapTotal"] / memunit
        swap_used = swap_total - self.hf_mem_prof["SwapFree"] / memunit
        plt.fill_between(self.hf_mem_stamps, swap_total, alpha=alpha, label="SwapTotal", color="r")
        plt.fill_between(self.hf_mem_stamps, swap_used, alpha=alpha*3, label="SwapUsed", color="r")

        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)
        plt.yticks(np.linspace(0, max(total), 8, dtype="i"))
        plt.ylabel("Memory (GB)")
        plt.legend(loc=1)
        plt.grid()

        if calls:
            plot_inline_calls(calls=calls, ymax=max(total))

        return 0


    def get_hf_cpufreq_prof(self):
        """
        Read HF cpu frequency csv report
        Get profile
        """
        cpufreq_report_lines = []
        with open(self.csv_cpufreq_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                if int(row[1][3:]) in self.sys_info["online_cores"]:
                    cpufreq_report_lines.append(row)

        # Init cpu time series
        cpufreq_ts = {}
        for cpu_nb in range(self.ncpu):
            cpufreq_ts[f"cpu{cpu_nb}"] = []

        # Read lines
        timestamps = []
        for line in cpufreq_report_lines:
            cpufreq_ts[line[1]] += [float(line[2])]
            timestamps += [line[0]]
        timestamps = np.sort(np.array(list(set(timestamps))).astype(np.float64))

        for cpu_nb in range(self.ncpu):
            cpufreq_ts[f"cpu{cpu_nb}"] = np.array(cpufreq_ts[f"cpu{cpu_nb}"]) / 1e6

        self.hf_cpufreq_prof = cpufreq_ts
        self.hf_cpufreq_stamps = timestamps

        return 0


    def plot_hf_cpufreq(self, cores_in: str = "", cores_out: str = "", calls: dict = None) -> int:
        """
        Plot cpu frequency per core
        """
        cpu_freq_min = self.sys_info["cpu_freq_min"] / 1e6 # GHz
        cpu_freq_max = self.sys_info["cpu_freq_max"] / 1e6 # GHz

        cores = [core for core in range(self.ncpu)]
        if len(cores_in) > 0:
            cores = [int(core) for core in cores_in.split(",")]
        elif len(cores_in) == 0 and len(cores_out) > 0:
            for core_ex in cores_out.split(","):
                cores.remove(int(core_ex))
        _ncpu = len(cores)

        cm = plt.cm.jet(np.linspace(0, 1, _ncpu+1))

        _nstamps = len(self.hf_cpufreq_stamps)
        freq_mean = np.zeros(_nstamps)

        for idx, core in enumerate(cores):
            plt.plot(self.hf_cpufreq_stamps, self.hf_cpufreq_prof[f"cpu{core}"], color=cm[idx], label=f"core-{core}")

        for cpu in range(self.ncpu):
            freq_mean += self.hf_cpufreq_prof[f"cpu{cpu}"] / self.ncpu
        plt.plot(self.hf_cpufreq_stamps, freq_mean, "k.-", label=f"mean")

        plt.plot(self.hf_cpufreq_stamps, cpu_freq_max * np.ones(_nstamps), "gray", linestyle="--", label=f"hw max/min")
        plt.plot(self.hf_cpufreq_stamps, cpu_freq_min * np.ones(_nstamps), "gray", linestyle="--")

        plt.xticks(self._xticks[0], self._xticks[1])
        _yrange = 10
        plt.yticks(cpu_freq_max * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(self._xlim)
        plt.ylabel(f" CPU frequencies (GHz)")
        plt.grid()
        plt.legend(loc=0, ncol=self.ncpu // ceil(self.ncpu/16) , fontsize="6")

        if calls:
            plot_inline_calls(calls=calls, ymax=cpu_freq_max)

        return 0



