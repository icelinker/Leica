import socket
import threading
from CESAPI.packet import *

class LTPacketStream(threading.Thread):
    def __init__(self, sock):
        super().__init__()
        self.__sock = sock
        self.__running = True
        self.PACKET_BUFFER_SIZE = 1000
        self.__packet_buffer = []
        self.__head_index = 0
        self.__tail_index = 0

    def stop(self):
        self.__running = False

    def run(self):
        PACKET_HEADER_SIZE = 12  # lPacketSize, type
        packet_factory = LTPacketFactory()

        while self.__running:
            try:
                data_list = []
                data_count = 0
                while data_count < PACKET_HEADER_SIZE:
                    read_data = self.__sock.recv(PACKET_HEADER_SIZE-data_count)
                    data_list += [read_data]
                    data_count += len(read_data)
                header_data = b''.join(data_list)
                print('DEBUG: LTPacketStream received {} bytes from laser tracker.'.format(len(header_data)))
                packet_header = PacketHeaderT()
                packet_header.unpack(header_data)
    
                print('DEBUG: LTPacketStream header data: {}'.format(header_data))
                print('DEBUG: LTPacketStream lPacketSize: {}'.format(packet_header.lPacketSize))

                while data_count < packet_header.lPacketSize:
                    read_data = self.__sock.recv(packet_header.lPacketSize-PACKET_HEADER_SIZE)
                    data_list += [read_data]
                    data_count += len(read_data)
                data = b''.join(data_list)
                print('DEBUG: LTPacketStream data: {}'.format(data))
                print('DEBUG: LTPacketStream received a {} byte packet.'.format(len(data)))
                packet = packet_factory.packet(data)
    
                # append or overwrite an old packet with the new packet
                if len(self.__packet_buffer) < self.PACKET_BUFFER_SIZE:
                    self.__packet_buffer += [packet]
                    print('DEBUG: LTPacketStream appended a {} byte packet to the input stream buffer.'.format(len(data)))
                else:
                    self.__packet_buffer[self.__tail_index] = packet
                    print('DEBUG: LTPacketStream set a {} byte packet to the input stream buffer.'.format(len(data)))
    
                self.__tail_index += 1
                if self.__head_index == 0 and self.__tail_index == self.PACKET_BUFFER_SIZE:
                    # If the head is at index 0 and the tail is past the end of the buffer (full buffer),
                    # move up the head index (lose oldest packet).
                    self.__head_index = 1
                    print('DEBUG: LTPacketStream incremented the input stream buffer head index to {}.'.format(self.__tail_index))
                elif self.__tail_index == self.__head_index:
                    # If the tail is right behind the head (full buffer),
                    # move up the head index (lose oldest packet).
                    self.__head_index += 1
                    print('DEBUG: LTPacketStream incremented the input stream buffer head index to {}.'.format(self.__tail_index))
    
                if self.__tail_index == self.PACKET_BUFFER_SIZE:
                    # If the tail is past the end of the buffer, loop it around to 0.
                    self.__tail_index = 0
                    print('DEBUG: LTPacketStream set the input stream buffer tail index to {}.'.format(self.__tail_index))
            except socket.timeout as ste:
                print('DEBUG: LTPacketStream timed out waiting for laser tracker packets.')

    def read(self):
        if self.__tail_index == self.__head_index:
            print('DEBUG: LTPacketStream packet buffer is empty. Returning None.'.format(self.__tail_index))
            return None
        packet = self.__packet_buffer[self.__head_index]
        self.__head_index += 1
        if self.__head_index == self.PACKET_BUFFER_SIZE:
            # If the head is past the end of the buffer, loop it around to 0
            self.__head_index = 0
            print('DEBUG: LTPacketStream set the input stream buffer head index to {}.'.format(self.__head_index))
        return packet

    def write(self, packet):
        data = packet.pack()
        self.__sock.sendall(data)
        print('DEBUG: LTPacketStream sent a {} byte packet.'.format(len(data)))

class LTConnection(object):
    def __init__(self):
        self.__sock = None
        self.__stream_in = None

    def connect(self, host='localhost', port=700):
        if self.__sock != None:
            raise Exception("Repeat connection. Only one connection to the laser tracker is allowed at one time.")

        try:
            # Create a TCP/IP socket
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.settimeout(3)
    
            # Connect the socket to the port where the server is listening
            self.__sock.connect((host, port))

            self.__stream_in = LTPacketStream(self.__sock)
            self.__stream_in.start()
        except socket.timeout as ste:
            self.disconnect()
            print('DEBUG: Client timed out waiting for a connection to the laser tracker.')
            raise ste
    
        return self.__stream_in

    def disconnect(self):
        if self.__stream_in != None:
            self.__stream_in.stop()
            self.__stream_in.join()
        if self.__sock != None:
            self.__sock.close()
            self.__sock = None