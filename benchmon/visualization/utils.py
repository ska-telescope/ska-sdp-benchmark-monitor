"""Visualization utils"""
import os
import csv
import glob
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

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


def plot_ical_stages(major_stages: dict, ymax=100.) -> None:
    """
    Plot ical stages

    Args:
        major_stages    (dict)  ical major stages dictionary
        ymax            (float) max value for y-axis
    """
    def margin(stage):
        if "cali" in stage: return 0    # noqa: E701 (@hc)
        elif "pred" in stage: return 1  # noqa: E701 (@hc)
        elif "imag" in stage: return 2  # noqa: E701 (@hc)
        else: return 3                  # noqa: E701 (@hc)

    for stage in major_stages:
        ydash = np.linspace(- ymax * .1, ymax * 1.1)

        plt.plot(major_stages[stage]["Start"] * np.ones_like(ydash),
                 ydash,
                 "k--",
                 linewidth=.75)

        plt.text(major_stages[stage]["Start"],
                 ymax * (1.1 - .04 * margin(stage)),
                 stage,
                 va="baseline",
                 ha="left",
                 size="x-small",
                 weight="semibold")

def read_annotation_csv(traces_repo: str, filename: str = "annotations.csv"):
    """
    Read annotation CSV and return a list of stage intervals.

    Output format:
    [
        {
            "label": "PIPELINE/STAGE",
            "start": float,
            "stop": float,
        },
        ...
    ]
    """

    # Support absolute or relative path
    if os.path.isabs(filename) or os.path.exists(filename):
        csv_path = filename
    else:
        csv_path = os.path.join(traces_repo, filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Annotation CSV not found: {csv_path}")

    # Temporary storage: { "PIPELINE/STAGE": {"START": ts, "STOP": ts} }
    stages_tmp = {}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            pipeline = row.get("pipeline", "").strip()
            stage = row.get("stage", "").strip()
            event = row.get("event", "").strip().upper()
            ts = float(row["timestamp"])

            label = f"{pipeline}/{stage}"

            if label not in stages_tmp:
                stages_tmp[label] = {}

            stages_tmp[label][event] = ts

    # Convert to ordered list
    stages = []
    for label, events in stages_tmp.items():
        if "START" in events and "FINISHED" in events:
            stages.append(
                {
                    "label": label,
                    "start": events["START"],
                    "stop": events["FINISHED"],
                }
            )

    # Sort by start time
    stages.sort(key=lambda s: s["start"])

    return stages


def add_stage_legend(ax):
    """
    Add a legend explaining the START/STOP markers.
    Should be called on the first subplot (pipeline events).
    """
    start_line = mlines.Line2D([], [], color='black', linestyle=(0, (4,3)), label='START')
    stop_marker = mlines.Line2D([], [], color='black', marker='+', linestyle='None', markersize=10, label='FINISHED')
    
    ax.legend(handles=[start_line, stop_marker], loc='upper right', fontsize=9)
def plot_stage_timeline(stages, ax, xlim=None):
    """
    Draw horizontal stage segments with start/stop caps and readable labels.
    """
    if ax is None:
        ax = plt.gca()
    if not stages:
        return

    ymin, ymax = ax.get_ylim()
    height = ymax - ymin

    y_base = ymin + 0.2 * height
    y_step = 0.3 * height

    colors = plt.cm.tab20.colors
    cap_height = 0.015 * height

    for i, stage in enumerate(stages):
        y = y_base + i * y_step
        color = get_stage_color(stage["label"], colors)

        start = stage["start"]
        stop = stage["stop"]

        # Main horizontal segment
        ax.hlines(
            y=y,
            xmin=start,
            xmax=stop,
            linewidth=1.6,
            color=color,
        )

        # Start cap
        ax.vlines(
            x=start,
            ymin=y - cap_height,
            ymax=y + cap_height,
            linewidth=1.6,
            color=color,
        )

        # Stop cap
        ax.vlines(
            x=stop,
            ymin=y - cap_height,
            ymax=y + cap_height,
            linewidth=1.6,
            color=color,
        )

        # Label
        ax.text(
            (start + stop) / 2,
            y + 1.5 * cap_height,
            stage["label"],
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color=color,
        )

    ax.set_yticks([])
    ax.set_ylabel("Pipeline events", fontsize=9)

    if xlim:
        ax.set_xlim(xlim)

def get_stage_color(label, palette=plt.cm.tab20.colors):
    """
    Return a consistent color for a given stage label.
    Uses a hash of the label to pick a color from the palette.
    """
    idx = abs(hash(label)) % len(palette)
    return palette[idx]


def plot_stage_markers(
    stages,
    ax_top,
    ax_bottom,
    xlim=None,
    *,
    linewidth=1.6,
    alpha=0.9,
    linestyle=(0, (4, 3)),
    n_markers=30,
):
    """
    Draw vertical stage START/STOP markers across ALL subplots,
    with dashed lines and star markers along the line.
    Each stage gets a consistent color based on its label.
    """
    if not stages or ax_top is None or ax_bottom is None:
        return

    # --- GLOBAL vertical span (all subplots)
    ymin_top, ymax_top = ax_top.get_ylim()
    ymin_bot, ymax_bot = ax_bottom.get_ylim()
    y_start = ymin_top
    y_stop = ymax_bot

    # y positions for star markers
    y_markers = np.linspace(y_start, y_stop, n_markers)

    EPS = 1e-6  # tiny temporal offset

    for stage in stages:
        color = get_stage_color(stage["label"])

        # ================= START =================
        x_start = stage["start"] - EPS
        plt.vlines(
            x=x_start,
            ymin=y_start,
            ymax=y_stop,
            colors=color,
            linestyles=linestyle,
            linewidth=linewidth,
            alpha=alpha,
            zorder=20,
        )
        plt.scatter(
            [x_start] * n_markers,
            y_markers,
            marker="",   # start: '.'
            s=5,
            color=color,
            alpha=alpha,
            zorder=25,
        )

        # ================= STOP =================
        x_stop = stage["stop"] + EPS
        plt.vlines(
            x=x_stop,
            ymin=y_start,
            ymax=y_stop,
            colors=color,
            linestyles=linestyle,
            linewidth=linewidth,
            alpha=alpha,
            zorder=20,
        )
        plt.scatter(
            [x_stop] * n_markers,
            y_markers,
            marker="+",  # stop: star
            s=15,
            color=color,
            alpha=alpha,
            zorder=25,
        )

    if xlim:
        ax_top.set_xlim(xlim)
        ax_bottom.set_xlim(xlim)