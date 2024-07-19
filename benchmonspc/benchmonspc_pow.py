import csv
import os
from datetime import datetime
import time
import numpy as np
import matplotlib.pyplot as plt

class PerfPowerData:
    """
    Perf power database
    """
    def __init__(self, csv_filename: str):
        """
        Constructor

        Args:
            csv_filename (str): csv filename
        """
        self.csv_filename = csv_filename
        self.csv_list = []

        self.events = []
        self.cpus = []
        self.prof = {}

        self._stamps = np.array([])

        self.read_csv_list()
        self.create_profile()
        self.create_plt_params()


    def read_csv_list(self) -> int:
        """
        Read csv list
        """
        with open(self.csv_filename, newline="", encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)
            for row in reader:
                self.csv_list.append(row)
        return 0


    def create_profile(self) -> int:
        """
        Create power profiles
        """
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

        return 0


    def create_plt_params(self) -> int:
        """
        Create plot parameters
        """
        header_date = os.popen(f"head -n 1 {self.csv_filename}").read()[13:-1]
        header_date_obj = datetime.strptime(header_date, "%a %b %d %H:%M:%S %Y")
        epoch0 = float(header_date_obj.strftime("%s"))

        self._stamps = np.zeros(self.nstamps)
        for i in range(self.nstamps):
            self._stamps[i] = epoch0 + self.prof["time"][i]

        self._plt_xrange = 5

        return 0


    def plot_events_per_cpu(self) -> int:
        """
        Plot power events per cpu
        """
        for event in self.events:
            for cpu in self.cpus:
                plt.plot(self._stamps, self.prof[cpu][event], label=f"{cpu}/{self.events_table[event]}")
        plt.xlabel("Time (s)")
        plt.xticks(self._xticks[0], self._xticks[1])
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

        return 0


    def plot_events(self, xticks: list = [], xlim: list = []) -> int:
        """
        Plots total power events

        Args:
            xticks (list): x-axis ticks of current plot
            xlim (list): x-axis limit of current plot
        """
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

        if xticks:
            plt.xticks(xticks[0], xticks[1])
        if xlim:
            plt.xlim(xlim)

        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

        return 0
