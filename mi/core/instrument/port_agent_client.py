#!/usr/bin/env python

"""
@package mi.core.instrument.port_agent_client
@file mi/core/instrument/port_agent_client
@author David Everett
@brief Client to connect to the port agent
and logging.
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import socket
import threading
import time
import struct
import array
import binascii

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentConnectionException

HEADER_SIZE = 16

"""
Packet Types
"""
DATA_FROM_DRIVER = 2

"""
Offsets into the packed header fields
"""
OFFSET_P_CHECKSUM_LOW = 6
OFFSET_P_CHECKSUM_HIGH = 7

"""
Offsets into the unpacked header fields
"""
OFFSET_UP_TYPE = 3
OFFSET_UP_LENGTH = 4
OFFSET_UP_CHECKSUM = 5

class PortAgentPacket():
    """
    An object that encapsulates the details packets that are sent to and
    received from the port agent.  
    """
    
    def __init__(self):
        self.__header = None
        self.__data = None
        self.__type = None
        self.__length = None
        self.__timestamp_low = None
        self.__timestamp_high = None
        self.__recv_checksum  = None
        self.__checksum = None
        
    def unpack_header(self, header):
        self.__header = header
        up_header = struct.unpack_from('>BBBBHHLL', header)
        self.__type = up_header[OFFSET_UP_TYPE]
        self.__length = int(up_header[OFFSET_UP_LENGTH]) - HEADER_SIZE
        self.__recv_checksum  = int(up_header[OFFSET_UP_CHECKSUM])

    def pack_header(self, packet_type):
        """
        Given a type and length, pack a header to be sent to the port agent.
        """
        if self.__data == None:
            log.error('pack_header: no data!')
            """
            TODO: throw an exception here?
            """
        else:
            self.__type = packet_type
            self.__length = len(self.__data)
            
            up_header = (0xa3, 0x9d, 0x7a, self.__type, self.__length + HEADER_SIZE, 0, 0, 0)
            #format = '>BBBBHHLL'
            format = '>BBBBHHLL'
            size = struct.calcsize(format)
            self.__header = array.array('B', '\0' * HEADER_SIZE)
            #struct.pack_into(format, self.__header, *up_header)
            #self.__header = bytearray("123456789abcdef")
            #crapola = "123456789abcdef"
            struct.pack_into(format, self.__header, 0, *up_header)
            print "here it is: ", binascii.hexlify(self.__header)
            
            """
            do the checksum last, since the checksum needs to include the
            populated header fields
            """
            self.__checksum = self.calculate_checksum()
        
    def attach_data(self, data):
        self.__data = data

    def calculate_checksum(self):
        checksum = 0
        for i in range(HEADER_SIZE):
            if i < OFFSET_P_CHECKSUM_LOW or i > OFFSET_P_CHECKSUM_HIGH:
                checksum += struct.unpack_from('B', str(self.__header[i]))[0]
                
        for i in range(self.__length):
            checksum += struct.unpack_from('B', str(self.__data[i]))[0]
            
        return checksum
            
                                
    def verify_checksum(self):
        checksum = 0
        for i in range(HEADER_SIZE):
            if i < OFFSET_P_CHECKSUM_LOW or i > OFFSET_P_CHECKSUM_HIGH:
                checksum += struct.unpack_from('B', self.__header[i])[0]
                
        for i in range(self.__length):
            checksum += struct.unpack_from('B', self.__data[i])[0]
            
        if checksum == self.__recv_checksum:
            self.__isValid = True
        else:
            self.__isValid = False
            
        log.info('checksum: %i.' %(checksum))

    def get_data_size(self):
        return self.__length
    
    def get_header(self):
        return self.__header
    
    def get_data(self):
        return self.__data
    
    def is_valid(self):
        return self.__isValid
                    

class PortAgentClient(object):
    """
    A port agent process client class to abstract the TCP interface to the 
    of port agent. From the instrument driver's perspective, data is sent 
    to the port agent with this client's send method, and data is received 
    asynchronously via a callback from this client's listener thread.
    """
    
    def __init__(self, host, port, delim=None):
        """
        Logger client constructor.
        """
        self.host = host
        self.port = port
        self.sock = None
        self.listener_thread = None
        self.stop_event = None
        self.delim = delim
        
    def init_comms(self, callback=None):
        """
        Initialize client comms with the logger process and start a
        listener thread.
        DHE: I'm going to need to establish two connections here: one 
        for the data connection and one for the command connection.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # This can be thrown here.
            # error: [Errno 61] Connection refused
            self.sock.connect((self.host, self.port))
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            """
            DHE: Setting socket to blocking to try something...
            """                        
            #self.sock.setblocking(0)
            self.sock.setblocking(1)
            self.user_callback = callback        
            self.listener_thread = Listener(self.sock, self.delim, self.callback)
            self.listener_thread.start()
            log.info('PortAgentClient.init_comms(): connected to port agent at %s:%i.'
                           % (self.host, self.port))        
        except:
            raise InstrumentConnectionException('Failed to connect to port agent at %s:%i.' 
                                                % (self.host, self.port))
        
    def stop_comms(self):
        """
        Stop the listener thread and close client comms with the device
        logger. This is called by the done function.
        """
        log.info('Logger shutting down comms.')
        self.listener_thread.done()
        self.listener_thread.join()
        #-self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.sock = None
        log.info('Logger client comms stopped.')

    def done(self):
        """
        Synonym for stop_comms.
        """
        self.stop_comms()

    def callback(self, paPacket):
        """
        A packet has been received from the port agent.  The packet is 
        contained in a packet object.  
        """
        paPacket.verify_checksum()
        self.user_callback(paPacket)
        
    def send(self, data):
        """
        Send data to the port agent.  (Instantiate a PortAgentPacket object and
        send the object to the port agent.)
        """
        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(DATA_FROM_DRIVER)
        
        header = paPacket.get_header()
        if self.sock:
            while len(header) > 0:
                try:
                    sent = self.sock.send(header)
                    gone = header[:sent]
                    header = header[sent:]
                except socket.error:
                    time.sleep(.1)

        if self.sock:
            while len(data) > 0:
                try:
                    sent = self.sock.send(data)
                    gone = data[:sent]
                    data = data[sent:]
                except socket.error:
                    time.sleep(.1)
                
