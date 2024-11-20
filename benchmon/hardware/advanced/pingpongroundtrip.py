import itertools
import os
import logging
import socket
import time
from time import sleep

import benchmon.common.slurm.slurm_utils as slurm_utils

log = logging.getLogger(__name__)


def arrange_pairs_min_overlap(pairs):
    """
        Take a list of pairs and order it in a way that creates as few overlap as possible.
        This enables most efficient usage of the nodes
    """
    result = []
    while pairs:
        # Create a new group of non-overlapping pairs
        non_overlapping = []
        used_nodes = set()

        # Loop over the pairs and add non-overlapping pairs to the group
        remaining_pairs = []
        for pair in pairs:
            if not (pair[0] in used_nodes or pair[1] in used_nodes):
                non_overlapping.append(pair)
                used_nodes.update(pair)
            else:
                remaining_pairs.append(pair)  # Leave for next round

        # Add this group to the result
        result.extend(non_overlapping)

        # Update pairs with remaining pairs for the next iteration
        pairs = remaining_pairs

    return result


def get_random_data(size):
    with open('/dev/urandom', 'rb') as f:
        return f.read(size)


class PingPongMeasure:
    num_ping: int = 10
    ping_payload: bytes = b"Ping"
    end_payload: bytes = b"BENCHMON_END"

    current_node: str = None

    socket_timeout = 30

    def measure(self, port=51434):
        original_port = port
        self.current_node = os.environ.get("SLURMD_NODENAME")
        nodes = slurm_utils.get_node_list()
        if self.current_node is None or len(nodes) == 0:
            log.error("Could not get the hostname or the slurm node list - Not running a PingPong Bandwidth Test")
            return
        if len(nodes) == 1:
            log.warning("Only one node in the reservation - Not running a PingPong Bandwidth Test")
            return

        log.debug(f"[{self.current_node}] Current node: {self.current_node}. Nodelist: {nodes}")

        data = {self.current_node: []}

        # Generate all possible directed unique pairs (permutations) of nodes and order them in a way with the least amount of overlap
        pairs = arrange_pairs_min_overlap(list(itertools.permutations(nodes, 2)))

        # Test between all pairs of nodes
        for p_idx, (client, server) in enumerate(pairs):
            port = original_port + p_idx
            # Fork process: one acts as server, the other as client
            try:
                if server == self.current_node:
                    log.info(f"[{self.current_node}][S] Acting as server to client {client} on port {port}")
                    self.server_ping_pong(port)
                elif client == self.current_node:
                    log.info(f"[{self.current_node}][C] Acting as client to server {server} on port {port}")
                    rtt, bw = self.client_ping_pong(server, port)
                    data[self.current_node] = {"node": server, "rtt": round(rtt, 4), "bandwidth": round(bw, 4)}
            except Exception as e:
                log.error(f"[{self.current_node}] Error during pingpong-test: {e}")
        return data

    # Function for server-side of ping-pong test
    def server_ping_pong(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            connected = False
            while not connected:
                try:
                    server_socket.bind(('', port))
                    connected = True
                except OSError as e:
                    log.error(f"[{self.current_node}][S] Could not bind socket! Got OSError: {e}. Retrying.")
                    sleep(1)

            server_socket.listen(1)

            conn, addr = server_socket.accept()
            num_bits_rcvd = 0
            with conn:
                # first, receive the Ping:
                data = conn.recv(1024)
                if data != self.ping_payload:
                    raise Exception(f"[{self.current_node}][S] Expected Ping as first message!")

                log.debug(f"[{self.current_node}][S] Received ping, returning ping.")
                conn.sendall(data)

                log.debug(f"[{self.current_node}][S] Standing by for large data.")
                while True:
                    data = conn.recv(1024)
                    if len(data) >= 12 and data[-len(self.end_payload):] == self.end_payload:
                        log.debug(f"[{self.current_node}][S] Received end-payload.")
                        break
                    num_bits_rcvd += 1024

                log.debug(f"[{self.current_node}][S] Done receiving data! Returning {num_bits_rcvd} bits.")
                # Generate new response with the same size to return to the client
                data = get_random_data(num_bits_rcvd)
                bytes_sent = 0
                while bytes_sent < num_bits_rcvd:
                    chunk = data[bytes_sent:bytes_sent + 1024]
                    conn.sendall(chunk)
                    bytes_sent += len(chunk)
                conn.sendall(self.end_payload)
                log.debug(f"[{self.current_node}][S] Done sending data.")
                conn.close()
            server_socket.shutdown(socket.SHUT_RDWR)
            server_socket.close()

    # Function for client-side of ping-pong test
    def client_ping_pong(self, server_ip, port, data_size=1024*1024*10):
        test_data = get_random_data(data_size)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            connected = False
            num_retries = 0
            while not connected:
                try:
                    client_socket.connect((server_ip, port))
                    connected = True
                except ConnectionRefusedError:
                    num_retries += 1
                    if num_retries == 30:
                        raise Exception(f"[C] Server {server_ip} did not respond within 30 seconds.")

                    log.debug(f"[{self.current_node}][C] Server not yet ready. Waiting...")
                    time.sleep(1)

            # Measure round-trip time
            start_time = time.time()
            client_socket.sendall(self.ping_payload)
            log.debug(f"[{self.current_node}][C] Sent Ping!")
            data = client_socket.recv(1024)
            end_time = time.time()

            if not data:
                raise IOError("PingPong data lost - no answer from the server")

            log.debug(f"[{self.current_node}][C] Received ping response. Sending large amount of data: {data_size} bits.")

            rtt = (end_time - start_time) * 1000  # Convert to milliseconds

            # Measure bandwidth by sending a large chunk of data
            start_time = time.time()

            # Send data to server in chunks
            bytes_sent = 0
            while bytes_sent < data_size:
                chunk = test_data[bytes_sent:bytes_sent + 1024]
                client_socket.sendall(chunk)
                bytes_sent += len(chunk)
            log.debug(f"[{self.current_node}][C] Done sending chunks - sending end payload.")
            # send end-payload
            client_socket.sendall(self.end_payload)

            # Wait to receive the full response from server
            log.debug(f"[{self.current_node}][C] Preparing to receive data back.")
            received_size = 0
            while received_size < data_size + len(self.end_payload):
                data = client_socket.recv(1024)
                if data == self.end_payload:
                    break
                received_size += len(data)
            end_time = time.time()
            log.debug(f"[{self.current_node}][C] Received everything back. Finalizing.")

            transfer_time = end_time - start_time
            bandwidth_mbps = (data_size * 8) / (transfer_time * 1_000_000)  # Convert to Mbps

            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()

        return rtt, bandwidth_mbps
