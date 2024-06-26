import csv
import os
from datetime import datetime
import time
import numpy as np
import matplotlib.pyplot as plt

class PerfPowerData:
    def __init__(self, csv_filename: str) -> None:
        self.csv_filename = csv_filename
        self.csv_list = []

        self.events = []
        self.cpus = []
        self.prof = {}

        self._stamps = np.array([])

        self.read_csv_list()
        self.create_profile()
        self.create_plt_params()


    def read_csv_list(self) -> None:
        # Read the csv list
        with open(self.csv_filename, newline="", encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)
            for row in reader:
                self.csv_list.append(row)


    def create_profile(self) -> None:
        EVENT_INDEX = 4
        self.events = list(set([item[EVENT_INDEX] for item in self.csv_list[1:]]))
        nevents = len(self.events)

        CPU_INDEX = 1
        self.cpus = list(set([item[CPU_INDEX] for item in self.csv_list[1:]]))
        ncpu = len(self.cpus)

        self.events_table = {
            "power/energy-cores/": "cores",
            "power/energy-ram/": "dram",
            "power/energy-pkg/": "cpu-pkg",
            "power/energy-psys/": "psys",
            "power/energy-gpu/": "gpu"
            }

        stride = ncpu * nevents
        self.prof["time"] = [float(self.csv_list[i][0]) for i in range(1, len(self.csv_list), stride)]
        self.nstamps = len(self.prof["time"])

        for cpu in self.cpus:
            for event in self.events:
                self.prof[cpu] = {event: [] for event in self.events}

        for _list in self.csv_list[1:]:
            cpu = _list[1]
            event = _list[4]
            value = float(_list[2]) / (float(_list[5]) * 1e-9) # J = W/S
            self.prof[cpu][event] += [value]

        for cpu in self.cpus:
            for event in self.events:
                self.prof[cpu][event] = np.array(self.prof[cpu][event])


    def create_plt_params(self):
        header_date = os.popen(f"head -n 1 {self.csv_filename}").read()[13:-1]
        header_date_obj = datetime.strptime(header_date, "%a %b %d %H:%M:%S %Y")
        epoch0 = float(header_date_obj.strftime("%s"))

        self._stamps = np.zeros(self.nstamps)
        for i in range(self.nstamps):
            self._stamps[i] = epoch0 + self.prof["time"][i]

        self._plt_xrange = 5
        # xstride = self.nstamps // self._plt_xrange

        # val0 = self._stamps[0]
        # vallst = self._stamps[xstride: self.nstamps-xstride+1: xstride]
        # valf = self._stamps[-1]
        # xticks_val = [val0] + vallst.tolist() + [valf]

        # t0 = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[0]))
        # tlst = np.round(self._stamps[xstride: self.nstamps-xstride+1: xstride] - self._stamps[0], 2)
        # tf = time.strftime("%b-%d\n%H:%M:%S", time.localtime(self._stamps[-1]))
        # xticks_label = [t0] + tlst.tolist() + [tf]

        # self._xticks = (xticks_val, xticks_label)


    def plot_events_per_cpu(self):
        for event in self.events:
            for cpu in self.cpus:
                plt.plot(self._stamps, self.prof[cpu][event], label=f"{cpu}/{self.events_table[event]}")
        plt.xlabel("Time (s)")
        plt.xticks(self._xticks[0], self._xticks[1])
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

    def plot_events(self, xticks, xlim):
        pow_total = {event: 0 for event in self.events}
        for cpu in self.cpus:
            for event in self.events:
                pow_total[event] += self.prof[cpu][event]

        alpha = 0.4
        event = "power/energy-cores/"
        if event in self.events:
            plt.fill_between(self._stamps, 0, pow_total[event], color="C4", alpha=alpha)
            plt.plot(self._stamps, pow_total[event], color="C4", ls="--", label=self.events_table[event])

        event = "power/energy-ram/"
        if event in self.events:
            plt.fill_between(self._stamps, 0, pow_total[event], color="C1", alpha=alpha)
            plt.plot(self._stamps, pow_total[event], color="C1", ls="-.", label=self.events_table[event])

        event = "power/energy-pkg/"
        if event in self.events:
            plt.plot(self._stamps, pow_total[event], label=self.events_table[event], color="k")

        event = "power/energy-psys/"
        if event in self.events:
            plt.plot(self._stamps, pow_total[event], label=self.events_table[event], color="b")

        plt.xlabel("Time (s)")
        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()