class Listener(threading.Thread):
    """
    A listener thread to monitor the client socket data incoming from
    the port agent process. 
    """
    
    def __init__(self, sock, delim, callback=None):
        """
        Listener thread constructor.
        @param sock The socket to listen on.
        @param delim The line delimiter to split incoming lines on, used in
        debugging when no callback is supplied.
        @param callback The callback on data arrival.
        """
        threading.Thread.__init__(self)
        self.sock = sock
        self._done = False
        self.linebuf = ''
        self.delim = delim
        
        if callback:
            def fn_callback(paPacket):
                callback(paPacket)            
            self.callback = fn_callback
        else:
            self.callback = None

    def done(self):
        """
        Signal to the listener thread to end its processing loop and
        conclude.
        """
        self._done = True
        
    def run(self):
        """
        Listener thread processing loop. Block on receive from port agent.
        Receive HEADER_SIZE bytes to receive the entire header.  From that,
        get the length of the whole packet (including header); compute the
        length of the remaining data and read that.  
        NOTE (DHE): I've noticed in my testing that if my test server
        (simulating the port agent) goes away, the client socket (ours)
        goes into a CLOSE_WAIT condition and stays there for a long time. 
        When that happens, this method loops furiously and for a long time. 
        I have not had the patience to wait it out, so I don't know how long
        it will last.  When it happens though, 0 bytes are received, which
        should never happen unless something is wrong.  So if that happens,
        I'm considering it an error.
        """
        log.info('Logger client listener started.')
        while not self._done:
            try:
                received_header = False
                bytes_left = HEADER_SIZE
                while not received_header and not self._done: 
                    header = self.sock.recv(bytes_left)
                    bytes_left -= len(header)
                    if bytes_left == 0:
                        received_header = True
                        print "RECEIVED HEADER!"
                        paPacket = PortAgentPacket()         
                        paPacket.unpack_header(header)         
                        data_size = paPacket.get_data_size()
                        bytes_left = data_size
                    elif len(header) == 0:
                        log.error('Zero bytes received from port_agent socket')
                        self._done = True
                
                received_data = False
                while not received_data and not self._done: 
                    data = self.sock.recv(bytes_left)
                    bytes_left -= len(data)
                    if bytes_left == 0:
                        received_data = True
                        paPacket.attach_data(data)
                    elif len(data) == 0:
                        log.error('Zero bytes received from port_agent socket')
                        self._done = True

                if not self._done:
                    """
                    Should have complete port agent packet.
                    """
                    if self.callback:
                        self.callback(paPacket)
                    else:
                        log.error('No callback registered')

                
                #--------------------------------- OLD
                """
                data = self.sock.recv(4069)
                if self.callback:
                    self.callback(header, data)
                else:
                    if not self.delim:
                        print 'from device:%s' % repr(data)
                    else:
                        self.linebuf += data
                        lines = str.split(self.linebuf, self.delim)
                        self.linebuf = lines[-1]
                        lines = lines[:-1]
                        for item in lines:
                            print 'from device:%s' % item
                """
                #--------------------------------- END OLD
                
            except socket.error:
                time.sleep(.1)
        log.info('Logger client done listening.')

    def parse_packet(self, packet):
        log.debug('Logger client parse_packet')
        
        