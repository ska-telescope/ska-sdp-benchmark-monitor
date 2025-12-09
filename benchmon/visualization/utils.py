"""Visualization utils (generic pipeline annotation)"""

import csv
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import glob
import os


def read_annotation_csv(traces_repo: str, filename: str = "annotations.csv") -> dict:
    """
    Read a generic CSV annotation file.
    
    Expected columns:
    timestamp,pipeline,stage,event,node,process,source,message,core

    Returns:
        dict structured as:
        {
            "INST/Predict": {
                "START": timestamp,
                "STOP": timestamp
            },
            "INST/Calibrate": {...}
        }
    """

    csv_path = os.path.join(traces_repo, filename)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Annotation CSV not found: {csv_path}")

    stages = {}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pipeline = row["pipeline"].strip()
            stage = row["stage"].strip()
            event = row["event"].strip().upper()
            ts = float(row["timestamp"])

            key = f"{pipeline}/{stage}"

            if key not in stages:
                stages[key] = {}

            stages[key][event] = ts

    return stages



def plot_annotation_stages(stages: dict, ymax=100.) -> None:
    """
    Plot vertical annotation lines for stages.

    Supports START/STOP, but works with any event.
    """

    def ypos(idx):
        return 1.1 - 0.05 * idx

    for idx, stage in enumerate(stages):
        events = stages[stage]

        for event, ts in events.items():
            ydash = np.linspace(-ymax * .1, ymax * 1.1)

            # vertical dashed line
            plt.plot(ts * np.ones_like(ydash),
                     ydash,
                     "--",
                     linewidth=.7,
                     color="black")

            # text placed above
            plt.text(ts,
                     ymax * ypos(idx),
                     f"{stage} [{event}]",
                     va="baseline",
                     ha="left",
                     size="x-small",
                     weight="semibold")
