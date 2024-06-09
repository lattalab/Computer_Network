import socket
import struct
import random
import sys

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes

def request_dns(domain_name):
    client_socket.send(b'DNS')
    client_socket.send(domain_name.encode())
    ip_address = client_socket.recv(1024).decode()
    print(f"DNS result for {domain_name}: {ip_address}")

def request_math(operation, a, b):
    client_socket.send(b'MATH')
    client_socket.send(operation.encode())
    client_socket.send(struct.pack('dd', a, b))
    result = client_socket.recv(1024).decode()
    print(f"Result of {operation} on {a} and {b}: {result}")

def request_file(filename):
    client_socket.send(b'FILE')
    client_socket.send(filename.encode())
    checksum = client_socket.recv(1024).decode()
    file_data = client_socket.recv(512 * 1024)
    if hashlib.sha256(file_data).hexdigest() == checksum:
        print(f"File {filename} received successfully with valid checksum")
    else:
        print(f"File {filename} received with invalid checksum")

def client_program():
    global client_socket
    # Create a TCP Socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    HOST = sys.argv[1]  # The server's IP address given by argv[1]
    PORT = int(sys.argv[2]) # The server's port number given by argv[2]
    print("Server's IP address: ", HOST)
    print("Server's port number: ", PORT)
    print("\n(Connecting to server)")
    client_socket.connect((HOST, PORT))
    
    # Craft SYN packet
    ACK = client_socket.send("seq=42, ACK=79, SYN=1".encode())
    print("SYN packet sent: (seq=42, ACK=79, SYN=1), waiting for server's response...")
    # Receive SYN-ACK packet
    recvpkt = SYN_ACK = client_socket.recv(RECEIVER_BUFFER_SIZE).decode()
    print("*Received SYN-ACK packet from server: ", recvpkt)
    # Send ACK packet
    print("Sending ACK packet to server which response to SYNACK")
    ACKforSYNACK = client_socket.send("seq=43, ACK=80".encode())
    print("ACK packet sent: (seq=43, ACK=80)")

    # Connection established
    print("TCP connection established\n")
    print("(Connected to server)")
    print("(Request tasks)")

    idx = 1
    for i in range(3, len(sys.argv)):
        print("task %d : %s" %(idx, sys.argv[i]))
        idx += 1


    # # Example usage:
    # request_dns('hsnl.cse.nsysu.edu.tw')
    # request_math('ADD', 5, 10)
    # request_file('example.txt')

    client_socket.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)
    else:
        client_program()
