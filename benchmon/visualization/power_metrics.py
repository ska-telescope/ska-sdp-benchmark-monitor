import csv
import logging
import json
import time
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

def compute_total_energy(time_stamps: list, power_stamps: list) -> float:
    """
    Compute the total energy (Wh), based on the trapezoid rule.
    """
    energy = 0
    for idx in range(len(time_stamps) - 1):
        energy += 0.5 * (power_stamps[idx + 1] + power_stamps[idx]) * (time_stamps[idx + 1] - time_stamps[idx]) / 3600

    return energy


class PerfPowerData:
    """
    Perf power database
    """
    def __init__(self, logger: logging.Logger, csv_filename: str):
        """
        Constructor

        Args:
            csv_filename    (str)               csv filename
            logger          (logging.Logger)    logging object
        """
        self.logger = logger
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
        self.logger.debug("Read PerfPower csv report..."); t0 = time.time()

        with open(self.csv_filename, newline="", encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)
            for row in reader:
                self.csv_list.append(row)

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0


    def create_profile(self) -> int:
        """
        Create power profiles
        """
        self.logger.debug("Create PerfPower profile..."); t0 = time.time()

        LINES_START_INDEX = 2

        EVENT_INDEX = 4
        self.events = list(set([item[EVENT_INDEX] for item in self.csv_list[LINES_START_INDEX:]]))
        nevents = len(self.events)

        CPU_INDEX = 1
        self.cpus = list(set([item[CPU_INDEX] for item in self.csv_list[LINES_START_INDEX:]]))
        ncpu = len(self.cpus)

        self.events_table = {
            "power/energy-cores/": "cores",
            "power/energy-ram/": "dram",
            "power/energy-pkg/": "cpu-pkg",
            "power/energy-psys/": "psys",
            "power/energy-gpu/": "gpu"
            }

        stride = ncpu * nevents
        self.prof["time"] = [float(self.csv_list[i][0]) for i in range(LINES_START_INDEX, len(self.csv_list), stride)]
        self.nstamps = len(self.prof["time"])

        for cpu in self.cpus:
            for event in self.events:
                self.prof[cpu] = {event: [] for event in self.events}

        for _list in self.csv_list[LINES_START_INDEX:]:
            cpu = _list[1]
            event = _list[4]
            value = float(_list[2]) / (float(_list[5]) * 1e-9) # J = W/S
            self.prof[cpu][event] += [value]

        for cpu in self.cpus:
            for event in self.events:
                self.prof[cpu][event] = np.array(self.prof[cpu][event])

        self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0


    def create_plt_params(self) -> int:
        """
        Create plot parameters
        """
        with open(self.csv_filename) as file:
            epoch0 = float(file.readline()[2:-1])

        self._stamps = np.zeros(self.nstamps+1)
        self._stamps[0] = epoch0
        for i in range(0, self.nstamps):
            self._stamps[i+1] = epoch0 + self.prof["time"][i]
        return 0


    def plot_events_per_cpu(self) -> int:
        """
        Plot power events per cpu
        """
        for event in self.events:
            for cpu in self.cpus:
                plt.plot(self._stamps, self.prof[cpu][event], label=f"{cpu}/{self.events_table[event]}")
        plt.xticks(self._xticks[0], self._xticks[1])
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

        return 0


    def plot_events(self, pre_label: str = "") -> float:
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

        events_style = {}
        events_style["power/energy-cores/"] = {"color": "C4", "ls": "--"}
        events_style["power/energy-ram/"] = {"color": "C1", "ls": "-."}
        events_style["power/energy-pkg/"] = {"color": "k", "ls": "-"}
        events_style["power/energy-psys/"] = {"color": "b", "ls": "-"}
        ymax = 0

        for event in self.events:
            power_array = np.append(pow_total[event], pow_total[event][-1])
            energy = compute_total_energy(time_stamps=self._stamps, power_stamps=power_array)
            plt.step(self._stamps, power_array, where="post",
                     label=f"{pre_label}{self.events_table[event]} ({round(energy, 1)} Wh)",
                     color=events_style[event]["color"],
                     ls=events_style[event]["ls"])
            ymax = max(ymax, max(power_array))

        return ymax


class G5KPowerData:
    """
    Grid5000 power database
    """
    def __init__(self, traces_dir: str):
        """
        Constructor
        """
        self.traces_dir = traces_dir
        self.g5k_pow_prof = {}
        self.get_g5k_pow_prof()


    def read_json_file(self, report_filename):
        """
        Read json report
        """
        with open (f"{self.traces_dir}/{report_filename}", "r") as jsfile:
            return json.load(jsfile)


    def get_g5k_pow_prof(self):
        """
        Get G5K power profile

        Example:
            In : g5k_pow_list[0]
            Out:
                {'timestamp': '2025-02-02T14:39:37.003778+01:00',
                'device_id': 'taurus-11',
                'metric_id': 'wattmetre_power_watt',
                'value': 69.4,
                'labels': {'_device_orig': ['wattmetre1-port33']}}
        """
        metrics = ["wattmetre_power_watt", "bmc_node_power_watt"]

        for metric in metrics:
            g5k_pow_list = self.read_json_file(f"g5k_pow_report_{metric}.json")
            nstamps = len(g5k_pow_list)

            self.g5k_pow_prof[metric] = {
            "timestamps": np.zeros(nstamps),
            "value": np.zeros(nstamps)
            }

            fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
            for idx, item in enumerate(g5k_pow_list):
                ts = item["timestamp"]
                if ts[19] != ".":
                    ts = ts[:19] + ".0" + ts[19:]

                self.g5k_pow_prof[metric]["timestamps"][idx] = datetime.strptime(ts, fmt).timestamp()
                self.g5k_pow_prof[metric]["value"][idx] = item["value"]


    def plot_g5k_pow_profiles(self, pre_label: str = "") -> float:
        """
        Plots total power events

        Args:
            xticks (list): x-axis ticks of current plot
            xlim (list): x-axis limit of current plot
        """
        _ymax = 0
        metrics = ["wattmetre_power_watt", "bmc_node_power_watt"]

        metrics_style = {}
        metrics_style["wattmetre_power_watt"] = {
            "ls": "-",
            "color": "C2",
            "marker": ".",
            "label": "g5k:wm"
        }
        metrics_style["bmc_node_power_watt"] = {
            "ls": "-",
            "marker": ".",
            "color": "C9",
            "label": "g5k:bmc"
        }

        for metric in metrics:
            ts = self.g5k_pow_prof[metric]["timestamps"]
            vals = self.g5k_pow_prof[metric]["value"]
            energy = compute_total_energy(time_stamps=ts, power_stamps=vals)
            plt.plot(ts, vals,
                     color=metrics_style[metric]["color"],
                     ls=metrics_style[metric]["ls"],
                     marker=metrics_style[metric]["marker"],
                     label=f"{pre_label}{metrics_style[metric]['label']} ({round(energy,1)} Wh)")
            if len(vals) > 1: _ymax = max(_ymax, max(vals))

        return _ymax
