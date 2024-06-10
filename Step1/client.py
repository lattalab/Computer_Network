import socket
import struct
import random
import sys
import tcp

# Define parameters
INITIAL_RTT = 30  # milliseconds
MSS = 1024  # bytes
THRESHOLD = 64 * 1024  # bytes
RECEIVER_BUFFER_SIZE = 512 * 1024  # bytes

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
    
    client_port = random.randint(1024, 65535)   # randomly assign client port number
    # Craft SYN packet
    tcp_header = tcp.TCPHeader(client_port, PORT, 42, 79, 'S', 65535)
    packet = tcp_header.pack()
    client_socket.send(packet)
    print("\tSYN packet sent: (seq=42, ACK=79, SYN=1), waiting for server's response...")
    # Receive SYN-ACK packet
    recvpkt = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(recvpkt)
    print("\t*Received SYN-ACK packet from server: ", tcp_header.__dict__)
    # Send ACK packet
    tcp_header = tcp.TCPHeader(client_port, PORT, 43, 80, 'A', 65535)
    packet = tcp_header.pack()
    client_socket.send(packet)
    print("\tACK packet sent: (seq=43, ACK=80)")

    # Connection established
    print("(TCP connection established)\n")
    print("(Connected to server)")
    print("(Request tasks)")

    idx = 1
    for i in range(3, len(sys.argv)):
        print("\n( task %d : %s )" %(idx, sys.argv[i]))
        idx += 1

        # send request packet
        tcp_header = tcp.TCPHeader(client_port, PORT, random.randint(100,5000), random.randint(100,5000), 
                                   'P', 65535, data=sys.argv[i])
        packet = tcp_header.pack() 
        client_socket.send(packet)
        print("\tRequest packet sent: ", tcp_header.__dict__)
        result = ""   # used to store the result of the request
        # receive response packet
        while True:
            recvpkt = client_socket.recv(MSS)
            
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
            print("\tACK packet sent: ", tcp_header2.__dict__)
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
    client_socket.send(closepkt)
    print("\tFIN packet sent")
    # Receive Server ACK packet
    recvpkt = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(recvpkt)
    print("\tReceived ACK packet: ", tcp_header.__dict__)
    # Receive Server FIN packet
    recvpkt = client_socket.recv(MSS)
    tcp_header = tcp.TCPHeader.unpack(recvpkt)
    print("\tReceived FIN packet: ", tcp_header.__dict__)
    # sent ACK packet
    closepkt = tcp.TCPHeader(client_port, PORT, tcp_header.ack_number, tcp_header.sequence_number+1, 'A', 65535)
    closepkt = closepkt.pack()
    client_socket.send(closepkt)
    print("\tACK packet sent: ")
    print("End connection")
    client_socket.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)
    else:
        client_program()
