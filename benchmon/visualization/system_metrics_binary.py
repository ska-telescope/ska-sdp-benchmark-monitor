
class SystemDataBinary:
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
                 bin_disk_report: str):

        if bin_cpufreq_report:
            self.ncpu_freq = 0
            self.cpufreq_prof = {}
            self.cpufreq_vals = {}
            self.cpufreq_stamps = np.array([])
            self.cpufreq_min = None
            self.cpufreq_max = None
            self.cpufreq_profile_valid = self.get_cpufreq_prof(bin_cpufreq_report=bin_cpufreq_report)

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
            self.net_profile_valid = self.get_net_prof(bin_net_report=bin_net_report)

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
            self.disk_profile_valid = self.get_disk_prof(bin_disk_report=bin_disk_report)

        self.xticks = None
        self.xlim = None
        self.yrange = None

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

    def read_cpufreq_bin_report(self, bin_cpufreq_report: str):
        hf = system_binary_reader.hf_cpufreq_sample()
        samples_list = []
        try:
            file = open(bin_cpufreq_report, "rb")
            min_cpufreq = np.uint64(int.from_bytes(file.read(8), byteorder='little', signed=False))
            max_cpufreq = np.uint64(int.from_bytes(file.read(8), byteorder='little', signed=False))
            while data := file.read(hf.get_pack_size()):
                try:
                    samples_list.append(hf.binary_to_dict(data))
                except ValueError as err:
                    logger.error(err)
        except FileNotFoundError:
            self.logger.error("CPU frequency binary report not found.")
            return 0, 0, samples_list
        return min_cpufreq, max_cpufreq, samples_list

    def get_cpufreq_prof(self, bin_cpufreq_report: str) -> bool:
        """
        Read cpu frequency report
        Get profile
        """
        cpufreq_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_prof.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_stamps.pkl"
        freqvals_pkl = f"{self.traces_repo}/pkl_dir/cpufreq_vals.pkl"

        try:
            if os.access(cpufreq_pkl, os.R_OK) and os.access(ts_pkl, os.R_OK) and os.access(freqvals_pkl, os.R_OK):
                self.logger.debug("Load CPU frequency profile..."); t0 = time.time()  # noqa: E702

                try:
                    with open(cpufreq_pkl, "rb") as _pf:
                        self.cpufreq_prof = pickle.load(_pf)
                    with open(ts_pkl, "rb") as _pf:
                        self.cpufreq_stamps = pickle.load(_pf)
                    with open(freqvals_pkl, "rb") as _pf:
                        self.cpufreq_vals = pickle.load(_pf)
                except Exception as e:
                    self.logger.error(f"Failed to load cpufreq pickle files: {e}")
                    return False

                if not self.cpufreq_prof or not self.cpufreq_stamps or not self.cpufreq_vals:
                    self.logger.error("Loaded cpufreq data is empty or invalid.")
                    return False

                self.cpufreq_min = self.cpufreq_vals.get("min", None)
                self.cpufreq_max = self.cpufreq_vals.get("max", None)
                self.ncpu_freq = len(self.cpufreq_prof)

                self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")
                return True

            else:
                self.logger.debug("Read CPUFreq report..."); t0 = time.time()  # noqa: E702
                cpufreq_min, cpufreq_max, samples_list = \
                    self.read_cpufreq_bin_report(bin_cpufreq_report=bin_cpufreq_report)
                self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

                if not samples_list:
                    self.logger.error("Unable to read CPUfreq report.")
                    return False

                self.logger.debug("Create CPUFreq profile..."); t0 = time.time()  # noqa: E702
                self.cpufreq_min = cpufreq_min or None
                self.cpufreq_max = cpufreq_max or None

                self.logger.warning("Dont plot cpu frequencies (dont use --cpu-freq) on virtual machines")

                self.ncpu_freq = 0
                try:
                    ts_0 = samples_list[0]["timestamp"]
                    ts = ts_0
                    line_idx = 0
                    while ts == ts_0:
                        line_idx += 1
                        ts = samples_list[line_idx]["timestamp"]
                        self.ncpu_freq += 1
                except Exception as e:
                    self.logger.error(f"Error determining number of CPU frequencies: {e}")
                    return False

                if self.ncpu_freq == 0:
                    self.logger.error("No CPU frequency data found.")
                    return False

                cpufreq_ts = []
                for cpu_nb in range(self.ncpu_freq):
                    cpufreq_ts.append([])

                # Read lines
                try:
                    for data in samples_list:
                        cpufreq_ts[data["cpu"]].append(data["frequency"])
                except Exception as e:
                    self.logger.error(f"Error processing CPU frequency samples: {e}")
                    return False

                HZ_UNIT = 1e6  # noqa: N806
                try:
                    for cpu_nb in range(self.ncpu_freq):
                        cpufreq_ts[cpu_nb] = np.array(cpufreq_ts[cpu_nb]) / HZ_UNIT
                except Exception as e:
                    self.logger.error(f"Error converting CPU frequency units: {e}")
                    return False

                self.cpufreq_prof = cpufreq_ts
                try:
                    self.cpufreq_stamps = [float(data["timestamp"] / 1e9) for data in samples_list[0::self.ncpu_freq]]
                except Exception as e:
                    self.logger.error(f"Error extracting CPU frequency timestamps: {e}")
                    return False

                try:
                    self.cpufreq_vals["mean"] = np.zeros_like(self.cpufreq_stamps)
                    for cpu in range(self.ncpu_freq):
                        self.cpufreq_vals["mean"] += self.cpufreq_prof[cpu] / self.ncpu_freq
                    self.cpufreq_vals["min"] = self.cpufreq_min
                    self.cpufreq_vals["max"] = self.cpufreq_max
                except Exception as e:
                    self.logger.error(f"Error calculating CPU frequency mean/min/max: {e}")
                    return False

                try:
                    with open(cpufreq_pkl, "wb") as _pf:
                        pickle.dump(self.cpufreq_prof, _pf)
                    with open(ts_pkl, "wb") as _pf:
                        pickle.dump(self.cpufreq_stamps, _pf)
                    with open(freqvals_pkl, "wb") as _pf:
                        pickle.dump(self.cpufreq_vals, _pf)
                except Exception as e:
                    self.logger.error(f"Error saving CPU frequency profiles: {e}")
                    return False

                self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")
                return True

        except Exception as e:
            self.logger.error(f"Exception in get_cpufreq_prof: {e}")
            return False

    def plot_cpufreq(self, cores_in: str = "", cores_out: str = "", annotate_with_cmds=None) -> float:
        """
        Plot cpu frequency per core
        """
        if not self.cpufreq_profile_valid:
            self.logger.warning("CPU frequency profile data not available, will not be plotted.")
            return False

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

        if not self.cpufreq_vals:
            self.logger.error("No CPU frequency data found.")
            return

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

    def get_net_prof(self, bin_net_report: str) -> bool:
        """
        Get network profile
        """
        net_pkl = f"{self.traces_repo}/pkl_dir/net_prof.pkl"
        dat_pkl = f"{self.traces_repo}/pkl_dir/net_data.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/net_stamps.pkl"

        try:
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
                        self.net_data[key][metric_key] = (
                            net_ts_raw[key][metric_key][-1]
                            - net_ts_raw[key][metric_key][0]
                        )
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
        except Exception as e:
            self.logger.error(f"Exception in get_net_prof: {e}")
            return False

        return True

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
        if not self.net_profile_valid:
            self.logger.warning("Network profile data not available, will not be plotted.")
            return False

        BYTES_UNIT = 1000**2  # noqa: N806  (MB)
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
        device_names = {}
        with open(bin_disk_report, "rb") as file:
            n_sector_sizes = np.frombuffer(file.read(4), dtype=np.uint32)[0]
            sector_sizes = {}

            for i in range(n_sector_sizes):
                name_size = np.frombuffer(file.read(4), dtype=np.uint32)[0]
                name = file.read(name_size)
                device_names[i] = name
                blocksize = np.frombuffer(file.read(4), dtype=np.uint32)[0]
                sector_sizes[name] = blocksize

            while data := file.read(disk_sampler.get_pack_size()):
                try:
                    sample = disk_sampler.binary_to_dict(data)
                except ValueError as err:
                    logger.error(err)
                sample["device_name"] = device_names[sample["device_id"]]
                samples_list.append(sample)

        self.disk_field_keys = [key for key, _, enabled in disk_sampler.field_definitions
                                if enabled and key not in ["timestamp", "major", "minor", "device_id"]]

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
                if key not in ["timestamp", "device_name", "major", "minor", "device_id"]:
                    disk_ts_raw[sample["device_name"]][key].append(float(value))

        # raw time stamps
        timestamps_raw = [float(sample["timestamp"]) / 1e9 for sample in samples_list[::ndisk_blk]]

        return disk_ts_raw, timestamps_raw

    def get_disk_prof(self, bin_disk_report: str) -> bool:
        """
        Get disk profile
        """
        disk_pkl = f"{self.traces_repo}/pkl_dir/disk_prof.pkl"
        dat_pkl = f"{self.traces_repo}/pkl_dir/disk_data.pkl"
        maj_pkl = f"{self.traces_repo}/pkl_dir/disk_maj.pkl"
        ts_pkl = f"{self.traces_repo}/pkl_dir/disk_stamps.pkl"

        try:
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
                nstamps = len(timestamps_raw) - 1
                self.disk_stamps = np.zeros(nstamps)
                for stamp in range(nstamps):
                    self.disk_stamps[stamp] = (timestamps_raw[stamp + 1] + timestamps_raw[stamp]) / 2

                self.disk_prof = {}
                self.disk_data = {}
                for blk in self.disk_blks:
                    self.disk_prof[blk] = {key: np.zeros(nstamps) for key in self.disk_field_keys}
                    self.disk_data[blk] = {key: -999.999 for key in self.disk_field_keys}

                for blk in self.disk_blks:
                    self.disk_prof[blk]["major"] = disk_ts_raw[blk]["major"]
                    self.disk_prof[blk]["minor"] = disk_ts_raw[blk]["minor"]

                BYTES_UNIT = 1000**2
                fields = ["sect-rd", "sect-wr", "sect-disc"]
                for blk in self.disk_blks:
                    # Find the matching sector size key for blk
                    matching_keys = [item for item in self.maj_blks_sects if item in blk]
                    if not matching_keys:
                        self.logger.error(f"No matching sector size found for block {blk}")
                        continue
                    bytes_by_sector = self.maj_blks_sects[matching_keys[0]]
                    for field in fields:
                        for stamp in range(nstamps):
                            self.disk_prof[blk][field][stamp] = (
                                (disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp])
                                / (timestamps_raw[stamp + 1] - timestamps_raw[stamp]) * bytes_by_sector / BYTES_UNIT
                            )
                        self.disk_data[blk][field] = int(
                            (disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0]) * bytes_by_sector / BYTES_UNIT
                        )

                op_fields = ["#rd-cd", "#rd-md", "#wr-cd", "#wr-md", "#io-ip", "#disc-cd", "#disc-md", "#flush-req"]
                for blk in self.disk_blks:
                    for field in op_fields:
                        for stamp in range(nstamps):
                            self.disk_prof[blk][field][stamp] = (
                                disk_ts_raw[blk][field][stamp + 1] - disk_ts_raw[blk][field][stamp]
                            ) / (timestamps_raw[stamp + 1] - timestamps_raw[stamp])
                        self.disk_data[blk][field] = int(disk_ts_raw[blk][field][-1] - disk_ts_raw[blk][field][0])

                with open(disk_pkl, "wb") as _pf:
                    pickle.dump(self.disk_prof, _pf)
                with open(dat_pkl, "wb") as _pf:
                    pickle.dump(self.disk_data, _pf)
                with open(maj_pkl, "wb") as _pf:
                    pickle.dump(self.maj_blks_sects, _pf)
                with open(ts_pkl, "wb") as _pf:
                    pickle.dump(self.disk_stamps, _pf)

                self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")
        except Exception as e:
            self.logger.error(f"Exception in get_disk_prof: {e}")
            return False

        return True

    def plot_disk(self,
                  is_rd_only=False,
                  is_wr_only=False,
                  is_with_iops=False,
                  is_diskdata_label=True,
                  annotate_with_cmds=None) -> float:
        """
        Plot disk activity
        """
        if not self.disk_profile_valid:
            self.logger.warning("Disk profile data not available, will not be plotted.")
            return False

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
