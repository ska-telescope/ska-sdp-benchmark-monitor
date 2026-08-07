"""Visualization utils"""
import os
import csv
import glob
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

import re
from collections import defaultdict
import matplotlib.patches as mpatches

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
            stage = row.get("stage", "").strip()
            event = row.get("event", "").strip().upper()
            ts = float(row["timestamp"])

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

# ─────────────────────────────────────────────────────────────────────────────
# Cheetah pipline style
# ─────────────────────────────────────────────────────────────────────────────

CHEETAH_PIPE_KNOWN_MODULES = [
    "rfim_iqrm",
    "klotski",
    "spsift",
    "spscluster",
    "psbc",
    "DRED",
    "CXFT_laby",
    "CXFT_fpga",
    "CDOS",
    "CXFT_setup",
    "FDAS_laby",
    "FDAS_fpga",
    "strongSIFT",
    "simpleSIFT",
    "fldo",
    "optim",
    "cheetah_pipe",
]

_CHEETAH_PIPE_BASE_COLORS = {
    "rfim_iqrm":   "#BE0032",   # red
    "klotski":     "#008856",   # green
    "spsift":      "#F38400",   # orange
    "spscluster":  "#875692",   # purple
    "psbc":        "#E25822",   # vermilion
    "DRED":        "#654522",   # brown
    "CXFT_laby":   "#2B3D26",   # dark green
    "CXFT_fpga":   "#0067A5",   # blue
    "CDOS":        "#B3446C",   # raspberry
    "CXFT_setup":  "#8B008B",   # dark magenta
    "FDAS_laby":   "#00A86B",   # jade
    "FDAS_fpga":   "#4169E1",   # royal blue
    "strongSIFT":  "#FF4500",   # orange-red
    "simpleSIFT":  "#FF8C00",   # dark orange
    "fldo":        "#20B2AA",   # light sea green
    "optim":       "#708090",   # slate gray
    "cheetah_pipe":"#0067A5",   # strong blue
}

def _get_cheetah_pipe_color(category: str) -> str:
    """Return a color for a category (module or module/beam)."""
    base = category.split("/")[0]
    return _CHEETAH_PIPE_BASE_COLORS.get(base, "#7F7F7F")  # gray fallback

def _classify_pss_stage(stage: str, message: str) -> str | None:
    """
    Map a PSS stage name.
    Returns None if the stage is not recognized.
    
    """
    stage = stage.strip()
    message = (message or "").strip().lower()

    # cheetah_pipe is global
    if stage == "cheetah_pipe":
        return "cheetah_pipe"

    # Extract base module name
    base = re.sub(r"_\d+$", "", stage)

    if base not in CHEETAH_PIPE_KNOWN_MODULES:
        return None

    # Beam detection
    beam = None
    if message in ("beam1", "beam2", "beam3"):
        beam = message
    elif message in ("beam<na>", "beamna", "na", ""):
        beam = None  # treat as no beam

    if beam:
        return f"{base}/{beam}"
    else:
        return base


def read_annotation_csv_pss(
    traces_repo: str, filename: str, node_name: str = None
) -> list:
    """
    Returns a list of stage intervals with an extra '_category' field.
    Only recognized modules are kept. Missing modules simply do not appear.
    """
    if os.path.isabs(filename) or os.path.exists(filename):
        csv_path = filename
    else:
        csv_path = os.path.join(traces_repo, filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"cheetah pipe annotation CSV file not found: {csv_path}")

    stages_tmp = {}  # key: (category, instance_label) → {"START": ts, "STOP": ts}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_node = row.get("node", "").strip()
            if node_name and row_node not in (node_name, "unknown", ""):
                continue

            stage = row.get("stage", "").strip()
            message = row.get("message", "").strip()
            event = row.get("event", "").strip().upper()
            ts = float(row["timestamp"])

            category = _classify_pss_stage(stage, message)
            if category is None:
                continue

            # Unique key per instance
            key = (category, f"{row.get('pipeline', 'PSS')}/{stage}")
            if key not in stages_tmp:
                stages_tmp[key] = {}
            stages_tmp[key][event] = ts

    stages = []
    for (category, label), events in stages_tmp.items():
        stop_ts = events.get("FINISHED") or events.get("STOP")
        if "START" in events and stop_ts is not None:
            stages.append({
                "label": label,
                "_category": category,
                "start": events["START"],
                "stop": stop_ts,
            })

    stages.sort(key=lambda s: s["start"])
    return stages

