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
# CWND = how many numbers of MSS
# Here, CWND also act as the character of Sender window to implement GO-BACK-N
CWND = 1
# Receiver window size indicating current empty buffer size
RWND = RECEIVER_BUFFER_SIZE 

# 是否有運算符號出現
def contains_math_operators(s, operators):
    return any(op in s for op in operators)

def is_math_expression(s):  # 判斷是否是合法的數學運算式
    math_operators = ['+', '-', '*', '/', '^', 'sqrt' , '0' , '1' , '2' , '3' , '4' , '5' , '6' , '7' , '8' , '9']
    # 如果是合法的domain name，Return False
    if is_domain_name(s):
        return False
    return contains_math_operators(s, math_operators)

def is_domain_name(s):
    # 用regular expression來判斷是否是合法的domain name (但檔案也會被誤判成domain name)
    domain_pattern = r'^[a-zA-Z0-9-]{1,63}(\.[a-zA-Z0-9-]{1,63})+$'
    return re.match(domain_pattern, s) is not None

def RWND_update():
    global RWND
    # 假設一開始塞封包很快，之後就會開始慢下來，
    # Receiver端能一次大量處理完，於是在Buffer快滿的時候又馬上清光buffer
    if RWND < 10*MSS:
        RWND = RECEIVER_BUFFER_SIZE

dup_ACK = 0
def fastRecovery():
    global CWND, THRESHOLD, dup_ACK
    rand = random.randint(0,2)
    if rand == 0:
        print("\t Received Duplicated ACK")
        CWND = CWND + 1
        return 0
    elif  rand == 1:
        print("\t Timeout, transition to Slow start")
        THRESHOLD = CWND/2
        CWND = 1
        dup_ACK = 0
        return 1
    else:
        print("\t New ACK!, transition to Congestion Avoidance")
        CWND = THRESHOLD
        dup_ACK = 0
        return 2

