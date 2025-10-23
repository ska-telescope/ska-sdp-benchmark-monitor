"""Module to process power/energy data"""

import csv
import logging
import json
import os
import pickle
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np


def compute_total_energy(time_stamps: list, power_stamps: list) -> float:
    """
    Compute the total energy (Wh), based on the trapezoid rule.
    """
    # Handle empty data
    if len(time_stamps) < 2 or len(power_stamps) < 2:
        return 0.0
    # Ensure both lists have the same length
    min_length = min(len(time_stamps), len(power_stamps))

    if min_length < 2:
        return 0.0

    energy = 0
    for idx in range(min_length - 1):
        energy += 0.5 * (power_stamps[idx + 1] + power_stamps[idx]) * (time_stamps[idx + 1] - time_stamps[idx]) / 3600

    return energy


class PerfPowerData:
    """
    Perf power database
    """

    def __init__(self, logger: logging.Logger, csv_filename: str):
        """
        Construct PerfPowData object

        Args:
            csv_filename    (str)               csv filename
            logger          (logging.Logger)    logging object
        """
        self.logger = logger
        self.csv_filename = csv_filename
        self.csv_list = []

        self.cpus = []
        self.pow_prof = {}
        self.time_stamps = np.array([])

        self.events_table = {
            "power/energy-cores/": "cores",
            "power/energy-ram/": "dram",
            "power/energy-pkg/": "cpu-pkg",
            "power/energy-psys/": "psys",
            "power/energy-gpu/": "gpu"
        }

        self.create_profile()


    def read_csv_list(self) -> int:
        """
        Read csv list
        """
        # Check if file exists
        if not os.path.isfile(self.csv_filename):
            self.logger.error(f"CSV file {self.csv_filename} does not exist!")
            return -1

        # Check if file is empty
        if os.path.getsize(self.csv_filename) == 0:
            self.logger.warning(f"CSV file {self.csv_filename} is empty!")
            return -1

        with open(self.csv_filename, newline="", encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)  # Skip header

            for row in reader:
                self.csv_list.append(row)

            if not self.csv_list:
                self.logger.warning(f"CSV file {self.csv_filename} contains no valid data!")
                return -1

        return 0


    def create_profile(self) -> int:
        """
        Create power profiles
        """
        pow_pkl = f"{os.path.dirname(self.csv_filename)}/pkl_dir/pow_prof.pkl"
        ts_pkl = f"{os.path.dirname(self.csv_filename)}/pkl_dir/pow_stamps.pkl"

        pickle_loaded = False

        if os.access(pow_pkl, os.R_OK):
            try:
                self.logger.debug("Load Power profile..."); t0 = time.time()  # noqa: E702

                with open(pow_pkl, "rb") as _pf:
                    self.pow_prof = pickle.load(_pf)
                with open(ts_pkl, "rb") as _pf:
                    self.time_stamps = pickle.load(_pf)

                self.cpus = list(self.pow_prof.keys())
                if "time" in self.cpus:
                    self.cpus.remove("time")

                if self.cpus:
                    self.events = self.pow_prof[self.cpus[0]].keys()
                else:
                    self.events = []

                self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")
                pickle_loaded = True

            except (IOError, pickle.PickleError, KeyError) as e:
                self.logger.warning(f"Error loading pickle files: {e}, will recreate from CSV")

        if not pickle_loaded:
            self.logger.debug("Read PerfPower csv report..."); t0 = time.time()  # noqa: E702
            result = self.read_csv_list()
            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

            # Check if CSV reading failed
            if result != 0:
                self.logger.warning("Failed to read CSV data, creating empty profile")
                self._create_empty_profile()
                return 0

            # Check if csv_list has sufficient data
            LINES_START_INDEX = 2  # noqa: N806
            if len(self.csv_list) < LINES_START_INDEX:
                self.logger.warning("CSV file has insufficient data, creating empty profile")
                self._create_empty_profile()
                return 0

            self.logger.debug("Create PerfPower profile..."); t0 = time.time()  # noqa: E702

            EVENT_INDEX = 4  # noqa: N806
            self.events = list({item[EVENT_INDEX] for item in self.csv_list[LINES_START_INDEX:]})
            nevents = len(self.events)

            CPU_INDEX = 1  # noqa: N806
            self.cpus = list({item[CPU_INDEX] for item in self.csv_list[LINES_START_INDEX:]})
            ncpu = len(self.cpus)

            stride = ncpu * nevents
            self.pow_prof["time"] = [float(self.csv_list[i][0]) for i in range(LINES_START_INDEX,
                                                                               len(self.csv_list),
                                                                               stride)]
            self.nstamps = len(self.pow_prof["time"])

            for cpu in self.cpus:
                for event in self.events:
                    self.pow_prof[cpu] = {event: [] for event in self.events}

            for _list in self.csv_list[LINES_START_INDEX:]:
                cpu = _list[1]
                event = _list[4]
                value = float(_list[2]) / (float(_list[5]) * 1e-9)  # J = W/S
                self.pow_prof[cpu][event] += [value]

            for cpu in self.cpus:
                for event in self.events:
                    self.pow_prof[cpu][event] = np.array(self.pow_prof[cpu][event])

            # Time stamps
            with open(self.csv_filename) as file:
                first_line = file.readline()
                if len(first_line) < 3:
                    self.logger.warning("CSV file has invalid timestamp format, using default")
                    epoch0 = 0.0
                else:
                    epoch0 = float(first_line[2:-1])

            self.time_stamps = np.zeros(self.nstamps + 1)
            self.time_stamps[0] = epoch0
            for i in range(0, self.nstamps):
                self.time_stamps[i + 1] = epoch0 + self.pow_prof["time"][i]

            with open(pow_pkl, "wb") as _pf:
                pickle.dump(self.pow_prof, _pf)
            with open(ts_pkl, "wb") as _pf:
                pickle.dump(self.time_stamps, _pf)

            self.logger.debug(f"...Done ({round(time.time() - t0, 3)} s)")

        return 0

    def _create_empty_profile(self):
        """
        Create empty profile when CSV data is not available
        """
        self.cpus = []
        self.events = []
        self.pow_prof = {"time": []}
        self.time_stamps = np.array([])
        self.nstamps = 0

    def plot_events_per_cpu(self) -> int:
        """
        Plot power events per cpu
        """
        # Check if data is available
        if not self.events or not self.cpus:
            self.logger.warning("No power data available for plotting")
            return 0

        for event in self.events:
            for cpu in self.cpus:
                plt.plot(self.time_stamps, self.pow_prof[cpu][event], label=f"{cpu}/{self.events_table[event]}")
        plt.xticks(self._xticks[0], self._xticks[1])
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

        return 0


    def plot_events(self, pre_label: str = "") -> float:
        """
        Plot total power events

        Args:
            xticks (list): x-axis ticks of current plot
            xlim (list): x-axis limit of current plot
        """
        # Check if data is available
        if not self.events or not self.cpus:
            self.logger.warning("No power data available for plotting")
            return 0.0

        pow_total = {event: 0 for event in self.events}  # noqa: C420
        for cpu in self.cpus:
            for event in self.events:
                pow_total[event] += self.pow_prof[cpu][event]

        events_style = {}
        events_style["power/energy-cores/"] = {"color": "C4", "ls": "--"}
        events_style["power/energy-ram/"] = {"color": "C1", "ls": "-."}
        events_style["power/energy-pkg/"] = {"color": "k", "ls": "-"}
        events_style["power/energy-psys/"] = {"color": "b", "ls": "-"}
        events_style["power/energy-gpu/"] = {"color": "g", "ls": ":"}
        ymax = 0

        for event in self.events:
            if len(pow_total[event]) > 0:
                power_array = np.append(pow_total[event], pow_total[event][-1])
                energy = compute_total_energy(time_stamps=self.time_stamps, power_stamps=power_array)
                plt.step(self.time_stamps, power_array, where="post",
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
        Construct Grid5000 power database
        """
        self.traces_dir = traces_dir
        self.g5k_pow_prof = {}
        self.get_g5k_pow_prof()


    def read_json_file(self, report_filename):
        """
        Read json report
        """
        file_path = f"{self.traces_dir}/{report_filename}"

        # Check if file exists
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"JSON file {file_path} does not exist")

        # Check if file is empty
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"JSON file {file_path} is empty")

        with open(file_path, "r") as jsfile:
            data = json.load(jsfile)
            if not data:
                raise ValueError(f"JSON file {file_path} contains no data")
            return data


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

            self.g5k_pow_prof[metric] = {"timestamps": np.zeros(nstamps),
                                         "value": np.zeros(nstamps)}

            fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
            for idx, item in enumerate(g5k_pow_list):
                ts = item["timestamp"]
                if ts[19] != ".":
                    ts = ts[:19] + ".0" + ts[19:]

                self.g5k_pow_prof[metric]["timestamps"][idx] = datetime.strptime(ts, fmt).timestamp()
                self.g5k_pow_prof[metric]["value"][idx] = item["value"]


    def plot_g5k_pow_profiles(self, pre_label: str = "") -> float:
        """
        Plot total power events

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

            # Skip empty data
            if len(ts) == 0 or len(vals) == 0:
                continue

            energy = compute_total_energy(time_stamps=ts, power_stamps=vals)
            plt.plot(ts, vals,
                     color=metrics_style[metric]["color"],
                     ls=metrics_style[metric]["ls"],
                     marker=metrics_style[metric]["marker"],
                     label=f"{pre_label}{metrics_style[metric]['label']} ({round(energy, 1)} Wh)")

            if len(vals) > 1:
                _ymax = max(_ymax, max(vals))

        return _ymax