def is_cheetah_csv(csv_path: str, sample_size: int = 50) -> bool:
    """
    Robust detection of Cheetah/PSS-format events.csv.
    Returns True only if the file looks genuinely like a Cheetah annotation file.
    """
    if not os.path.exists(csv_path):
        return False

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            fieldnames = [c.strip().lower() for c in (reader.fieldnames or [])]

            # 1. Header check
            required = {"timestamp", "pipeline", "stage", "event"}
            if not required.issubset(set(fieldnames)):
                return False

            # 2. Sample some rows
            pss_count = 0
            known_stage_count = 0
            total = 0

            known_stages = {
                "cheetah_pipe", "rfim_iqrm", "klotski", "spsift",
                "spscluster", "fdas_laby", "strongsift", "fldo", "psbc",
                "fdas_fpga", "dred", "cxft_setup", "cxft_laby", "cxft_fpga",
                "cdos", "optim", "simplesift"
            }

            for row in reader:
                total += 1
                pipeline = row.get("pipeline", "").strip().upper()
                stage = row.get("stage", "").strip().lower()

                if pipeline == "PSS":
                    pss_count += 1

                # strip trailing _digits for matching
                base_stage = re.sub(r"_\d+$", "", stage)
                if base_stage in known_stages or any(k in stage for k in known_stages):
                    known_stage_count += 1

                if total >= sample_size:
                    break

            if total == 0:
                return False

            # 3. Decision rules
            pss_ratio = pss_count / total
            has_known_stages = known_stage_count > 0

            return pss_ratio >= 0.8 and has_known_stages

    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# concurrency
# ─────────────────────────────────────────────────────────────────────────────

def compute_concurrency_from_stages(stages: list) -> dict:
    """
    Compute concurrent activity per category.
    Returns: { category: (times_array, counts_array) }
    Only categories present in the data are returned.
    """
    events = defaultdict(list)

    for st in stages:
        category = st.get("_category")
        if not category:
            # fallback
            label = st.get("label", "")
            category = re.sub(r"_\d+$", "", label.split("/")[-1])
        events[category].append((st["start"], +1))
        events[category].append((st["stop"], -1))

    concurrency = {}
    for category, evts in events.items():
        evts.sort(key=lambda x: x[0])
        times, counts = [], []
        current = 0
        for ts, delta in evts:
            current += delta
            times.append(ts)
            counts.append(current)
        concurrency[category] = (np.array(times), np.array(counts))

    return concurrency

def plot_concurrency(concurrency_dict: dict, ax=None, max_concurrency: int = 2) -> None:

    if ax is None:
        ax = plt.gca()

    if not concurrency_dict:
        ax.set_ylabel("Stage concurrency")
        return

    def sort_key(cat):
        base = cat.split("/")[0]
        try:
            base_idx = CHEETAH_PIPE_KNOWN_MODULES.index(base)
        except ValueError:
            base_idx = 999
        beam = cat.split("/")[1] if "/" in cat else ""
        beam_idx = {"beam1": 1, "beam2": 2, "beam3": 3}.get(beam, 0)
        return (base_idx, beam_idx)

    sorted_cats = sorted(concurrency_dict.keys(), key=sort_key)

    offset = 0.0
    spacing = 1.2
    handles = []

    for cat in sorted_cats:
        times, counts = concurrency_dict[cat]
        if len(times) == 0:
            continue

        # concurrency
        real_counts = counts.copy()
        # concurrency after thresholding
        display_counts = np.minimum(counts, max_concurrency)

        color = _get_cheetah_pipe_color(cat)

        ax.fill_between(
            times,
            offset,
            offset + display_counts,
            step="post",
            alpha=0.85,
            color=color,
            linewidth=0.6,
            label=cat,
        )
        handles.append(mpatches.Patch(color=color, label=cat))

        # ---------- Annotation of peaks exceeding the threshold ----------
        #  real_counts > max_concurrency ?
        above = real_counts > max_concurrency
        if np.any(above):
            # using  the threshold 
            
            diff = np.diff(above.astype(int), prepend=0)
            starts = np.where(diff == 1)[0]
            ends   = np.where(diff == -1)[0]
            if len(ends) < len(starts):
                ends = np.append(ends, len(above) - 1)

            for s, e in zip(starts, ends):
                # max value peak
                peak_val = int(real_counts[s:e+1].max())
                # Position of the peak
                peak_x = times[s + np.argmax(real_counts[s:e+1])]
                # Position y
                peak_y = offset + max_concurrency + 0.3

                ax.text(
                    peak_x, peak_y,
                    f"{peak_val}",
                    fontsize=3,
                    ha='center', va='bottom',
                    color=color,
                    alpha=0.9,
                    fontweight='bold',
                    zorder=10,
                )

        max_c = float(display_counts.max()) if len(display_counts) else 0.0
        offset += spacing + max_c
    ax.set_yticks([])
    ax.set_ylabel(f"Stage concurrency (capped at {max_concurrency})", fontsize=9)

    # legend config
    n_items = len(handles)
    ncol = min(n_items, 6)
    if n_items > 6:
        ncol = min(8, (n_items + 1) // 2)

    # ax.legend(
    #     handles=handles,
    #     loc='upper center',
    #     bbox_to_anchor=(0.5, 1.14),
    #     ncol=ncol,
    #     fontsize=7,
    #     frameon=False,
    #     columnspacing=1.2,
    #     handletextpad=0.4,
    #     handlelength=1.2,
    # )
    ax.legend(
    handles=handles,
    loc='upper center',
    bbox_to_anchor=(0.5, 1.25),   # move the legendary on the very top of the subplot subplot
    ncol=17,                      # 49 éléments / 3 lignes ~ 16.3 -> 17 column
    fontsize=7,
    frameon=False,                # not a square
    columnspacing=1.2,
    handletextpad=0.4,
    handlelength=1.2,
    )
    ax.grid(axis="x", linestyle="--", linewidth=0.5, alpha=0.5)