def handle_request(pkt , client_socket):
    global RWND ,CWND , THRESHOLD
    payload = str(pkt.data)  # The payload of the packet
    timeoutFlag = 0 # 用來判斷是否有timeout發生
    # check FIN flag
    if pkt.flags == 'F':
        print("(trying to terminate TCP connection)")

        # Send Server-FIN packet
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, pkt.ack_number, pkt.sequence_number+1, 'F', 65535)
        packet = tcp_header.pack()
        while True:
            if not should_drop_packet():
                client_socket.send(packet)
                print("\tSent  Server-FIN packet: ", tcp_header.__dict__)
            else:
                print("\tPacket dropped: ", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                print("\tTimeOut for Retransmitting Server-FIN packet...")
                continue
        return

    # check if a valid arithmetic operation
    if is_math_expression(payload):
        RWND_update()
        # pass result and wrap in packet
        result = perform_math(payload)
        tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                       pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(result))
        packet = tcp_header.pack()
        RWND -= MSS
        while True:
            if not should_drop_packet():
                if CWND != 8:
                    client_socket.send(packet)
                    print("\tSent packet: ", tcp_header.__dict__)
                else:
                    print("\tLast packet dropped......")
                    tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(result)
                                , checksum=2)
                    packet = tcp_header.pack()
                    client_socket.send(packet)
                    pkt = client_socket.recv(MSS)   # get duplicate ACK
                    pkt = tcp.TCPHeader.unpack(pkt)
                    pkt_dict = pkt.__dict__
                    del pkt_dict['data']
                    print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 1)")
                    print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 2)")
                    print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 3)")
                    print()
                break
            else:
                print("\tPacket dropped: ", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                print("\tTimeOut for Retransmitting packet...")
                CWND = 1
                timeoutFlag = 1
                continue
        if timeoutFlag == 1:
            THRESHOLD /= 2; timeoutFlag = 0
        return
    else:
        # In this section, we will check if the payload is a domain name or a file name
        # If file not found, we will see this a DNS lookup.
        print("(try file transimission)")
        val = send_file(payload)
        if val == None:
            RWND_update()
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
                        if CWND != 8:
                            client_socket.send(packet)
                            print("\tSent packet: ", tcp_header.__dict__)
                        else:
                            print("\tLast packet dropped......")
                            tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(ip_address)
                                        , checksum=2)
                            packet = tcp_header.pack()
                            client_socket.send(packet)
                            pkt = client_socket.recv(MSS)   # get duplicate ACK
                            pkt = tcp.TCPHeader.unpack(pkt)
                            pkt_dict = pkt.__dict__
                            del pkt_dict['data']
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 1)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 2)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 3)")
                            print()
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        CWND = 1; timeoutFlag =1
                        continue
                if timeoutFlag == 1:
                    THRESHOLD /= 2; timeoutFlag = 0
                return 
            except: # DNS Failed
                RWND_update()
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data="DNS lookup failed")
                packet = tcp_header.pack()
                RWND -= MSS
                while True:
                    if not should_drop_packet():
                        if CWND != 8:
                            client_socket.send(packet)
                            print("\tSent packet: ", tcp_header.__dict__)
                        else:
                            print("\tLast packet dropped......")
                            tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data="DNS lookup failed"
                                        , checksum=2)
                            packet = tcp_header.pack()
                            client_socket.send(packet)
                            pkt = client_socket.recv(MSS)   # get duplicate ACK
                            pkt = tcp.TCPHeader.unpack(pkt)
                            pkt_dict = pkt.__dict__
                            del pkt_dict['data']
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 1)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 2)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 3)")
                            print()
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        CWND = 1; timeoutFlag = 1
                        continue
                if timeoutFlag == 1:
                    THRESHOLD /= 2; timeoutFlag = 0
                return
        else:
            # file transmission (有需要分段送跟直接送的)
            if len(str(val)) > 1000:    # 扣除tcp header的長度 (1024 - 20 大約等於 1000)
                ack = pkt.sequence_number+1000+1
                seq = pkt.ack_number
                offset = 1000
                segments = [val[i:i+offset] for i in range(0, len(val), offset)]
                len_segments = len(segments); idx = 0
                def send_segment(i, segments, client_socket, Checksum = 1):
                    tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        seq, ack, 'P', 65535, data=segments[i], checksum=Checksum)
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
                    RWND_update()
                    counter = 0
                    for i in range(0, CWND):
                        counter += 1 # 紀錄這次的CWND總值
                        start = time.time()
                        if idx < len_segments:
                            # 快速重傳
                            if CWND + counter -1 != 8:
                                send_segment(idx, segments=segments, client_socket=client_socket)
                            else:
                                print("\tLast packet dropped......")
                                send_segment(idx, segments=segments, client_socket=client_socket, Checksum=2)
                                pkt = client_socket.recv(MSS)
                                pkt = tcp.TCPHeader.unpack(pkt)
                                pkt_dict = pkt.__dict__
                                del pkt_dict['data']
                                print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 1)")
                                print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 2)")
                                print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 3)")
                                # state transition
                                while True:
                                    value = fastRecovery()
                                    if value >0:
                                        break
                                print()

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
                                    print ("\treceive packet : " , pkt_fromClient.__dict__)
                                    break
                                except socket.timeout:
                                    print("\tTimeout waiting for Client-ACK, retransmitting packet...")
                                    THRESHOLD /=2; timeoutFlag = 1
                                    continue
                        else:
                            break

                    if timeoutFlag == 1:
                        THRESHOLD /= 2; timeoutFlag = 0
                    RWND -= counter*MSS
                    if CWND > int(THRESHOLD/MSS):  # CWND threshold , transistion to congestion avoidance
                        counter =1
                    CWND += counter
                    print("\t(*CWND %d, RWND %d, THRESHOLD %d*)" %(CWND*MSS, RWND , THRESHOLD))

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
                        CWND = 1; timeoutFlag = 1
                        continue
                packet = tcp_header.pack()
                if timeoutFlag == 1:
                    THRESHOLD /= 2; timeoutFlag = 0
            else:
                RWND_update()
                tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(val))
                packet = tcp_header.pack()
                RWND -= MSS
                # add timeout for transmitting packet
                while True:
                    if not should_drop_packet():
                        if CWND != 8:
                            client_socket.send(packet)
                            tcp_header_dict = tcp_header.__dict__.copy()  # 複製一份 __dict__
                            del tcp_header_dict['data']  # 移除 data 字段
                            print("\tSent packet: ", tcp_header.__dict__)
                        else:
                            print("\tLast packet dropped......")
                            tcp_header = tcp.TCPHeader(pkt.destination_port, pkt.source_port, 
                                        pkt.ack_number, pkt.sequence_number+len(pkt.data)+1, 'P', 65535, data=str(val)
                                        , checksum=2)
                            packet = tcp_header.pack()
                            client_socket.send(packet)
                            pkt = client_socket.recv(MSS)   # get duplicate ACK
                            pkt = tcp.TCPHeader.unpack(pkt)
                            pkt_dict = pkt.__dict__
                            del pkt_dict['data']
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 1)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 2)")
                            print("\t(*receive packet : " , pkt_dict , "*) (duplicate ACK 3)")
                            print()
                        break
                    else:
                        print("\tPacket dropped: ", tcp_header.__dict__)
                        time.sleep(timeout / 1000)
                        print("\tTimeOut for Retransmitting packet...")
                        CWND = 1; timeoutFlag = 1
                        continue
                if timeoutFlag == 1:
                    THRESHOLD /= 2; timeoutFlag = 0
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
    print("(Receiving SYN packet from client)")
    print("\tReceived SYN packet: ", tcp_header.__dict__)
    # Send SYN-ACK packet
    tcp_header = tcp.TCPHeader(tcp_header.destination_port, tcp_header.source_port, tcp_header.ack_number, tcp_header.sequence_number + 1 , 'A', 65535)
    packet = tcp_header.pack()
    # 加入掉包情況
    while True:
        if not should_drop_packet():
            if CWND != 8:
                client_socket.send(packet)
                print("\tSent SYN-ACK packet: ", tcp_header.__dict__)
            else:
                print("\tLast packet dropped......")
                print("\t3 Duplicate ACK received", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                time.sleep(timeout / 1000)
                time.sleep(timeout / 1000)
                client_socket.send(packet)
                print("\t(*Fast Retransmit*)")
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
        print ("\treceive packet : " , pkt.__dict__)
        
        lock.acquire()
        handle_request(pkt , client_socket) # handle the request
        
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
        print("\t(cwnd = %d , rwnd = %d , THRESHOLD %d)" %(CWND*MSS, RWND , THRESHOLD))
        print()
        lock.release()
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
            global CWND , RWND , THRESHOLD
            THRESHOLD = 64 * 1024  # bytes
            print("\t(cwnd = %d , rwnd = %d , Threshold %d)" %(CWND*MSS, RWND, THRESHOLD))  # 收到先初始化
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
