import socket
import threading
import os
import hashlib
import math
import struct
import sys

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes
HOST_IP = '127.0.0.1'   # The server's IP address

def handle_client(client_socket, addr):
    try:
        print(f"Handling client {addr}")

        # Receive the type of job requested
        job_type = client_socket.recv(1024).decode()

        if job_type == 'DNS':
            domain_name = client_socket.recv(1024).decode()
            ip_address = socket.gethostbyname(domain_name)
            # print(socket.gethostbyname("hsnl.cse.nsysu.edu.tw"))
            # 在做exception
            client_socket.send(ip_address.encode())

        elif job_type == 'MATH':
            operation = client_socket.recv(1024).decode()
            numbers = struct.unpack('dd', client_socket.recv(16))
            result = perform_math(operation, numbers)
            client_socket.send(str(result).encode())

        elif job_type == 'FILE':
            filename = client_socket.recv(1024).decode()
            send_file(client_socket, filename)
        
    except Exception as e:
        print(f"Exception handling client {addr}: {e}")
    finally:
        client_socket.close()
        print(f"Client {addr} disconnected")

def perform_math(operation, numbers):
    a, b = numbers
    if operation == 'ADD':
        return a + b
    elif operation == 'SUBTRACT':
        return a - b
    elif operation == 'MULTIPLY':
        return a * b
    elif operation == 'DIVIDE':
        return a / b
    elif operation == 'POWER':
        return math.pow(a, b)
    elif operation == 'SQRT':
        return math.sqrt(a)

def send_file(client_socket, filename):
    try:
        with open(filename, 'rb') as f:
            file_data = f.read()
            checksum = hashlib.sha256(file_data).hexdigest()
            client_socket.send(checksum.encode())
            client_socket.sendall(file_data)
    except FileNotFoundError:
        client_socket.send(b'FILE NOT FOUND')

def server_program():
    # Create a TCP Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    PORT = int(sys.argv[1])
    print("My port: ", PORT , "\n")
    server_socket.bind((HOST_IP, PORT))
    server_socket.listen(1)
    client_socket, addr = server_socket.accept()

    # simulating the 3-way handshake
    print("(Waiting for client connection)")
    recvpkt = client_socket.recv(RECEIVER_BUFFER_SIZE)
    print("*Received SYN packet: ", recvpkt.decode())
    print("Sending SYN-ACK packet: (seq=43, ACK=79, SYN=1) to client")
    client_socket.send("seq=79, ACK=43, SYN=1".encode())
    recvpkt = client_socket.recv(RECEIVER_BUFFER_SIZE)
    print("*Received ACK packet from client: ", recvpkt.decode())
    print("Server started and listening on port %d"%(PORT))

    # TCP congestion flow stage
    cwnd = MSS  # default to 1 MSS
    rwnd = RECEIVER_BUFFER_SIZE # current empty buffer size
    threshold = THRESHOLD
    print("\nIn slows start mode , cwnd = %d , rwnd = %d , threshold = %d" % (cwnd, rwnd, threshold))

    # while True:
    #     print ('Connected by ', addr)
    #     data = client_socket.recv(1024)
    #     print ("Client recv data : %s " % (data.decode()))

    #     client_socket.send("ACK!".encode())
        # client_handler = threading.Thread(target=handle_client, args=(client_socket, addr))
        # client_handler.start()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python server.py <PORT>")
        sys.exit(1)
    else :
        server_program()
