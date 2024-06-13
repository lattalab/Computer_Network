import struct

class TCPHeader:
    def __init__(self, source_port, destination_port, sequence_number, ack_number, flags, rcv_window, data =None, header_length=5, checksum=0):
        self.source_port = int(source_port)  # 2 bytes
        self.destination_port = int(destination_port)  # 2 bytes
        self.sequence_number = int(sequence_number)  # 4 bytes
        self.ack_number = int(ack_number)  # 4 bytes
        self.flags = flags  # 6 bits, but we will use character(1 byte) to represent it
        self.header_length = int(header_length)  # 4 bits, use word number to calculate header length
        self.rcv_window = int(rcv_window)  # 2 bytes
        self.checksum = int(checksum)  # 2 bytes
        self.data = data

    def pack(self):
        if self.data is None:
            self.data = b''
        elif type(self.data) == str: 
            self.data = bytes(self.data, 'utf-8')
        return struct.pack('!HHLLBBHHI%ds' %(len(self.data)) , self.source_port, self.destination_port, 
                           self.sequence_number, self.ack_number, ord(self.flags), self.header_length, 
                           self.rcv_window, self.checksum, len(self.data), self.data)

    @classmethod
    def unpack(cls, data):
         # Unpack a bit at a time
        (source_port, destination_port, sequence_number, ack_number, flags,
         header_length, rcv_window, checksum, data_length) = struct.unpack('!HHLLBBHHI', data[:22])
        data_bytes = data[22:]
        flags = chr(flags)  # convert to character
        return cls(source_port, destination_port, sequence_number, ack_number,
                   flags, rcv_window, data_bytes.decode('latin-1'), header_length, checksum)