import os

from benchmon.common.utils import execute_cmd


# Function to get the list of nodes from the SLURM environment
def get_node_list():
    # Using SLURM_JOB_NODELIST to get the list of nodes
    node_list = os.getenv("SLURM_JOB_NODELIST")
    if not node_list:
        raise ValueError("SLURM_JOB_NODELIST not found")

    # Resolving node names to a list (assuming the nodes are numbered like node[1-3])
    nodes = [k.strip() for k in execute_cmd(f"scontrol show hostnames {node_list}").strip().splitlines()]

    return nodes
