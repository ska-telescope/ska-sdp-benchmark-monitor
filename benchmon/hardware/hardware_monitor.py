"""Docstring @todo."""

import json
import logging
import os
import sys

from .gatherers import cpu, memory, mounts, interface, accelerator, system, topology, pci, ping
from .advanced import pingpongroundtrip as ppr
from ..common.utils import execute_cmd

logger = logging.getLogger(__name__)


class HardwareMonitor:
    """Docstring @todo."""

    def __init__(self, args):
        """Docstring @todo."""

        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO)
        self.save_dir = args.save_dir
        self.verbose = args.verbose
        self.run_long_tasks = not args.no_long_checks
        os.makedirs(self.save_dir, exist_ok=True)

    def run(self):
        """Docstring @todo."""

        logger.info("Starting Hardware Monitor")

        hostname = execute_cmd("hostname")

        data = {}

        # CPU
        logger.info("Gathering CPU Data")
        data["cpu"] = cpu.CpuReader().read()

        # Memory
        logger.info("Gathering Memory Data")
        data["memory"] = memory.MemoryReader().read()

        # Disk
        logger.info("Gathering Disk Data")
        data["mounts"] = mounts.MountpointsReader().read()

        # Network
        logger.info("Gathering Network Interfaces")
        data["interfaces"] = interface.InterfacesReader().read()

        # Accelerator
        logger.info("Gathering Accelerator Data")
        data["accelerators"] = accelerator.AcceleratorReader().read()

        # Topology & PCI Data raw
        logger.info("Gathering Topology Data")
        data["topology_raw"] = topology.TopologyReader().read()
        data["pci_raw"] = pci.PciReader().read()

        # System
        logger.info("Gathering OS Data")
        data["system"] = system.SystemReader().read()

        # Ping to other nodes in reservation
        is_locking = True  # @bug to be fixed
        nnodes = os.environ.get("SLURM_NNODES")
        if not is_locking and nnodes is not None and int(nnodes) > 1:
            logger.info("Gathering Ping Data to other nodes in the reservation")
            data["ping"] = ping.PingReader().read()

            if self.run_long_tasks:
                logger.info("Gathering RoundTrip Time to other nodes in the reservation")
                data["pingpong"] = ppr.PingPongMeasure().measure()
            else:
                logger.info("Skipping RoundTrip test because -n / --no-long-checks is set.")

        # Serialize to json
        logger.info("Save Data to file")
        json.dump(data, open(f"{self.save_dir}/hwmon-{hostname}.json", "w"))

        logger.info("Exiting...")
        return
