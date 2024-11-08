import os
import logging
import socket
import time
from math import trunc

import benchmon.common.slurm.slurm_utils as slurm_utils
from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)

num_ping = 10
ping_payload = b"Ping"
end_payload = b"BENCHMON_END"

class PingPongMeasure:
    def get_random_data(self, size):
        with open('/dev/urandom', 'rb') as f:
            return f.read(size)

    def measure(self, port=51437):
        hostname = os.environ.get("SLURMD_NODENAME")
        nodes = slurm_utils.get_node_list()
        if hostname is None or len(nodes) == 0:
            log.error("Could not get the hostname or the slurm node list - Not running a PingPong Bandwidth Test")
            return
        if len(nodes) == 1:
            log.warning("Only one node in the reservation - Not running a PingPong Bandwidth Test")
            return

        current_node = socket.gethostname()

        log.debug(f"Current node: {current_node}")
        log.debug(f"Node list: {nodes}")

        data = {current_node: []}

        # Test between all pairs of nodes
        for node in nodes:
            if node != current_node:
                log.debug(f"Testing with {node}")
                # Fork process: one acts as server, the other as client
                if current_node > node:
                    log.debug(f"Node {current_node} acting as server")
                    self.server_ping_pong(port)
                else:
                    log.debug(f"Node {current_node} acting as client")
                    rtt, bw = self.client_ping_pong(node, port)
                    data[current_node] = {"node": node, "rtt": round(rtt, 4), "bandwidth": round(bw, 4)}
        return data

    # Function for server-side of ping-pong test
    def server_ping_pong(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind(('', port))
            server_socket.listen(1)

            conn, addr = server_socket.accept()
            num_bits_rcvd = 0
            with conn:
                # first, receive the Ping:
                data = conn.recv(1024)
                print(f"Received first element: {data}", flush=True)
                if data != ping_payload:
                    raise "Expected Ping as first message!"

                print("Received ping, returning ping.", flush=True)
                conn.sendall(data)

                while True:
                    data = conn.recv(1024)
                    # print(f"Received data! -> {num_bits_rcvd + 1024}", flush=True)
                    if data == end_payload:
                        print("Received end-payload")
                        break
                    num_bits_rcvd += 1024

                print(f"Done receiving data! Returning {num_bits_rcvd} bits.")
                # Generate new response with the same size to return to the client
                data = self.get_random_data(num_bits_rcvd)
                bytes_sent = 0
                while bytes_sent < num_bits_rcvd:
                    chunk = data[bytes_sent:bytes_sent + 1024]
                    conn.sendall(chunk)
                    bytes_sent += len(chunk)
                conn.sendall(end_payload)

    # Function for client-side of ping-pong test
    def client_ping_pong(self, server_ip, port, data_size=1024*1024*1000):
        test_data = self.get_random_data(data_size)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            connected = False
            while not connected:
                try:
                    client_socket.connect((server_ip, port))
                    connected = True
                except ConnectionRefusedError:
                    log.debug("Server not yet ready. Waiting...")
                    print("Server not yet ready. Waiting...")
                    time.sleep(1)

            # Measure round-trip time
            start_time = time.time()
            client_socket.sendall(ping_payload)
            print(f"Sent Ping!", flush=True)
            data = client_socket.recv(1024)
            end_time = time.time()

            if not data:
                raise IOError("PingPong data lost - no answer from the server")

            rtt = (end_time - start_time) * 1000  # Convert to milliseconds

            # Measure bandwidth by sending a large chunk of data
            start_time = time.time()

            # Send data to server in chunks
            bytes_sent = 0
            while bytes_sent < data_size:
                chunk = test_data[bytes_sent:bytes_sent + 1024]
                # print("Sending chunk")
                client_socket.sendall(chunk)
                bytes_sent += len(chunk)
            print("Done sending chunks - sending end payload")
            # send end-payload
            client_socket.sendall(end_payload)

            # Wait to receive the full response from server
            print("Preparing to receive")
            received_size = 0
            while received_size < data_size + len(end_payload):
                data = client_socket.recv(1024)
                # print(f"Received data: {received_size + len(data)}", flush=True)
                if data == end_payload:
                    break
                received_size += len(data)
            print("Done receiving on client-side", flush=True)
            end_time = time.time()

            transfer_time = end_time - start_time
            bandwidth_mbps = (data_size * 8) / (transfer_time * 1_000_000)  # Convert to Mbps

            return rtt, bandwidth_mbps
