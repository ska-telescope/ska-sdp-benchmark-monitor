"""Module to test benchmon metrics"""

import argparse
import logging
import os
import pickle
import shutil
import time

from benchmon.visualization import BenchmonVisualizer


def create_args(traces_repo: str = "",
                cpu: bool = False,
                cpu_all: bool = False,
                cpu_cores_full: str = "",
                cpu_cores_in: str = "",
                cpu_cores_out: str = "",
                cpu_freq: bool = False,
                mem: bool = False,
                net: bool = False,
                net_all: bool = False,
                net_data: bool = False,
                net_rx_only: bool = False,
                net_tx_only: bool = False,
                disk: bool = False,
                disk_iops: bool = False,
                disk_data: bool = False,
                disk_rd_only: bool = False,
                disk_wr_only: bool = False,
                ib: bool = False,
                sys: bool = False,
                pow: bool = False,
                inline_call: bool = False,
                inline_call_cmd: str = "",
                call: bool = False,
                call_depth: int = 1,
                call_depths: str = "",
                call_cmd: str = "",
                annotate_with_log: str = "",
                start_time: str = "",
                end_time: str = "",
                interactive: bool = False,
                fig_path: str = None,
                fig_fmt: str = "svg",
                fig_name: str = "benchmon_test_fig",
                fig_dpi: str = "unset",
                fig_call_legend_ncol: int = 8,
                fig_width: float = 25.6,
                fig_height_unit: float = 3,
                fig_xrange: int = 25,
                fig_yrange: int = 11,
                verbose: bool = False,
                test: bool = False):
    """Create argument namespace for visuaalization"""

    return argparse.Namespace(**locals())


def test_metrics():
    """Run visualizer"""
    logger = logging.getLogger("benchmon_test_logger")
    logger.setLevel(logging.DEBUG)

    cwd = os.path.dirname(__file__)
    now = time.time()
    test_repo = f"{cwd}/tmp/benchmon_savedir_test_{now}"
    os.makedirs(test_repo)

    ref_repo = f"{cwd}/data_for_visu/benchmon_traces_jed"
    shutil.copytree(ref_repo, test_repo, dirs_exist_ok=True)

    args = create_args(cpu=True, cpu_freq=True, mem=True, net=True, disk=True, ib=True, call=True, pow=True)

    bm = BenchmonVisualizer(args=args, logger=logger, traces_repo=test_repo)

    # *_data.plk to be added

    profiles = {
        f"{ref_repo}/pkl_dir/cpu_prof.pkl": bm.system_metrics.cpu_prof,
        f"{ref_repo}/pkl_dir/disk_prof.pkl": bm.system_metrics.disk_prof,
        f"{ref_repo}/pkl_dir/ib_prof.pkl": bm.system_metrics.ib_prof,
        f"{ref_repo}/pkl_dir/net_prof.pkl": bm.system_metrics.net_prof,
    }

    import numpy as np

    eps = 1e-6
    for key in profiles.keys():
        with open(key, "rb") as _pf:
            expected_prof = pickle.load(_pf)

        if key == f"{ref_repo}/pkl_dir/pow_prof.pkl":
            profiles[key].pop("time", None)
            expected_prof.pop("time", None)

        for device in expected_prof.keys():
            for space in expected_prof[device].keys():
                err = np.linalg.norm(expected_prof[device][space] - profiles[key][device][space])
                assert err < eps, f"Unexpected results for {device}/{space}"

    profiles = {
        f"{ref_repo}/pkl_dir/mem_prof.pkl": bm.system_metrics.mem_prof,
        f"{ref_repo}/pkl_dir/cpufreq_prof.pkl": bm.system_metrics.cpufreq_prof
    }

    with open(f"{ref_repo}/pkl_dir/mem_prof.pkl", "rb") as _pf:
        expected_prof = pickle.load(_pf)
        for metric in expected_prof.keys():
            err = np.linalg.norm(expected_prof[metric] - bm.system_metrics.mem_prof[metric])
            assert err < eps, f"Unexpected results for {metric}"

    with open(f"{ref_repo}/pkl_dir/cpufreq_prof.pkl", "rb") as _pf:
        expected_prof = pickle.load(_pf)

        for ref, val in zip(expected_prof, bm.system_metrics.cpufreq_prof):
            err = np.linalg.norm(ref - val)
            assert err < eps, f"Unexpected results for {metric}"
