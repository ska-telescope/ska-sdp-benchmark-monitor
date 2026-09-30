"""Module to process perf record data"""

import os
import logging
import pickle
import time

import matplotlib.pyplot as plt

CMAPS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'] * 10  # noqa: E501 (@hc)
MARKERS = ["|", "s", ".", ">", "+", ",", "x", "*", "v", "^", "o", "<"] * 10  # @hc
DEBUG = False


class PerfCallRawData:
    """
    Perf callsatck raw data
    """

    def __init__(self, logger: logging.Logger, filename: str):
        """
        Construct RawData class

        Args:
            logger      (logging.Logger)    Logging object
            filename    (str)               Data filename
        """
        self.logger = logger
        self.filename = filename


    def load_data(self) -> list:
        """
        Load raw data
        """
        if not os.path.isfile(self.filename):
            self.logger.warning(f"File does not exist: {self.filename}")
            return []

        if os.path.getsize(self.filename) == 0:
            self.logger.warning(f"File is empty: {self.filename}")
            return []

        with open(self.filename, "r") as file:
            content = file.readlines()

        if not content:
            self.logger.warning(f"No content read from file: {self.filename}")
            return []

        return content


    def read_blocks(self) -> list:
        """
        Read data blocks from raw data
        """
        content = self.load_data()

        if not content:
            self.logger.warning("No content available to read blocks")
            return []

        blocks = []
        _block_lines = []
        for line in content:
            if line[0] == "\n" or line == content[-1]:
                blocks.append(_block_lines)
                _block_lines = []
                continue
            _block_lines.append(line)

        return blocks


    def create_samples(self) -> list:
        """
        Create data samples
        """
        self.logger.debug("Read PerfCall txt report + blocks..."); t0 = time.time()  # noqa: E702
        blocks = self.read_blocks()
        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        if not blocks:
            self.logger.warning("No blocks available to create samples")
            return []

        self.logger.debug("Create PerfCall samples..."); t0 = time.time()  # noqa: E702
        samples = []
        for block in blocks:
            if len(block) == 0:
                continue  # @hc avoid empty line

            if "cycles" not in block[0] and block[0][-1] == "\n":
                continue  # @hc avoid line starting with kind of Warning:\n

            sample_info = block[0].split()

            # Check if we have enough information
            if len(sample_info) < 2:
                self.logger.debug(f"Insufficient sample info: {sample_info}")
                continue

            # Hard-coded exceptions
            if ":Reg" in sample_info[1]:
                continue  # @hc

            try:
                float(sample_info[1])
            except (ValueError, IndexError):
                continue  # @hc Avoid second element not being a float

            if len(block) > 1 and any(line[0] != "\t" for line in block[1:]):
                continue

            if len(sample_info) != 6:
                self.logger.debug(f"{sample_info=} skipped!")
                continue

            try:
                sample = {
                    "cmd": sample_info[0],
                    "cpu": sample_info[2],
                    "timestamp": float(sample_info[3].split(":")[0]),
                    "cycles": sample_info[4],
                    "callstack":
                        [
                            {
                                "depth": di,
                                "addr": depth.split()[0] if len(depth.split()) > 0 else "",
                                "call": depth.split()[1] if len(depth.split()) > 1 else "",
                                "path": depth.split()[2] if len(depth.split()) > 2 else ""
                            }
                            for di, depth in enumerate(block[:0:-1])
                        ]  # noqa: E123
                }

                try:  # Sometimes, the pid is not provided is ("pid/tid")
                    sample["tid"] = int(sample_info[1].split("/")[1])
                    sample["pid"] = int(sample_info[1].split("/")[0])
                except (IndexError, ValueError):
                    try:
                        sample["tid"] = int(sample_info[1])
                    except (ValueError, IndexError):
                        self.logger.debug(f"Invalid tid in sample_info: {sample_info}")
                        continue

                samples.append(sample)
            except (IndexError, ValueError) as e:
                self.logger.debug(f"Error processing sample block: {e}")
                continue

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return samples


    def cmds_list(self) -> tuple:
        """
        Get samples and commands
        """
        samples_pkl = f"{os.path.dirname(self.filename)}/pkl_dir/call_samples.pkl"
        cmds_pkl = f"{os.path.dirname(self.filename)}/pkl_dir/call_cmds.pkl"

        if os.access(samples_pkl, os.R_OK) and os.access(cmds_pkl, os.R_OK):
            self.logger.debug("Load PerfCall samples + PerfCall commands list..."); t0 = time.time()  # noqa: E702

            try:
                with open(samples_pkl, "rb") as _pf:
                    samples = pickle.load(_pf)
                with open(cmds_pkl, "rb") as _pf:
                    cmds = pickle.load(_pf)

                # Validate loaded data
                if not samples or not cmds:
                    self.logger.warning("Loaded pickle data is empty, recreating...")
                    raise ValueError("Empty pickle data")

            except (pickle.PickleError, EOFError, ValueError) as e:
                self.logger.warning(f"Error loading pickle files: {e}, recreating...")
                samples = self.create_samples()
                if not samples:
                    self.logger.warning("No samples created from raw data")
                    return [], {}

                os.makedirs(os.path.dirname(samples_pkl), exist_ok=True)
                with open(samples_pkl, "wb") as _pf:
                    pickle.dump(samples, _pf)

                self.logger.debug("Get PerfCall command list..."); t0 = time.time()  # noqa: E702

                cmds = {}
                for sample in samples:
                    cmd = sample["cmd"]
                    try:
                        cmds[cmd] += 1
                    except KeyError:
                        cmds[cmd] = 1
                cmds = {ky: val for ky, val in sorted(cmds.items(), key=lambda item: -item[1])}

                with open(cmds_pkl, "wb") as _pf:
                    pickle.dump(cmds, _pf)

        else:

            samples = self.create_samples()
            if not samples:
                self.logger.warning("No samples created from raw data")
                return [], {}

            os.makedirs(os.path.dirname(samples_pkl), exist_ok=True)
            with open(samples_pkl, "wb") as _pf:
                pickle.dump(samples, _pf)


            self.logger.debug("Get PerfCall command list..."); t0 = time.time()  # noqa: E702

            cmds = {}
            for sample in samples:
                cmd = sample["cmd"]
                try:
                    cmds[cmd] += 1
                except KeyError:
                    cmds[cmd] = 1
            cmds = {ky: val for ky, val in sorted(cmds.items(), key=lambda item: -item[1])}

            with open(cmds_pkl, "wb") as _pf:
                pickle.dump(cmds, _pf)

        list_filename = f"{os.path.realpath(os.path.dirname(self.filename))}/list_recorded_perf_cmds.txt"
        with open(list_filename, "w") as _file:
            for cmd in cmds.keys():
                _file.write(f"{cmd}: {cmds[cmd]} samples\n")
        self.logger.debug(f"List of recorded commands with perf: {list_filename}")

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return samples, cmds


