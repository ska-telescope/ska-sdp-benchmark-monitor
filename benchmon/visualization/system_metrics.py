"""
Python module to read and plot system resources measurements
"""

import csv
import logging
import itertools
import os
import pickle
import sys
import time
from math import ceil

import numpy as np
import matplotlib.pyplot as plt
from benchmon.visualization import system_binary_reader


def read_binary_samples(file_path: str, sampler_type: system_binary_reader.generic_sample):
    samples_list = []
    sampler = sampler_type()
    with open(file_path, "rb") as file:
        while data := file.read(sampler.get_pack_size()):
            samples_list.append(sampler.binary_to_dict(data))
    return samples_list


def read_c_string(file):
    chars = []
    while True:
        byte = file.read(1)
        if not byte or byte == b'\n':
            break
        chars.append(byte)
    return b''.join(chars).decode('utf-8')


class SystemData:
    """
    System resource monitoring database
    """


    def __init__(self,
                 logger: logging.Logger,
                 traces_repo: str,
                 bin_cpu_report: str,
                 bin_cpufreq_report: str,
                 bin_mem_report: str,
                 bin_net_report: str,
                 bin_disk_report: str,
                 csv_ib_report: str):
        """
        Construct and profile system resource usage profile
        """
        self.logger = logger
        self.traces_repo = traces_repo

        if bin_cpu_report:
            self.ncpu = 0
            self.cpus = []
            self.cpu_prof = {}
            self.cpu_stamps = np.array([])
            self.get_cpu_profile(bin_cpu_report=bin_cpu_report)

        if bin_cpufreq_report:
            self.ncpu_freq = 0
            self.cpufreq_prof = {}
            self.cpufreq_vals = {}
            self.cpufreq_stamps = np.array([])
            self.cpufreq_min = None
            self.cpufreq_max = None
            self.get_cpufreq_prof(bin_cpufreq_report=bin_cpufreq_report)

        if bin_mem_report:
            self.mem_prof = {}
            self.mem_stamps = np.array([])
            self.get_mem_profile(bin_mem_report=bin_mem_report)

        if bin_net_report:
            self.net_prof = {}
            self.net_data = {}
            self.net_metric_keys = {}
            self.net_interfs = []
            self.net_stamps = np.array([])
            self.net_rx_total = np.array([])
            self.net_tx_total = np.array([])
            self.net_rx_data = 0
            self.net_tx_data = 0
            self.get_net_prof(bin_net_report=bin_net_report)

        if bin_disk_report:
            self.disk_prof = {}
            self.disk_data = {}
            self.disk_field_keys = {}
            self.maj_blks_sects = {}
            self.disk_blks = []
            self.disk_stamps = np.array([])
            self.disk_rd_total = np.array([])
            self.disk_wr_total = np.array([])
            self.disk_rd_data = 0
            self.disk_wr_data = 0
            self.get_disk_prof(bin_disk_report=bin_disk_report)

        if csv_ib_report:
            self.ib_prof = {}
            self.ib_data = {}
            self.ib_metric_keys = []
            self.ib_interfs = []
            self.ib_stamps = np.array([])
            self.ib_rx_total = np.array([])
            self.ib_tx_total = np.array([])
            self.ib_rx_data = 0
            self.ib_tx_data = 0
            self.get_ib_prof(csv_ib_report=csv_ib_report)

        self.xticks = None
        self.xlim = None
        self.yrange = None

    def read_cpu_bin_report(self, bin_cpu_report: str):
        """
        Read cpu report
        """
        t0 = time.time()
        self.logger.debug(f"\t open+read = {round(time.time() - t0, 3)} s")

        samples_list = read_binary_samples(bin_cpu_report, system_binary_reader.hf_cpu_sample)

        self.cpus = []
        ts_0 = samples_list[0]["timestamp"]
        ts = ts_0
        idx = 0
        while ts == ts_0:
            self.cpus.append(samples_list[idx]["cpu"])
            idx += 1
            ts = samples_list[idx]["timestamp"]

        ncpu_glob = len(self.cpus)
        self.ncpu = ncpu_glob - 1

        cpu_metric_keys = {key for key, _, _ in system_binary_reader.hf_cpu_sample().field_definitions}

        # Init cpu time series
        cpu_ts_raw = {}
        for cpu in self.cpus:
            cpu_ts_raw[cpu] = {key: [] for key in cpu_metric_keys}

        # Read lines
        timestamps_raw = []

        t0 = time.time()
        for data in samples_list:
            for key in cpu_metric_keys:
                cpu_ts_raw[data["cpu"]][key].append(data[key])

        self.logger.debug(f"\t fill dict = {round(time.time() - t0, 3)} s")

        t0 = time.time()
        timestamps_raw = [float(data["timestamp"] / 1e9) for data in samples_list[1::ncpu_glob]]
        self.logger.debug(f"\t ts_raw = {round(time.time() - t0, 3)} s")

        return cpu_ts_raw, timestamps_raw

    def get_cpu_profile(self, bin_cpu_report=str) -> int:
        """
        Get cpu profile
        """
        cpu_pkl = f"{self.traces_repo}/pkl_dir/cpu_prof.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/cpu_stamps.pkl"

        if os.access(cpu_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK):
            self.logger.debug("Load CPU profile..."); t0 = time.time()  # noqa: E702

            with open(cpu_pkl, "rb") as _pf:
                self.cpu_prof = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.cpu_stamps = pickle.load(_pf)
            self.ncpu = len(self.cpu_prof) - 1

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            max_int = np.iinfo(np.uint32).max
            self.logger.debug("Read CPU report..."); t0 = time.time()  # noqa: E702
            cpu_ts_raw, timestamps_raw = self.read_cpu_bin_report(bin_cpu_report=bin_cpu_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create CPU profile..."); t0 = time.time()  # noqa: E702
            nstamps = len(timestamps_raw) - 1

            t0i = time.time()
            timestamps = np.zeros(nstamps)
            for stamp in range(nstamps):
                timestamps[stamp] = (timestamps_raw[stamp + 1] + timestamps_raw[stamp]) / 2
            self.logger.debug(f"\t ts = {round(time.time() - t0i, 3)} s")

            t0i = time.time()
            cpu_ts = {}
            for key in cpu_ts_raw.keys():
                cpu_ts[key] = {metric_key: np.zeros(nstamps) for metric_key in cpu_ts_raw[max_int].keys()}
            self.logger.debug(f"\t init dict = {round(time.time() - t0i, 3)} s")

            t0i = time.time()
            for stamp in range(nstamps):
                for key, metric_key in itertools.product(cpu_ts_raw.keys(), cpu_ts_raw[max_int].keys()):
                    cpu_ts[key][metric_key][stamp] = (
                        cpu_ts_raw[key][metric_key][stamp + 1] - cpu_ts_raw[key][metric_key][stamp]
                    )
            self.logger.debug(f"\t compute spaces = {round(time.time() - t0i, 3)} s")

            t0i = time.time()
            for key in cpu_ts.keys():
                for stamp in range(nstamps):
                    cpu_total = 0
                    for metric_key in cpu_ts[max_int].keys():
                        if metric_key != "timestamp":
                            cpu_total += cpu_ts[key][metric_key][stamp]

                    for metric_key in cpu_ts[max_int].keys():
                        cpu_ts[key][metric_key][stamp] = cpu_ts[key][metric_key][stamp] / cpu_total * 100
            self.logger.debug(f"\t compute percents = {round(time.time() - t0i, 3)} s")

            self.cpu_prof = cpu_ts
            self.cpu_stamps = timestamps

            t0i = time.time()
            with open(cpu_pkl, "wb") as _pf:
                pickle.dump(self.cpu_prof, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.cpu_stamps, _pf)
            self.logger.debug(f"\t save profile = {round(time.time() - t0i, 3)} s")

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def plot_cpu(self, number="", annotate_with_cmds=None) -> int:
        """
        Plot average cpu usage
        """
        core = np.iinfo(np.uint32).max if number == "" else number
        alpha = 0.8
        prefix = f"{number}: " if number else ""

        cpu_usr = self.cpu_prof[core]["user"] + self.cpu_prof[core]["nice"]
        cpu_sys = self.cpu_prof[core]["system"] + self.cpu_prof[core]["irq"] + self.cpu_prof[core]["softirq"]
        cpu_wai = self.cpu_prof[core]["iowait"]
        cpu_stl = self.cpu_prof[core]["steal"] + self.cpu_prof[core]["guest"] + self.cpu_prof[core]["guestnice"]

        plt.fill_between(self.cpu_stamps, 100, color="C7", alpha=alpha / 3, label=f"{prefix}idle")

        curve_stl = cpu_stl
        plt.fill_between(self.cpu_stamps, curve_stl, color="C5", alpha=alpha, label=f"{prefix}virt")

        curve_wai = curve_stl + cpu_wai
        plt.fill_between(self.cpu_stamps, curve_stl, curve_wai, color="C8", alpha=alpha, label=f"{prefix}wait")

        curve_sys = curve_wai + cpu_sys
        plt.fill_between(self.cpu_stamps, curve_wai, curve_sys, color="C4", alpha=alpha, label=f"{prefix}sys")

        curve_usr = curve_sys + cpu_usr
        plt.fill_between(self.cpu_stamps, curve_sys, curve_usr, color="C0", alpha=alpha, label=f"{prefix}usr")

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.yticks(100 / (self.yrange - 1) * np.arange(self.yrange))
        plt.grid()

        if number:
            plt.ylabel(f"CPU Core-{number} usage (%)")
        else:
            plt.ylabel("CPU average usage (%)")

        # Order legend
        _order = [0, 4, 3, 2, 1]
        _handles, _labels = plt.gca().get_legend_handles_labels()
        plt.legend([_handles[idx] for idx in _order], [_labels[idx] for idx in _order], loc=1)

        if annotate_with_cmds:
            annotate_with_cmds(ymax=100)

        return 0

    def plot_cpu_per_core(self, cores_in: str = "", cores_out: str = "", annotate_with_cmds=None) -> int:
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

        cm = plt.cm.jet(np.linspace(0, 1, _ncpu + 1))
        for idx, core in enumerate(cores):
            core_name = f"cpu{core}"

            cpu_usr = self.cpu_prof[core_name]["user"] \
                + self.cpu_prof[core_name]["nice"]

            cpu_sys = self.cpu_prof[core_name]["system"] \
                + self.cpu_prof[core_name]["irq"] \
                + self.cpu_prof[core_name]["softirq"]

            cpu_wai = self.cpu_prof[core_name]["iowait"]

            plt.plot(self.cpu_stamps, cpu_usr + cpu_sys + cpu_wai, color=cm[idx], label=f"core-{core}")

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.yticks(100 / (self.yrange - 1) * np.arange(self.yrange))
        plt.ylabel("CPU Cores (%)")
        plt.grid()
        plt.legend(loc=0, ncol=_ncpu // ceil(_ncpu / 16), fontsize="6")

        if annotate_with_cmds:
            annotate_with_cmds(ymax=100)

        return 0

    def read_mem_bin_report(self, bin_mem_report: str):
        """
        Read memory report
        """
        hf = system_binary_reader.hf_mem_sample()
        samples_list = []
        with open(bin_mem_report, "rb") as file:
            while data := file.read(hf.get_pack_size()):
                samples_list.append(hf.binary_to_dict(data))

        return samples_list

    def get_mem_profile(self, bin_mem_report: str) -> int:
        """
        Get memory profile
        """
        mem_pkl = f"{self.traces_repo}/pkl_dir/mem_prof.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/mem_stamps.pkl"

        if os.access(mem_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK):
            self.logger.debug("Load Memory profile..."); t0 = time.time()  # noqa: E702

            with open(mem_pkl, "rb") as _pf:
                self.mem_prof = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.mem_stamps = pickle.load(_pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            ALL_MEM_KEYS = "MemTotal,MemFree,MemAvailable,Buffers,Cached,SwapCached,Active,Inactive,Active(anon),Inactive(anon),Active(file),Inactive(file),Unevictable,Mlocked,SwapTotal,SwapFree,Dirty,Writeback,AnonPages,Mapped,Shmem,KReclaimable,Slab,SReclaimable,SUnreclaim,KernelStack,PageTables,NFS_Unstable,Bounce,WritebackTmp,CommitLimit,Committed_AS,VmallocTotal,VmallocUsed,VmallocChunk,Percpu,HardwareCorrupted,AnonHugePages,ShmemHugePages,ShmemPmdMapped,FileHugePages,FilePmdMapped,HugePages_Total,HugePages_Free,HugePages_Rsvd,HugePages_Surp,Hugepagesize,Hugetlb,DirectMap4k,DirectMap2M,DirectMap1G"  # noqa: F841, E501, N806, B950

            self.logger.debug("Read Memory report..."); t0 = time.time()  # noqa: E702
            samples_list = self.read_mem_bin_report(bin_mem_report=bin_mem_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create Memory profile..."); t0 = time.time()  # noqa: E702

            hf = system_binary_reader.hf_mem_sample()
            memory_dict_ = {key: [] for key, _, enabled in hf.field_definitions if enabled}
            for data in samples_list:
                for key in memory_dict_:
                    memory_dict_[key].append(data[key])

            self.mem_prof = {key: np.array(values, dtype=np.float64) for key, values in memory_dict_.items()}
            self.mem_stamps = [np.float64(timestamp) / 1e9 for timestamp in memory_dict_["timestamp"]]

            with open(mem_pkl, "wb") as _pf:
                pickle.dump(self.mem_prof, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.mem_stamps, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def plot_memory_usage(self, annotate_with_cmds=None) -> float:
        """
        Plot memory/swap usage
        """
        alpha = 0.3
        memunit = 1024**2  # (GB)

        # Memory
        total = self.mem_prof["MemTotal"] / memunit
        cached = (self.mem_prof["Buffers"] + self.mem_prof["Cached"] + self.mem_prof["Slab"]) / memunit
        used = - cached + (self.mem_prof["MemTotal"] - self.mem_prof["MemFree"]) / memunit
        plt.fill_between(self.mem_stamps, total, alpha=alpha, label="MemTotal", color="b")
        plt.fill_between(self.mem_stamps, used, alpha=alpha * 3, label="MemUsed", color="b")
        plt.fill_between(self.mem_stamps, used, used + cached, alpha=alpha * 2, label="Cach/Buff", color="g")

        # Swap
        swap_total = self.mem_prof["SwapTotal"] / memunit
        swap_used = swap_total - self.mem_prof["SwapFree"] / memunit
        plt.fill_between(self.mem_stamps, swap_total, alpha=alpha, label="SwapTotal", color="r")
        plt.fill_between(self.mem_stamps, swap_used, alpha=alpha * 3, label="SwapUsed", color="r")

        total_max = max(total)
        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)

        for powtwo in range(25):
            yticks = np.arange(0, total_max + 2**powtwo, 2**powtwo, dtype="i")
            if len(yticks) < self.yrange:
                break
        plt.yticks(yticks)

        plt.ylabel("Memory (GB)")
        plt.legend(loc=1)
        plt.grid()

        if annotate_with_cmds:
            annotate_with_cmds(ymax=total_max)

        return total_max

    def read_cpufreq_bin_report(self, bin_cpufreq_report: str):
        hf = system_binary_reader.hf_cpufreq_sample()
        samples_list = []
        with open(bin_cpufreq_report, "rb") as file:
            min_cpufreq = np.uint64(int.from_bytes(file.read(8), byteorder='little', signed=False))
            max_cpufreq = np.uint64(int.from_bytes(file.read(8), byteorder='little', signed=False))
            while data := file.read(hf.get_pack_size()):
                samples_list.append(hf.binary_to_dict(data))

        return min_cpufreq, max_cpufreq, samples_list

    def get_cpufreq_prof(self, bin_cpufreq_report: str):
        """
        Read cpu frequency report
        Get profile
        """
        cpufreq_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_prof.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_stamps.pkl"
        freqvals_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_vals.pkl"

        if os.access(cpufreq_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK):
            self.logger.debug("Load CPU profile..."); t0 = time.time()  # noqa: E702

            with open(cpufreq_pkl, "rb") as _pf:
                self.cpufreq_prof = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.cpufreq_stamps = pickle.load(_pf)
            with open(freqvals_pkl, "rb") as _pf:
                self.cpufreq_vals = pickle.load(_pf)

            self.cpufreq_min = self.cpufreq_vals["min"]
            self.cpufreq_max = self.cpufreq_vals["max"]
            self.ncpu_freq = len(self.cpufreq_prof)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            self.logger.debug("Read CPUFreq report..."); t0 = time.time()  # noqa: E702
            cpufreq_min, cpufreq_max, samples_list = self.read_cpufreq_bin_report(bin_cpufreq_report=bin_cpufreq_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create CPUFreq profile..."); t0 = time.time()  # noqa: E702
            self.cpufreq_min = cpufreq_min or None
            self.cpufreq_max = cpufreq_max or None

            self.ncpu_freq = 0
            ts_0 = samples_list[0]["timestamp"]
            ts = ts_0
            line_idx = 0
            while ts == ts_0:
                line_idx += 1
                ts = samples_list[line_idx]["timestamp"]
                self.ncpu_freq += 1

            cpufreq_ts = []
            for cpu_nb in range(self.ncpu_freq):
                cpufreq_ts.append([])

            # Read lines
            for data in samples_list:
                cpufreq_ts[data["cpu"]].append(data["frequency"])

            HZ_UNIT = 1e6  # noqa: N806
            for cpu_nb in range(self.ncpu_freq):
                cpufreq_ts[cpu_nb] = np.array(cpufreq_ts[cpu_nb]) / HZ_UNIT

            self.cpufreq_prof = cpufreq_ts
            self.cpufreq_stamps = [float(data["timestamp"] / 1e9) for data in samples_list[0::self.ncpu_freq]]

            self.cpufreq_vals["mean"] = np.zeros_like(self.cpufreq_stamps)
            for cpu in range(self.ncpu_freq):
                self.cpufreq_vals["mean"] += self.cpufreq_prof[cpu] / self.ncpu_freq
            self.cpufreq_vals["min"] = self.cpufreq_min
            self.cpufreq_vals["max"] = self.cpufreq_max

            with open(cpufreq_pkl, "wb") as _pf:
                pickle.dump(self.cpufreq_prof, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.cpufreq_stamps, _pf)
            with open(freqvals_pkl, "wb") as _pf:
                pickle.dump(self.cpufreq_vals, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def plot_cpufreq(self, cores_in: str = "", cores_out: str = "", annotate_with_cmds=None) -> float:
        """
        Plot cpu frequency per core
        """
        HZ_UNIT = 1e6  # noqa: N806

        cores = [core for core in range(self.ncpu_freq)]
        if len(cores_in) > 0:
            cores = [int(core) for core in cores_in.split(",")]
        elif len(cores_in) == 0 and len(cores_out) > 0:
            for core_ex in cores_out.split(","):
                cores.remove(int(core_ex))
        _ncpu = len(cores)

        cm = plt.cm.jet(np.linspace(0, 1, _ncpu + 1))

        for idx, core in enumerate(cores):
            plt.plot(self.cpufreq_stamps, self.cpufreq_prof[core], color=cm[idx], label=f"core-{core}")

        plt.plot(self.cpufreq_stamps, self.cpufreq_vals["mean"], "k.-", label="mean")

        cpu_freq_max = 6  # Hard-coded 6 HZ
        if self.cpufreq_min and self.cpufreq_max:
            cpu_freq_min = float(self.cpufreq_min) / HZ_UNIT
            cpu_freq_max = float(self.cpufreq_max) / HZ_UNIT
            plt.plot(self.cpufreq_stamps, cpu_freq_max * np.ones_like(self.cpufreq_stamps),
                     color="gray", linestyle="--", label="hw max/min")
            plt.plot(self.cpufreq_stamps, cpu_freq_min * np.ones_like(self.cpufreq_stamps),
                     color="gray", linestyle="--")

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        plt.yticks(cpu_freq_max / (self.yrange - 1) * np.arange(self.yrange))
        plt.ylabel("CPU frequencies (GHz)")
        plt.grid()
        plt.legend(loc=0, ncol=self.ncpu_freq // ceil(self.ncpu_freq / 16), fontsize="6")

        if annotate_with_cmds:
            annotate_with_cmds(ymax=cpu_freq_max)

        return cpu_freq_max

    def read_net_bin_report(self, bin_net_report: str):
        """
        Read network report
        """
        samples_list = read_binary_samples(bin_net_report, system_binary_reader.hf_net_sample)

        # Get network interfaces
        ts_0 = samples_list[0]["timestamp"]
        ts = ts_0
        line_idx = 0
        self.net_interfs = []
        while ts == ts_0:
            self.net_interfs += [samples_list[line_idx]["interface"]]
            line_idx += 1
            ts = samples_list[line_idx]["timestamp"]
        nnet_interf = len(self.net_interfs)
        self.net_metric_keys = [key for key, _, enabled in system_binary_reader.hf_net_sample().field_definitions
                                if key not in ["timestamp", "interface"] and enabled]

        net_ts_raw = {}
        for interf in self.net_interfs:
            net_ts_raw[interf] = {key: [] for key in self.net_metric_keys}

        for sample in samples_list:
            for key in self.net_metric_keys:
                net_ts_raw[sample["interface"]][key].append(float(sample[key]))

        timestamps_raw = [float(item["timestamp"]) / 1e9 for item in samples_list[::nnet_interf]]
        return net_ts_raw, timestamps_raw

    def get_net_prof(self, bin_net_report: str):
        """
        Get network profile
        """
        net_pkl = f"{self.traces_repo}/pkl_dir/net_prof.pkl"
        dat_pkl = f"{self.traces_repo}/pkl_dir/net_data.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/net_stamps.pkl"

        if os.access(net_pkl, os.R_OK) and os.access(dat_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK):
            self.logger.debug("Load Network profile..."); t0 = time.time()  # noqa: E702

            with open(net_pkl, "rb") as _pf:
                self.net_prof = pickle.load(_pf)
            with open(dat_pkl, "rb") as _pf:
                self.net_data = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.net_stamps = pickle.load(_pf)
            self.net_interfs = list(self.net_prof.keys())

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            self.logger.debug("Read Network report..."); t0 = time.time()  # noqa: E702
            net_ts_raw, timestamps_raw = self.read_net_bin_report(bin_net_report=bin_net_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create Network profile..."); t0 = time.time()  # noqa: E702

            nstamps = len(timestamps_raw) - 1
            self.net_stamps = np.zeros(nstamps)
            for stamp in range(nstamps):
                self.net_stamps[stamp] = (timestamps_raw[stamp + 1] + timestamps_raw[stamp]) / 2

            # Init network profile
            for interf in self.net_interfs:
                self.net_prof[interf] = {key: np.zeros(nstamps) for key in self.net_metric_keys}
                self.net_data[interf] = {key: 0 for key in self.net_metric_keys}  # noqa: C420

            # Fill in
            for key in net_ts_raw:
                for metric_key in self.net_metric_keys:
                    self.net_data[key][metric_key] = net_ts_raw[key][metric_key][-1] - net_ts_raw[key][metric_key][0]
                    for stamp in range(nstamps):
                        self.net_prof[key][metric_key][stamp] = (
                            net_ts_raw[key][metric_key][stamp + 1] - net_ts_raw[key][metric_key][stamp]
                        ) / (timestamps_raw[stamp + 1] - timestamps_raw[stamp])

            with open(net_pkl, "wb") as _pf:
                pickle.dump(self.net_prof, _pf)
            with open(dat_pkl, "wb") as _pf:
                pickle.dump(self.net_data, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.net_stamps, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

    def plot_network(self,
                     all_interfaces=False,
                     total_network=True,
                     is_rx_only=False,
                     is_tx_only=False,
                     is_netdata_label=True,
                     annotate_with_cmds=None) -> float:
        """
        Plot network activity
        """
        BYTES_UNIT = 1024**2  # noqa: N806  (MB)
        _alpha = 0.5
        _mrksz = 3.5

        # Interface to exclude (eg: br0)
        interf_to_exclude = ["br0:",]
        is_excluded = lambda interf: any(_interf in interf for _interf in interf_to_exclude)

        self.net_rx_total = np.zeros_like(self.net_stamps)
        self.net_tx_total = np.zeros_like(self.net_stamps)

        for interf in self.net_interfs:
            if is_excluded(interf):
                continue

            self.net_rx_total += self.net_prof[interf]["rx-bytes"] / BYTES_UNIT
            self.net_tx_total += self.net_prof[interf]["tx-bytes"] / BYTES_UNIT

            self.net_rx_data += self.net_data[interf]["rx-bytes"] / BYTES_UNIT
            self.net_tx_data += self.net_data[interf]["tx-bytes"] / BYTES_UNIT

        # RX
        if not is_tx_only:
            if total_network:
                label = "rx:total"
                if is_netdata_label:
                    label += f" ({int(self.net_rx_data)} MB)"
                plt.fill_between(self.net_stamps, self.net_rx_total, label=label, color="b", alpha=_alpha)

            if all_interfaces:
                for interf in self.net_interfs:
                    if is_excluded(interf):
                        continue
                    rx_arr = self.net_prof[interf]["rx-bytes"] / BYTES_UNIT
                    rd = self.net_data[interf]["rx-bytes"] / BYTES_UNIT
                    if rd > 1:  # and rd / self.net_rx_data > 0.001:
                        label = f"rx:{interf[:-1]}"
                        if is_netdata_label:
                            label += f" ({int(rd)} MB)"
                        plt.plot(self.net_stamps, rx_arr, label=label, ls="-",
                                 alpha=_alpha, marker="v", markersize=_mrksz)

        # TX
        if not is_rx_only:
            if total_network:
                label = "tx:total"
                if is_netdata_label:
                    label += f" ({int(self.net_tx_data)} MB)"
                plt.fill_between(self.net_stamps, self.net_tx_total, label=label, color="r", alpha=_alpha)

            if all_interfaces:
                for interf in self.net_interfs:
                    if is_excluded(interf):
                        continue
                    tx_arr = self.net_prof[interf]["tx-bytes"] / BYTES_UNIT
                    td = self.net_data[interf]["tx-bytes"] / BYTES_UNIT
                    if td > 1:  # and td / self.net_tx_data > 0.001:
                        label = f"tx:{interf[:-1]}"
                        if is_netdata_label:
                            label += f" ({int(td)} MB)"
                        plt.plot(self.net_stamps, tx_arr, label=label, ls="-",
                                 alpha=_alpha, marker="^", markersize=_mrksz)

        netmax = max(max(self.net_rx_total), max(self.net_tx_total))
        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        for powtwo in range(25):
            yticks = np.arange(0, netmax + 2**powtwo, 2**powtwo, dtype="i")
            if len(yticks) < self.yrange:
                break
        plt.yticks(yticks)
        plt.ylabel("Network (MB/s)")
        plt.legend(loc=1)
        plt.grid()

        if annotate_with_cmds:
            annotate_with_cmds(ymax=netmax)

        return netmax

    def read_disk_bin_report(self, bin_disk_report: str):
        """
        Read disk monitoring report
        """
        disk_sampler = system_binary_reader.hf_disk_sample()
        sector_sizes = {}
        samples_list = []
        with open(bin_disk_report, "rb") as file:
            np.frombuffer(file.read(8), dtype=np.uint64)[0]  # n_major_blocks
            np.frombuffer(file.read(8), dtype=np.uint64)[0]  # n_all_blocks
            sector_sizes_str = read_c_string(file).split(",")
            sector_sizes = {key: int(value) for key, value in zip(sector_sizes_str[0::2], sector_sizes_str[1::2])}
            while data := file.read(disk_sampler.get_pack_size()):
                samples_list.append(disk_sampler.binary_to_dict(data))

        self.disk_field_keys = [key for key, _, enabled in disk_sampler.field_definitions
                                if enabled and key not in ["timestamp", "major", "minor", "device_name"]]

        # get major blocks and associated sector size
        self.maj_blks_sects = sector_sizes

        # all disk blocks
        ts_0 = samples_list[0]["timestamp"]
        ts = ts_0
        line_idx = 0
        ndisk_blk = 0
        while ts == ts_0:
            line_idx += 1
            ndisk_blk += 1
            ts = samples_list[line_idx]["timestamp"]
        self.disk_blks = [samples_list[idx]["device_name"] for idx in range(ndisk_blk)]

        # raw disk measure stamps
        disk_ts_raw = {}
        for blk in self.disk_blks:
            disk_ts_raw[blk] = {key: [] for key in self.disk_field_keys}

        for idx in range(ndisk_blk):
            disk_ts_raw[self.disk_blks[idx]]["major"] = int(samples_list[idx]["major"])  # major index: 1
            disk_ts_raw[self.disk_blks[idx]]["minor"] = int(samples_list[idx]["minor"])  # minor index: 2

        for idx, sample in enumerate(samples_list):
            for key, value in sample.items():
                if key not in ["timestamp", "device_name", "major", "minor"]:
                    disk_ts_raw[sample["device_name"]][key].append(float(value))

        # raw time stamps
        timestamps_raw = [float(sample["timestamp"]) / 1e9 for sample in samples_list[::ndisk_blk]]

        return disk_ts_raw, timestamps_raw

    def get_disk_prof(self, bin_disk_report: str):
        """
        Get disk profile
        """
        disk_pkl = f"{self.traces_repo}/pkl_dir/disk_prof.pkl"
        dat_pkl = f"{self.traces_repo}/pkl_dir/disk_data.pkl"
        maj_pkl = f"{self.traces_repo}/pkl_dir/disk_maj.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/disk_stamps.pkl"

        if all(os.access(pkl_file, os.R_OK) for pkl_file in (disk_pkl, dat_pkl, maj_pkl, ts_pkl)):
            self.logger.debug("Load Disk profile..."); t0 = time.time()  # noqa: E702

            with open(disk_pkl, "rb") as _pf:
                self.disk_prof = pickle.load(_pf)
            with open(dat_pkl, "rb") as _pf:
                self.disk_data = pickle.load(_pf)
            with open(maj_pkl, "rb") as _pf:
                self.maj_blks_sects = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.disk_stamps = pickle.load(_pf)
            self.disk_blks = list(self.disk_prof.keys())

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            self.logger.debug("Read Disk report..."); t0 = time.time()  # noqa: E702
            disk_ts_raw, timestamps_raw = self.read_disk_bin_report(bin_disk_report=bin_disk_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create Disk profile..."); t0 = time.time()  # noqa: E702
            # final time stamps
            nstamps = len(timestamps_raw) - 1
            self.disk_stamps = np.zeros(nstamps)
            for stamp in range(nstamps):
                self.disk_stamps[stamp] = (timestamps_raw[stamp + 1] + timestamps_raw[stamp]) / 2

            # Init disk profile
            self.disk_prof = {}
            self.disk_data = {}
            for blk in self.disk_blks:
                self.disk_prof[blk] = {key: np.zeros(nstamps) for key in self.disk_field_keys}
                self.disk_data[blk] = {key: -999.999 for key in self.disk_field_keys}

            # Fill in
            for blk in self.disk_blks:
                self.disk_prof[blk]["major"] = disk_ts_raw[blk]["major"]
                self.disk_prof[blk]["minor"] = disk_ts_raw[blk]["minor"]

            # Sectors and data n bytes
            BYTES_UNIT = 1024**2  # noqa: N806
            fields = ["sect-rd", "sect-wr", "sect-disc"]
            for blk in self.disk_blks:
                bytes_by_sector = self.maj_blks_sects[[item for item in self.maj_blks_sects if item in blk][0]]
                for field in fields:
                    for stamp in range(nstamps):
                        self.disk_prof[blk][field][stamp] = (
                            (disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp])
                            / (timestamps_raw[stamp + 1] - timestamps_raw[stamp]) * bytes_by_sector / BYTES_UNIT
                        )

                    self.disk_data[blk][field] = int(
                        (disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0]) * bytes_by_sector / BYTES_UNIT
                    )

            # Number of operations
            fields = ["#rd-cd", "#rd-md", "#wr-cd", "#wr-md", "#io-ip", "#disc-cd", "#disc-md", "#flush-req"]
            for blk in self.disk_blks:
                for field in fields:
                    for stamp in range(nstamps):
                        self.disk_prof[blk][field][stamp] = (
                            disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp]
                        ) / (timestamps_raw[stamp + 1] - timestamps_raw[stamp])

                    self.disk_data[blk][field] = int(disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0])

            # Save profiles
            with open(disk_pkl, "wb") as _pf:
                pickle.dump(self.disk_prof, _pf)
            with open(dat_pkl, "wb") as _pf:
                pickle.dump(self.disk_data, _pf)
            with open(maj_pkl, "wb") as _pf:
                pickle.dump(self.maj_blks_sects, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.disk_stamps, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

    def plot_disk(self,
                  is_rd_only=False,
                  is_wr_only=False,
                  is_with_iops=False,
                  is_diskdata_label=True,
                  annotate_with_cmds=None) -> float:
        """
        Plot disk activity
        """
        alpha = 0.5
        diskmax = 0.0

        self.disk_rd_total = np.zeros_like(self.disk_stamps)
        self.disk_wr_total = np.zeros_like(self.disk_stamps)

        # Read/WRite bandwdith
        fields = ["sect-rd", "sect-wr"]
        if is_rd_only:
            fields.remove("sect-wr")
        if is_wr_only:
            fields.remove("sect-rd")

        for field in fields:
            for blk in self.disk_blks:
                if blk in self.maj_blks_sects:
                    array = self.disk_prof[blk][field]
                    label = f"{field[-2:]}:{blk}"
                    if is_diskdata_label:
                        label += f" ({self.disk_data[blk][field]} MB)"
                    if np.linalg.norm(array) > 1:
                        plt.fill_between(self.disk_stamps, array, label=label, alpha=alpha)
                        diskmax = max(diskmax, max(array))

                        if field == "sect-rd":
                            self.disk_rd_total += array
                            self.disk_rd_data += self.disk_data[blk][field]
                        elif field == "sect-wr":
                            self.disk_wr_total += array
                            self.disk_wr_data += self.disk_data[blk][field]

        for powtwo in range(25):
            yticks = np.arange(0, diskmax + 2**powtwo, 2**powtwo, dtype="i")
            if len(yticks) < self.yrange:
                break
        plt.yticks(yticks)
        plt.ylabel("Disk bandwidth (MB/s)")
        plt.grid()
        hand, lab = plt.gca().get_legend_handles_labels()

        # Read/Write iops
        if is_with_iops:
            pltt = plt.twinx()
            fields = ["#rd-cd", "#wr-cd"]

            if is_rd_only:
                fields.remove("#wr-cd")
            if is_wr_only:
                fields.remove("#rd-cd")

            for field in fields:
                for blk in self.disk_blks:
                    if blk in self.maj_blks_sects:
                        array = self.disk_prof[blk][field]
                        label = f"{field[:3]}:{blk}"
                        if is_diskdata_label:
                            label += f" ({self.disk_data[blk][field]:.3e} op)"
                        if np.linalg.norm(array) > 1:
                            pltt.plot(self.disk_stamps, array, label=label, ls="-")
            pltt.set_ylabel("Disk operations per second (IOPS)")
            pltt.grid()
            hand_twin, lab_twin = pltt.get_legend_handles_labels()

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        if is_with_iops:
            plt.legend(hand + hand_twin, lab + lab_twin, loc=1)
        else:
            plt.legend(loc=1)

        if annotate_with_cmds and not is_with_iops:
            annotate_with_cmds(ymax=diskmax)  # @todo

        return diskmax

    def read_ib_csv_report(self, csv_ib_report: str):
        """
        Read infiniband monitoring csv report
        """
        ib_report_lines = self.read_csv_line_as_list(csv_report=csv_ib_report)

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

        timestamps_raw = [
            float(item[0]) for item in ib_report_lines[1:][:: len(self.ib_interfs) * len(self.ib_metric_keys)]
        ]

        return ib_ts_raw, timestamps_raw

    def get_ib_prof(self, csv_ib_report: str):
        """
        Get infiniband profile
        """
        ib_pkl = f"{self.traces_repo}/pkl_dir/ib_prof.pkl"
        dat_pkl = f"{self.traces_repo}/pkl_dir/ib_data.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/ib_stamps.pkl"

        if os.access(ib_pkl, os.R_OK) and os.access(dat_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK):
            self.logger.debug("Load IB profile..."); t0 = time.time()  # noqa: E702

            with open(ib_pkl, "rb") as _pf:
                self.ib_prof = pickle.load(_pf)
            with open(dat_pkl, "rb") as _pf:
                self.ib_data = pickle.load(_pf)
            with open(ts_pkl, "rb") as _pf:
                self.ib_stamps = pickle.load(_pf)
            self.ib_interfs = list(self.ib_prof.keys())

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        else:

            self.logger.debug("Read IB csv report..."); t0 = time.time()  # noqa: E702
            ib_ts_raw, timestamps_raw = self.read_ib_csv_report(csv_ib_report=csv_ib_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            self.logger.debug("Create IB profile..."); t0 = time.time()  # noqa: E702
            nstamps = len(timestamps_raw) - 1

            self.ib_stamps = np.zeros(nstamps)
            for stamp in range(nstamps):
                self.ib_stamps[stamp] = (timestamps_raw[stamp + 1] + timestamps_raw[stamp]) / 2

            # Init infiniband profile
            for interf in self.ib_interfs:
                self.ib_prof[interf] = {key: np.zeros(nstamps) for key in self.ib_metric_keys}
                self.ib_data[interf] = {key: 0 for key in self.ib_metric_keys}  # noqa: C420

            # Fill in
            BYTES_UNIT = (1 / 4) * 1024**2  # noqa: N806 (MB)
            for interf in self.ib_interfs:
                for metric_key in self.ib_metric_keys:
                    for stamp in range(nstamps):
                        self.ib_prof[interf][metric_key][stamp] = (
                            (ib_ts_raw[interf][metric_key][stamp + 1] - ib_ts_raw[interf][metric_key][stamp])
                            / (timestamps_raw[stamp + 1] - timestamps_raw[stamp]) / BYTES_UNIT
                        )

                    self.ib_data[interf][metric_key] = int(
                        (ib_ts_raw[interf][metric_key][-1] - ib_ts_raw[interf][metric_key][0]) / BYTES_UNIT
                    )

            with open(ib_pkl, "wb") as _pf:
                pickle.dump(self.ib_prof, _pf)
            with open(dat_pkl, "wb") as _pf:
                pickle.dump(self.ib_data, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.ib_stamps, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

    def plot_ib(self, annotate_with_cmds=None):
        """
        Plot infiniband activity
        """
        self.ib_rx_total = np.zeros_like(self.ib_stamps)
        self.ib_tx_total = np.zeros_like(self.ib_stamps)
        for interf in self.ib_interfs:
            self.ib_rx_total += self.ib_prof[interf]["port_rcv_data"]
            self.ib_tx_total += self.ib_prof[interf]["port_xmit_data"]

            self.ib_rx_data += self.ib_data[interf]["port_rcv_data"]
            self.ib_tx_data += self.ib_data[interf]["port_xmit_data"]

        alpha = 0.5

        # RX:IB
        plt.fill_between(self.ib_stamps, self.ib_rx_total,
                         label=f"rx:total ({self.ib_rx_data}) MB",
                         color="b", alpha=alpha / 2)

        for interf in self.ib_interfs:
            rx_arr = self.ib_prof[interf]["port_rcv_data"]
            rx_data_label = self.ib_data[interf]["port_rcv_data"]
            if rx_data_label > 1:  # np.linalg.norm(rx_arr) > 1:
                plt.plot(self.ib_stamps, rx_arr,
                         label=f"rx:(ib){interf} ({rx_data_label} MB)",
                         ls="-", marker="v", alpha=alpha)

        # TX:IB
        plt.fill_between(self.ib_stamps, self.ib_tx_total,
                         label=f"tx:total ({self.ib_tx_data} MB)",
                         color="r", alpha=alpha / 2)

        for interf in self.ib_interfs:
            tx_arr = self.ib_prof[interf]["port_xmit_data"]
            tx_data_label = self.ib_data[interf]["port_xmit_data"]
            if tx_data_label > 1:  # np.linalg.norm(tx_arr) > 1:
                plt.plot(self.ib_stamps, tx_arr,
                         label=f"tx:(ib){interf} ({tx_data_label} MB)",
                         ls="-", marker="^", alpha=alpha)

        ibmax = max(max(self.ib_rx_total), max(self.ib_tx_total))

        plt.xticks(*self.xticks)
        plt.xlim(self.xlim)
        for powtwo in range(25):
            yticks = np.arange(0, ibmax + 2**powtwo, 2**powtwo, dtype="i")
            if len(yticks) < self.yrange:
                break
        plt.yticks(yticks)
        plt.ylabel("Infiniband bandwidth (MB/s)")
        plt.grid()
        plt.legend(loc=1)

        ibmax = max(max(self.ib_rx_total), max(self.ib_tx_total))

        for powtow in range(25):
            yticks = np.arange(0, ibmax + 2**powtow, 2**powtow, dtype="i")
            if len(yticks) < self.yrange:
                break
        plt.yticks(yticks)

        if annotate_with_cmds:
            annotate_with_cmds(ymax=ibmax)

        return ibmax

    def read_csv_line_as_list(self, csv_report: str) -> list:
        """
        Read csv report as list

        Args:
            csv_report  (str)   CSV report filename

        Returns:
            (list)  read csv report as list
        """
        if os.path.isfile(csv_report):
            with open(csv_report, newline="") as csvfile:
                return list(csv.reader(csvfile))

        else:
            self.logger.error(f"Report {csv_report} does not exist! -> Remove the associated flag to this report")
            sys.exit(1)
