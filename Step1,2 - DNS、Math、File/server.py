import socket   # Import socket module
import threading
from concurrent.futures import ThreadPoolExecutor
import os  # for some os function
import math  # math.sqrt
import struct   # for packing and unpacking binary data
import sys  # for command line arguments
import re   # regular expression
import random   # random number
import tcp  # import the self-written tcp module

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes
HOST_IP = '127.0.0.1'   # The server's IP address

# 同步問題
lock = threading.Lock()

# 是否有運算符號出現
def contains_math_operators(s, operators):
    return any(op in s for op in operators)

def is_math_expression(s):  # 判斷是否是合法的數學運算式
    math_operators = ['+', '-', '*', '/', '^', 'sqrt' , '0' , '1' , '2' , '3' , '4' , '5' , '6' , '7' , '8' , '9' , '.']
    # 如果是合法的domain name，Return False
    if is_domain_name(s):
        return False
    return contains_math_operators(s, math_operators)

def is_domain_name(s):
    # 用regular expression來判斷是否是合法的domain name (但檔案也會被誤判成domain name)
    domain_pattern = r'^[a-zA-Z0-9-]{1,63}(\.[a-zA-Z0-9-]{1,63})+$'
    return re.match(domain_pattern, s) is not None

def handle_request(pkt , client_socket):
    payload = str(pkt.data)  # The payload of the packet
    # check FIN flag
    if pkt.flags == 'F':
        print("(trying to terminate TCP connection)")
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, pkt.ack_number, pkt.sequence_number+1, 'A', 65535)
        packet = tcp_header.pack()
        client_socket.send(packet)
        print("\tSent ACK packet: ", tcp_header.__dict__)
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, pkt.ack_number, pkt.sequence_number+1, 'F', 65535)
        packet = tcp_header.pack()
        client_socket.send(packet)
        print("\tSent FIN packet: ", tcp_header.__dict__)
        return

    # check if a valid arithmetic operation
    if is_math_expression(payload):
        # pass result and wrap in packet
        result = perform_math(payload)
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                       pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(result))
        packet = tcp_header.pack()
        client_socket.send(packet)
        print("\tSent packet: ", tcp_header.__dict__)
        return
    else:
        # In this section, we will check if the payload is a domain name or a file name
        # If file not found, we will see this a DNS lookup.
        print("(try file transimission)")
        val = send_file(payload)
        if val == None:
            # perform DNS lookup
            try: 
                ip_address = socket.gethostbyname(payload)
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(ip_address))
                packet = tcp_header.pack()
                client_socket.send(packet)
                print("\tSent packet: ", tcp_header.__dict__)
                return 
            except:
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data="DNS lookup failed or File failed")
                packet = tcp_header.pack()
                client_socket.send(packet)
                print("\tSent packet: ", tcp_header.__dict__)
                return
        else:
            # file transmission (有需要分段送跟直接送的)
            if len(str(val)) > 1000:    # 扣除tcp header的長度 (1024 - 20 大約等於 1000)
                ack = pkt.sequence_number+1000+1
                seq = pkt.ack_number
                for i in range(0, len(val), 1000):
                    tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        seq, ack, 'P', 65535, data=val[i:i+1000], checksum=1)
                    packet = tcp_header.pack()
                    client_socket.send(packet)
                    # 等待ACK
                    pkt_fromClient = client_socket.recv(MSS)
                    pkt_fromClient = tcp.TCPHeader.unpack(pkt_fromClient)
                    seq = pkt_fromClient.ack_number
                    ack = pkt_fromClient.sequence_number+len(val[i+1000:i+2000])+1
                    print ("\treceive packet : " , pkt_fromClient.__dict__)

                # 控制封包，代表資料傳遞結束
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        seq, ack, 'P', 65535)
                packet = tcp_header.pack()
                client_socket.send(packet)
            else:
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(val))
                packet = tcp_header.pack()
                client_socket.send(packet)
                tcp_header_dict = tcp_header.__dict__.copy()  # 複製一份 __dict__
                del tcp_header_dict['data']  # 移除 data 字段
                print("\tSent packet: ", tcp_header_dict)
                return

def perform_math(exp):
    if 'sqrt' in exp:
        exp = exp.replace('sqrt', 'math.sqrt')  # replace sqrt with math.sqrt
    try:
        result = eval(exp)  # evaluate the expression
    except:
        result = "NAN"
    return result

def send_file(filename):
    base_root = '../files/'     # The directory where the files are stored
    try:
        with open(base_root + filename, 'rb') as f: # open the file in binary mode
            file_data = f.read()
            if filename.endswith('.txt'):   # txt要回傳裡面的資料
                return file_data.decode()
            else:
                return file_data # 其他直接傳回去，但之後會以檔案大小的形式當作結果
    except FileNotFoundError:
        print(f"File {filename} not found")
        return None
        
def handle_client(client_socket):
    # simulating the 3-way handshake
    # Receive SYN packet
    packet = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(packet)
    print("\tReceived SYN packet: ", tcp_header.__dict__)
    # Send SYN-ACK packet
    tcp_header = tcp.TCPHeader(tcp_header.destination_port, tcp_header.source_port, tcp_header.ack_number, tcp_header.sequence_number + 1 , 'A', 65535)
    packet = tcp_header.pack()
    client_socket.send(packet)
    print("\tSent SYN-ACK packet: ", tcp_header.__dict__)
    # Receive ACK packet
    packet = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(packet)
    print("\tReceived Client ACK packet: ", tcp_header.__dict__)
    print("(TCP connection established)\n")

    number = 1
    while True:
        pkt = client_socket.recv(MSS)  # 接收封包
        if not pkt:  # 如果收到空訊息，中斷迴圈
            break
        print("(Task %d)" %(number)); number += 1
        pkt = tcp.TCPHeader.unpack(pkt)
        print ("\treceive packet : " , pkt.__dict__)
        
        lock.acquire()
        handle_request(pkt , client_socket) # handle the request
        
        # wait for client's ACK
        pkt_fromClient = client_socket.recv(MSS)
        pkt_fromClient = tcp.TCPHeader.unpack(pkt_fromClient)
        print ("\treceive packet : " , pkt_fromClient.__dict__)
        print()
        lock.release()
        
    print("(No more tasks, closing connection)\n")
    client_socket.close()
    return

def server_program():
    # Create a TCP Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    PORT = int(sys.argv[1])
    print("Server local IP:", HOST_IP)
    print("My port: ", PORT , "\n")
    server_socket.bind((HOST_IP, PORT))
    server_socket.listen(5)

    all_threads = []

    try:
        while True:
            print("Waiting for Client...")
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr}")
            t = threading.Thread(target=handle_client, args=(client_socket,))
            t.start()

            all_threads.append(t)
    except KeyboardInterrupt:
        print(" Server stopped by ^C")
    finally:
        if server_socket:
            server_socket.close()
        for t in all_threads:
            t.join()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python server.py <PORT>")
        sys.exit(1)
    else :
        server_program()
