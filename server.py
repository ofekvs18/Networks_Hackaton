#!/usr/bin/env python3
import socket
import struct
import threading
import time
import random
import logging
from typing import Tuple, Optional

class SpeedTestServer:
    
    # Constants for message formats
    MAGIC_COOKIE = 0xabcddcba
    OFFER_MSG_TYPE = 0x2
    REQUEST_MSG_TYPE = 0x3
    PAYLOAD_MSG_TYPE = 0x4
    
    def __init__(self, broadcast_port: int = 13117):
        """
        Initialize the server with configuration parameters.
        
        Args:
            broadcast_port: Port number for broadcasting offer messages
        """
        # Get server IP address
        self.server_ip = self._get_server_ip()
        
        # Initialize server ports
        self.broadcast_port = broadcast_port
        self.tcp_port = self._get_random_port()
        self.udp_port = self._get_random_port()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='\033[92m%(asctime)s - %(message)s\033[0m'
        )
        
        # Initialize sockets
        self.broadcast_socket = None
        self.tcp_socket = None
        self.udp_socket = None
        
    def _get_server_ip(self) -> str:
        """Get the server's IP address."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
        
    def _get_random_port(self) -> int:
        """Get a random available port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
            
    def _setup_broadcast_socket(self):
        """Setup the UDP broadcast socket for sending offers."""
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
    def _setup_tcp_socket(self):
        """Setup the TCP socket for handling speed test requests."""
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(('', self.tcp_port))
        self.tcp_socket.listen(5)
        
    def _setup_udp_socket(self):
        """Setup the UDP socket for handling speed test requests."""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', self.udp_port))
        
    def _create_offer_message(self) -> bytes:
        """
        Create an offer message according to the specified format.
        Returns:
            Bytes containing the formatted offer message
        """
        return struct.pack('!IbHH', 
                         self.MAGIC_COOKIE,
                         self.OFFER_MSG_TYPE,
                         self.udp_port,
                         self.tcp_port)
                         
    def _broadcast_offers(self):
        """Continuously broadcast offer messages."""
        while True:
            try:
                offer_message = self._create_offer_message()
                self.broadcast_socket.sendto(offer_message, 
                                          ('<broadcast>', self.broadcast_port))
                time.sleep(1)  # Send offer every second
            except Exception as e:
                logging.error(f"Error broadcasting offer: {e}")
                
    def _handle_tcp_client(self, client_socket: socket.socket, 
                          client_address: Tuple[str, int]):
        """
        Handle a TCP client connection for speed testing.
        
        Args:
            client_socket: Connected client socket
            client_address: Client address tuple (ip, port)
        """
        try:
            # Receive file size request
            file_size_str = client_socket.recv(1024).decode().strip()
            file_size = int(file_size_str)
            
            # Generate and send random data
            data = b'0' * file_size  # Generate dummy data
            client_socket.sendall(data)
            
        except Exception as e:
            logging.error(f"Error handling TCP client {client_address}: {e}")
        finally:
            client_socket.close()
            
    def _handle_udp_request(self, data: bytes, client_address: Tuple[str, int]):
        """
        Handle a UDP speed test request.
        
        Args:
            data: Request data received
            client_address: Client address tuple (ip, port)
        """
        try:
            # Parse request message
            magic_cookie, msg_type, file_size = struct.unpack('!IbQ', data)
            
            if magic_cookie != self.MAGIC_COOKIE or msg_type != self.REQUEST_MSG_TYPE:
                return
                
            # Send data in segments
            segment_size = 1024  # Size of each UDP segment
            total_segments = (file_size + segment_size - 1) // segment_size
            
            for segment_num in range(total_segments):
                remaining = min(segment_size, file_size - segment_num * segment_size)
                payload_data = b'0' * remaining
                
                # Create payload message
                header = struct.pack('!IbQQ', 
                                  self.MAGIC_COOKIE,
                                  self.PAYLOAD_MSG_TYPE,
                                  total_segments,
                                  segment_num)
                                  
                message = header + payload_data
                self.udp_socket.sendto(message, client_address)
                
        except Exception as e:
            logging.error(f"Error handling UDP request from {client_address}: {e}")
            
    def _handle_tcp_connections(self):
        """Accept and handle TCP connections."""
        while True:
            try:
                client_socket, client_address = self.tcp_socket.accept()
                thread = threading.Thread(target=self._handle_tcp_client,
                                       args=(client_socket, client_address))
                thread.daemon = True
                thread.start()
            except Exception as e:
                logging.error(f"Error accepting TCP connection: {e}")
                
    def _handle_udp_requests(self):
        """Handle incoming UDP requests."""
        while True:
            try:
                data, client_address = self.udp_socket.recvfrom(1024)
                thread = threading.Thread(target=self._handle_udp_request,
                                       args=(data, client_address))
                thread.daemon = True
                thread.start()
            except Exception as e:
                logging.error(f"Error receiving UDP request: {e}")
                
    def start(self):
        """Start the speed test server."""
        try:
            # Setup all sockets
            self._setup_broadcast_socket()
            self._setup_tcp_socket()
            self._setup_udp_socket()
            
            logging.info(f"Server started, listening on IP address {self.server_ip}")
            
            # Start broadcast thread
            broadcast_thread = threading.Thread(target=self._broadcast_offers)
            broadcast_thread.daemon = True
            broadcast_thread.start()
            
            # Start TCP handler thread
            tcp_thread = threading.Thread(target=self._handle_tcp_connections)
            tcp_thread.daemon = True
            tcp_thread.start()
            
            # Handle UDP requests in the main thread
            self._handle_udp_requests()
            
        except Exception as e:
            logging.error(f"Server error: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up server resources."""
        for socket_obj in [self.broadcast_socket, self.tcp_socket, self.udp_socket]:
            if socket_obj:
                try:
                    socket_obj.close()
                except:
                    pass

if __name__ == "__main__":
    server = SpeedTestServer()

    try:
        server.start()
    except KeyboardInterrupt:
        print("\033[93mServer shutting down...\033[0m")
