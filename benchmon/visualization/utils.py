"""Visualization utils"""

import glob
from datetime import datetime

import json
from dateutil.parser import parse

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates.date2num as date2num


def read_ical_log_file(traces_repo: str) -> dict:
    """
    Read ical log file

    Args:
        traces_repo (str)   Traces repository

    Returns:
        (dict)  Major stages with start time stamps
    """
    ical_log_file = glob.glob(f"{traces_repo}/wflow-selfcal.*.log")[0]
    with open(ical_log_file, "r") as _file:
        ical_log_content = _file.readlines()

    stage_lines = []
    for line in ical_log_content:
        if "run_pipeline::" in line:
            stage_lines += [line]
    major_stages = {}
    other_stages = {}
    fmt = "%Y-%m-%dT%H:%M:%S.%f"
    for line in stage_lines:
        entry = line.split(" ")[6].replace("\n", "")
        ts_fmt = f"{line.split(' ')[0]}T{line.split(' ')[1]}"
        ts = datetime.strptime(ts_fmt, fmt).timestamp()
        entry_key = entry  # f"{entry[:4]}{entry[-1]}"
        if any(stage in entry for stage in ("calibrate", "predict", "image")):
            try:
                major_stages[entry_key][line.split(" ")[5]] = ts
            except KeyError:
                major_stages[entry_key] = {}
                major_stages[entry_key][line.split(" ")[5]] = ts
        else:
            # major_stages[" ".join(line.split(" ")[5:]).replace("\n", "")] = {}
            # major_stages[" ".join(line.split(" ")[5:]).replace("\n", "")]["Start"] = ts
            major_stages[""] = {}
            major_stages[""]["Start"] = ts
            other_stages[" ".join(line.split(" ")[5:]).replace("\n", "")] = ts

    return major_stages


def plot_ical_stages(major_stages: dict, ymax=100.0) -> None:
    """
    Plot ical stages

    Args:
        major_stages    (dict)  ical major stages dictionary
        ymax            (float) max value for y-axis
    """

    def margin(stage):
        if "cali" in stage:
            return 0  # noqa: E701 (@hc)
        elif "pred" in stage:
            return 1  # noqa: E701 (@hc)
        elif "imag" in stage:
            return 2  # noqa: E701 (@hc)
        else:
            return 3  # noqa: E701 (@hc)

    for stage in major_stages:
        ydash = np.linspace(-ymax * 0.1, ymax * 1.1)

        plt.plot(
            major_stages[stage]["Start"] * np.ones_like(ydash),
            ydash,
            "k--",
            linewidth=0.75,
        )

        plt.text(
            major_stages[stage]["Start"],
            ymax * (1.1 - 0.04 * margin(stage)),
            stage,
            va="baseline",
            ha="left",
            size="x-small",
            weight="semibold",
        )


def datetime_object_hook(json_dict):
    for key, value in json_dict.items():
        if isinstance(value, str):
            try:
                # Attempt to parse the string as a datetime object
                json_dict[key] = parse(value)
            except ValueError:
                # If parsing fails, it's not a datetime string, so keep it as is
                pass
    return json_dict


def plot_stage_boxes(stage_file, ymax=100.0) -> None:
    """
    Plot stages with boxes for each stage that has been stored in the json file.

    Args:
        stage+file (path) stages dictionary, including "Start" and "End" times for each stage.
        ymax       (float) max value for y-axis
    """

    with open(stage_file, "r") as file_in:
        stages = json.load(file_in, object_hook=datetime_object_hook)

    for stage in stages:
        start_time = stages[stage]["Start"]
        end_time = stages[stage]["End"]

        # Draw a filled rectangle that spans the whole y-axis extent
        plt.axvspan(
            xmin=date2num(start_time),
            xmax=date2num(end_time),
            ymin=-ymax * 0.1,
            ymax=ymax * 1.1,
            alpha=0.2,
            color="gray",
            edgecolor=(1, 1, 1, 1),
        )

        # Add stage label
        plt.text(
            end_time - start_time,
            ymax,
            f"{stage}",
            va="baseline",
            ha="center",
            size="x-small",
            weight="semibold",
        )
