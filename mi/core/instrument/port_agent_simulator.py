#!/usr/bin/env python

"""
@package ion.services.mi.port_agent_simulator Port Agent Simulator
@file ion/services/mi/port_agent_simulator.py
@author Bill French
@brief Simulate an instrument connection for a port agent.  Set
up a TCP listener in a thread then an interface will allow you
to send data through that TCP connection
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

import time
import errno
import socket
import thread

from mi.core.exceptions import InstrumentConnectionException

LOCALHOST='localhost'
DEFAULT_TIMEOUT=15
DEFAULT_PORT_RANGE=range(12200,12300)

class TCPSimulatorServer(object):
    """
    Simulate a TCP instrument connection that can be used by
    the port agent.  Start a TCP listener on a port in a configurable
    range.  Then provide an interface to send data through the
    connection. The connection is running in it's own thread.
    """
    def __init__(self, port_range = DEFAULT_PORT_RANGE, timeout = DEFAULT_TIMEOUT):
        """
        Instantiate a simulator on a port specified in the
        given port range.
        @param port_range: port numbers to attempt to bind too
        """
        self.connection = None
        self.address = None

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)

        self.__bind(port_range)
        self.socket.listen(0)

        thread.start_new_thread(self.__accept)

    def __bind(self, port_range):
        """
        bind to a port in a specified range.  Set the port number on
        success.  Raise an exception on failure.
        @param port_range: port numbers to attempt to bind too
        @raise: InstrumentConnectionException if bind failure
        """
        for port in port_range:
            try:
                self.socket.bind((LOCALHOST,port))
                self.port = port
                log.debug("Bind to port: %d" % port)
                return
            except Exception as e:
                log.error("Failed to bind to port %s (%s)" % (port, e))

        # If we made it this far we haven't found a port to bind to.
        raise InstrumentConnectionException("Failed to bind to a port")

    def __accept(self):
        """
        thread handler to accept connections
        """
        (self.connection, self.address) = self.socket.accept()
        log.debug("accepted tcp connection")

    def close(self):
        """
        Close the socket connection
        """
        if(self.connection):
            self.connection.close()
            log.debug("Connection close.")
        else:
            log.debug("Nothing to close")

        self.connection = None
        self.address = None

    def send(self, data):
        """
        Send data on the socket
        @raise: InstrumentConnectionException not connected
        """

        # Give our self a little time for the thread to accept a client
        timeout = time.time() + 10
        while(not self.connection):
            if(not self.connection):
                log.debug("not connected yet. waiting for connection.")
                time.sleep(0.1)

            if(timeout < time.time()):
                raise InstrumentConnectionException("socket not connected for send")

        self.connection.sendall(data)

class TCPSimulatorClient(object):
    """
    Connect to a tcp socket and provide an interface to send an receive
    data.
    """
    def __init__(self, port, address=LOCALHOST):
        """
        Instantiate a client on a port
        @param port: port to connect to
        @param address: address to connect to
        """
        self.port =port
        self.address = address

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.address, self.port))
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.setblocking(0)

        self.clear_buffer()
        self._done = False

        thread.start_new_thread(self.__listen)

    def __listen(self):
        """
        Thread handler to read bytes of data from a socket and then
        sleep for a bit. All bytes read are stored in a buffer
        """
        while not self._done:
            try:
                bytes_read = self.socket.recv(1024)
                if(bytes_read):
                    log.debug("RECV: %s" % bytes_read)
                    self._buffer += bytes_read

            except socket.error as e:
                if e.errno == errno.EWOULDBLOCK:
                    time.sleep(.1)
                else:
                    log.error("Socket read error: %s" % e)

    def clear_buffer(self):
        """
        Clear the read buffer
        """
        self._buffer = ''

    def close(self):
        """
        Stop the listener thread and close the socket
        """
        self._done = True
        self.socket.close()

    def read(self):
        """
        Return all bytes in the read buffer, then clear the buffer.
        @return: all bytes read.
        """
        result = self._buffer
        self.clear_buffer()
        return result

    def send(self, data):
        """
        Send data on the socket
        @raise: InstrumentConnectionException not connected
        """
        self.socket.sendall(data)



