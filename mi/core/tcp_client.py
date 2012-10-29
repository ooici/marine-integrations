#!/usr/bin/env python

from mi.core.log import get_logger ; log = get_logger()

import gevent
import socket

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'

class TcpClient():
    '''
    Setup a tcp client to act as a telnet client for testing.
    '''
    buf = ""

    def __init__(self, host, port):
        '''
        Constructor - open/connect to the socket
        @param host: host address
        @param port: host port
        '''
        self.buf = ""
        self.host = host
        self.port = port
        # log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.settimeout(0.0)

    def telnet_handshake(self):
        if(self.expect(WILL_ECHO_CMD)):
            self.send_data(DO_ECHO_CMD)
            return True
        return False

    def read_a_char(self):
        temp = self.s.recv(1024)
        if len(temp) > 0:
            log.debug("read_a_char got '" + str(repr(temp)) + "'")
            self.buf += temp
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            c = None
        return c

    def peek_at_buffer(self):
        if len(self.buf) == 0:
            try:
                self.buf = self.s.recv(1024)
                log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")
            except:
                """
                Ignore this exception, its harmless
                """
        return self.buf

    def remove_from_buffer(self, remove):
        log.debug("BUF WAS " + str(repr(self.buf)))
        self.buf = self.buf.replace(remove, "")
        log.debug("BUF IS '" + str(repr(self.buf)) + "'")

    def expect(self, target, max_retries = 10, sleep_time = 1):
        '''
        Watch the input buffer for a string to show up.  If it does
        then consume that string from the buffer and return success.
        If the string isn't seen in a timely manor (retry + sleep_time)
        then return fail
        @param target: string to watch for
        @param max_retries: how many times to we check for that string
        @param sleep_time: how long to wait between queries
        @return: True if the string was seen, False otherwise
        '''
        try_count = 0

        while self.peek_at_buffer().find(target) == -1:
            log.debug("WANT '%s:' READ (%d): '%s' HEX: %s" %
                     (target, len(self.peek_at_buffer()), str(self.peek_at_buffer()), self.to_hex(self.peek_at_buffer())))
            gevent.sleep(sleep_time)
            try_count += 1
            if try_count > max_retries:
                log.error("EXPECT Timeout. target not found '%s'" % target)
                return False

        self.remove_from_buffer(target)
        return True


    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c == None:
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

    def to_hex(self, s):
        """
        return a hex representation of a string
        @param s: input bytes
        @return: hex representation of the input
        """
        if(not len(s)): return None

        lst = []
        for ch in s:
            hv = hex(ord(ch)).replace('0x', '')
            if len(hv) == 1:
                hv = '0'+hv

            lst.append(hv.upper() + ' ')


        return reduce(lambda x,y:x+y, lst)