#!/usr/bin/env python

from mi.core.log import get_logger ; log = get_logger()

import re
import gevent
import socket

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'
BUFFER_SIZE = 4096


class TcpClient():
    """
    Setup a tcp client to act as a telnet client for testing.
    """
    buf = ""

    def __init__(self, host = None, port = None):
        """
        Constructor - open/connect to the socket
        @param host: host address
        @param port: host port
        """
        self.buf = ""

        if(host and port):
            self.connect(host, port)

    def connect(self, host, port):
        log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((host, port))
        self.s.settimeout(0.0)

    def disconnect(self):
        log.debug("CLOSE SOCKET")
        if(self.s):
            self.s.close()

    def telnet_handshake(self):
        if(self.expect(WILL_ECHO_CMD)):
            self.send_data(DO_ECHO_CMD)
            return True
        return False

    def read_a_char(self):
        temp = self.s.recv(BUFFER_SIZE)
        if len(temp) > 0:
            log.debug("read_a_char got '" + str(repr(temp)) + "'")
            self.buf += temp
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            c = None
        return c

    def expect(self, target, max_retries=10, sleep_time=1):
        """
        Watch the input buffer for a string to show up.  If it does
        then consume that string from the buffer and return success.
        If the string isn't seen in a timely manner (retry * sleep_time)
        then return fail
        @param target: string to watch for
        @param max_retries: how many times to we check for that string
        @param sleep_time: how long to wait between queries
        @return: True if the string was seen, False otherwise
        """
        return self.expect_regex(target, max_retries, sleep_time) is not None

    def expect_regex(self, pattern, max_retries=10, sleep_time=1):
        """
        Watch the input buffer for a regular expression match.  If found,
        then consume that string from the buffer and return the match object.
        If the string isn't seen in a timely manner (retry * sleep_time)
        then return None
        @param pattern: regular expression to watch for
        @param max_retries: how many times to we check for that string
        @param sleep_time: how long to wait between queries
        @return: Match object if the string was seen, None otherwise
        """
        match = None

        if type(pattern) == str:
            pattern = re.compile(pattern)

        for attempt in range(max_retries):
            try:
                self.buf += self.s.recv(BUFFER_SIZE)
            except:
                pass
            log.trace('expect | attempt: %d/%d pattern: %r buf(%d): %r',
                      attempt + 1, max_retries, pattern.pattern, len(self.buf), self.buf)
            match = pattern.search(self.buf)
            if match:
                self.buf = self.buf[match.end():]
                log.debug('expect | found match: %r', match.group())
                break

            gevent.sleep(sleep_time)
        if match is None:
            log.error('expect | no match found: %r', pattern.pattern)
        return match

    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c is None:
                    break
                if c == '\n' or c == '':
                    ret += c
                    break
                else:
                    ret += c

            data = ret
        except AttributeError:
            log.debug("CLOSING - GOT AN ATTRIBUTE ERROR")
            self.s.close()
        except:
            data = ""

        if data:
            data = data.lower()
            log.debug("IN  [" + repr(data) + "]")
        return data

    def send_data(self, data, debug = 1):
        try:
            log.debug("OUT [" + repr(data) + "]")
            self.s.sendall(data)
        except:
            log.debug("*** send_data FAILED [" + debug + "] had an exception sending [" + data + "]")

