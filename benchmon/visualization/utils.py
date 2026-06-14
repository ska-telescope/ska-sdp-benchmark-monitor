"""Visualization utils"""
import os
import csv
import glob
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# ─────────────────────────────────────────────────────────────────────────────
# Stage color palette — Kelly's 20 colors of maximum contrast.
# Ordered so that consecutive entries are perceptually as different as possible:
# stage N and stage N+1 will never share a similar color.
# If the number of stages exceeds the palette size, colors cycle from index 0.
# ─────────────────────────────────────────────────────────────────────────────
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
    Read annotation CSV and return a list of stage intervals.

    Each row in the CSV must have: timestamp, pipeline, stage, event, node, ...
    Only rows matching node_name are kept (multi-node filtering).
    Only stages that have BOTH a START and a FINISHED event are included.
    If a stage label appears multiple times, the last occurrence is used.

    Output format:
    [
        {"label": "PIPELINE/STAGE", "start": float, "stop": float},
        ...
    ]

    Args:
        traces_repo (str)           : Directory containing the CSV file (or parent)
        filename    (str)           : CSV filename or absolute path
        node_name   (str, optional) : Node hostname to filter on

    Returns:
        list[dict]: Sorted list of stage intervals
    """
    # Support absolute path or path relative to traces_repo
    if os.path.isabs(filename) or os.path.exists(filename):
        csv_path = filename
    else:
        csv_path = os.path.join(traces_repo, filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Annotation CSV not found: {csv_path}")

    # Temporary storage: { "PIPELINE/STAGE": {"START": ts, "FINISHED": ts} }
    stages_tmp = {}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            row_node = row.get("node", "").strip()

            # Multi-node filtering: skip rows that do not belong to this node
            if node_name is not None and row_node != node_name:
                continue

            pipeline = row.get("pipeline", "").strip()
            stage    = row.get("stage",    "").strip()
            event    = row.get("event",    "").strip().upper()
            ts       = float(row["timestamp"])

            # Build a unique label combining pipeline and stage names
            label = f"{pipeline}/{stage}"

            if label not in stages_tmp:
                stages_tmp[label] = {}

            # Store the timestamp for this event type (START or FINISHED)
            stages_tmp[label][event] = ts

    # Keep only stages that have both a START and a FINISHED timestamp
    stages = [
        {"label": label, "start": events["START"], "stop": events["FINISHED"]}
        for label, events in stages_tmp.items()
        if "START" in events and "FINISHED" in events
    ]

    # Sort chronologically by start time
    stages.sort(key=lambda s: s["start"])

    return stages


def add_stage_legend(ax):
    """
    Add a legend explaining the START/STOP markers.
    Should be called on the first subplot (pipeline events).
    """
    start_line = mlines.Line2D([], [], color='black', linestyle=(0, (4, 3)), label='START')
    stop_marker = mlines.Line2D([], [], color='black', marker='+', linestyle='None', markersize=10, label='FINISHED')

    ax.legend(handles=[start_line, stop_marker], loc='upper right', fontsize=9)


def plot_stage_timeline(stages, ax, xlim=None):
    """
    Draw horizontal stage segments with start/stop caps and readable labels.
    Each stage gets a color based on its index — consecutive stages are always
    visually distinct.
    """
    if ax is None:
        ax = plt.gca()
    if not stages:
        return

    # Use normalised y-coordinates (0 --> 1) since this is a dedicated subplot
    y_base = 0.2
    y_step = 0.6 / max(len(stages), 1)
    cap_height = 0.03

    for i, stage in enumerate(stages):
        # Assign color by index — not by label hash — for consistent ordering
        color = get_stage_color(i)
        y = y_base + i * y_step

        start = stage["start"]
        stop = stage["stop"]

        # Main horizontal segment representing the stage duration
        ax.hlines(y=y, xmin=start, xmax=stop, linewidth=1.6, color=color,
                  transform=ax.get_xaxis_transform())

        # Vertical start cap
        ax.axvline(x=start, ymin=y - cap_height, ymax=y + cap_height,
                   linewidth=1.6, color=color)

        # Vertical stop cap
        ax.axvline(x=stop, ymin=y - cap_height, ymax=y + cap_height,
                   linewidth=1.6, color=color)

        # Stage label centred above the segment
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
    """
    Return a color for a stage based on its position index in the stages list.

    Colors are assigned sequentially from STAGE_COLOR_PALETTE so that
    two consecutive stages always get visually distinct colors.
    Cycles back to palette[0] when index exceeds the palette length.

    Args:
        index (int): 0-based position of the stage in the stages list

    Returns:
        str: Hex color string
    """
    return STAGE_COLOR_PALETTE[index % len(STAGE_COLOR_PALETTE)]


def _draw_boundary(ax, x, color, linewidth, alpha, linestyle,
                   as_markers=False, marker='+', marker_size=40, n_markers=25):
    """
    Draw a vertical boundary at x on ax.

    Two modes:
      - as_markers=False : axvline with given linestyle  →  "----"
      - as_markers=True  : scatter markers along the axis →  "++++"

    x is in data coordinates, y positions are in axes coordinates [0,1]
    so the boundary always spans the full subplot height regardless of Y scale.
    """
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
    color_map=None,               # (hostname, label) → int  — for interleaved multi-node colors
    linewidth=1.6,                # ← thickness of START and STOP lines
    alpha=0.9,
    linestyle_start=(0, (4, 3)),  # START style  e.g. (0,(4,3)) = "----"
    linestyle_stop=(0, (4, 3)),   # STOP  style  e.g. (0,(1,2)) = "...."  or None if stop_as_markers=True
    stop_as_markers=False,        # True  → draw STOP as "++++" scatter
    stop_marker='+',              # marker symbol when stop_as_markers=True
    stop_marker_size=40,          # scatter s= size  (increase for bigger +)
    n_stop_markers=25,            # how many markers along the vertical
    show_legend=False,            # add a START/STOP legend on ax_top
    legend_loc="upper right",     # 'upper right' | 'upper left' | 'lower right' |
                                  # 'lower left'  | 'upper center' | 'center' | ...
):
    """
    Draw vertical START/STOP boundaries across all subplots between ax_top and ax_bottom.

    Color priority:
      1. color_map  (hostname, label) → index   [multi-node interleaved]
      2. label_to_index  label → index          [single-node consistent]
      3. position index i                        [fallback]

    START and STOP can have different visual styles (linestyle or marker type).
    """
    if not stages or ax_top is None or ax_bottom is None:
        return

    fig = ax_top.get_figure()
    idx_top = fig.axes.index(ax_top)
    idx_bot = fig.axes.index(ax_bottom)
    axes_range = fig.axes[idx_top:idx_bot + 1]

    for i, stage in enumerate(stages):
        # color resolution
        hostname = stage.get("_hostname")
        if color_map is not None and hostname is not None:
            color = get_stage_color(color_map.get((hostname, stage["label"]), i))
        elif label_to_index is not None:
            color = get_stage_color(label_to_index.get(stage["label"], i))
        else:
            color = get_stage_color(i)

        for ax in axes_range:
            # START boundary  :  "----"
            _draw_boundary(ax, stage["start"], color, linewidth, alpha,
                           linestyle_start, as_markers=False)
            # STOP boundary   :  "----" or "++++"
            _draw_boundary(ax, stage["stop"], color, linewidth, alpha,
                           linestyle_stop, as_markers=stop_as_markers,
                           marker=stop_marker, marker_size=stop_marker_size,
                           n_markers=n_stop_markers)

    #  optional legend on the top subplot
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
