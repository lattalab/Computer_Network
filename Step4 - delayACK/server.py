import socket   # Import socket module
import threading
from concurrent.futures import ThreadPoolExecutor
import os  # for some os function
import math  # math.sqrt
import struct   # for packing and unpacking binary data
import sys  # for command line arguments
import re   # regular expression
import random   # random number
from numpy import random as npr  # for poisson distribution
import time  # for sleep
import tcp  # import the self-written tcp module

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes
HOST_IP = '127.0.0.1'   # The server's IP address

# 同步問題
lock = threading.Lock()

# Packet loss
PoissonMean = 0.000001 # 0.000001 , default is 0.000001 but test in other value
def should_drop_packet():
    # sampled from poisson distribution , if the value is greater than 0, then drop the packet
    num = npr.poisson(PoissonMean)
    if num > 0:
        return True
    else:
        return False

# set timeout = 2 * RTT
timeout = 2 * INITIAL_RTT  # ms
# Delayed ACK 
delay = 600 / 1000  # 600ms
# CWND = how many numbers of MSS
# Here, CWND also act as the character of Sender window to implement GO-BACK-N
CWND = 1
# Receiver window size indicating current empty buffer size
RWND = RECEIVER_BUFFER_SIZE 

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
    global RWND ,CWND
    payload = str(pkt.data)  # The payload of the packet
    # check FIN flag
    if pkt.flags == 'F':
        print("(trying to terminate TCP connection)")
        # delay ACK
        time.sleep(delay)
        print("\t(*No more new segment, ACK for FIN send*)")
        # Send Server-FIN packet
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, pkt.ack_number, pkt.sequence_number+1, 'F', 65535)
        packet = tcp_header.pack()
        while True:
            if not should_drop_packet():
                client_socket.send(packet)
                print("\tSent  Server-FIN packet: ", tcp_header.__dict__)
                break
            else:
                print("\tPacket dropped: ", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                print("\tTimeOut for Retransmitting Server-FIN packet...")
                continue
        return

    # check if a valid arithmetic operation
    if is_math_expression(payload):
        # pass result and wrap in packet
        result = perform_math(payload)
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                       pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(result))
        packet = tcp_header.pack()
        RWND -= MSS
        while True:
            if not should_drop_packet():
                client_socket.send(packet)
                print("\tSent packet: ", tcp_header.__dict__)
                break
            else:
                print("\tPacket dropped: ", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                print("\tTimeOut for Retransmitting packet...")
                continue
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
                RWND -= MSS
                # add timeout for transmitting packet
                while True:
                    if not should_drop_packet():
                        client_socket.send(packet)
                        print("\tSent packet: ", tcp_header.__dict__)
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        continue
                return 
            except: # DNS Failed
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data="DNS lookup failed")
                packet = tcp_header.pack()
                RWND -= MSS
                while True:
                    if not should_drop_packet():
                        client_socket.send(packet)
                        print("\tSent packet: ", tcp_header.__dict__)
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        continue
                return
        else:
            # file transmission (有需要分段送跟直接送的)
            if len(str(val)) > 1000:    # 扣除tcp header的長度 (1024 - 20 大約等於 1000)
                ack = pkt.sequence_number+1000+1
                seq = pkt.ack_number
                offset = 1000
                segments = [val[i:i+offset] for i in range(0, len(val), offset)]
                len_segments = len(segments); idx = 0
                def send_segment(i, segments, client_socket):
                    tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        seq, ack, 'P', 65535, data=segments[i], checksum=1)
                    packet = tcp_header.pack()
                    tcp_header_dict = tcp_header.__dict__.copy()  # 複製一份 __dict__
                    del tcp_header_dict['data']  # 移除 data 字段
                    # set timeout for transmitting packet
                    while True:
                        if not should_drop_packet():
                            client_socket.send(packet)
                            print("\tSent packet: ", tcp_header_dict)
                            break
                        else:
                            print("\tPacket dropped: ", tcp_header_dict)
                            time.sleep(timeout / 1000)
                            print("\tTimeOut for Retransmitting packet...")
                            continue
                    return 
                # 送CWND個封包
                while idx < len_segments:
                    counter = 0
                    for i in range(0, CWND):
                        start = time.time()
                        if idx < len_segments:
                            send_segment(idx, segments=segments, client_socket=client_socket)
                            idx += 1
                            end = time.time()
                            # 等待ACK
                            while True:
                                try:
                                    client_socket.settimeout(timeout / 1000)
                                    pkt_fromClient = client_socket.recv(MSS)
                                    pkt_fromClient = tcp.TCPHeader.unpack(pkt_fromClient)
                                    seq = pkt_fromClient.ack_number
                                    ack = pkt_fromClient.sequence_number+len(pkt_fromClient.data)+1
                                    break
                                except socket.timeout:
                                    print("\tTimeout waiting for Client-ACK, retransmitting packet...")
                                    time.sleep(timeout / 1000)
                                    continue
                            
                            counter += 1
                            
                            # 假設連線時雙方送方送成功，接收方接收成功，會馬上送封包回來 = 1 RTT
                            # 但送方可能drop、收方可能ACK drop
                            if ((counter%2) == 1):
                                time_elapsed = (end - start)*1000
                                if time_elapsed > 600:  # Not delayed ACK
                                    tcp_header_dict = pkt_fromClient.__dict__.copy()  # 複製一份 __dict__
                                    del tcp_header_dict['data']  # 移除 data 字段
                                    print("\t(*A Normal ACK*):")
                                    print ("\treceive packet : " , tcp_header_dict)
                            else:
                                time_elapsed2 = (end - start)*1000
                                if ((time_elapsed + time_elapsed2) < 600):  
                                    print("\t(*An delayed ACK received*)")
                                    tcp_header_dict = pkt_fromClient.__dict__.copy()  # 複製一份 __dict__
                                    del tcp_header_dict['data']  # 移除 data 字段
                                    print ("\treceive packet : " , tcp_header_dict)
                        else:
                            break
                    RWND -= counter*MSS
                    CWND += counter
                    print("\t(*CWND %d, RWND %d*)" %(CWND*MSS, RWND))

                # 控制封包，代表資料傳遞結束
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        seq, ack, 'P', 65535)
                packet = tcp_header.pack()
                # add timeout for transmitting packet
                while True:
                    if not should_drop_packet():
                        client_socket.send(packet)
                        print("\tSent packet: ", tcp_header.__dict__)
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        continue
                packet = tcp_header.pack()
            else:
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(val))
                packet = tcp_header.pack()
                RWND -= MSS
                # add timeout for transmitting packet
                while True:
                    if not should_drop_packet():
                        client_socket.send(packet)
                        tcp_header_dict = tcp_header.__dict__.copy()  # 複製一份 __dict__
                        del tcp_header_dict['data']  # 移除 data 字段
                        print("\tSent packet: ", tcp_header.__dict__)
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        continue
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
    global CWND, RWND
    # simulating the 3-way handshake
    # Receive SYN packet
    packet = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(packet)
    time.sleep(delay)   # delayed ACK
    print("\t(*No more new segment, ACK send*)")
    print("\tReceived SYN packet: ", tcp_header.__dict__)
    # Send SYN-ACK packet
    tcp_header = tcp.TCPHeader(tcp_header.destination_port, tcp_header.source_port, tcp_header.ack_number, tcp_header.sequence_number + 1 , 'A', 65535)
    packet = tcp_header.pack()
    # 加入掉包情況
    while True:
        if not should_drop_packet():
            client_socket.send(packet)
            print("\tSent SYN-ACK packet: ", tcp_header.__dict__)
            break
        else:
            print("\tSYN-ACK packet dropped: ", tcp_header.__dict__)
            time.sleep(timeout / 1000)
            print("\tTimeOut for Retransmitting SYN-ACK packet...")
            continue

    # Receive ACK packet
    while True:
        client_socket.settimeout(timeout / 1000)
        try:
            recvpkt = client_socket.recv(MSS)
            time.sleep(delay)   # delayed ACK
            print("\t(*No more new segment, ACK send*)")
            tcp_header = tcp.TCPHeader.unpack(recvpkt)
            print("\t*Received SYN-ACK packet from server: ", tcp_header.__dict__)
            break  # Exit loop if packet received
        except socket.timeout:
            print("\tTimeout waiting for Client-ACK, retransmitting SYN-ACK packet...")
        
    # TCP connection established
    print("(TCP connection established)\n")

    # send ACK for Request
    number = 1
    while True:
        client_socket.settimeout(None)  # Disable timeout
        pkt = client_socket.recv(MSS)  # 接收封包
        if not pkt:  # 如果收到空訊息，中斷迴圈
            break
        print("(Task %d)" %(number)); number += 1
        pkt = tcp.TCPHeader.unpack(pkt)
        time.sleep(delay)   # delayed ACK
        print("\t(*No more new segment, ACK send*)")
        print ("\treceive packet : " , pkt.__dict__)
        
        lock.acquire()
        handle_request(pkt , client_socket) # handle the request
        lock.release()

        # wait for client's ACK
        CWND += 1
        while True:
            client_socket.settimeout(timeout / 1000)
            try:
                pkt_fromClient = client_socket.recv(MSS)
                pkt_fromClient = tcp.TCPHeader.unpack(pkt_fromClient)
                print ("\treceive packet : " , pkt_fromClient.__dict__)
                break  # Exit loop if packet received
            except socket.timeout:
                print("\tTimeout waiting for Client-ACK, retransmitting packet...")
        print("\t(cwnd = %d , rwnd = %d)" %(CWND*MSS, RWND))
        print()
        ##############################################
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
            print("\t(Connecting)")
            global CWND , RWND
            CWND = 1 ; RWND = RECEIVER_BUFFER_SIZE
            print("\t(cwnd = %d , rwnd = %d)" %(CWND*MSS, RWND))  # 收到先初始化
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
