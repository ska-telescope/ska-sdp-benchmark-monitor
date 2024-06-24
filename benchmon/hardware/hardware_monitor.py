import json
import logging
import sys

from .gatherers import cpu, memory
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
        data['cpu'] = cpu.CpuReader().read()

        # Memory
        data['memory'] = memory.MemoryReader().read()

        print(data)
        # Disk

        # Network

        # Interconnect

        # Accelerator

        # Mainboard

        # OS

        # PSU

        # Physical stuff

        # Serialize to json
        json.dump(data, open(f"{self.save_dir}/{f'{self.prefix}-' if self.prefix is not None else ''}hwmon-{hostname}.json", "w"))

        return
