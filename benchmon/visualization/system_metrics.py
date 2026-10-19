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

import numpy as np
import matplotlib.pyplot as plt

from benchmon.visualization import system_binary_reader


class SystemData:
    """
    System resource monitoring database
    """

    def __init__(self,
                 logger: logging.Logger,
                 traces_repo: str,
                 is_binary: bool,
                 cpu_report: str,
                 cpufreq_report: str,
                 mem_report: str,
                 net_report: str,
                 disk_report: str,
                 ib_report: str):
        """
        Construct and profile system resource usage profile
        """
        self.logger = logger
        self.traces_repo = traces_repo
        self.is_binary = is_binary

        if cpu_report:
            self.ncpu = 0
            self.cpus = []
            self.cpu_prof = {}
            self.cpu_stamps = np.array([])
            self.cpu_profile_valid = self.get_cpu_profile(cpu_report=cpu_report) == 0

        if mem_report:
            self.mem_prof = {}
            self.mem_stamps = np.array([])
            self.mem_profile_valid = self.get_mem_profile(mem_report=mem_report)

    def read_cpu_csv_report(self, csv_cpu_report: str):
        """
        Read CPU report from CSV file
        """
        # Read line of cpu csv report
        t0 = time.time()
        cpu_report_lines = self.read_csv_line_as_list(csv_report=csv_cpu_report)
        self.logger.debug(f"\t open+read = {round(time.time() - t0, 3)} s")

        # Check if csv file is empty or limited to header
        if not cpu_report_lines or len(cpu_report_lines) <= 1:
            self.logger.warning("CPU CSV report is empty, returning empty data")
            return {}, []

        # Get cpus, number of cpu cores + global
        ts_0 = cpu_report_lines[1][0]
        ts = ts_0
        line_idx = 1
        while ts == ts_0:
            self.cpus += [cpu_report_lines[line_idx][1]]
            line_idx += 1
            ts = cpu_report_lines[line_idx][0]
        ncpu_glob = len(self.cpus)
        self.ncpu = ncpu_glob - 1

        # CPU metric keys {"user": 2, "nice": 3, "system": 4, "idle": 5, "iowait": 6,
        #                  "irq": 7, "softirq": 8, "steal": 9, "guest": 10, "guestnice": 11}
        _sidx = 2
        cpu_metric_keys = {key: idx + _sidx for idx, key in enumerate(cpu_report_lines[0][_sidx:])}

        # Init cpu time series
        cpu_ts_raw = {}
        for cpu in self.cpus:
            cpu_ts_raw[cpu] = {key: [] for key in cpu_metric_keys.keys()}

        # Read lines
        time_index = 0
        cpu_index = 1
        timestamps_raw = []

        t0 = time.time()
        for line in cpu_report_lines[1:]:
            for key in cpu_metric_keys:
                cpu_ts_raw[line[cpu_index]][key] += [float(line[cpu_metric_keys[key]])]
        self.logger.debug(f"\t fill dict = {round(time.time() - t0, 3)} s")

        t0 = time.time()
        timestamps_raw = [float(line[time_index]) for line in cpu_report_lines[1::ncpu_glob]]
        self.logger.debug(f"\t ts_raw = {round(time.time() - t0, 3)} s")

        return cpu_ts_raw, timestamps_raw


    def read_cpu_bin_report(self, bin_cpu_report: str):
        """
        Read CPU report from binary file
        """
        t0 = time.time()
        self.logger.debug(f"\t open+read = {round(time.time() - t0, 3)} s")

        samples_list = self.read_binary_samples(bin_cpu_report, system_binary_reader.hf_cpu_sample)

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


    def get_cpu_profile(self, report=str) -> int:
        """
        Get CPU profile
        """
        if self.is_binary:
            return self.get_cpu_profile_binary(bin_cpu_report=report)
        else:
            return self.get_cpu_profile_csv(csv_cpu_report=report)


    def get_cpu_profile_csv(self, csv_cpu_report=str) -> int:
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

            self.logger.debug("Read CPU csv report..."); t0 = time.time()  # noqa: E702
            cpu_ts_raw, timestamps_raw = self.read_cpu_csv_report(csv_cpu_report=csv_cpu_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            # Check if CPU report data is empty
            if not cpu_ts_raw:
                self.logger.warning("CPU CSV report data is empty, creating empty profile")
                self.cpu_prof = {}
                self.cpu_stamps = np.array([])
                self.ncpu = 0
                return 0

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
                cpu_ts[key] = {metric_key: np.zeros(nstamps) for metric_key in cpu_ts_raw["cpu"].keys()}
            self.logger.debug(f"\t init dict = {round(time.time() - t0i, 3)} s")

            t0i = time.time()
            for stamp in range(nstamps):
                for key, metric_key in itertools.product(cpu_ts_raw.keys(), cpu_ts_raw["cpu"].keys()):
                    cpu_ts[key][metric_key][stamp] = (
                        cpu_ts_raw[key][metric_key][stamp + 1] - cpu_ts_raw[key][metric_key][stamp]
                    )
            self.logger.debug(f"\t compute spaces = {round(time.time() - t0i, 3)} s")

            t0i = time.time()
            for key in cpu_ts.keys():
                for stamp in range(nstamps):
                    cpu_total = 0
                    for metric_key in cpu_ts["cpu"].keys():
                        cpu_total += cpu_ts[key][metric_key][stamp]

                    for metric_key in cpu_ts["cpu"].keys():
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
        core = f"cpu{number}"
        alpha = 0.8
        prefix = f"{number}: " if number else ""

        # Check there is content
        if (len(self.cpu_stamps) < 1):
            self.logger.warning("Empty cpu journal, skipping corresponding overall plot")
            return -1

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

        # Check there is content
        if (len(self.cpu_stamps) < 1):
            self.logger.warning("Empty cpu journal, skipping corresponding core plot")
            return -1

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

    def read_mem_csv_report(self, csv_mem_report: str):
        """
        Read csv memory report
        """
        mem_report_lines = self.read_csv_line_as_list(csv_report=csv_mem_report)

        # Check if csv file is empty
        if not mem_report_lines or len(mem_report_lines) <= 1:
            self.logger.warning("Memory CSV report is empty, returning empty data")
            return [], {}

        keys_with_idx = {key: idx for idx, key in enumerate(mem_report_lines[0][:-1])}

        return mem_report_lines, keys_with_idx


    def read_mem_bin_report(self, bin_mem_report: str):
        """
        Read binary memory report
        """
        hf = system_binary_reader.hf_mem_sample()
        samples_list = []
        with open(bin_mem_report, "rb") as file:
            while data := file.read(hf.get_pack_size()):
                try:
                    samples_list.append(hf.binary_to_dict(data))
                except ValueError as err:
                    self.logger.error(err)

        return samples_list


    def get_mem_profile(self, mem_report: str) -> int:
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

            _chosen_keys = ["timestamp", "MemTotal", "MemFree", "Buffers", "Cached",
                            "Slab", "SwapTotal", "SwapFree", "SwapCached"]

            self.logger.debug("Read Memory report..."); t0 = time.time()  # noqa: E702
            samples_list = self.read_mem_bin_report(bin_mem_report=mem_report)
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            if not samples_list or len(samples_list) == 0:
                self.logger.error("Memory binary report is empty or unreadable.")
                return False

            self.logger.debug("Create Memory profile..."); t0 = time.time()  # noqa: E702

            try:
                hf = system_binary_reader.hf_mem_sample()
                memory_dict_ = {key: [] for key, _, enabled in hf.field_definitions if enabled}
                for data in samples_list:
                    for key in memory_dict_:
                        if key in data:
                            memory_dict_[key].append(data[key])
                        else:
                            self.logger.warning(f"Key '{key}' missing in memory sample, appending 0.")
                            memory_dict_[key].append(0)
                if "timestamp" not in memory_dict_ or len(memory_dict_["timestamp"]) == 0:
                    self.logger.error("No timestamp data found in memory report.")
                    return False
            except Exception as e:
                self.logger.error(f"Failed to process memory samples: {e}")
                return False

            try:
                self.mem_prof = {key: np.array(values, dtype=np.float64) for key, values in memory_dict_.items()}
                self.mem_stamps = [np.float64(timestamp) / 1e9 for timestamp in memory_dict_["timestamp"]]
            except Exception as e:
                self.logger.error(f"Failed to convert memory data to numpy arrays: {e}")
                return False

            try:
                with open(mem_pkl, "wb") as _pf:
                    pickle.dump(self.mem_prof, _pf)
                with open(ts_pkl, "wb") as _pf:
                    pickle.dump(self.mem_stamps, _pf)
            except Exception as e:
                self.logger.error(f"Failed to save memory profile pickle files: {e}")
                return False

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def plot_memory_usage(self, annotate_with_cmds=None) -> float:
        """
        Plot memory/swap usage
        """
        if not self.mem_profile_valid:
            self.logger.warning("Memory profile data not available, will not be plotted.")
            return False

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

        plt.ylabel("Memory (GiB)")
        plt.legend(loc=1)
        plt.grid()

        if annotate_with_cmds:
            annotate_with_cmds(ymax=total_max)

        return total_max

    def read_csv_line_as_list(self, csv_report: str) -> list:
        """
        Read csv report as list

        Args:
            csv_report  (str)   CSV report filename

        Returns:
            (list)  read csv report as list, empty list if file is empty or invalid
        """
        if os.path.isfile(csv_report):
            # Check if file is empty
            if os.path.getsize(csv_report) == 0:
                self.logger.warning(f"Report {csv_report} is empty! -> Returning empty list")
                return []

            with open(csv_report, newline="") as csvfile:
                csv_lines = list(csv.reader(csvfile))
                if not csv_lines:
                    self.logger.warning(f"Report {csv_report} contains no valid CSV data! -> Returning empty list")
                    return []
                return csv_lines

        else:
            self.logger.error(f"Report {csv_report} does not exist! -> Remove the associated flag to this report")
            sys.exit(1)


    def read_binary_samples(self, file_path: str, sampler_type: system_binary_reader.generic_sample):
        samples_list = []
        sampler = sampler_type()
        with open(file_path, "rb") as file:
            while data := file.read(sampler.get_pack_size()):
                try:
                    sample = sampler.binary_to_dict(data)
                    samples_list.append(sample)
                except ValueError:
                    self.logger.error(
                        f"invalid binary sample read, size was {len(data)} and {sampler.get_pack_size()} was expected."
                    )
        return samples_list


