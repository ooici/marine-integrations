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
import datetime
import struct
import array
import binascii

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentConnectionException

HEADER_SIZE = 16 # BBBBHHLL = 1 + 1 + 1 + 1 + 2 + 2 + 4 + 4 = 16


"""
Packet Types
"""
DATA_FROM_DRIVER = 2


OFFSET_P_CHECKSUM_LOW = 6
OFFSET_P_CHECKSUM_HIGH = 7

"""
Offsets into the unpacked header fields
"""
SYNC_BYTE1_INDEX = 0
SYNC_BYTE1_INDEX = 1
SYNC_BYTE1_INDEX = 2
TYPE_INDEX = 3
LENGTH_INDEX = 4 # packet size (including header)
CHECKSUM_INDEX = 5
TIMESTAMP_INDEX = 6

SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[0:3])
NTP_EPOCH = datetime.date(1900, 1, 1)
NTP_DELTA = (SYSTEM_EPOCH - NTP_EPOCH).days * 24 * 3600

class PortAgentPacket():
    """
    An object that encapsulates the details packets that are sent to and
    received from the port agent.
    https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+Port+Agent+Design
    """
    
    def __init__(self):
        self.__header = None
        self.__data = None
        self.__type = None
        self.__length = None
        self.__port_agent_timestamp = None
        self.__recv_checksum  = None
        self.__checksum = None

        
    def unpack_header(self, header):
        self.__header = header
        #@TODO may want to switch from big endian to network order '!' instead of '>' note network order is big endian.
        # B = unsigned char size 1 bytes
        # H = unsigned short size 2 bytes
        # L = unsigned long size 4 bytes
        # d = float size8 bytes
        variable_tuple = struct.unpack_from('>BBBBHHd', header)
        # change offset to index.
        self.__type = variable_tuple[TYPE_INDEX]
        self.__length = int(variable_tuple[LENGTH_INDEX]) - HEADER_SIZE
        self.__recv_checksum  = int(variable_tuple[CHECKSUM_INDEX])
        self.__port_agent_timestamp = variable_tuple[TIMESTAMP_INDEX]


    def pack_header(self):
        """
        Given a type and length, pack a header to be sent to the port agent.
        """
        if self.__data == None:
            log.error('pack_header: no data!')
            """
            TODO: throw an exception here?
            """
        else:
            self.__type = DATA_FROM_DRIVER
            self.__length = len(self.__data)
            self.__port_agent_timestamp = time.time() + NTP_DELTA


            variable_tuple = (0xa3, 0x9d, 0x7a, self.__type, self.__length + HEADER_SIZE, 0x0000, self.__port_agent_timestamp)

            # B = unsigned char size 1 bytes
            # H = unsigned short size 2 bytes
            # L = unsigned long size 4 bytes
            # d = float size 8 bytes
            format = '>BBBBHHd'
            size = struct.calcsize(format)
            self.__header = array.array('B', '\0' * HEADER_SIZE)
            struct.pack_into(format, self.__header, 0, *variable_tuple)
            #print "here it is: ", binascii.hexlify(self.__header)
            
            """
            do the checksum last, since the checksum needs to include the
            populated header fields
            """
            self.__checksum = self.calculate_checksum()

            self.__header[OFFSET_P_CHECKSUM_HIGH] = self.__checksum & 0x00ff
            self.__header[OFFSET_P_CHECKSUM_LOW] = (self.__checksum & 0xff00) >> 8

        
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
            
        #log.debug('checksum: %i.' %(checksum))

    def get_data_size(self):
        return self.__length
    
    def get_header(self):
        return self.__header

    def get_data(self):
        return self.__data

    def get_timestamp(self):
        return self.__port_agent_timestamp

    def get_header_length(self):
        return self.__length

    def get_header_type(self):
        return self.__type

    def get_header_checksum(self):
        return self.__checksum

    def get_header_recv_checksum (self):
        return self.__recv_checksum

    def get_as_dict(self):
        """
        Return a dictionary representation of a port agent packet
        """
        return {
            'type': self.__type,
            'length': self.__length,
            'checksum': self.__checksum,
            'raw': self.__data
        }

    def is_valid(self):
        return self.__isValid
                    

class PortAgentClient(object):
    """
    A port agent process client class to abstract the TCP interface to the 
    of port agent. From the instrument driver's perspective, data is sent 
    to the port agent with this client's send method, and data is received 
    asynchronously via a callback from this client's listener thread.
    """
    
    def __init__(self, host, port, cmd_port, delim=None):
        """
        Logger client constructor.
        """
        self.host = host
        self.port = port
        self.cmd_port = cmd_port
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
            self.sock.setblocking(0)
            self.user_callback = callback        
            self.listener_thread = Listener(self.sock, self.delim, self.callback)
            self.listener_thread.start()
            log.info('PortAgentClient.init_comms(): connected to port agent at %s:%i.'
                           % (self.host, self.port))        
        except:
            log.error("init_comms(): Exception occurred.", exc_info=True)
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

    def send_break(self):
        """
        Command the port agent to send a break
        """
        self._command_port_agent('break')

    def _command_port_agent(self, cmd):
        """
        Command the port agent.  We connect to the command port, send the command
        and then disconnect.  Connection is not persistent
        @raise InstrumentConnectionException if cmd_port is missing.  We don't
                        currently do this on init  where is should happen because
                        some instruments wont set the  command port quite yet.
        """
        try:
            if(not self.cmd_port):
                raise InstrumentConnectionException("Missing port agent command port config")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.cmd_port))
            log.info('PortAgentClient.init_comms(): connected to port agent at %s:%i.'
                     % (self.host, self.cmd_port))
            self.send(cmd, sock)
            sock.close()
        except Exception as e:
            log.error("send_break(): Exception occurred.", exc_info=True)
            raise InstrumentConnectionException('Failed to connect to port agent command port at %s:%i (%s).'
                                                % (self.host, self.cmd_port, e))


    def send(self, data, sock=None):
        """
        Send data to the port agent.
        """
        if(not sock):
            sock = self.sock

        if sock:
            while len(data) > 0:
                try:
                    sent = sock.send(data)
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

            except socket.error:
                time.sleep(.1)
        log.info('Logger client done listening.')

    def parse_packet(self, packet):
        log.debug('Logger client parse_packet')
        
        