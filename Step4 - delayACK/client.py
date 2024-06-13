import socket  # for socket
import struct  # for packing and unpacking
import random   # random number
import sys # for command line arguments
import tcp # import TCPHeader class
import time # for sleep
import numpy.random as npr # for poisson distribution
from server import CWND, RWND

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes

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
# delayed ACK
delay = 600/1000 # ms

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
    # print client's information
    print("(Client's IP address, Client's Port number): ", client_socket.getsockname())
    
    client_port = random.randint(1024, 65535)   # randomly assign client port number
    # Craft SYN packet
    tcp_header = tcp.TCPHeader(client_port, PORT, 42, 79, 'S', 65535)
    packet = tcp_header.pack()
     # Send SYN packet with possible drops and retransmission
    while True:
        if not should_drop_packet():
            client_socket.send(packet)
            print("\tSYN packet sent: (seq=42, ACK=79, SYN=1), waiting for server's response...")
            break
        else:
            print("\tSYN packet dropped: (seq=42, ACK=79, SYN=1)")
            time.sleep(timeout / 1000)
            print("\tTimeOut for Retransmitting SYN packet...")
            continue

    # Wait for SYN-ACK packet
    # 沒收到timeout發生，於是請求Client重送
    while True:
        client_socket.settimeout(timeout / 1000)
        try:
            recvpkt = client_socket.recv(MSS)
            tcp_header = tcp.TCPHeader.unpack(recvpkt)
            time.sleep(delay)
            print("\t(*No more segment , ACK send*)")
            print("\t*Received SYN-ACK packet from server: ", tcp_header.__dict__)
            break  # Exit loop if packet received
        except socket.timeout:
            print("\tTimeout waiting for SYN-ACK, retransmitting SYN packet...")
            continue

    # Send ACK packet
    tcp_header = tcp.TCPHeader(client_port, PORT, 43, 80, 'A', 65535)
    packet = tcp_header.pack()
    # 加入掉包情況
    while True:
        if not should_drop_packet():
            client_socket.send(packet)
            print("\tACK packet sent: (seq=43, ACK=80)")
            break
        else:
            print("\tACK packet dropped: (seq=43, ACK=80)")
            time.sleep(timeout / 1000)
            print("\tRetransmitting ACK packet...")

    # Connection established
    print("(TCP connection established)\n")
    print("(Connected to server)")
    print("(Request tasks)")

    # Request tasks to Server
    idx = 1
    for i in range(3, len(sys.argv)):
        print("\n( task %d : %s )" %(idx, sys.argv[i]))
        idx += 1

        # send request packet
        tcp_header = tcp.TCPHeader(client_port, PORT, random.randint(100,5000), random.randint(100,5000), 
                                   'P', 65535, data=sys.argv[i])
        packet = tcp_header.pack()
        while True:
            if not should_drop_packet():
                client_socket.send(packet)
                print("\tRequest packet sent: ", tcp_header.__dict__)
            else:
                print("\tRequest packet dropped: ", tcp_header.__dict__)
                time.sleep(timeout / 1000)
                print("\tTimeOut for Retransmitting request packet...")
                continue
            break 

        result = ""   # used to store the result of the request
        # receive response packet (如果很多封包傳的話一直ACK)
        counter = 0 # 計算是第一個收到，還第二個收到
        packet_list = ["", ""] # 存放兩個封包一直循環(影響要印delayed ACK還是一般的ACK)
        
        while True:
            try:
                client_socket.settimeout(timeout / 1000)
                recvpkt = client_socket.recv(MSS)
            except socket.timeout:
                print("\tTimeout waiting for response packet, retransmitting request packet...")
                continue

            start = time.time() # delayed ACK收到開始算等待時間
            if len(recvpkt) < 22:   # 不能被正確分析要重讀
                recvpkt = client_socket.recv(MSS)

            tcp_header = tcp.TCPHeader.unpack(recvpkt)
            tcp_header_dict = tcp_header.__dict__.copy()  # 複製一份 __dict__
            del tcp_header_dict['data']  # 移除 data 字段

            print("\tReceived response packet: ", tcp_header_dict)

        # response ACK packet
            tcp_header2 = tcp.TCPHeader(client_port, PORT, 
                                        tcp_header.ack_number, tcp_header.sequence_number+len(tcp_header.data)+1, 'A', 65535)
            packet = tcp_header2.pack()
            while True:
                if not should_drop_packet():
                    break
                else:
                    print("\tACK packet dropped: ", tcp_header2.__dict__)
                    time.sleep(timeout / 1000)
                    print("\tRetransmitting ACK packet...")
        
            counter += 1
            end = time.time() # 等待時間
            time_elapsed = time_elapsed2 = 0    # initial
            if (counter %2 == 1):
                time_elapsed = (end - start)*1000   # ms
            else :
                time_elapsed2 = (end - start)*1000   # ms
                if time_elapsed2 - time_elapsed > 600: # delayed ACK
                    print("\t(*No more segment , Normal ACK send*)")
                    print("\t(*No more segment , Normal ACK send*)")
                else:
                    print("\t(*Delayed ACK send*)")
            
            client_socket.send(packet)
            
            result += tcp_header.data   # update result
            if tcp_header.checksum == 0:    # break condition
                break

        # print this request's result
        if sys.argv[i].endswith('.mp4') or sys.argv[i].endswith('.jpg'):
            print("\tResult: ", len(result), " bytes")
        else:
            print("\tResult: ", result)

    # Client no more tasks, so close the socket
    print("\n(No more tasks)")
    closepkt = tcp.TCPHeader(client_port, PORT, 5, 10, 'F', 65535)
    closepkt = closepkt.pack()
    # Send FIN packet with possible drops and retransmission
    while True:
        if not should_drop_packet():
            client_socket.send(closepkt)
            print("\tFIN packet sent")
        else:
            print("\tFIN packet dropped")
            time.sleep(timeout / 1000)
            print("\tTimeOut for Retransmitting FIN packet...")
            continue
        break

    # Receive Server FIN packet
    while True:
        client_socket.settimeout(timeout / 1000)
        try:
            recvpkt = client_socket.recv(MSS)
            time.sleep(delay) # delayed ACK
            print("\t(*No more segment , ACK send*)")
            tcp_header = tcp.TCPHeader.unpack(recvpkt)
            print("\tReceived FIN packet: ", tcp_header.__dict__)
            break
        except socket.timeout:
            print("\tTimeout waiting for Server-FIN packet, retransmitting Server-FIN packet...")

    # sent ACK packet
    closepkt = tcp.TCPHeader(client_port, PORT, tcp_header.ack_number, tcp_header.sequence_number+1, 'A', 65535)
    closepkt = closepkt.pack()
    while True:
        if not should_drop_packet():
            break
        else:
            print("\tACK packet dropped: ", tcp_header2.__dict__)
            time.sleep(timeout / 1000)
            print("\tRetransmitting ACK packet...")
    client_socket.send(closepkt)
    print("\tACK packet sent: ")
    print("End connection")
    time.sleep(2)   # 等一下才關掉
    client_socket.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)
    else:
        client_program()
