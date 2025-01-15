# Router Rangers Speed Test 🚀

## Introduction
Router Rangers Speed Test is a network performance testing tool that allows you to compare UDP and TCP download speeds on your network. This client-server application enables simultaneous testing of multiple connections and provides detailed performance metrics.

## Features
- Multi-protocol support (TCP and UDP)
- Multiple concurrent connections
- Real-time transfer statistics
- Automatic server discovery
- Detailed performance metrics
- Cross-platform compatibility

## Requirements
- Python 3.x
- No external dependencies required (uses standard library only)

## Installation
1. Clone the repository:

2. No additional installation steps required!

## Usage

### Starting the Server
Run the server script:
```bash
python server.py
```
The server will automatically:
- Start listening for client connections
- Begin broadcasting its presence
- Display its IP address and status

### Running the Client
Run the client script:
```bash
python client.py
```
The client will prompt you for:
1. File size for the speed test
2. Number of TCP connections
3. Number of UDP connections

### Example Output
```
Server started, listening on IP address 172.1.0.4

Client started, listening for offer requests...
Received offer from 172.1.0.4
TCP transfer #1 finished, total time: 3.55 seconds, total speed: 5.4 bits/second
UDP transfer #2 finished, total time: 3.55 seconds, total speed: 5.4 bits/second, percentage of packets received successfully: 95%
```

## Protocol Specifications

### Offer Message Format
- Magic cookie (4 bytes): 0xabcddcba
- Message type (1 byte): 0x2
- Server UDP port (2 bytes)
- Server TCP port (2 bytes)

### Request Message Format
- Magic cookie (4 bytes): 0xabcddcba
- Message type (1 byte): 0x3
- File size (8 bytes)

### Payload Message Format
- Magic cookie (4 bytes): 0xabcddcba
- Message type (1 byte): 0x4
- Total segment count (8 bytes)
- Current segment count (8 bytes)
- Payload data

## Architecture
- **Server**: Multi-threaded design handling broadcast announcements and client connections
- **Client**: State machine with three states (Startup, Looking for Server, Speed Test)
- **Error Handling**: Comprehensive error handling for network issues and invalid inputs
- **Statistics**: Detailed performance metrics for each transfer

## Implementation Details
- Non-blocking architecture
- Proper resource cleanup
- Efficient memory usage
- Thread synchronization for concurrent transfers
- Timeout handling for UDP transfers

## Running Tests on Different Machines
1. Ensure both machines are on the same network
2. Start the server on one machine
3. Run the client on another machine
4. The client will automatically discover the server

## Known Issues
- Windows OS doesn't support SO_REUSEPORT (not needed when running on different machines) - To run multiple clients on the same Unix computer, uncomment line 83 in the client.py file
- Large file transfers might require additional memory management


## Acknowledgments
- Created for the Intro to Nets 2025 Hackathon
- Special thanks to the course staff

## Contact
Router Rangers Team - Maayan Weizman & Ofek Vilkerstone