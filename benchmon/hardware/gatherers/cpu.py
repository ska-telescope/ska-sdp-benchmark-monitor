from benchmon.common.utils import execute_cmd, get_parser
import logging
import re
log = logging.getLogger(__name__)


class CpuReader:
    def __init__(self):
        pass

    def read(self):
        proc_cpuinfo = self.read_cpuinfo()
        lscpu = self.read_lscpu()

        return proc_cpuinfo, lscpu

    def read_lscpu(self):
        # Get output from lscpu command
        cmd_out = execute_cmd('lscpu')
        parse_lscpu = get_parser(cmd_out)

        cpu = {
            'Architecture': parse_lscpu('Architecture'),
            'CPU_Model': parse_lscpu('Model name'),
            'CPU_Family': parse_lscpu('CPU family'),
            'CPU_num': int(parse_lscpu(r'CPU\(s\)')),
            'Online_CPUs_list': parse_lscpu(r'On-line CPU\(s\) list'),
            'Threads_per_core': int(parse_lscpu(r'Thread\(s\) per core')),
            'Cores_per_socket': int(parse_lscpu(r'Core\(s\) per socket')),
            'Sockets': int(parse_lscpu(r'Socket\(s\)')),
            'Vendor_ID': parse_lscpu('Vendor ID'),
            'Stepping': int(parse_lscpu('Stepping')),
            'CPU_Max_Speed_MHz': float(parse_lscpu('CPU max MHz')),
            'CPU_Min_Speed_MHz': float(parse_lscpu('CPU min MHz')),
            'BogoMIPS': float(parse_lscpu('BogoMIPS')),
            'L1d_cache': parse_lscpu('L1d cache'),
            'L1i_cache': parse_lscpu('L1i cache'),
            'L2_cache': parse_lscpu('L2 cache'),
            'L3_cache': parse_lscpu('L3 cache'),
            'NUMA_nodes': int(parse_lscpu(r'NUMA node\(s\)')),
        }

        # Populate NUMA nodes
        try:
            for i in range(0, int(cpu['NUMA_nodes'])):
                cpu['NUMA_node{}_CPUs'.format(i)] = parse_lscpu(r'NUMA node{} CPU\(s\)'.format(i))
        except ValueError:
            log.warning('Failed to parse or NUMA nodes not existent.')

        # Update with additional data
        cpu.update(
            {
                'Power_Policy': execute_cmd(
                    'cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor ' '| sort | uniq'
                ),
                'Power_Driver': execute_cmd(
                    'cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_driver ' '| sort | uniq'
                ),
                'Microcode': execute_cmd(
                    'grep microcode /proc/cpuinfo | uniq | awk ' '\'NR==1{print $3}\''
                ),
                'SMT_Enabled?': bool(execute_cmd('cat /sys/devices/system/cpu/smt/active')),
            }
        )

        return cpu

    def read_cpuinfo(self):
        cpu_infos = []
        f = execute_cmd("cat /proc/cpuinfo", handle_exception=False)

        cpuinfo = {}
        for line in f.split('\n'):
            if line.strip():
                name, value = line.strip().split(':')
                cpuinfo[name.strip()] = value.strip()
            else:
                cpu_infos.append(cpuinfo)
                cpuinfo = {}

        return cpu_infos
