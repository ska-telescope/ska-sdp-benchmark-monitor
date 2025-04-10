"""
Visualization manager
"""
import numpy as np
from .system_metrics import HighFreqData

class BenchmonVisualizer():
    def __init__(self, args, logger) -> None:
        self.args = args
        self.logger = logger


    def load_measurements(self):
        """
        """
        # Load HF data
        is_hf_sys = self.args.hf_sys

        is_hf_cpu = self.args.hf_cpu
        is_hf_cpu_all = self.args.hf_cpu_all
        is_hf_cpu_freq = self.args.hf_cpu_freq
        is_hf_cores_full = bool(self.args.hf_cpu_cores_full)

        is_hf_mem = self.args.hf_mem
        is_hf_swap = is_hf_mem # @hc

        is_hf_net_all = self.args.hf_net_all
        is_hf_net_data = self.args.hf_net_data
        is_hf_net = self.args.hf_net or is_hf_net_all or is_hf_net_data

        is_hf_disk_data = self.args.hf_disk_data
        is_hf_disk_iops = self.args.hf_disk_iops
        is_hf_disk = self.args.hf_disk or is_hf_disk_data or is_hf_disk_iops

        is_hf_ib = self.args.hf_ib

        _n_cores_full = len(self.args.hf_cpu_cores_full.split(",")) if is_hf_cores_full  else 0
        self.n_hf_sys = is_hf_cpu + is_hf_cpu_all + is_hf_cpu_freq + _n_cores_full + is_hf_mem + is_hf_net + is_hf_disk + is_hf_ib

        # High-frequency monitoring data
        traces_repo = self.args.traces_repo
        is_any_hf_sys = is_hf_cpu or is_hf_cpu_all or is_hf_cpu_freq or is_hf_cores_full \
                        or is_hf_mem or is_hf_net or is_hf_disk or is_hf_ib

        csv_reports = {}
        conds = {"mem": is_hf_mem, "cpu": is_hf_cpu or is_hf_cpu_all or is_hf_cores_full,
                "cpufreq": is_hf_cpu_freq, "net": is_hf_net, "disk": is_hf_disk, "ib": is_hf_ib}
        for key in conds.keys():
            csv_reports[f"csv_{key}_report"] = f"{traces_repo}/hf_{key}_report.csv" if conds[key] else None

        if is_any_hf_sys:
            return HighFreqData(logger=self.logger, **csv_reports)
        else:
            return None


def get_inline_calls_prof(args, logger, cmd, cmds, samples, mono_to_real_val):
    # Hard-coded system command to remove
    kernel_calls = [
        "swapper", "bash", "awk", "cat", "date", "grep", "sleep", "perf_5.10", "perf", "prometheus-node",
        "htop", "kworker", "dbus-daemon", "ipmitool", "slurmstepd", "rcu_sched", "ldlm_bl", "socknal",
        "systemd", "snapd", "apparmor", "sed", "kswap", "queue"
    ]

    # Create list of keys for user calls (remove command if less thant 5% of the larger command)
    if args.inline_call_cmd:
        user_calls_keys = args.inline_call_cmd.split(",")

    else:
        INLINE_CMDS_THRESHOLD = 0.01
        user_calls_keys = []
        for key in cmds:
            if cmds[key] / cmds[cmd] > INLINE_CMDS_THRESHOLD:
                user_calls_keys += [key]

        # print(f"{user_calls_keys = }") # @dbg
        user_calls_keys_raw = user_calls_keys.copy()
        for command in user_calls_keys_raw:
            for kcall in kernel_calls:
                if kcall in command:
                    user_calls_keys.remove(command)
                    break

    inline_calls_prof = {key: [] for key in user_calls_keys}

    # DEBUG
    msg = "Inline commands:\n"
    for cmd in user_calls_keys:
        msg += f"\t{cmd}: {cmds[cmd]} samples\n"
    logger.debug(msg)

    for sample in samples:
        if sample["cmd"] in user_calls_keys: # and  sample["cpu"] == "[000]":
            inline_calls_prof[sample["cmd"]] += [sample["timestamp"] + mono_to_real_val]

    # Remove duplicated wrt decimal
    ROUND_VAL = 2
    msg = "Inline commands (Lightened):\n"
    for cmd in user_calls_keys:
        inline_calls_prof[cmd] = np.unique(np.array(inline_calls_prof[cmd]).round(ROUND_VAL))
        msg += f"\t{cmd}: {len(inline_calls_prof[cmd])} samples\n"
    logger.debug(msg)

    return inline_calls_prof


