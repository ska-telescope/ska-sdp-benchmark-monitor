"""Visualization utils"""
import os
import csv
import glob
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# Colors used for the stages
STAGE_COLOR_PALETTE = [
    "#875692",  # strong purple
    "#F38400",  # vivid orange
    "#A1CAF1",  # very light blue
    "#BE0032",  # vivid red
    "#008856",  # vivid green
    "#E68FAC",  # strong purplish pink
    "#0067A5",  # strong blue
    "#F99379",  # strong yellowish pink
    "#604E97",  # strong violet
    "#F6A600",  # vivid orange yellow
    "#B3446C",  # strong purplish red
    "#882D17",  # strong reddish brown
    "#8DB600",  # vivid yellow green
    "#654522",  # deep yellowish brown
    "#E25822",  # vivid reddish orange
    "#2B3D26",  # dark olive green
    "#848482",  # medium gray
    "#C2B280",  # grayish yellow
    "#4A90D9",  # muted blue
    "#F3C300",  # vivid yellow
]


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


def read_annotation_csv(traces_repo: str, filename: str = "annotations.csv", node_name: str = None):
    """
    Read the annotation CSV and return the stages (start/stop).

    Args:
        traces_repo (str): Folder containing the CSV
        filename    (str): CSV name or absolute path
        node_name   (str): Keep only this node

    Returns:
        list[dict]: [{"label": "PIPELINE/STAGE", "start": float, "stop": float}, ...]
    """
    # Absolute path or relative to traces_repo
    if os.path.isabs(filename) or os.path.exists(filename):
        csv_path = filename
    else:
        csv_path = os.path.join(traces_repo, filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Annotation CSV not found: {csv_path}")

    # {label: {"START": ts, "FINISHED": ts} }
    stages_tmp = {}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            row_node = row.get("node", "").strip()

            # skip other node
            if node_name is not None and row_node != node_name:
                continue

            pipeline = row.get("pipeline", "").strip()
            stage = row.get("stage", "").strip()
            event = row.get("event", "").strip().upper()
            ts = float(row["timestamp"])

            # label pipeline / stage
            label = f"{pipeline}/{stage}"

            if label not in stages_tmp:
                stages_tmp[label] = {}

            # Save timestamp of this event
            stages_tmp[label][event] = ts

    # Keep complete stage only
    stages = [
        {"label": label, "start": events["START"], "stop": events["FINISHED"]}
        for label, events in stages_tmp.items()
        if "START" in events and "FINISHED" in events
    ]

    # Sort by start time
    stages.sort(key=lambda s: s["start"])

    return stages


def add_stage_legend(ax):
    """Add a START/FINISHED legend."""
    start_line = mlines.Line2D([], [], color='black', linestyle=(0, (4, 3)), label='START')
    stop_marker = mlines.Line2D([], [], color='black', marker='+', linestyle='None', markersize=10, label='FINISHED')

    ax.legend(handles=[start_line, stop_marker], loc='upper right', fontsize=9)


def plot_stage_timeline(stages, ax, xlim=None):
    """Draw each stage as a horizontal segment with its label."""
    if ax is None:
        ax = plt.gca()
    if not stages:
        return

    # y positions in axes coordinates (0 to 1)
    y_base = 0.2
    y_step = 0.6 / max(len(stages), 1)
    cap_height = 0.03

    for i, stage in enumerate(stages):
        # Color by stage index
        color = get_stage_color(i)
        y = y_base + i * y_step

        start = stage["start"]
        stop = stage["stop"]

        # stage segment
        ax.hlines(y=y, xmin=start, xmax=stop, linewidth=1.6, color=color,
                  transform=ax.get_xaxis_transform())

        # start cap
        ax.axvline(x=start, ymin=y - cap_height, ymax=y + cap_height,
                   linewidth=1.6, color=color)

        # stop cap
        ax.axvline(x=stop, ymin=y - cap_height, ymax=y + cap_height,
                   linewidth=1.6, color=color)

        # label
        ax.text(
            (start + stop) / 2,
            y + cap_height * 1.5,
            stage["label"],
            ha="center", va="bottom",
            fontsize=8, fontweight="bold",
            color=color,
            transform=ax.get_xaxis_transform(),
        )

    ax.set_yticks([])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Pipeline events", fontsize=9)

    if xlim:
        ax.set_xlim(xlim)


def get_stage_color(index: int) -> str:
    """Return the stage color for an index"""
    return STAGE_COLOR_PALETTE[index % len(STAGE_COLOR_PALETTE)]


def _draw_boundary(ax, x, color, linewidth, alpha, linestyle,
                   as_markers=False, marker='+', marker_size=40, n_markers=25):
    """Draw a vertical line or markers at x"""
    if as_markers:
        y_pos = np.linspace(0.02, 0.98, n_markers)
        ax.scatter(
            [x] * n_markers, y_pos,
            marker=marker,
            s=marker_size,
            color=color,
            alpha=alpha,
            zorder=20,
            transform=ax.get_xaxis_transform(),
        )
    else:
        ax.axvline(x=x, color=color, linestyle=linestyle,
                   linewidth=linewidth, alpha=alpha, zorder=20)


def plot_stage_markers(
    stages,
    ax_top,
    ax_bottom,
    xlim=None,
    *,
    label_to_index=None,
    color_map=None,               # color per (hostname, label), multi-node
    linewidth=1.6,                # line thickness
    alpha=0.9,                    # transparency
    linestyle_start=(0, (4, 3)),  # START line style
    linestyle_stop=(0, (4, 3)),   # STOP line style
    stop_as_markers=False,        # STOP drawn as markers instead of a line
    stop_marker='+',              # marker symbol
    stop_marker_size=40,          # marker size
    n_stop_markers=25,            # number of markers
    show_legend=False,            # show START/STOP legend
    legend_loc="upper right",     # legend position
):
    """Draw  START/STOP markers for each stage on the top and bottom axes."""
    if not stages or ax_top is None or ax_bottom is None:
        return

    fig = ax_top.get_figure()
    idx_top = fig.axes.index(ax_top)
    idx_bot = fig.axes.index(ax_bottom)
    axes_range = fig.axes[idx_top:idx_bot + 1]

    for i, stage in enumerate(stages):
        # color
        hostname = stage.get("_hostname")
        if color_map is not None and hostname is not None:
            color = get_stage_color(color_map.get((hostname, stage["label"]), i))
        elif label_to_index is not None:
            color = get_stage_color(label_to_index.get(stage["label"], i))
        else:
            color = get_stage_color(i)

        for ax in axes_range:
            # START line
            _draw_boundary(ax, stage["start"], color, linewidth, alpha,
                           linestyle_start, as_markers=False)
            # STOP line or markers
            _draw_boundary(ax, stage["stop"], color, linewidth, alpha,
                           linestyle_stop, as_markers=stop_as_markers,
                           marker=stop_marker, marker_size=stop_marker_size,
                           n_markers=n_stop_markers)

    #  optional legend
    if show_legend:
        start_handle = mlines.Line2D(
            [], [], color='gray', linestyle=linestyle_start,
            linewidth=linewidth, label='START'
        )
        if stop_as_markers:
            stop_handle = mlines.Line2D(
                [], [], color='gray', marker=stop_marker,
                linestyle='None', markersize=8, label='STOP'
            )
        else:
            stop_handle = mlines.Line2D(
                [], [], color='gray', linestyle=linestyle_stop,
                linewidth=linewidth, label='STOP'
            )
        ax_top.legend(handles=[start_handle, stop_handle],
                      loc=legend_loc, fontsize=8)

    if xlim:
        for ax in axes_range:
            ax.set_xlim(xlim)
