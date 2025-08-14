"""Module to test benchmon-visu"""

import argparse
import logging
import os
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
    """Create argument namespace for visualization"""

    return argparse.Namespace(**locals())


def run(args: argparse.ArgumentParser):
    """Run visualizer"""
    logger = logging.getLogger("benchmon_test_logger")
    logger.setLevel(logging.DEBUG)

    cwd = os.path.dirname(__file__)
    now = time.time()
    test_repo = f"{cwd}/tmp/benchmon_savedir_test_{now}"
    os.makedirs(test_repo)

    ref_repo = f"{cwd}//data_for_visu/benchmon_traces_jed"
    shutil.copytree(ref_repo, test_repo, dirs_exist_ok=True)

    BenchmonVisualizer(args=args, logger=logger, traces_repo=test_repo).run_plots()


def test_visu_cpu():
    """Test CPU reading and visualization"""
    run(args=create_args(cpu=True, cpu_all=True, cpu_cores_full="0,1,2,3"))

    run(args=create_args(cpu=True, cpu_all=True, cpu_cores_in="1,4"))

    run(args=create_args(cpu=True, cpu_all=True, cpu_cores_out="4,7"))


def test_visu_cpufreq():
    """Test CPU Freq reading and visualization"""
    run(args=create_args(cpu_freq=True))


def test_visu_mem():
    """Test Memory reading and visualization"""
    run(args=create_args(mem=True))


def test_visu_net():
    """Test Network reading and visualization"""
    run(args=create_args(net=True, net_all=True, net_data=True))

    run(args=create_args(net=True, net_all=True, net_data=True, net_rx_only=True))

    run(args=create_args(net=True, net_all=True, net_data=True, net_tx_only=True))


def test_visu_disk():
    """Test Disk reading and visualization"""
    run(args=create_args(disk=True, disk_data=True, disk_iops=True))

    run(args=create_args(disk=True, disk_data=True, disk_iops=True, disk_rd_only=True))

    run(args=create_args(disk=True, disk_data=True, disk_iops=True, disk_wr_only=True))


def test_visu_ib():
    """Test IB reading and visualization"""
    run(args=create_args(ib=True))


def test_visu_pow():
    """Test Power reading and visualization"""
    run(args=create_args(cpu=True, pow=True))


def test_visu_call():
    """Test Callstack reading and visualization"""
    run(args=create_args(cpu=True, inline_call=True))
    run(args=create_args(cpu=True, inline_call=True, call_cmd="ft.C.x"))
    run(args=create_args(cpu=True, call=True, call_depth=4))
    run(args=create_args(cpu=True, call=True, call_depth=4, call_cmd="ft.C.x"))


def test_visu_all():
    """Test all reading and visualization"""
    run(args=create_args(cpu=True, cpu_all=True, cpu_cores_full="0",
                         cpu_freq=True,
                         mem=True,
                         net=True, net_all=True, net_data=True,
                         disk=True, disk_data=True, disk_iops=True,
                         ib=True,
                         pow=True,
                         inline_call=True, call=True, call_depth=4))
