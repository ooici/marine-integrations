#!/usr/bin/env python

"""
@package mi.core.instrument.port_agent_client
@file mi/core/instrument/port_agent_client
@author Edward Hunter
@brief Client to connect to the port agent
and logging.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

import socket
import threading
import time

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentConnectionException


class LoggerClient(object):
    """
    A logger process client class to test and demonstrate the correct use
    of device logger processes. The client object starts and stops
    comms with the logger. Data is sent to the logger with the send function,
    and data is retrieved from the logger with a listener thread.
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
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # This can be thrown here.
            # error: [Errno 61] Connection refused
            self.sock.connect((self.host, self.port))
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)                        
            self.sock.setblocking(0)        
            self.listener_thread = Listener(self.sock, self.delim, callback)
            self.listener_thread.start()
            log.info('LoggerClient.init_comms(): connected to port agent at %s:%i.'
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

    def send(self, data):
        """
        Send data to the device logger, retrying until all is sent.
        """
        
        if self.sock:
            while len(data)>0:
                try:
                    sent = self.sock.send(data)
                    gone = data[:sent]
                    data = data[sent:]
                except socket.error:
                    time.sleep(.1)
                
class Listener(threading.Thread):
    """
    A listener thread to monitor the client socket data incomming from
    the logger process. A similar construct will be used in drivers
    to catch and act upon the incomming data, so the pattern is presented here.
    """
    
    def __init__(self, sock, delim, callback=None):
        """
        Listener thread constructor.
        @param sock The socket to listen on.
        @param delim The line delimiter to split incomming lines on, used in
        debugging when no callback is supplied.
        @param callback The callback on data arrival.
        """
        threading.Thread.__init__(self)
        self.sock = sock
        self._done = False
        self.linebuf = ''
        self.delim = delim
        
        if callback:
            def fn_callback(data):
                callback(data)            
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
        Listener thread processing loop. Read incomming data when
        available and report it to the logger.
        """
        log.info('Logger client listener started.')
        while not self._done:
            try:
                data = self.sock.recv(4069)
                if self.callback:
                    self.callback(data)
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
                
            except socket.error:
                time.sleep(.1)
        log.info('Logger client done listening.')
