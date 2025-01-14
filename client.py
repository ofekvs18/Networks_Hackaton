#!/usr/bin/env python3
import socket
import struct
import threading
import time
from typing import List, Tuple
import logging
from enum import Enum
import sys
from dataclasses import dataclass
import queue


class ClientState(Enum):
    """Enum representing the possible states of the client."""
    STARTUP = 1
    LOOKING_FOR_SERVER = 2
    SPEED_TEST = 3


@dataclass
class TransferStats:
    """Class for holding statistics about a transfer."""
    transfer_id: int
    protocol: str
    start_time: float
    end_time: float = 0
    bytes_received: int = 0
    packets_received: int = 0
    total_packets: int = 0


class SpeedTestClient:
    """
    Client implementation for network speed testing.
    Supports both TCP and UDP protocols and maintains transfer statistics.
    """

    # Constants for message formats
    MAGIC_COOKIE = 0xabcddcba
    OFFER_MSG_TYPE = 0x2
    REQUEST_MSG_TYPE = 0x3
    PAYLOAD_MSG_TYPE = 0x4

    def __init__(self, broadcast_port: int = 13117):
        """
        Initialize the client.

        Args:
            broadcast_port: Port to listen for server broadcasts
        """
        self.broadcast_port = broadcast_port
        self.state = ClientState.STARTUP
        self.active_transfers = []
        self.transfer_stats = []
        self.current_server = None

        # Setup logging with colors
        logging.basicConfig(
            level=logging.INFO,
            format='\033[94m%(asctime)s - %(message)s\033[0m'
        )

        # Thread synchronization
        self.transfer_complete = threading.Event()
        self.stats_queue = queue.Queue()

    def _get_user_parameters(self) -> Tuple[int, int, int]:
        """Get transfer parameters from the user."""
        try:
            print("\033[95mPlease enter the following parameters:\033[0m")
            file_size = int(input("File size (in bytes): "))
            tcp_connections = int(input("Number of TCP connections: "))
            udp_connections = int(input("Number of UDP connections: "))
            return file_size, tcp_connections, udp_connections
        except ValueError as e:
            logging.error("Invalid input. Please enter numeric values.")
            sys.exit(1)

    def _setup_broadcast_listener(self) -> socket.socket:
        """Setup UDP socket for listening to server broadcasts."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) - commented for windows, uncomment to use in unix
        sock.bind(('', self.broadcast_port))
        return sock

    def _parse_offer_message(self, data: bytes) -> Tuple[str, int, int]:
        """Parse received offer message from server."""
        try:
            magic_cookie, msg_type, udp_port, tcp_port = struct.unpack(
                '!IbHH', data)
            if magic_cookie != self.MAGIC_COOKIE or msg_type != self.OFFER_MSG_TYPE:
                return None
            return udp_port, tcp_port
        except struct.error:
            return None

    def _handle_tcp_transfer(self, server_ip: str, server_port: int,
                             file_size: int, transfer_id: int):
        """Handle a TCP file transfer."""
        stats = TransferStats(transfer_id, "TCP", time.time())

        try:
            # Connect to server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((server_ip, server_port))

            # Send file size request
            sock.sendall(f"{file_size}\n".encode())

            # Receive data
            bytes_received = 0
            while bytes_received < file_size:
                data = sock.recv(4096)
                if not data:
                    break
                bytes_received += len(data)
                stats.bytes_received = bytes_received

            stats.end_time = time.time()
            self.stats_queue.put(stats)

        except Exception as e:
            logging.error(f"TCP transfer {transfer_id} error: {e}")
        finally:
            sock.close()
            self.transfer_complete.set()

    def _handle_udp_transfer(self, server_ip: str, server_port: int,
                             file_size: int, transfer_id: int):
        """Handle a UDP file transfer."""
        stats = TransferStats(transfer_id, "UDP", time.time())

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Send request
            request = struct.pack('!IbQ',
                                  self.MAGIC_COOKIE,
                                  self.REQUEST_MSG_TYPE,
                                  file_size)
            sock.sendto(request, (server_ip, server_port))

            # Receive data
            received_segments = set()
            last_packet_time = time.time()

            while True:
                try:
                    sock.settimeout(1.0)  # 1 second timeout
                    data, _ = sock.recvfrom(4096)

                    # Parse header
                    header_size = struct.calcsize('!IbQQ')
                    header = data[:header_size]
                    payload = data[header_size:]

                    magic_cookie, msg_type, total_segments, segment_num = struct.unpack(
                        '!IbQQ', header)

                    if magic_cookie != self.MAGIC_COOKIE or msg_type != self.PAYLOAD_MSG_TYPE:
                        continue

                    stats.total_packets = total_segments
                    received_segments.add(segment_num)
                    stats.bytes_received += len(payload)
                    stats.packets_received = len(received_segments)
                    last_packet_time = time.time()

                except socket.timeout:
                    if time.time() - last_packet_time >= 1.0:
                        break

            stats.end_time = time.time()
            self.stats_queue.put(stats)

        except Exception as e:
            logging.error(f"UDP transfer {transfer_id} error: {e}")
        finally:
            sock.close()
            self.transfer_complete.set()

    def _print_transfer_stats(self, stats: TransferStats):
        """Print statistics for a completed transfer."""
        duration = stats.end_time - stats.start_time
        speed = (stats.bytes_received * 8) / duration  # bits per second

        if stats.protocol == "TCP":
            logging.info(
                f"\033[92mTCP transfer #{stats.transfer_id} finished, "
                f"total time: {duration:.2f} seconds, "
                f"total speed: {speed:.1f} bits/second\033[0m"
            )
        else:
            success_rate = (stats.packets_received / stats.total_packets *
                            100) if stats.total_packets > 0 else 0
            logging.info(
                f"\033[92mUDP transfer #{stats.transfer_id} finished, "
                f"total time: {duration:.2f} seconds, "
                f"total speed: {speed:.1f} bits/second, "
                f"percentage of packets received successfully: {success_rate:.1f}%\033[0m"
            )

    def start(self):
        """Start the speed test client."""
        while True:
            try:
                if self.state == ClientState.STARTUP:
                    file_size, tcp_count, udp_count = self._get_user_parameters()
                    self.state = ClientState.LOOKING_FOR_SERVER
                    logging.info(
                        "Client started, listening for offer requests...")

                elif self.state == ClientState.LOOKING_FOR_SERVER:
                    # Listen for server offers
                    sock = self._setup_broadcast_listener()
                    data, (server_ip, _) = sock.recvfrom(1024)

                    ports = self._parse_offer_message(data)
                    if ports:
                        udp_port, tcp_port = ports
                        logging.info(f"Received offer from {server_ip}")
                        self.current_server = (server_ip, tcp_port, udp_port)
                        self.state = ClientState.SPEED_TEST
                    sock.close()

                elif self.state == ClientState.SPEED_TEST:
                    server_ip, tcp_port, udp_port = self.current_server
                    transfer_threads = []
                    transfer_id = 1

                    # Start TCP transfers
                    for _ in range(tcp_count):
                        thread = threading.Thread(
                            target=self._handle_tcp_transfer,
                            args=(server_ip, tcp_port, file_size, transfer_id)
                        )
                        transfer_threads.append(thread)
                        transfer_id += 1

                    # Start UDP transfers
                    for _ in range(udp_count):
                        thread = threading.Thread(
                            target=self._handle_udp_transfer,
                            args=(server_ip, udp_port, file_size, transfer_id)
                        )
                        transfer_threads.append(thread)
                        transfer_id += 1

                    # Start all transfers
                    for thread in transfer_threads:
                        thread.daemon = True
                        thread.start()

                    # Wait for all transfers to complete
                    for _ in transfer_threads:
                        stats = self.stats_queue.get()
                        self._print_transfer_stats(stats)

                    logging.info(
                        "All transfers complete, listening for offer requests")
                    self.state = ClientState.LOOKING_FOR_SERVER

            except KeyboardInterrupt:
                logging.info("Client shutting down...")
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                self.state = ClientState.LOOKING_FOR_SERVER


if __name__ == "__main__":
    client = SpeedTestClient()
    client.start()
