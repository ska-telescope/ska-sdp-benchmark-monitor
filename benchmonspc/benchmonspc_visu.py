#!/usr/bin/env python3

import argparse
import matplotlib.pyplot as plt
from benchmonspc_sys import DoolData
from benchmonspc_pow import PerfPowerData
from benchmonspc_call import PerfCallRawData, PerfCallData

def parsing():
    """
    Parse benchmonspc_visu arguments
    """
    # Parser
    parser = argparse.ArgumentParser()

    # Traces repo
    parser.add_argument("--traces-repo", "-r", type=str, default="./", help="Report path")

    # System metrics
    parser.add_argument("--cpu", action="store_true", help="Visualize CPU")
    parser.add_argument("--cpu-all", action="store_true", help="Visualize all CPU cores")
    parser.add_argument("--mem", action="store_true", help="Visualize memory")
    parser.add_argument("--net", action="store_true", help="Visualize network")
    parser.add_argument("--io", action="store_true", help="Visualize io")

    # Power profile
    parser.add_argument("--pow", action="store_true", help="Visualize power")

    # Callstack
    parser.add_argument("--call", action="store_true", help="Visualize callstack")
    parser.add_argument("--call-depth", type=int, default=1, help="Callstack depth level")
    parser.add_argument('--call-depths', type=str, default="", help="Comma-separated depth levels")
    parser.add_argument('--call-cmd', type=str, default="", help="Command to visualize")

    # Figures
    parser.add_argument("--interactive", action="store_true", help="Interactive visualization")
    parser.add_argument("--fig-path", type=str, help="Figure format")
    parser.add_argument("--fig-fmt", type=str, default="svg", help="Figure format")
    parser.add_argument("--fig-name", type=str, default="benchmon_fig", help="Figure name")
    parser.add_argument("--fig-dpi", type=str, default="medium", help="Quality of figure: low, medium, high")
    parser.add_argument("--fig-call-legend-ncol", type=int, default=8, help="Number of columns of call traces legend")

    return parser.parse_args()


def main():
    """
    Main of benchmonspc_visu
    """
    args = parsing()

    # Load dool data
    _xticks = []
    _xlim = []
    if args.cpu or args.cpu_all or args.mem or args.net or args.io:
        sys_trace = DoolData(csv_filename=f"{args.traces_repo}/sys_report.csv")
        _xticks = sys_trace._xticks
        _xlim = sys_trace._xlim
    n_sys = args.cpu + args.cpu_all + args.mem + args.net + (args.io and sys_trace.with_io)

    # Load power data
    if args.pow:
        power_trace = PerfPowerData(csv_filename=f"{args.traces_repo}/pow_report.csv")

    # Load call data
    call_depths = []
    if args.call:
        with open(f"{args.traces_repo}/mono_to_real_file.txt", "r") as file:
            mono_to_real_val = float(file.readline())
        call_raw = PerfCallRawData(filename=f"{args.traces_repo}/call_report.txt")
        samples, cmds = call_raw.cmds_list()

        if args.call_cmd:
            cmd = args.call_cmd
        else:
            cmd = list(cmds.keys())[0]

        call_trace = PerfCallData(cmd=cmd, samples=samples, m2r=mono_to_real_val)
        if args.call_depth:
            call_depths = [depth for depth in range(args.call_depth)]
        elif args.call_depths:
            call_depths = [int(depth) for depth in args.call_depths.split(",")]

    # Figure and subplots
    nsbp = n_sys + args.pow + args.call * (2 if len(call_depths) > 2 else 1)
    sbp = 1
    wid, hei = 19.2, nsbp * 3 #10.8
    fig = plt.figure(figsize=(wid,hei))

    # CPU plot
    if args.cpu:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        sys_trace.plot_cpu_average()

    # CPU per core plot
    if args.cpu_all:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        sys_trace.plot_cpu_per_core(with_color_bar=True, fig=fig, nsbp=nsbp, sbp=sbp-1) #, with_legend=True)

    # Memory plot
    if args.mem:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        sys_trace.plot_memory_usage()

    # Network plot
    if args.net:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        sys_trace.plot_network()

    # IO plot
    if args.io and sys_trace.with_io:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        sys_trace.plot_io()

    # Power plot
    if args.pow:
        plt.subplot(nsbp, 1, sbp); sbp += 1
        power_trace.plot_events(xticks=_xticks, xlim=_xlim)

    # Calltrace plot
    if args.call:
        plt.subplot(nsbp, 1, (sbp,sbp+1))
        call_trace.plot(call_depths, xticks=_xticks, xlim=_xlim, legend_ncol=args.fig_call_legend_ncol)

    plt.subplots_adjust(hspace=.5)
    plt.tight_layout()

    # Enable interactive plot
    if args.interactive:
        plt.show()

    # Figure saving parameters
    dpi = {"low": 200, "medium": 600, "high": 1200}
    figpath = f"{args.traces_repo}" if args.fig_path is None else args.fig_path
    for fmt in args.fig_fmt.split(","):
        figname = f"{figpath}/{args.fig_name}.{fmt}"
        fig.savefig(figname, format=fmt, dpi=dpi[args.fig_dpi])
        print(f"Figure saved: {figname}")

    return 0


if __name__ == "__main__":
    main()
