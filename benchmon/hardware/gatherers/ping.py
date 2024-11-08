from ping3 import ping
import os
import logging

from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)

num_ping = 10


class PingReader():
    def read(self):
        job_nodes = os.environ.get("SLURM_NODELIST")
        if job_nodes is None:
            return
        job_nodes = execute_cmd(f"scontrol show hostnames {job_nodes}").splitlines()
        log.info(f"Running Ping Test to all nodes in the reservation. Found nodes: {job_nodes}")

        data = {}

        try:
            for node in job_nodes:
                latency = sum([ping(node, unit="ms") for _ in range(num_ping)]) / num_ping
                data[node] = {"avg_latency": latency}
        except PermissionError:
            log.exception("Permission error when running ping: On some systems ICMP packages might only be sent with elevated privileges.")
            return
