#!/usr/bin/env python3

import os
import logging
import pickle
import time
import matplotlib.pyplot as plt

CMAPS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'] * 10 # @hc
MARKERS = ["|", "s", ".", ">", "+", ",", "x", "*", "v", "^", "o", "<"] * 10 # @hc
DEBUG = False

class PerfCallRawData:
    """
    Perf callsatck raw data
    """
    def __init__(self, logger: logging.Logger, filename: str):
        """
        Constructor of RawData

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
        with open(self.filename, "r") as file:
            content = file.readlines()

        return content


    def read_blocks(self) -> list:
        """
        Read data blocks from raw data
        """
        content = self.load_data()

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
        self.logger.debug("Read PerfCall txt report + blocks..."); t0 = time.time()
        blocks = self.read_blocks()
        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        self.logger.debug("Create PerfCall samples..."); t0 = time.time()
        samples = []
        for block in blocks:
            if len(block) == 0: continue        # @hc avoid empty line
            if "cycles" not in block[0] and block[0][-1] == "\n": continue   # @hc avoid line starting with kind of Warning:\n
            sample_info = block[0].split()

            # Hard-coded exceptions
            if ":Reg" in sample_info[1]: continue # @hc
            try: float(sample_info[1]) # @hc Avoid second element not being a float
            except ValueError: continue
            if any(line[0] != "\t" for line in block[1:]): continue
            if len(sample_info) != 6:
                self.logger.debug(f"{sample_info = } skipped!")
                continue

            sample = {
                "cmd": sample_info[0],
                "cpu": sample_info[2],
                "timestamp": float(sample_info[3].split(":")[0]),
                "cycles": sample_info[4],
                "callstack":
                    [
                        {
                            "depth": di,
                            "addr": depth.split()[0],
                            "call": depth.split()[1],
                            "path": depth.split()[2]
                        }
                        for di, depth in enumerate(block[:0:-1])
                    ]
                }

            try: # Sometimes, the pid is not provided is ("pid/tid")
                sample["tid"] = int(sample_info[1].split("/")[1])
                sample["pid"] = int(sample_info[1].split("/")[0])
            except IndexError:
                sample["tid"] = int(sample_info[1])

            samples.append(sample)
        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return samples


    def cmds_list(self) -> tuple:
        """
        Get samples and commands
        """
        samples_pkl = f"{os.path.dirname(self.filename)}/pkl_dir/call_samples.pkl"
        cmds_pkl = f"{os.path.dirname(self.filename)}/pkl_dir/call_cmds.pkl"

        if os.access(samples_pkl, os.R_OK) and os.access(cmds_pkl, os.R_OK):
            self.logger.debug("Load PerfCall samples + PerfCall commands list..."); t0 = time.time()

            with open(samples_pkl, "rb") as _pf: samples = pickle.load(_pf)
            with open(cmds_pkl, "rb") as _pf: cmds = pickle.load(_pf)

        else:

            samples = self.create_samples()
            with open(samples_pkl, "wb") as _pf: pickle.dump(samples, _pf)


            self.logger.debug("Get PerfCall command list..."); t0 = time.time()

            cmds = {}
            for sample in samples:
                cmd = sample["cmd"]
                try:
                    cmds[cmd] += 1
                except KeyError:
                    cmds[cmd] = 1
            cmds = {ky: val for ky, val in sorted(cmds.items(), key = lambda item: -item[1])}

            with open(cmds_pkl, "wb") as _pf: pickle.dump(cmds, _pf)

        list_filename = f"{os.path.realpath(os.path.dirname(self.filename))}/list_recorded_perf_cmds.txt"
        with open(list_filename, "w") as _file:
            for cmd in cmds.keys():
                _file.write(f"{cmd}: {cmds[cmd]} samples\n")
        self.logger.debug(f"List of recorded commands with perf: {list_filename}")

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return samples, cmds


class PerfCallData():
    """
    Per callstack data with cmd
    """
    def __init__(self, logger: logging.Logger, cmd: str, samples: list, m2r: float, traces_repo: str):
        """
        Constructor

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
        self._plt_legend_threshold = 0.01 # @pars
        self._plt_depth_size = 2/3

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
            self.logger.debug(f"Load PerfCall samples for command = {self.cmd} ..."); t0 = time.time()

            with open(cmd_samples, "rb") as _pf: self.samples = pickle.load(_pf)
            with open(cmd_tids, "rb") as _pf: self.tids = pickle.load(_pf)

        else:

            self.logger.debug("Construct PerfCall command samples..."); t0 = time.time()

            self.samples = []
            pids = []
            tids = []
            timestamps = []
            for sample in samples:
                if sample["cmd"] == self.cmd:
                    self.samples += [{
                        # "pid": sample["pid"],
                        "tid": sample["tid"],
                        "timestamp": sample["timestamp"],
                        "cycles": sample["cycles"],
                        "callstack": sample["callstack"],
                        "ncalls": len(sample["callstack"])
                        }]
                    # pids += [sample["pid"]]
                    tids += [sample["tid"]]
                    timestamps += [sample["timestamp"]]

            # self.pids = {pid: rel_pid for rel_pid, pid in enumerate(set(pids))} # @hc
            self.tids = {tid: rel_tid for rel_tid, tid in enumerate(set(tids))}

            with open(cmd_samples, "wb") as _pf: pickle.dump(self.samples, _pf)
            with open(cmd_tids, "wb") as _pf: pickle.dump(self.tids, _pf)

        self.nt = len(self.tids)
        self.nsamples = len(self.samples)

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0


    def _depth_data(self, depth: int) -> dict:
        """
        Get callstack data from given depth

        Args:
            depth (int): Depth value
        """
        if DEBUG: print("\tCount calls...")

        t0 = time.time()
        calls = {}
        for sample in self.samples:
            if sample["ncalls"] > depth:
                name = sample["callstack"][depth]["call"].split("+")[0]
                try:
                    calls[name] += 1
                except KeyError:
                    calls[name] = 1

        if DEBUG: print(f"\t...{round(time.time() - t0, 3)} s\n")

        return calls


    def plot(self, depths: list, xticks: list = [], xlim: list = [], legend_ncol: int = 4) -> int:
        """
        Plot callstack

        Args:
            depths (list): List of given depths
            xticks (list): x-axis ticks
            xlim (list): x-axis limits
            legend_ncol (int): Number of columns for call legend
        """
        for depth in depths:
            if DEBUG: print(f"Plot {depth} of {depths}...")
            t0 = time.time()

            calls = self._depth_data(depth)
            colors = {call: CMAPS[color % len(CMAPS)] for color, call in enumerate(calls)}

            # Initialize call_line
            call_line = {}
            for sample in self.samples:
                if sample["ncalls"] > depth:
                    call = sample["callstack"][depth]["call"].split("+")[0]
                    call_line[call] = {"stamps": [], "sample_vals": [], "color": ""}

            for sample in self.samples:
                if sample["ncalls"] > depth:
                    call = sample["callstack"][depth]["call"].split("+")[0]
                    color = colors[call]
                    tid = self.tids[sample["tid"]]
                    stamp = sample["timestamp"] + self.mono_to_real_time

                    call_line[call]["stamps"] += [stamp]
                    call_line[call]["sample_vals"] += [depth + self._plt_depth_size / self.nt * tid]
                    call_line[call]["color"] = color

            for call in call_line.keys():
                plot, = plt.plot(
                    call_line[call]["stamps"],
                    call_line[call]["sample_vals"],
                    linestyle = "",
                    marker = MARKERS[depth],
                    color = call_line[call]["color"]
                    )
                if calls[call] / self.nsamples > self._plt_legend_threshold:
                    plot.set_label(f"{depth}: {call}")

            if DEBUG: print(f"...{round(time.time() - t0, 3)} s\n")

        # Y axis options
        plt.ylim([min(depths) - 1/4 - 1/8 * len(depths), max(depths) + 1 + 1/4 * len(depths)])
        yvals = []
        ylabels = []

        # Threads ticks
        for depth in depths:
            for tid in range(self.nt):
                ylabels += [""] #[f"{tid}"]
                if tid == 0: ylabels[-1] = f"CallStack {depth}" #+ ylabels[-1]
                yvals += [depth + self._plt_depth_size / self.nt * tid]

        # Without threads ticks
        if False:
            ylabels = [f"CallStack {depth}" for depth in depths]
            yvals = [depth for depth in depths]

        plt.yticks(yvals, ylabels)

        # X axis options
        if xticks:
            plt.xticks(xticks[0], xticks[1])

        if xlim:
            plt.xlim(xlim)

        # Legend
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys(), loc="upper center", ncol=legend_ncol, fontsize="6")

        # Global plot
        plt.grid()
        plt.title(self.cmd)

        return 0
