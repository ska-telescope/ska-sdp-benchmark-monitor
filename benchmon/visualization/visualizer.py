"""
Visualization manager
"""

from .system_metrics import HighFreqData

class BenchmonVisualizer():
    def __init__(self, args, logger) -> None:
        self.args = args
        self.logger = logger


    def load_measurements(self, args, logger):
        # Load HF data
        is_hf_sys = args.hf_sys

        is_hf_cpu = args.hf_cpu
        is_hf_cpu_all = args.hf_cpu_all
        is_hf_cpu_freq = args.hf_cpu_freq
        is_hf_cores_full = bool(args.hf_cpu_cores_full)

        is_hf_mem = args.hf_mem
        is_hf_swap = is_hf_mem # @hc

        is_hf_net_all = args.hf_net_all
        is_hf_net_data = args.hf_net_data
        is_hf_net = args.hf_net or is_hf_net_all or is_hf_net_data

        is_hf_disk_data = args.hf_disk_data
        is_hf_disk_iops = args.hf_disk_iops
        is_hf_disk = args.hf_disk or is_hf_disk_data or is_hf_disk_iops

        is_hf_ib = args.hf_ib


        # High-frequency monitoring data
        traces_repo = args.traces_repo
        is_any_hf_sys = is_hf_cpu or is_hf_cpu_all or is_hf_cpu_freq or is_hf_cores_full \
                        or is_hf_mem or is_hf_net or is_hf_disk or is_hf_ib

        csv_reports = {}
        conds = {"mem": is_hf_mem, "cpu": is_hf_cpu or is_hf_cpu_all or is_hf_cores_full,
                "cpufreq": is_hf_cpu_freq, "net": is_hf_net, "disk": is_hf_disk, "ib": is_hf_ib}
        for key in conds.keys():
            csv_reports[f"csv_{key}_report"] = f"{traces_repo}/hf_{key}_report.csv" if conds[key] else None

        if is_any_hf_sys:
            return HighFreqData(logger=logger, **csv_reports)
        else:
            return None
