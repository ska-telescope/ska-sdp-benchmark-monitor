import glob
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def read_ical_log_file(traces_repo: str):
    """
    Read ical log file
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
        entry_key = entry # f"{entry[:4]}{entry[-1]}"
        if any([stage in entry for stage in ("calibrate", "predict", "image")]):
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

def plot_ical_stages(major_stages: dict, ymax = 100.):
    """
    Plot ical stages
    """
    def margin(stage):
        if "cali" in stage: return 0
        elif "pred" in stage: return 1
        elif "imag" in stage: return 2
        else: return 3

    for idx, stage in enumerate(major_stages):
        ydash = np.linspace(- ymax * .1, ymax * 1.1)

        plt.plot(major_stages[stage]["Start"] * np.ones_like(ydash), ydash, "k--", linewidth=.75)
        plt.text(major_stages[stage]["Start"], ymax * (1.1 - .04 * margin(stage)), stage, va="baseline", ha="left", size="x-small", weight="semibold")
