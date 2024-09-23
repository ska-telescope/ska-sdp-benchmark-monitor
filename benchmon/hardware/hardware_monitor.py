import json
import logging
import sys

from .gatherers import cpu, memory, mounts, interface, accelerator, system, topology, pci
from ..common.utils import execute_cmd

logger = logging.getLogger(__name__)

class HardwareMonitor:
    def __init__(self, args):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO)
        self.save_dir = args.save_dir
        self.prefix = args.prefix
        self.verbose = args.verbose

    def run(self):
        logger.info("Starting Hardware Monitor")

        hostname = execute_cmd('hostname')

        data = {}

        # CPU
        logger.info("Gathering CPU Data")
        data['cpu'] = cpu.CpuReader().read()

        # Memory
        logger.info("Gathering Memory Data")
        data['memory'] = memory.MemoryReader().read()

        # Disk
        logger.info("Gathering Disk Data")
        data['mounts'] = mounts.MountpointsReader().read()

        # Network
        logger.info("Gathering Network Interfaces")
        data['interfaces'] = interface.InterfacesReader().read()

        # Accelerator
        logger.info("Gathering Accelerator Data")
        data['accelerators'] = accelerator.AcceleratorReader().read()

        # Topology & PCI Data raw
        logger.info("Gathering Topology Data")
        data['topology_raw'] = topology.TopologyReader().read()
        data['pci_raw'] = pci.PciReader().read()

        # System
        logger.info("Gathering OS Data")
        data['system'] = system.SystemReader().read()

        # Serialize to json
        logger.info("Save Data to file")
        json.dump(data, open(f"{self.save_dir}/{f'{self.prefix}-' if self.prefix is not None else ''}hwmon-{hostname}.json", "w"))

        logger.info("Exiting...")
        return
