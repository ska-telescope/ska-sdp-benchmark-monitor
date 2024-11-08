import json
import logging
from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)


class SpackReader:

    def read(self):
        data = self.get_spack_dependency_tree()
        if data is None:
            log.warning("Spack is not available. Skipping gathering of spack dependency tree")
        return data

    def get_spack_dependency_tree(self):
        """
        Get output from spack
        """

        found = execute_cmd('which spack') != 'not_available'
        if not found:
            return None

        # spack was found. See if we are in an environment:
        env = None
        env_data = execute_cmd('spack env status')
        if env_data.startswith("==> In environment"):
            env = env_data.strip().split()[-1]
        elif env_data.startswith("==> No active environment"):
            env = None
        else:
            # something is wrong with the spack installation! Logging and aborting
            log.error("Could not determine spack env status! Is the spack installation corrupt?")
            return None

        if env is not None:
            # We are in an environment, use env specific commands
            val = execute_cmd("spack spec -c paths --json").split('\n')
            deps_list = [json.loads(k)['spec']['nodes'] for k in val]
            full_deps = {}
            for d in deps_list:
                full_deps[d[0]['name']] = d

        else:
            # Not in an environment, use generic commands
            val = execute_cmd("spack find --explicit --json")
            root_deps = json.loads(val)
            full_deps = {}
            for d in root_deps:
                val = execute_cmd(f"spack spec -c paths --json {d['name']}/{d['hash']}")
                full_deps[d['name']] = json.loads(val)['spec']['nodes']

        return full_deps