class PerfCallData:
    """
    Per callstack data with cmd
    """

    def __init__(self, logger: logging.Logger, cmd: str, samples: list, m2r: float, traces_repo: str):
        """
        Construct PerfCallData class for a given command

        Args:
            logger      (logging.Logger)    Logging object
            cmd         (str)               Recorded command
            samples     (list)              Samples of recorded command
            m2r         (int)               Delta monotonic time to real
            traces_repo (str)               Traces repository
        """
        self.logger = logger
        self.cmd = cmd
        self.mono_to_real_time = m2r
        self._plt_legend_threshold = 0.01  # @pars
        self._plt_depth_size = 2 / 3

        self.traces_repo = traces_repo

        self._construct(samples)


    def _construct(self, samples: list) -> int:
        """
        Constrcut samples for command

        Args:
            samples (list): Samples
        """
        cmd_samples = f"{self.traces_repo}/pkl_dir/call_{self.cmd}_samples.pkl"
        cmd_tids = f"{self.traces_repo}/pkl_dir/call_{self.cmd}_tids.pkl"

        if os.access(cmd_samples, os.R_OK) and os.access(cmd_tids, os.R_OK):
            self.logger.debug(f"Load PerfCall samples for command = {self.cmd} ..."); t0 = time.time()  # noqa: E702

            try:
                with open(cmd_samples, "rb") as _pf:
                    self.samples = pickle.load(_pf)
                with open(cmd_tids, "rb") as _pf:
                    self.tids = pickle.load(_pf)

                # Validate loaded data
                if not self.samples or not self.tids:
                    self.logger.warning(f"Loaded pickle data is empty for command {self.cmd}, recreating...")
                    raise ValueError("Empty pickle data")

            except (pickle.PickleError, EOFError, ValueError) as e:
                self.logger.warning(f"Error loading pickle files for command {self.cmd}: {e}, recreating...")
                self._construct_from_samples(samples, cmd_samples, cmd_tids)

        else:
            self._construct_from_samples(samples, cmd_samples, cmd_tids)

        self.nt = len(self.tids) if self.tids else 0
        self.nsamples = len(self.samples) if self.samples else 0

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def _construct_from_samples(self, samples: list, cmd_samples: str, cmd_tids: str):
        """
        Construct samples and tids from raw samples

        Args:
            samples (list): Raw samples
            cmd_samples (str): Path to save samples pickle
            cmd_tids (str): Path to save tids pickle
        """
        self.logger.debug("Construct PerfCall command samples...")

        self.samples = []
        pids = []  # noqa: F841
        tids = []
        timestamps = []

        if not samples:
            self.logger.warning(f"No samples provided for command {self.cmd}")
            self.tids = {}
            return

        for sample in samples:
            if sample["cmd"] == self.cmd:
                self.samples += [
                    {
                        # "pid": sample["pid"],
                        "tid": sample["tid"],
                        "timestamp": sample["timestamp"],
                        "cycles": sample["cycles"],
                        "callstack": sample["callstack"],
                        "ncalls": len(sample["callstack"]),
                    }
                ]
                # pids += [sample["pid"]]
                tids += [sample["tid"]]
                timestamps += [sample["timestamp"]]

        # self.pids = {pid: rel_pid for rel_pid, pid in enumerate(set(pids))} # @hc
        self.tids = {tid: rel_tid for rel_tid, tid in enumerate(set(tids))}

        try:
            os.makedirs(os.path.dirname(cmd_samples), exist_ok=True)
            with open(cmd_samples, "wb") as _pf:
                pickle.dump(self.samples, _pf)
            with open(cmd_tids, "wb") as _pf:
                pickle.dump(self.tids, _pf)
        except (IOError, OSError) as e:
            self.logger.warning(f"Could not save pickle files for command {self.cmd}: {e}")


    def _depth_data(self, depth: int) -> dict:
        """
        Get callstack data from given depth

        Args:
            depth (int): Depth value
        """
        calls = {}

        if not self.samples:
            self.logger.warning(f"No samples available for depth data at depth {depth}")
            return calls

        for sample in self.samples:
            if sample["ncalls"] > depth:
                try:
                    # Check if callstack has enough depth and call field exists
                    if (len(sample["callstack"]) > depth
                            and "call" in sample["callstack"][depth]
                            and sample["callstack"][depth]["call"]):
                        name = sample["callstack"][depth]["call"].split("+")[0]
                        try:
                            calls[name] += 1
                        except KeyError:
                            calls[name] = 1
                    else:
                        self.logger.debug(f"Invalid callstack at depth {depth} for sample")
                except (IndexError, KeyError, TypeError) as e:
                    self.logger.debug(f"Error accessing callstack at depth {depth}: {e}")
                    continue

        return calls


    def plot(self, depths: list, xticks: list, xlim: list, legend_ncol: int = 4) -> int:
        """
        Plot callstack

        Args:
            depths (list): List of given depths
            xticks (list): x-axis ticks
            xlim (list): x-axis limits
            legend_ncol (int): Number of columns for call legend
        """
        # Check for empty or invalid input
        if not depths:
            self.logger.warning("No depths provided for plotting")
            return -1

        if not self.samples:
            self.logger.warning("No samples available for plotting")
            return -1

        if self.nsamples == 0:
            self.logger.warning("Number of samples is zero, cannot plot")
            return -1

        if not self.tids:
            self.logger.warning("No thread IDs available for plotting")
            return -1

        for depth in depths:
            calls = self._depth_data(depth)

            if not calls:
                self.logger.warning(f"No calls found at depth {depth}")
                continue

            colors = {call: CMAPS[color % len(CMAPS)] for color, call in enumerate(calls)}

            # Initialize call_line
            call_line = {}
            for sample in self.samples:
                if (sample["ncalls"] > depth
                        and len(sample["callstack"]) > depth
                        and "call" in sample["callstack"][depth]
                        and sample["callstack"][depth]["call"]):
                    try:
                        call = sample["callstack"][depth]["call"].split("+")[0]
                        call_line[call] = {"stamps": [], "sample_vals": [], "color": ""}
                    except (IndexError, KeyError, TypeError):
                        continue

            for sample in self.samples:
                if (sample["ncalls"] > depth
                        and len(sample["callstack"]) > depth
                        and "call" in sample["callstack"][depth]
                        and sample["callstack"][depth]["call"]):
                    try:
                        call = sample["callstack"][depth]["call"].split("+")[0]

                        if call not in colors:
                            continue

                        color = colors[call]

                        # Check if tid exists in our mapping
                        if sample["tid"] not in self.tids:
                            self.logger.debug(f"Unknown tid {sample['tid']} in sample")
                            continue

                        tid = self.tids[sample["tid"]]
                        stamp = sample["timestamp"] + self.mono_to_real_time

                        if call in call_line:
                            call_line[call]["stamps"] += [stamp]
                            call_line[call]["sample_vals"] += [depth + self._plt_depth_size / self.nt * tid]
                            call_line[call]["color"] = color
                    except (IndexError, KeyError, TypeError, ZeroDivisionError) as e:
                        self.logger.debug(f"Error processing sample at depth {depth}: {e}")
                        continue

            # Plot the data
            for call in call_line.keys():
                if (call_line[call]["stamps"]
                        and call_line[call]["sample_vals"]
                        and len(call_line[call]["stamps"]) == len(call_line[call]["sample_vals"])):
                    try:
                        plot, = plt.plot(
                            call_line[call]["stamps"],
                            call_line[call]["sample_vals"],
                            linestyle="",
                            marker=MARKERS[depth % len(MARKERS)],
                            color=call_line[call]["color"],
                        )

                        # Avoid division by zero
                        if call in calls and self.nsamples > 0:
                            if calls[call] / self.nsamples > self._plt_legend_threshold:
                                plot.set_label(f"{depth}: {call}")
                    except Exception as e:
                        self.logger.warning(f"Error plotting call {call} at depth {depth}: {e}")
                        continue

        # Only proceed with axis setup if we have valid depths
        if depths:
            try:
                # Y axis options
                plt.ylim([min(depths) - 1 / 4 - 1 / 8 * len(depths), max(depths) + 1 + 1 / 4 * len(depths)])
                yvals = []
                ylabels = []

                # Threads ticks
                for depth in depths:
                    for tid in range(self.nt):
                        ylabels += [""]  # [f"{tid}"]
                        if tid == 0:
                            ylabels[-1] = f"CallStack {depth}"  # + ylabels[-1]
                        if self.nt > 0:  # Avoid division by zero
                            yvals += [depth + self._plt_depth_size / self.nt * tid]

                # Without threads ticks
                if False:
                    ylabels = [f"CallStack {depth}" for depth in depths]
                    yvals = [depth for depth in depths]

                if yvals and ylabels:
                    plt.yticks(yvals, ylabels)

                # X axis options
                if xticks and len(xticks) >= 2:
                    plt.xticks(xticks[0], xticks[1])

                if xlim and len(xlim) >= 2:
                    plt.xlim(xlim)

                # Legend
                handles, labels = plt.gca().get_legend_handles_labels()
                if handles and labels:
                    by_label = dict(zip(labels, handles))
                    plt.legend(by_label.values(), by_label.keys(), loc="upper center", ncol=legend_ncol, fontsize="6")

                # Global plot
                plt.grid()
                plt.title(self.cmd)

            except Exception as e:
                self.logger.error(f"Error setting up plot axes: {e}")
                return -1

        return 0
