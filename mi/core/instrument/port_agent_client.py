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
import errno
import threading
import time
import datetime
import struct
import array
import binascii
import ctypes
import subprocess

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentConnectionException

HEADER_SIZE = 16 # BBBBHHLL = 1 + 1 + 1 + 1 + 2 + 2 + 4 + 4 = 16


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
TIMESTAMP_UPPER_INDEX = 6
TIMESTAMP_LOWER_INDEX = 7

SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[0:3])
NTP_EPOCH = datetime.date(1900, 1, 1)
NTP_DELTA = (SYSTEM_EPOCH - NTP_EPOCH).days * 24 * 3600


"""
NOTE!!! MAX_RECOVERY_ATTEMPTS must not be greater than 1; if we decide
in the future to make it greater than 1, we need to test the 
error_callback, because it will be able to be re-entered.
"""
MAX_RECOVERY_ATTEMPTS = 1  # !! MUST BE 1 and ONLY 1 (see above comment) !!
MIN_RETRY_WINDOW = 2 # 2 seconds

MAX_SEND_ATTEMPTS = 15              # Max number of times we can get EAGAIN


class SocketClosed(Exception): pass


class PortAgentPacket():
    """
    An object that encapsulates the details packets that are sent to and
    received from the port agent.
    https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+Port+Agent+Design
    """
    
    """
    Port Agent Packet Types
    """
    DATA_FROM_INSTRUMENT = 1
    DATA_FROM_DRIVER = 2
    PORT_AGENT_COMMAND = 3
    PORT_AGENT_STATUS = 4
    PORT_AGENT_FAULT = 5
    INSTRUMENT_COMMAND = 6
    HEARTBEAT = 7
    PICKLED_DATA_FROM_INSTRUMENT = 8
    PICKLED_DATA_FROM_DRIVER = 9

    def __init__(self, packetType = None):
        self.__header = None
        self.__data = None
        self.__type = packetType
        self.__length = None
        self.__port_agent_timestamp = None
        self.__recv_checksum  = None
        self.__checksum = None
        self.__isValid = False

    def unpack_header(self, header):
        self.__header = header
        #@TODO may want to switch from big endian to network order '!' instead of '>' note network order is big endian.
        # B = unsigned char size 1 bytes
        # H = unsigned short size 2 bytes
        # L = unsigned long size 4 bytes
        # d = float size8 bytes
        variable_tuple = struct.unpack_from('>BBBBHHII', header)
        # change offset to index.
        self.__type = variable_tuple[TYPE_INDEX]
        self.__length = int(variable_tuple[LENGTH_INDEX]) - HEADER_SIZE
        self.__recv_checksum  = int(variable_tuple[CHECKSUM_INDEX])
        upper = variable_tuple[TIMESTAMP_UPPER_INDEX]
        lower = variable_tuple[TIMESTAMP_LOWER_INDEX]
        self.__port_agent_timestamp = float("%s.%s" % (upper, lower))
        #log.trace("port_timestamp: %f", self.__port_agent_timestamp)

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
            """
            Set the packet type if it was not passed in as parameter
            """
            if self.__type == None:
                self.__type = self.DATA_FROM_DRIVER
            self.set_data_length(len(self.__data))
            self.set_timestamp()


            variable_tuple = (0xa3, 0x9d, 0x7a, self.__type, 
                              self.__length + HEADER_SIZE, 0x0000, 
                              self.__port_agent_timestamp)

            # B = unsigned char size 1 bytes
            # H = unsigned short size 2 bytes
            # L = unsigned long size 4 bytes
            # d = float size 8 bytes
            format = '>BBBBHHd'
            size = struct.calcsize(format)
            temp_header = ctypes.create_string_buffer(size)
            struct.pack_into(format, temp_header, 0, *variable_tuple)
            self.__header = temp_header.raw
            #print "here it is: ", binascii.hexlify(self.__header)
            
            """
            do the checksum last, since the checksum needs to include the
            populated header fields.  
            NOTE: This method is only used for test; messages TO the port_agent
            do not include a header (as I mistakenly believed when I wrote
            this)
            """
            self.__checksum = self.calculate_checksum()
            self.__recv_checksum  = self.__checksum

            """
            This was causing a problem, and since it is not used for our tests,
            commented out; if we need it we'll have to fix
            """
            #self.__header[OFFSET_P_CHECKSUM_HIGH] = self.__checksum & 0x00ff
            #self.__header[OFFSET_P_CHECKSUM_LOW] = (self.__checksum & 0xff00) >> 8


    def attach_data(self, data):
        self.__data = data

    def calculate_checksum(self):
        checksum = 0
        for i in range(HEADER_SIZE):
            if i < OFFSET_P_CHECKSUM_LOW or i > OFFSET_P_CHECKSUM_HIGH:
                checksum ^= struct.unpack_from('B', str(self.__header[i]))[0]
                
        for i in range(self.__length):
            checksum ^= struct.unpack_from('B', str(self.__data[i]))[0]
            
        return checksum
            
                                
    def verify_checksum(self):
        checksum = 0
        for i in range(HEADER_SIZE):
            if i < OFFSET_P_CHECKSUM_LOW or i > OFFSET_P_CHECKSUM_HIGH:
                checksum ^= struct.unpack_from('B', self.__header[i])[0]
                
        for i in range(self.__length):
            checksum ^= struct.unpack_from('B', self.__data[i])[0]
            
        if checksum == self.__recv_checksum:
            self.__isValid = True
        else:
            self.__isValid = False
            
        #log.debug('checksum: %i.' %(checksum))

    def get_header(self):
        return self.__header

    
    def set_header(self, header):
        """
        This method is used for testing only; we want to test the checksum so
        this is one of the hoops we jump through to do that.
        """
        self.__header = header

    def get_data(self):
        return self.__data

    def get_timestamp(self):
        return self.__port_agent_timestamp

    def attach_timestamp(self, timestamp):
        self.__port_agent_timestamp = timestamp

    def set_timestamp(self):
        self.attach_timestamp(time.time())

    def get_data_length(self):
        return self.__length

    def set_data_length(self, length):
        self.__length = length

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
    
    RECOVERY_SLEEP_TIME = 2
    HEARTBEAT_INTERVAL_COMMAND = "heartbeat_interval "
    BREAK_COMMAND = "break "
    
    def __init__(self, host, port, cmd_port, delim=None):
        """
        PortAgentClient constructor.
        """
        self.host = host
        self.port = port
        self.cmd_port = cmd_port
        self.sock = None
        self.listener_thread = None
        self.stop_event = None
        self.delim = delim
        self.heartbeat = 0
        self.max_missed_heartbeats = None
        self.send_attempts = MAX_SEND_ATTEMPTS
        self.recovery_attempts = 0
        self.user_callback_data = None
        self.user_callback_raw = None
        self.user_callback_error = None
        self.listener_callback_error = None
        self.last_retry_time = None
        self.recovery_mutex = threading.Lock()
        
    def _init_comms(self):
        """
        Initialize client comms with the logger process and start a
        listener thread.
        """
        
        try:
            self._destroy_connection()
            self._create_connection()

            ###
            # Send the heartbeat command, but only if it's greater
            # than zero
            ###
            if 0 < self.heartbeat:
                heartbeat_string = str(self.heartbeat)
                self.send_config_parameter(self.HEARTBEAT_INTERVAL_COMMAND, 
                                           heartbeat_string)
            
            ###
            # start the listener thread if instructed to
            ###
            if self.start_listener:
                self.listener_thread = Listener(self.sock,  
                                                self.recovery_attempts,
                                                self.delim, self.heartbeat, 
                                                self.max_missed_heartbeats, 
                                                self.callback_data,
                                                self.callback_raw,
                                                self.listener_callback_error,
                                                self.callback_error,
                                                self.user_callback_error)
                self.listener_thread.start()

            ###
            # Reset recovery_attempts because we were successful, but only 
            # if the we haven't reset it already within a the configured
            # time window.
            ###
            if (self.last_retry_time):
                current_time = time.time()
                log.debug(" Thread %s: current_time: %r; last_retry_time: %r", 
                          str(threading.current_thread().name), current_time,  (self.last_retry_time))
                if current_time > (self.last_retry_time + MIN_RETRY_WINDOW):
                    log.debug("Outside min retry window: reseting retry counter")
                    self.recovery_attempts = 0
                else:
                    log.info('PortAgentClient._init_comms(): still within min ' +
                              'retry window: not resetting retry counter')
            else:
                self.last_retry_time = time.time()
            
            log.info('PortAgentClient._init_comms(), thread: %s: connected to port agent at %s:%i.',
                           str(threading.current_thread().name), self.host, self.port)
            return True
                
        except Exception as e:
            errorString = "_init_comms(): Exception initializing comms for " +  \
                      str(self.host) + ": " + str(self.port) + ": " + repr(e)
            log.error(errorString, exc_info = True)
            time.sleep(self.RECOVERY_SLEEP_TIME)
            returnCode = self.callback_error(errorString)
            if returnCode == True:
                log.debug("_init_comms: callback_error succeeded.")
            else:
                log.error("_init_comms: callback_error failed to recover connection.")
            
            return returnCode

    def _create_connection(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.setblocking(0)

    def _destroy_connection(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            log.info('Port agent data socket closed.')
                        
    def init_comms(self, user_callback_data = None, user_callback_raw = None,
                   listener_callback_error = None,
                   user_callback_error = None, heartbeat = 0,
                   max_missed_heartbeats = None, start_listener = True):
        
        self.user_callback_data = user_callback_data        
        self.user_callback_raw = user_callback_raw
        self.listener_callback_error = listener_callback_error
        self.user_callback_error = user_callback_error
        self.heartbeat = heartbeat
        self.max_missed_heartbeats = max_missed_heartbeats
        self.start_listener = start_listener 

        if  False == self._init_comms():
            error_string = ' port_agent_client private _init_comms failed.'
            log.error(error_string)
            raise InstrumentConnectionException(error_string)

    def stop_comms(self):
        """
        Stop the listener thread if there is one, and close client comms 
        with the device logger. This is called by the done function.
        """
        log.info('PortAgentClient shutting down comms.')
        if (self.listener_thread):
            self.listener_thread.done()
            self.listener_thread.join()

        #-self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.sock = None
        log.info('Port Agent Client stopped.')

    def done(self):
        """
        Synonym for stop_comms.
        """
        self.stop_comms()

    def callback_data(self, paPacket):
        """
        A packet has been received from the port agent.  The packet is 
        contained in a packet object.  
        """
        if (self.user_callback_data):
            paPacket.verify_checksum()
            self.user_callback_data(paPacket)
        else:
            log.error("No user_callback_data defined")

    def callback_raw(self, paPacket):
        """
        A packet has been received from the port agent.  The packet is 
        contained in a packet object.  
        """
        if (self.user_callback_raw):
            paPacket.verify_checksum()
            self.user_callback_raw(paPacket)
        else:
            log.error("No user_callback_raw defined")

    def callback_error(self, errorString = "No error string passed."):
        """
        A catastrophic error has occurred; attempt to recover, but only
        attempt MAX_RECOVERY_ATTEMPTS times. 
        @param errorString: reason for call
        @ retval True: recovery attempt worked
                 False: recovery attempt failed
        """
        returnValue = False
        
        self.recovery_mutex.acquire()

        if (self.recovery_attempts >= MAX_RECOVERY_ATTEMPTS):
            """
            Release the mutex here.  The other thread can notice an error and
            we will have not released the semaphore, and the thread will hang.  
            The fact that we've incremented the MAX_RECOVERY_ATTEMPTS will
            stop any re-entry.
            """        
            self.recovery_mutex.release()
            log.error("Maximum connection_level recovery attempts (%d) reached." % (self.recovery_attempts))
            if self.listener_thread and self.listener_thread.is_alive():
                log.info("Stopping listener thread.") 
                self.listener_thread.done()
            returnValue = False
        else:
            """
            Try calling _init_comms() again;
            release the mutex before calling _init_comms, which can cause
            another exception, and we will have not released the semaphore.  
            The fact that we've incremented the MAX_RECOVERY_ATTEMPTS will
            stop any re-entry.
            """
            self.recovery_attempts = self.recovery_attempts + 1
            log.error("Attempting connection_level recovery; attempt number %d" % (self.recovery_attempts))
            self.recovery_mutex.release()
            returnValue = self._init_comms()
            if True == returnValue:
                log.info("_init_comms recovery succeeded.")
            else:
                log.error("_init_comms recovery failed.")
            
        return returnValue
            
    def send_config_parameter(self, parameter, value):
        """
        Send a configuration parameter to the port agent
        """
        command = parameter + value
        log.debug("Sending config parameter: %s" % (command))
        self._command_port_agent(command)

    def send_break(self, duration):
        """
        Command the port agent to send a break
        """
        self._command_port_agent(self.BREAK_COMMAND + str(duration))

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
            log.info('PortAgentClient._command_port_agent(): connected to port agent at %s:%i.'
                     % (self.host, self.cmd_port))
            self.send(cmd, sock)
            sock.close()
        except Exception as e:
            log.error("send_break(): Exception occurred.", exc_info=True)
            raise InstrumentConnectionException('Failed to connect to port agent command port at %s:%s (%s).'
                                                % (self.host, self.cmd_port, e))


    def send(self, data, sock = None, host = None, port = None):
        """
        Send data to the port agent.
        """
        returnValue = 0
        total_bytes_sent = 0
        
        """
        The socket can be a parameter (in case we need to send to the command
        port, for instance); if not provided, default to self.sock which 
        should be the data port.  The same pattern applies to the host and port,
        but those are for logging information in case of error.
        """
        if (not sock):
            sock = self.sock

        if (not host):
            host = self.host

        if (not port):
            port = self.port
            
        if sock:
            would_block_tries = 0
            continuing = True
            while len(data) > 0 and continuing:
                try:
                    sent = sock.send(data)
                    total_bytes_sent = len(data[:sent])
                    data = data[sent:]
                except socket.error as e:
                    if e.errno == errno.EWOULDBLOCK:
                        would_block_tries = would_block_tries + 1
                        if would_block_tries > self.send_attempts:
                            """
                            TODO: Remove the commented out lines that print self.host and self.port after verifying that getpeername works
                            (self.host and self.port aren't necessarily correct; the sock is a parameter here and host and port might not
                            be correct).
                            """
                            #error_string = 'Send EWOULDBLOCK attempts (%d) exceeded while sending to %s:%i'  % (would_block_tries, self.host, self.port)
                            error_string = 'Send EWOULDBLOCK attempts (%d) exceeded while sending to %r'  % (would_block_tries, sock.getpeername())
                            log.error(error_string)
                            continuing = False 
                            self._invoke_error_callback(error_string)
                        else:
                            #error_string = 'Socket error while sending to (%s:%i): %r; tries = %d'  % (self.host, self.port, e, would_block_tries)
                            error_string = 'Socket error while sending to %r: %r; tries = %d'  % (sock.getpeername(), e, would_block_tries)
                            log.error(error_string)
                            time.sleep(.1)
                    else:
                        error_string = 'Socket error while sending to (%r:%r): %r'  % (host, port, e)
                        #error_string = 'Socket error while sending to %r: %r'  % (sock.getpeername(), e)
                        log.error(error_string)
                        self._invoke_error_callback(error_string)
        else:
            error_string = 'No socket defined!'
            log.error(error_string)
            self._invoke_error_callback(error_string)
        
        return total_bytes_sent
            
    def _invoke_error_callback(self, error_string = "No error string passed."):
        """
        Invoke callback_error; and its return_code indicates that it failed to
        recover, invoke the user_error_callback and raise an exception  
        @param error_string: error description.
        """
        log.debug('port_agent_client listen thread calling local_callback_error.')
        if False == self.callback_error(error_string):
            log.debug('port_agent_client calling user_callback_error and raising exception.')
            self.user_callback_error(error_string)
            raise InstrumentConnectionException(error_string)
        else:
            log.debug('port_agent_client listen thread: recovery succeeded.')

class Listener(threading.Thread):

    MAX_HEARTBEAT_INTERVAL = 20 # Max, for range checking parameter
    MAX_MISSED_HEARTBEATS = 5   # Max number we can miss 
    HEARTBEAT_FUDGE = 1         # Fudge factor to account for delayed heartbeat

    """
    A listener thread to monitor the client socket data incoming from
    the port agent process. 
    """
    
    def __init__(self, sock, recovery_attempt, 
                 delim = None, heartbeat = 0, 
                 max_missed_heartbeats = None, 
                 callback_data = None, callback_raw = None,
                 default_callback_error = None,
                 local_callback_error = None,
                 user_callback_error = None):
        """
        Listener thread constructor.
        @param sock The socket to listen on.
        @param delim The line delimiter to split incoming lines on, used in
        debugging when no callback is supplied.
        @param heartbeat The heartbeat interval in which to expect heartbeat
        messages from the Port Agent.
        @param max_missed_heartbeats The number of allowable missed heartbeats
        before attempting recovery.
        @param callback_data The callback on data arrival.
        @param callback_raw The callback for raw.
        @param default_callback_data A callback to handle non-network exceptions
        @param local_callback_data The local callback when error encountered.
        @param user_callback_data The user callback on error_encountered.
        """
        threading.Thread.__init__(self)
        self.sock = sock
        self.recovery_attempt = recovery_attempt
        self._done = False
        self.linebuf = ''
        self.delim = delim
        self.heartbeat_timer = None
        self.thread_name = None
        if (max_missed_heartbeats == None):
            self.max_missed_heartbeats = self.MAX_MISSED_HEARTBEATS
        else:
            self.max_missed_heartbeats = max_missed_heartbeats
        self.heartbeat_missed_count = self.max_missed_heartbeats
        
        self.set_heartbeat(heartbeat)
        
        def fn_callback_data(paPacket):
            if callback_data:
                callback_data(paPacket)
            else:
                log.error("No callback_data function has been registered")

        def fn_callback_raw(paPacket):
            if callback_raw:
                callback_raw(paPacket)
            else:
                log.error("No callback_raw function has been registered")

        def fn_callback_error(exception):
            """
            This method is invoked pass exceptions upstream that occur
            in the context of the listener thread (callback_data or 
            callback_raw).
            """ 
            log.info("fn_callback_error; unknown exception being " +
                     "passed upstream")
            if default_callback_error:
                default_callback_error(exception)
            else:
                log.error("No default_callback_error function has been registered")
                            
        def fn_local_callback_error(errorString = "No error string passed."):
            """
            Local error callback; this will try local recovery first; 
            """
            log.error("fn_local_callback_error, Connection error: %s" % (errorString))
            
            if local_callback_error:
                return local_callback_error(errorString)
            else:
                log.error("No local_callback_error function has been registered")            


        def fn_user_callback_error(errorString = "No error string passed."):
            """
            User error callback; 
            """
            log.error("fn_user_callback_error (thread: %s), Connection error: %s", str(threading.current_thread().name), errorString)
            
            if user_callback_error:
                user_callback_error(errorString)
            else:
                log.error("No user_callback_error function has been registered")            

        """
        Now that the callbacks have have been defined, assign them
        """                
        self.callback_data = fn_callback_data
        self.callback_raw = fn_callback_raw
        self.local_callback_error = fn_local_callback_error
        self.user_callback_error = fn_user_callback_error
        self.default_callback_error = fn_callback_error

    def heartbeat_timeout(self):
        log.error('heartbeat timeout')
        self.heartbeat_missed_count = self.heartbeat_missed_count - 1
    
        """
        Take corrective action here.
        """
        if self.heartbeat_missed_count <= 0:
            errorString = 'Maximum allowable Port Agent heartbeats (' + str(self.max_missed_heartbeats) + ') missed!'
            log.error(errorString)
            self._invoke_error_callback(self.recovery_attempt, errorString)
        else:
            self.start_heartbeat_timer()

    def set_heartbeat(self, heartbeat):
        """
        Make sure the heartbeat is reasonable; if so, initialize the class 
        member heartbeat (plus fudge factor) to greater than the value passed 
        in.  This is to account for possible delays in the heartbeat packet 
        from the port_agent.
        """
        if heartbeat == 0:
            self.heartbeat = heartbeat
            returnValue = True
        elif heartbeat > 0 and heartbeat <= self.MAX_HEARTBEAT_INTERVAL: 
            self.heartbeat = heartbeat + self.HEARTBEAT_FUDGE;
            returnValue = True
        else:
            log.error('heartbeat out of range: %d' % (heartbeat))
            returnValue = False
            
        return returnValue
        
    def start_heartbeat_timer(self):
        """
        Note: the threading timer here is only run once.  The cancel
        only applies if the function has yet run.  You can't reset
        it and start it again, you have to instantiate a new one.
        I don't like this; we need to implement a tread timer that 
        stays up and can be reset and started many times.
        """
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()

        self.heartbeat_timer = threading.Timer(self.heartbeat, 
                                            self.heartbeat_timeout)
        self.heartbeat_timer.start()
        
    def done(self):
        """
        Signal to the listener thread to end its processing loop and
        conclude.
        """
        self._done = True

    def handle_packet(self, paPacket):
        packet_type = paPacket.get_header_type()
        
        if packet_type == PortAgentPacket.DATA_FROM_INSTRUMENT:
            self.callback_raw(paPacket)
            self.callback_data(paPacket)
        elif packet_type == PortAgentPacket.DATA_FROM_DRIVER:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.PICKLED_DATA_FROM_INSTRUMENT:
            self.callback_raw(paPacket)
            self.callback_data(paPacket)
        elif packet_type == PortAgentPacket.PICKLED_DATA_FROM_DRIVER:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.PORT_AGENT_COMMAND:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.PORT_AGENT_STATUS:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.PORT_AGENT_FAULT:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.INSTRUMENT_COMMAND:
            self.callback_raw(paPacket)
        elif packet_type == PortAgentPacket.HEARTBEAT:
            """
            Got a heartbeat; reset the timer and re-init 
            heartbeat_missed_count.
            """
            log.debug("HEARTBEAT Packet Received")
            if 0 < self.heartbeat:
                self.start_heartbeat_timer()
                
            self.heartbeat_missed_count = self.max_missed_heartbeats


    def run(self):
        """
        Listener thread processing loop. Block on receive from port agent.
        Receive HEADER_SIZE bytes to receive the entire header.  From that,
        get the length of the whole packet (including header); compute the
        length of the remaining data and read that.  
        """
        self.thread_name = str(threading.current_thread().name)
        log.info('PortAgentClient listener thread: %s started.', self.thread_name)
        
        if self.heartbeat:
            self.start_heartbeat_timer()

        while not self._done:
            try:
                log.debug('RX NEW PACKET')
                header = bytearray(HEADER_SIZE)
                headerview = memoryview(header)
                bytes_left = HEADER_SIZE
                while bytes_left and not self._done:
                    try:
                        bytesrx = self.sock.recv_into(headerview[HEADER_SIZE - bytes_left:], bytes_left)
                        log.debug('RX HEADER BYTES %d LEFT %d SOCK %r' % (
                                                    bytesrx, bytes_left, self.sock,))
                        if bytesrx <= 0:
                            raise SocketClosed()
                        bytes_left -= bytesrx
                    except socket.error as e:
                        if e.errno == errno.EWOULDBLOCK:
                            time.sleep(.1)
                        else:
                            raise

                """
                Only do this if we've received the whole header, otherwise (ex. during shutdown)
                we can have a completely invalid header, resulting in negative count exceptions.
                """
                if (bytes_left == 0):
                    paPacket = PortAgentPacket()
                    paPacket.unpack_header(str(header))
                    data_size = paPacket.get_data_length()
                    bytes_left = data_size
                    data = bytearray(data_size)
                    dataview = memoryview(data)
                    log.debug('Expecting DATA BYTES %d' % data_size)
                    
                while bytes_left and not self._done:
                    try:
                        bytesrx = self.sock.recv_into(dataview[data_size - bytes_left:], bytes_left)
                        log.debug('RX DATA BYTES %d LEFT %d SOCK %r' % (
                                                    bytesrx, bytes_left, self.sock,))
                        if bytesrx <= 0:
                            raise SocketClosed()
                        bytes_left -= bytesrx
                    except socket.error as e:
                        if e.errno == errno.EWOULDBLOCK:
                            time.sleep(.1)
                        else:
                            raise

                if not self._done:
                    """
                    Should have complete port agent packet.
                    """
                    paPacket.attach_data(str(data))
                    log.debug("HANDLE PACKET")
                    self.handle_packet(paPacket)

            except SocketClosed:
                errorString = 'Listener thread: %s SocketClosed exception from port_agent socket' \
                    % (self.thread_name) 
                log.error(errorString)
                self._invoke_error_callback(self.recovery_attempt, errorString)
                """
                This next statement causes the thread to exit.  This 
                thread is done regardless of which condition exists 
                above; it is the job of the callbacks to restart the
                thread
                """
                self._done = True

            except socket.error as e:
                errorString = 'Listener thread: %s Socket error while receiving from port agent: %r' \
                 % (self.thread_name, e)
                log.error(errorString)
                self._invoke_error_callback(self.recovery_attempt, errorString)
                """
                This next statement causes the thread to exit.  This 
                thread is done regardless of which condition exists 
                above; it is the job of the callbacks to restart the
                thread
                """
                self._done = True

            except Exception as e:
                self.default_callback_error(e)

        log.info('Port_agent_client thread done listening; going away.')

    def _invoke_error_callback(self, recovery_attempt, error_string = "No error string passed."):
        """
        Invoke either the user_error_callback or the local_error_callback, depending upon the
        recovery_attempt value.  If the local_error_callback is invoked, and its return_code
        indicates that it failed, invoke the user_error_callback. 
        @param recovery_attempt: the number of this recovery attempt.
        @param error_string: error description.
        """
        if self.recovery_attempt < MAX_RECOVERY_ATTEMPTS:
            log.debug('port_agent_client listen thread calling local_callback_error.')
            recovery = self.local_callback_error(error_string)
            if (False == recovery):
                log.debug('port_agent_client listen thread calling user_callback_error.')
                self.user_callback_error(error_string)
            else:
                log.debug('port_agent_client listen thread: recovery succeeded.')
        else:
            log.debug('port_agent_client listen thread calling user_callback_error.')
            self.user_callback_error(error_string)
