import json
import logging
import os

from .gatherers import spack, pyenv, environment, modules
from ..common.utils import execute_cmd

logger = logging.getLogger(__name__)

class SoftwareMonitor:
    def __init__(self, args):
        self.save_dir = args.save_dir
        self.prefix = args.prefix
        self.verbose = args.verbose
        self.save_path = f"{self.save_dir}/{self.prefix if self.prefix is not None else ''}"
        os.makedirs(self.save_path, exist_ok=True)

    def run(self):
        logger.info("Starting Software Monitor")
        hostname = execute_cmd('hostname')

        data = {}

        # get env variables
        logger.info("Reading Environment Variables")
        data["env"] = environment.EnvGatherer().read()

        # get spack dependencies
        logger.info("Reading Spack Dependencies")
        data["spack_dependencies"] = spack.SpackReader().read()

        # Get python environment
        logger.info("Reading Python Environment")
        data['pyenv'] = pyenv.PythonEnv().read()

        # Get Loaded Modules
        logger.info("Reading Loaded Modules")
        data['modules'] = modules.ModuleReader().read()

        # Dump to json
        logger.info("Save Data to file")
        json.dump(data, open(f"{self.save_path}/swmon-{hostname}.json", "w"))

        logger.info("Exiting...")
        return
