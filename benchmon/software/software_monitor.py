"""Docstring @todo."""

import json
import logging
import os
import sys

from .gatherers import spack, pyenv, environment, modules
from ..common.utils import execute_cmd

logger = logging.getLogger(__name__)


class SoftwareMonitor:
    """Docstring @todo."""

    def __init__(self, args):
        """Docstring @todo."""

        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO)
        self.save_dir = args.save_dir
        self.verbose = args.verbose
        os.makedirs(self.save_dir, exist_ok=True)

    def run(self):
        """Docstring @todo."""

        logger.info("Starting Software Monitor")
        hostname = execute_cmd("hostname")

        data = {}

        # get env variables
        logger.info("Reading Environment Variables")
        data["env"] = environment.EnvGatherer().read()

        # get spack dependencies
        logger.info("Reading Spack Dependencies")
        data["spack_dependencies"] = spack.SpackReader().read()

        # Get python environment
        logger.info("Reading Python Environment")
        data["pyenv"] = pyenv.PythonEnv().read()

        # Get Loaded Modules
        logger.info("Reading Loaded Modules")
        data["modules"] = modules.ModuleReader().read()

        # Dump to json
        logger.info("Save Data to file")
        json.dump(data, open(f"{self.save_dir}/swmon-{hostname}.json", "w"))

        logger.info("Exiting...")
        return