def run_plots(args, logger, nsbp, hfsys_trace, inline_calls_prof, xlim, xticks, power_trace, power_g5k_trace, system_metrics, call_depths, call_trace):
    import matplotlib.pyplot as plt

    sbp = 1

    # (HF) CPU plot
    if args.hf_cpu:
        logger.debug("Plotting (hf) cpu")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_cpu(calls=inline_calls_prof)

    # (HF) Full individual core plot
    if bool(args.hf_cpu_cores_full):
        for core_number in args.hf_cpu_cores_full.split(","):
            logger.debug(f"Plotting (hf) full cpu core {core_number}")
            ax = plt.subplot(nsbp, 1, sbp); sbp += 1
            hfsys_trace.plot_hf_cpu(core_number)

    # (HF) CPU per core plot
    if args.hf_cpu_all:
        logger.debug("Plotting (hf) cpu per core")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_cpu_per_core(cores_in=args.cpu_cores_in, cores_out=args.cpu_cores_out, calls=inline_calls_prof)


    # (HF) CPU cores frequency plot
    if args.hf_cpu_freq:
        logger.debug("Plotting (hf) cpu cores frequency")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_cpufreq(cores_in=args.cpu_cores_in, cores_out=args.cpu_cores_out, calls=inline_calls_prof)


    # (HF) Memory/swap plot
    if args.hf_mem:
        logger.debug("Plotting (hf) memory/swap")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_memory_usage(xticks=xticks, xlim=xlim, calls=inline_calls_prof)

    # (HF) Network plot
    if args.hf_net:
        logger.debug("Plotting (hf) network")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_network(xticks=xticks, xlim=xlim, calls=inline_calls_prof, all_interfaces=args.hf_net_all,
                                    is_rx_only=args.hf_net_rx_only, is_tx_only=args.hf_net_tx_only, is_netdata_label=args.hf_net_data)

    # (HF) Infiniband plot
    if args.hf_ib:
        logger.debug("Plotting (hf) infiniband")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_ib(xticks=xticks, xlim=xlim, calls=inline_calls_prof)


    # (HF) Disk plot
    if args.hf_disk:
        logger.debug("Plotting (hf) disk")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        hfsys_trace.plot_hf_disk(xticks=xticks, xlim=xlim, calls=inline_calls_prof, is_with_iops=args.hf_disk_iops,
                                 is_rd_only=args.hf_disk_rd_only, is_wr_only=args.hf_disk_wr_only, is_diskdata_label=args.hf_disk_data)

    # (perf+g5k) Power plot
    if args.pow or args.pow_g5k:
        logger.debug("Plotting perf power")
        ax = plt.subplot(nsbp, 1, sbp); sbp += 1
        _ymax_pow = [0]
        if args.pow:
            _ymax_pow += [power_trace.plot_events(xticks=xticks, xlim=xlim)]
        if args.pow_g5k:
            _ymax_pow += [power_g5k_trace.plot_g5k_pow_profiles(xticks=xticks, xlim=xlim)]
        if inline_calls_prof:
            system_metrics.plot_inline_calls(inline_calls_prof, ymax=max(_ymax_pow), xlim=xlim)
        plt.xticks(xticks[0], xticks[1])
        plt.xlim(xlim)
        plt.ylabel("Power (W)")
        plt.legend(loc=1)
        plt.grid()

    # (perf) Calltrace plot
    if args.call:
        logger.debug("Plotting perf call graph")
        plt.subplot(nsbp, 1, (sbp,sbp+1), sharex=ax)
        call_trace.plot(call_depths, xticks=xticks, xlim=xlim, legend_ncol=args.fig_call_legend_ncol)
