#!/usr/bin/env python3

import time
import matplotlib.pyplot as plt

cmaps = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'] * 10 # @hc

class PerfCallRawData:
    def __init__(self, filename):
        self.filename = filename

    def load_data(self):
        print("Load file...")
        t0 = time.time()
        with open(self.filename, "r") as file:
            content = file.readlines()
        print(f"...{round(time.time() - t0, 3)} s\n")
        return content

    def read_blocks(self):
        content = self.load_data()
        print("Read blocks...")
        t0 = time.time()
        blocks = []
        _block_lines = []
        for line in content:
            if line[0] == "\n" or line == content[-1]:
                blocks.append(_block_lines)
                _block_lines = []
                continue
            _block_lines.append(line)
        print(f"...{round(time.time() - t0, 3)} s\n")
        return blocks


    def create_samples(self):
        blocks = self.read_blocks()
        print("Create samples...")
        t0 = time.time()
        samples = []
        for block in blocks:
            if len(block) == 0: continue
            sample_info = block[0].split()
            if ":Reg" in sample_info[1]: continue # @hc

            sample = {
                "cmd": sample_info[0],
                "cpu": sample_info[2],
                "timestamp": float(sample_info[3].split(":")[0]),
                "cycles": sample_info[4],
                "callstack":
                    [ {"depth": di, "addr": depth.split()[0], "call": depth.split()[1], "path": depth.split()[2]} for di, depth in enumerate(block[:0:-1])]
                }
            try: # Sometimes, the pid is not provided is ("pid/tid")
                sample["tid"] = int(sample_info[1].split("/")[1])
                sample["pid"] = int(sample_info[1].split("/")[0])
            except IndexError:
                sample["tid"] = int(sample_info[1])

            samples.append(sample)
        nsamples = len(samples)
        print(f"...{round(time.time() - t0, 3)} s\n")
        return samples


    def cmds_list(self):
        #%% List commands
        samples = self.create_samples()
        print("List commands...")
        t0 = time.time()
        cmds = {}
        for sample in samples:
            cmd = sample["cmd"]
            try:
                cmds[cmd] += 1
            except KeyError:
                cmds[cmd] = 1
        cmds = {ky: val for ky, val in sorted(cmds.items(), key = lambda item: -item[1])}
        print(f"...{round(time.time() - t0, 3)} s\n")
        return samples, cmds

class PerfCallData():
    def __init__(self, cmd: str, samples: str, m2r: float) -> None:
        self.cmd = cmd
        self.mono_to_real_time = m2r
        self._plt_legend_threshold = 0.01 # @pars
        self._plt_depth_size = 2/3

        self._construct(samples)

    def _construct(self, samples: list) -> None:
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

        # self.pids = {pid: rel_pid for rel_pid, pid in enumerate(set(pids))}
        self.tids = {tid: rel_tid for rel_tid, tid in enumerate(set(tids))}
        self.nt = len(self.tids)
        self.nsamples = len(self.samples)

    def _depth_data(self, depth: int) -> dict:
        print("\tCount calls...")
        t0 = time.time()
        calls = {}
        for sample in self.samples:
            if sample["ncalls"] > depth:
                name = sample["callstack"][depth]["call"].split("+")[0]
                try:
                    calls[name] += 1
                except KeyError:
                    calls[name] = 1
        print(f"\t...{round(time.time() - t0, 3)} s\n")
        return calls


    def plot(self, depths: list, xticks: list, xlim: list, legend_ncol: int = 8) -> None:
        # # fig = plt.figure(figsize=(20, len(depths) * 2))
        # fig = plt.figure(figsize=(19.2, len(depths) * 2))
        for depth in depths:
            print(f"Plot {depth} of {depths}...")
            t0 = time.time()
            calls = self._depth_data(depth)
            colors = {call: cmaps[color % len(cmaps)] for color, call in enumerate(calls)}
            for sample in self.samples:
                if sample["ncalls"] > depth:
                    call = sample["callstack"][depth]["call"].split("+")[0]
                    color = colors[call]
                    tid = self.tids[sample["tid"]]
                    stamp = sample["timestamp"] + self.mono_to_real_time

                    plot, = plt.plot(
                        stamp,
                        depth + self._plt_depth_size / self.nt * tid, #@hc
                        marker = "|",
                        color = color
                        )

                    if calls[call] / self.nsamples > self._plt_legend_threshold:
                        plot.set_label(f"{depth}: {call}")
            print(f"...{round(time.time() - t0, 3)} s\n")

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
        # # Without threads ticks
        # ylabels = [f"CallStack {depth}" for depth in depths]
        # yvals = [depth for depth in depths]
        plt.yticks(yvals, ylabels)
        plt.xlabel("Time (s)")

        # @db
        # X axis options
        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)

        # Legend
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys(), loc="upper center", ncol=legend_ncol, fontsize="6")
        plt.tight_layout()

        # Global plot
        plt.grid()
        plt.tight_layout()
        # plt.title(self.cmd)
