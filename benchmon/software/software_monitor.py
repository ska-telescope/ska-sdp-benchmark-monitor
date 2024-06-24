import json
import logging
import os

from .gatherers import spack
from ..common.utils import execute_cmd

log = logging.getLogger(__name__)

class SoftwareMonitor:
    def __init__(self, args):
        self.save_dir = args.save_dir
        self.prefix = args.prefix
        self.verbose = args.verbose
        self.save_path = f"{self.save_dir}/{self.prefix if self.prefix is not None else ''}"
        os.makedirs(self.save_path, exist_ok=True)

    def run(self):
        hostname = execute_cmd('hostname')

        # get spack dependencies
        spack_dependencies = spack.SpackReader().read()

        if spack_dependencies is None:
            log.warning("Spack is not available. Skipping gathering of spack dependency tree")

        # Dump to json
        json.dump(spack_dependencies, open(f"{self.save_path}/swmon-{hostname}.json", "w"))

