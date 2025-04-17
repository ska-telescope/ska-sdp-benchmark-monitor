"""
Python script to read and plot system resources measurements
"""
import csv
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from math import ceil


class HighFreqData():
    """
    High-frequency monitoring database
    """
    def __init__(self, csv_mem_report: str,
                 csv_cpu_report: str,
                 csv_cpufreq_report: str,
                 csv_net_report: str,
                 csv_disk_report: str,
                 csv_ib_report: str):
        """
        Constructor
        """

        if csv_cpu_report:
            self.ncpu = 0
            self.hf_cpus = []
            self.hf_cpu_prof = {}
            self.hf_cpu_stamps = np.array([])
            self.get_hf_cpu_profile(csv_cpu_report=csv_cpu_report)

        if csv_cpufreq_report:
            self.hf_cpufreq_prof = {}
            self.hf_cpufreq_stamps = np.array([])
            self.hf_cpufreq_min = None
            self.hf_cpufreq_max = None
            self.get_hf_cpufreq_prof(csv_cpufreq_report=csv_cpufreq_report)

        if csv_mem_report:
            self.hf_mem_prof = {}
            self.hf_mem_stamps = np.array([])
            self.get_hf_mem_profile(csv_mem_report=csv_mem_report)

        if csv_net_report:
            self.hf_net_prof = {}
            self.hf_net_data = {}
            self.hf_net_metric_keys = {}
            self.hf_net_interfs = []
            self.hf_net_stamps = np.array([])
            self.hf_net_rx_total = np.array([])
            self.hf_net_tx_total = np.array([])
            self.hf_net_rx_data = 0
            self.hf_net_tx_data = 0
            self.get_hf_net_prof(csv_net_report=csv_net_report)

        if csv_disk_report:
            self.hf_disk_prof = {}
            self.hf_disk_data = {}
            self.hf_disk_field_keys = {}
            self.hf_maj_blks_sects = {}
            self.hf_disk_blks = []
            self.hf_disk_stamps = np.array([])
            self.hf_disk_rd_total = np.array([])
            self.hf_disk_wr_total = np.array([])
            self.hf_disk_rd_data = 0
            self.hf_disk_wr_data = 0
            self.get_hf_disk_prof(csv_disk_report=csv_disk_report)

        if csv_ib_report:
            self.hf_ib_prof = {}
            self.hf_ib_data = {}
            self.ib_metric_keys = []
            self.ib_interfs = []
            self.hf_ib_stamps = np.array([])
            self.ib_rx_total = np.array([])
            self.ib_tx_total = np.array([])
            self.get_hf_ib_prof(csv_ib_report=csv_ib_report)


    def read_hf_cpu_csv_report(self, csv_cpu_report: str):
        """
        Read high-frequency cpu report
        """
        # Read line of cpu csv report
        cpu_report_lines = []
        with open(csv_cpu_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                cpu_report_lines.append(row)

        # Get cpus, number of cpu cores + global
        ts_0 = cpu_report_lines[1][0]
        ts = ts_0
        line_idx = 1
        self.hf_cpus = []
        while ts == ts_0:
            self.hf_cpus += [cpu_report_lines[line_idx][1]]
            line_idx += 1
            ts = cpu_report_lines[line_idx][0]
        ncpu_glob = len(self.hf_cpus)
        self.ncpu = ncpu_glob - 1

        # CPU metric keys {"user": 2, "nice": 3, "system": 4, "idle": 5, "iowait": 6, "irq": 7, "softirq": 8, "steal": 9, "guest": 10, "guestnice": 11}
        _sidx = 2
        cpu_metric_keys = {key: idx + _sidx for idx,key in enumerate(cpu_report_lines[0][_sidx:])}

        # Init cpu time series
        cpu_ts_raw = {}
        for cpu in self.hf_cpus:
            cpu_ts_raw[cpu] = {key: [] for key in cpu_metric_keys.keys()}

        # Read lines
        time_index = 0
        cpu_index = 1
        timestamps_raw = []

        for line in cpu_report_lines[1:]:
            for key in cpu_metric_keys:
                cpu_ts_raw[line[cpu_index]][key] += [float(line[cpu_metric_keys[key]])]
        timestamps_raw = [float(line[time_index]) for line in cpu_report_lines[1::ncpu_glob]]

        timestamps_raw = np.sort(np.array(list(set(timestamps_raw))).astype(np.float64))

        return cpu_ts_raw, timestamps_raw


    def get_hf_cpu_profile(self, csv_cpu_report = str) -> int:
        """
        Get high-frequency cpu profile
        """
        cpu_ts_raw, timestamps_raw = self.read_hf_cpu_csv_report(csv_cpu_report=csv_cpu_report)

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


    def plot_hf_cpu(self, number="", annotate_with_cmds = None) -> int:
        core = f"cpu{number}"
        alpha = .8
        prefix = f"{number}: " if number else ""

        cpu_usr = self.hf_cpu_prof[core]["user"] + self.hf_cpu_prof[core]["nice"]
        cpu_sys = self.hf_cpu_prof[core]["system"] + self.hf_cpu_prof[core]["irq"] + self.hf_cpu_prof[core]["softirq"]
        cpu_wai = self.hf_cpu_prof[core]["iowait"]
        cpu_stl = self.hf_cpu_prof[core]["steal"] + self.hf_cpu_prof[core]["guest"] + self.hf_cpu_prof[core]["guestnice"]

        plt.fill_between(self.hf_cpu_stamps, 100, color="C7", alpha=alpha/3, label=f"{prefix}idle")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl, color="C5", alpha=alpha, label=f"{prefix}virt")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl, cpu_stl+cpu_wai, color="C8", alpha=alpha, label=f"{prefix}wait")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl+cpu_wai, cpu_stl+cpu_wai+cpu_sys, color="C4", alpha=alpha, label=f"{prefix}sys")
        plt.fill_between(self.hf_cpu_stamps, cpu_stl+cpu_wai+cpu_sys, cpu_stl+cpu_wai+cpu_sys+cpu_usr, color="C0", alpha=alpha, label=f"{prefix}usr")

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
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

        if annotate_with_cmds: annotate_with_cmds(ymax=100)

        return 0


    def plot_hf_cpu_per_core(self, cores_in: str = "", cores_out: str = "", annotate_with_cmds = None) -> int:
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
            cpu_usr = self.hf_cpu_prof[core_name]["user"] + self.hf_cpu_prof[core_name]["nice"]
            cpu_sys = self.hf_cpu_prof[core_name]["system"] + self.hf_cpu_prof[core_name]["irq"] + self.hf_cpu_prof[core_name]["softirq"]
            cpu_wai = self.hf_cpu_prof[core_name]["iowait"]
            plt.plot(self.hf_cpu_stamps, cpu_usr+cpu_sys+cpu_wai, color=cm[idx], label=f"core-{core}")
        plt.xticks(*self.xticks)
        _yrange = 10
        plt.yticks(100 * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(self.xlim)
        plt.ylabel(f" CPU Cores (%)")
        plt.grid()
        plt.legend(loc=0, ncol=_ncpu // ceil(_ncpu/16) , fontsize="6")

        if annotate_with_cmds: annotate_with_cmds(ymax=100)

        return 0


    def read_hf_mem_csv_report(self, csv_mem_report: str):
        """
        Read high-frequency memory report
        """
        mem_report_lines = []
        with open(csv_mem_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                mem_report_lines.append(row)
        keys_full = mem_report_lines[0][:-1]

        keys_with_idx = {key: idx for idx, key in enumerate(mem_report_lines[0][:-1])}

        return mem_report_lines, keys_with_idx


    def get_hf_mem_profile(self, csv_mem_report: str) -> int:
        """
        Get memory profile
        """
        ALL_MEM_KEYS = "MemTotal,MemFree,MemAvailable,Buffers,Cached,SwapCached,Active,Inactive,Active(anon),Inactive(anon),Active(file),Inactive(file),Unevictable,Mlocked,SwapTotal,SwapFree,Dirty,Writeback,AnonPages,Mapped,Shmem,KReclaimable,Slab,SReclaimable,SUnreclaim,KernelStack,PageTables,NFS_Unstable,Bounce,WritebackTmp,CommitLimit,Committed_AS,VmallocTotal,VmallocUsed,VmallocChunk,Percpu,HardwareCorrupted,AnonHugePages,ShmemHugePages,ShmemPmdMapped,FileHugePages,FilePmdMapped,HugePages_Total,HugePages_Free,HugePages_Rsvd,HugePages_Surp,Hugepagesize,Hugetlb,DirectMap4k,DirectMap2M,DirectMap1G"

        _chosen_keys = ["timestamp", "MemTotal", "MemFree", "Buffers", "Cached", "Slab", "SwapTotal", "SwapFree", "SwapCached"]

        mem_report_lines, keys_with_idx = self.read_hf_mem_csv_report(csv_mem_report=csv_mem_report)

        memory_dict = {key: [] for key in _chosen_keys}

        for line in mem_report_lines[1:]:
            for key in memory_dict:
                memory_dict[key] += [float(line[keys_with_idx[key]])]

        for key in memory_dict:
            memory_dict[key] = np.array(memory_dict[key])

        self.hf_mem_prof = memory_dict
        self.hf_mem_stamps = memory_dict["timestamp"]

        return 0


    def plot_hf_memory_usage(self, annotate_with_cmds=None) -> int:
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

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.yticks(np.linspace(0, max(total), 8, dtype="i"))
        plt.ylabel("Memory (GB)")
        plt.legend(loc=1)
        plt.grid()

        if annotate_with_cmds: annotate_with_cmds(ymax=max(total))

        return 0


    def get_hf_cpufreq_prof(self, csv_cpufreq_report: str):
        """
        Read HF cpu frequency csv report
        Get profile
        """
        cpufreq_report_lines = []
        with open(csv_cpufreq_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                cpufreq_report_lines.append(row)

        cpu_freq_parsing = cpufreq_report_lines[0][2].split('[')[1].split(']')[0].split("-")
        self.hf_cpufreq_min = cpu_freq_parsing[0] or None
        self.hf_cpufreq_max = cpu_freq_parsing[1] or None

        # Init cpu time series
        cpufreq_ts = {}
        for cpu_nb in range(self.ncpu):
            cpufreq_ts[f"cpu{cpu_nb}"] = []

        # Read lines
        for line in cpufreq_report_lines[1:]:
            cpufreq_ts[line[1]] += [float(line[2])]

        HZ_UNIT = 1e6
        for cpu_nb in range(self.ncpu):
            cpufreq_ts[f"cpu{cpu_nb}"] = np.array(cpufreq_ts[f"cpu{cpu_nb}"]) / HZ_UNIT

        self.hf_cpufreq_prof = cpufreq_ts
        self.hf_cpufreq_stamps = [float(line[0]) for line in cpufreq_report_lines[1::self.ncpu]]

        return 0


    def plot_hf_cpufreq(self, cores_in: str = "", cores_out: str = "", annotate_with_cmds=None) -> int:
        """
        Plot cpu frequency per core
        """
        HZ_UNIT = 1e6 # GHz

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

        cpu_freq_max = 6 # Hard-coded 6 HZ
        if self.hf_cpufreq_min and self.hf_cpufreq_max:
            cpu_freq_min = float(self.hf_cpufreq_min) / HZ_UNIT
            cpu_freq_max = float(self.hf_cpufreq_max) / HZ_UNIT
            plt.plot(self.hf_cpufreq_stamps, cpu_freq_max * np.ones(_nstamps), "gray", linestyle="--", label=f"hw max/min")
            plt.plot(self.hf_cpufreq_stamps, cpu_freq_min * np.ones(_nstamps), "gray", linestyle="--")

        plt.xticks(*self.xticks)
        _yrange = 10
        plt.yticks(cpu_freq_max * 1/_yrange * np.arange(_yrange + 1))
        plt.xlim(self.xlim)
        plt.ylabel(f" CPU frequencies (GHz)")
        plt.grid()
        plt.legend(loc=0, ncol=self.ncpu // ceil(self.ncpu/16) , fontsize="6")

        if annotate_with_cmds: annotate_with_cmds(ymax=cpu_freq_max)

        return 0


    def read_hf_net_csv_report(self, csv_net_report: str):
        """
        Read high-frequency native network csv report
        """
        net_report_lines = []
        with open(csv_net_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                net_report_lines.append(row)

        # Get network interfaces
        ts_0 = net_report_lines[1][0]
        ts = ts_0
        line_idx = 1
        while ts == ts_0:
            self.hf_net_interfs += [net_report_lines[line_idx][1]]
            line_idx += 1
            ts = net_report_lines[line_idx][0]
        nnet_interf = len(self.hf_net_interfs)

        # self.hf_net_metric_keys = { # https://www.kernel.org/doc/html/v6.7/networking/statistics.html
        #     "rx-bytes": 2, "rx-packets": 3, "rx-errs": 4, "rx-drop": 5,
        #     "rx-fifo": 6, "rx-frame": 7, "rx-compressed": 8, "rx-multicast": 9,
        #     "tx-bytes": 10, "tx-packets": 11, "tx-errs": 12, "tx-drop": 13,
        #     "tx-fifo": 14, "tx-colls": 15, "tx-carrier": 16, "tx-compressed": 17
        # }
        _sidx = 2
        self.hf_net_metric_keys = {key: idx + _sidx for idx,key in enumerate(net_report_lines[0][_sidx:])}

        _interf_idx = 1
        net_ts_raw = {}
        for interf in self.hf_net_interfs:
            net_ts_raw[interf] = {key: [] for key in self.hf_net_metric_keys}

        _samples_idx = 1
        for report_line in net_report_lines[_samples_idx:]:
            for key in self.hf_net_metric_keys:
                net_ts_raw[report_line[_interf_idx]][key] += [float(report_line[self.hf_net_metric_keys[key]])]

        timestamps_raw = [float(item[0]) for item in net_report_lines[_samples_idx:][::nnet_interf]]

        return net_ts_raw, timestamps_raw


    def get_hf_net_prof(self, csv_net_report: str):
        """
        Get high-frequency native network profile
        """
        net_ts_raw, timestamps_raw = self.read_hf_net_csv_report(csv_net_report=csv_net_report)

        time_interval = 1
        time_interval_step = 1 if time_interval == 0 else int(time_interval / (timestamps_raw[1] - timestamps_raw[0]))

        nstamps = len(timestamps_raw) - 1
        self.hf_net_stamps = np.zeros(nstamps)
        for stamp in range(nstamps):
            self.hf_net_stamps[stamp] = (timestamps_raw[stamp+1] + timestamps_raw[stamp]) / 2

        # Init network profile
        for interf in self.hf_net_interfs:
            self.hf_net_prof[interf] = {key: np.zeros(nstamps) for key in self.hf_net_metric_keys}
            self.hf_net_data[interf] = {key: 0 for key in self.hf_net_metric_keys}

        # Fill in
        for key in net_ts_raw:
            for metric_key in self.hf_net_metric_keys:
                self.hf_net_data[key][metric_key] = net_ts_raw[key][metric_key][-1] - net_ts_raw[key][metric_key][0]
                for stamp in range(nstamps):
                    self.hf_net_prof[key][metric_key][stamp] = (net_ts_raw[key][metric_key][stamp + 1] - net_ts_raw[key][metric_key][stamp]) / (timestamps_raw[stamp + 1] - timestamps_raw[stamp])


    def plot_hf_network(self,
                        all_interfaces=False,
                        total_network=True,
                        is_rx_only=False,
                        is_tx_only=False,
                        is_netdata_label=True,
                        annotate_with_cmds=None) -> int:
        """
        Plot high-frequency network activity
        """
        BYTES_UNIT = 1024 ** 2 # MB
        ALPHA = .5
        MRKSZ = 3.5

        # Interface to exclude (eg: br0)
        interf_to_exclude = ["br0:",]
        is_excluded = lambda interf: any([_interf in interf for _interf in interf_to_exclude])

        self.hf_net_rx_total = np.zeros_like(self.hf_net_stamps)
        self.hf_net_tx_total = np.zeros_like(self.hf_net_stamps)

        for interf in self.hf_net_interfs:
            if is_excluded(interf): continue

            self.hf_net_rx_total = self.hf_net_rx_total + self.hf_net_prof[interf]["rx-bytes"] / BYTES_UNIT
            self.hf_net_tx_total = self.hf_net_tx_total + self.hf_net_prof[interf]["tx-bytes"] / BYTES_UNIT

            self.hf_net_rx_data += self.hf_net_data[interf]["rx-bytes"] / BYTES_UNIT
            self.hf_net_tx_data += self.hf_net_data[interf]["tx-bytes"] / BYTES_UNIT

        # RX
        if not is_tx_only:
            if total_network:
                label = f"rx:total"
                if is_netdata_label: label += f" ({int(self.hf_net_rx_data)} MB)"
                plt.fill_between(self.hf_net_stamps, self.hf_net_rx_total, label=label, color="b", alpha=ALPHA)

            if all_interfaces:
                for interf in self.hf_net_interfs:
                    if is_excluded(interf): continue
                    rx_arr = self.hf_net_prof[interf]["rx-bytes"] / BYTES_UNIT
                    rd = self.hf_net_data[interf]["rx-bytes"] / BYTES_UNIT
                    if rd > 1: # and rd / self.hf_net_rx_data > 0.001:
                        label = f"rx:{interf[:-1]}"
                        if is_netdata_label: label += f" ({int(rd)} MB)"
                        plt.plot(self.hf_net_stamps, rx_arr, label=label, ls="-", alpha=ALPHA, marker="v", markersize=MRKSZ)

        # TX
        if not is_rx_only:
            if total_network:
                label = f"tx:total"
                if is_netdata_label: label +=  f" ({int(self.hf_net_tx_data)} MB)"
                plt.fill_between(self.hf_net_stamps, self.hf_net_tx_total, label=label, color="r", alpha=ALPHA)

            if all_interfaces:
                for interf in self.hf_net_interfs:
                    if is_excluded(interf): continue
                    tx_arr = self.hf_net_prof[interf]["tx-bytes"] / BYTES_UNIT
                    td = self.hf_net_data[interf]['tx-bytes'] / BYTES_UNIT
                    if td > 1: # and td / self.hf_net_tx_data > 0.001:
                        label = f"tx:{interf[:-1]}"
                        if is_netdata_label: label += f" ({int(td)} MB)"
                        plt.plot(self.hf_net_stamps, tx_arr, label=label, ls="-", alpha=ALPHA, marker="^", markersize=MRKSZ)

        _ymax = max(max(self.hf_net_rx_total), max(self.hf_net_tx_total))
        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        # plt.yticks(np.linspace(0, _ymax, 11, dtype="i"))
        plt.ylabel("Network (MB/s)")
        plt.legend(loc=1)
        plt.grid()

        if annotate_with_cmds: annotate_with_cmds(ymax=_ymax)

        return 0


    def read_hf_disk_csv_report(self, csv_disk_report: str):
        """
        Read high-frequency native disk monitoring csv report
        """
        disk_report_lines = []
        with open(csv_disk_report, newline="") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                disk_report_lines.append(row)

        # useful indexes for the csv report
        _maj_blk_indx = 0
        _all_blk_indx = 1
        _sect_blk_indx = 2
        _header_indx = 3
        _samples_idx = 4

        _blk_idx = 3 # Horizontal

        # self.hf_disk_field_keys = { # https://www.kernel.org/doc/Documentation/ABI/testing/procfs-diskstats
        #     "#rd-cd": 4, "#rd-md": 5, "sect-rd": 6, "time-rd": 7,
        #     "#wr-cd": 8, "#wr-md": 9, "sect-wr": 10, "time-wr": 11,
        #     "#io-ip": 12, "time-io": 13, "time-wei-io": 14,
        #     "#disc-cd": 15, "#disc-md": 16, "sect-disc": 17, "time-disc": 18,
        #     "#flush-req": 19, "time-flush": 20
        # }
        _sidx = 4
        self.hf_disk_field_keys = {key: idx + _sidx for idx,key in enumerate(disk_report_lines[_header_indx][_sidx:])}

        # get major blocks and associated sector size
        self.hf_maj_blks_sects = dict(zip(
                            disk_report_lines[_sect_blk_indx][0::2],
                            [int(sect) for sect in disk_report_lines[_sect_blk_indx][1::2]]
                        ))

        # all disk blocks
        ts_0 = disk_report_lines[_samples_idx][0]
        ts = ts_0
        line_idx = _samples_idx
        ndisk_blk = 0
        while ts == ts_0:
            line_idx += 1
            ndisk_blk += 1
            ts = disk_report_lines[line_idx][0]
        # ndisk_blk = int(disk_report_lines[_all_blk_indx][0])
        self.hf_disk_blks = [disk_report_lines[_samples_idx + idx][_blk_idx] for idx in range(ndisk_blk)]

        # raw disk measure stamps
        disk_ts_raw = {}
        for blk in self.hf_disk_blks:
            disk_ts_raw[blk] = {key: [] for key in self.hf_disk_field_keys}

        for idx in range(ndisk_blk):
            disk_ts_raw[self.hf_disk_blks[idx]]["major"] = int(disk_report_lines[_samples_idx + idx][1]) # major index: 1
            disk_ts_raw[self.hf_disk_blks[idx]]["minor"] = int(disk_report_lines[_samples_idx + idx][2]) # minor index: 2

        for report_line in disk_report_lines[_samples_idx:]:
            for key in self.hf_disk_field_keys:
                disk_ts_raw[report_line[_blk_idx]][key] += [float(report_line[self.hf_disk_field_keys[key]])]

        # raw time stamps
        timestamps_raw = [float(item[0]) for item in disk_report_lines[_samples_idx:][::ndisk_blk]]

        return disk_ts_raw, timestamps_raw


    def get_hf_disk_prof(self, csv_disk_report: str):
        """
        Get high-frequency native disk profile
        """
        disk_ts_raw, timestamps_raw = self.read_hf_disk_csv_report(csv_disk_report=csv_disk_report)

        # final time stamps
        nstamps = len(timestamps_raw) - 1
        self.hf_disk_stamps = np.zeros(nstamps)
        for stamp in range(nstamps):
            self.hf_disk_stamps[stamp] = (timestamps_raw[stamp+1] + timestamps_raw[stamp]) / 2

        # Init disk profile
        self.hf_disk_prof = {}
        self.hf_disk_data = {}
        for blk in self.hf_disk_blks:
            self.hf_disk_prof[blk] = {key: np.zeros(nstamps) for key in self.hf_disk_field_keys}
            self.hf_disk_data[blk] = {key: -999.999 for key in self.hf_disk_field_keys}

        # Fill in
        for blk in self.hf_disk_blks:
            self.hf_disk_prof[blk]["major"] = disk_ts_raw[blk]["major"]
            self.hf_disk_prof[blk]["minor"] = disk_ts_raw[blk]["minor"]
            # for field_key in self.hf_disk_field_keys:
            #     for stamp in range(nstamps):
            #         self.hf_disk_prof[blk][field_key][stamp] = (disk_ts_raw[blk][field_key][stamp + 1] - disk_ts_raw[blk][field_key][stamp])

        # Sectors and data n bytes
        BYTES_UNIT = 1024 ** 2
        fields = ["sect-rd", "sect-wr", "sect-disc"]
        for blk in self.hf_disk_blks:
            bytes_by_sector = self.hf_maj_blks_sects[[item for item in self.hf_maj_blks_sects if item in blk][0]]
            for field in fields:
                for stamp in range(nstamps):
                    self.hf_disk_prof[blk][field][stamp] = \
                        (disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp]) \
                        / (timestamps_raw[stamp + 1] - timestamps_raw[stamp]) \
                        * bytes_by_sector / BYTES_UNIT
                self.hf_disk_data[blk][field] = int((disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0]) \
                                               * bytes_by_sector / BYTES_UNIT)

        # Number of operations
        fields = ["#rd-cd", "#rd-md", "#wr-cd", "#wr-md", "#io-ip", "#disc-cd", "#disc-md", "#flush-req"]
        for blk in self.hf_disk_blks:
            for field in fields:
                for stamp in range(nstamps):
                    self.hf_disk_prof[blk][field][stamp] = (disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp]) \
                                                    / (timestamps_raw[stamp + 1] - timestamps_raw[stamp])
                self.hf_disk_data[blk][field] = int(disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0])


    def plot_hf_disk(self,
                     is_rd_only=False,
                     is_wr_only=False,
                     is_with_iops=False,
                     is_diskdata_label=True,
                     annotate_with_cmds=None) -> int:
        """
        Plot high-frequency disk activity
        """
        alpha = 0.5
        _ymax = 0.

        self.hf_disk_rd_total = np.zeros_like(self.hf_disk_stamps)
        self.hf_disk_wr_total = np.zeros_like(self.hf_disk_stamps)

        # Read/WRite bandwdith
        fields = ["sect-rd", "sect-wr"]
        if is_rd_only: fields.remove("sect-wr")
        if is_wr_only: fields.remove("sect-rd")
        for field in fields:
            for blk in self.hf_disk_blks:
                if blk in self.hf_maj_blks_sects:
                    array = self.hf_disk_prof[blk][field]
                    label = f"{field[-2:]}:{blk}"
                    if is_diskdata_label:
                        label += f" ({self.hf_disk_data[blk][field]} MB)"
                    if np.linalg.norm(array) > 1:
                        plt.fill_between(self.hf_disk_stamps, array, label=label, alpha=alpha)
                        _ymax = max(_ymax, max(array))

                        if field == "sect-rd":
                            self.hf_disk_rd_total = self.hf_disk_rd_total + array
                            self.hf_disk_rd_data = self.hf_disk_rd_data + self.hf_disk_data[blk][field]
                        elif field == "sect-wr":
                            self.hf_disk_wr_total = self.hf_disk_wr_total + array
                            self.hf_disk_wr_data = self.hf_disk_wr_data + self.hf_disk_data[blk][field]

        plt.ylabel("Disk bandwidth (MB/s)")
        plt.grid()
        hand, lab = plt.gca().get_legend_handles_labels()

        # Read/Write iops
        if is_with_iops:
            pltt = plt.twinx()
            fields = ["#rd-cd", "#wr-cd"]
            if is_rd_only: fields.remove("#wr-cd")
            if is_wr_only: fields.remove("#rd-cd")
            for field in fields:
                for blk in self.hf_disk_blks:
                    if blk in self.hf_maj_blks_sects:
                        array = self.hf_disk_prof[blk][field]
                        label = f"{field[:3]}:{blk}"
                        if is_diskdata_label:
                            label += f" ({self.hf_disk_data[blk][field]:.3e} op)"
                        if np.linalg.norm(array) > 1:
                            pltt.plot(self.hf_disk_stamps, array, label=label, ls="-")
            pltt.set_ylabel("Disk operations per second (IOPS)")
            pltt.grid()
            hand_twin, lab_twin = pltt.get_legend_handles_labels()

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        if is_with_iops:
            plt.legend(hand + hand_twin, lab + lab_twin, loc=1)
        else:
            plt.legend(loc=1)

        if annotate_with_cmds and not is_with_iops: annotate_with_cmds(ymax=_ymax) # @todo


    def read_hf_ib_csv_report(self, csv_ib_report: str):
        """
        Read high-frequency native infiniband monitoring csv report
        """
        ib_report_lines = []

        self.ib_metric_keys = ["port_rcv_data", "port_xmit_data"]

        ts_0 = ib_report_lines[1][0]
        ts = ts_0
        line_idx = 1
        while ts == ts_0:
            self.ib_interfs += [ib_report_lines[line_idx][1]]

            line_idx += 1
            ts = ib_report_lines[line_idx][0]
        self.ib_interfs = set(self.ib_interfs)

        ib_ts_raw = {}
        for interf in self.ib_interfs:
            ib_ts_raw[interf] = {key: [] for key in self.ib_metric_keys}

        for line in ib_report_lines[1:]:
            interf = line[1]
            metric_key = line[2]
            metric_val = line[3]
            ib_ts_raw[interf][metric_key] += [float(metric_val)]

        timestamps_raw = [float(item[0]) for item in ib_report_lines[1:][::len(self.ib_interfs)*len(self.ib_metric_keys)]]

        return ib_ts_raw, timestamps_raw


    def get_hf_ib_prof(self, csv_ib_report: str):
        """
        Get high-frequency native infiniband profile
        """
        ib_ts_raw, timestamps_raw = self.read_hf_ib_csv_report(csv_ib_report=csv_ib_report)
        nstamps = len(timestamps_raw) - 1

        self.hf_ib_stamps = np.zeros(nstamps)
        for stamp in range(nstamps):
            self.hf_ib_stamps[stamp] = (timestamps_raw[stamp+1] + timestamps_raw[stamp]) / 2

        # Init infiniband profile
        for interf in self.ib_interfs:
            self.hf_ib_prof[interf] = {key: np.zeros(nstamps) for key in self.ib_metric_keys}
            self.hf_ib_data[interf] = {key: 0 for key in self.ib_metric_keys}

        # Fill in
        BYTES_UNIT = (1/4) * 1024 ** 2 # MB
        for interf in self.ib_interfs:
            for metric_key in self.ib_metric_keys:
                for stamp in range(nstamps):
                    self.hf_ib_prof[interf][metric_key][stamp] = (ib_ts_raw[interf][metric_key][stamp + 1] - ib_ts_raw[interf][metric_key][stamp]) / (timestamps_raw[stamp + 1] - timestamps_raw[stamp]) / BYTES_UNIT
                self.hf_ib_data[interf][metric_key] = int((ib_ts_raw[interf][metric_key][-1] - ib_ts_raw[interf][metric_key][0]) / BYTES_UNIT)


    def plot_hf_ib(self, annotate_with_cmds=None):
        """
        Plot high-frequency infiniband activity
        """
        for interf in self.ib_interfs:
            self.ib_rx_total = self.ib_rx_total + self.hf_ib_prof[interf]["port_rcv_data"]
            self.ib_tx_total = self.ib_tx_total + self.hf_ib_prof[interf]["port_xmit_data"]
        alpha = .5

        # RX:IB
        plt.fill_between(self.hf_ib_stamps, self.ib_rx_total, label="rx:total", color="b", alpha=alpha/2)
        for interf in self.ib_interfs:
            rx_arr = self.hf_ib_prof[interf]["port_rcv_data"]
            rx_data_label = self.hf_ib_data[interf]["port_rcv_data"]
            if rx_data_label > 1: # np.linalg.norm(rx_arr) > 1:
                plt.plot(self.hf_ib_stamps, rx_arr, label=f"rx:(ib){interf} ({rx_data_label} MB)", ls="-", marker="v", alpha=alpha)

        # TX:IB
        plt.fill_between(self.hf_ib_stamps, self.ib_tx_total, label="tx:total", color="r", alpha=alpha/2)
        for interf in self.ib_interfs:
            tx_arr = self.hf_ib_prof[interf]["port_xmit_data"]
            tx_data_label = self.hf_ib_data[interf]["port_xmit_data"]
            if tx_data_label > 1: # np.linalg.norm(tx_arr) > 1:
                plt.plot(self.hf_ib_stamps, tx_arr, label=f"tx:(ib){interf} ({tx_data_label} MB)", ls="-", marker="^", alpha=alpha)

        plt.ylabel("Infiniband bandwidth (MB/s)")
        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.grid()
        plt.legend(loc=1)


        _ymax = max(max(self.ib_rx_total), max(self.ib_tx_total))
        if annotate_with_cmds: annotate_with_cmds(ymax=_ymax)
