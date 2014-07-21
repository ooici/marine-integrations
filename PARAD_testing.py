#!/usr/bin/env python

from __future__ import division    # Makes division "/" work like Python 3.0

USAGE = """

GP- This has been modified to make it a generic raw socket connection, with <CR><LF>

This program allows direct user iteraction with the PARAD instrument via a socket.


USAGE:
    PARAD_testing.py address port  # connect to instrument on address:port
    PARAD_testing.py port          # connect to instrument on localhost:port

Example:
    PARAD_testing.py 10.180.80.170 2101

To save output to screen and to a log file:

    PARAD_testing.py 10.180.80.170 2101 | tee file.txt

It establishes a TCP connection with the provided service, starts a thread to
print all incoming data from the associated socket, and goes into a loop to
dispach commands from the user.

The commands are:
    - an empty string --> sends a '\r\n' (<CR><LF>)
    - The letter 'q' --> quits the program
    - Any other non-empty string --> sends the string followed by a '\r\n' (<CR><LF>)


"""

__author__ = 'Giora Proskurowski modified original Carlos Rueda'
__license__ = 'Apache 2.0'

import sys
import socket
import os
import time
import re

from threading import Thread

MAX_BUFFER_SIZE=32768
# MAX_BUFFER_SIZE=100
COMMAND_PATTERN = r'Satlantic'
# COMMAND_PATTERN = r"Satlantic PAR Sensor\r\nCommand Console\r\nType 'help' for a list of available commands.\r\n" \
#                   r"S/N: (?P<sernum>\d{4,10})\r\nFirmware: (.*)\r\n"
COMMAND_REGEX = re.compile(COMMAND_PATTERN)

SAMPLE_PATTERN = r'SATPAR(?P<sernum>\d{4,10}),(?P<timer>\d{1,7}.\d\d),(?P<counts>\d{10}),(?P<checksum>\d{1,3})\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

PRESS_PATTERN = r'Copyright'
PRESS_REGEX = re.compile(PRESS_PATTERN)

INVALID_PATTERN = r'Invalid command'
INVALID_REGEX = re.compile(INVALID_PATTERN)

class _Recv(Thread):
    """
    Thread to receive and print data.
    """

    def __init__(self, conn):
        Thread.__init__(self, name="_Recv")
        self._conn = conn
        self._last_line = ''
        self._new_line = ''
        self.setDaemon(True)
        self._linebuf = ''
        self._promptbuf = ''
        self._block_flag = False
        self._time_start = 0
        self.count = 0

    def _update_lines(self, recv):
        if recv == '\n':
            self._last_line = self._new_line
            self._new_line = ''
            return True
        else:
            self._new_line += recv
            return False

    def send_control(self, char):
        """
        Sends a control character.
        @param char must satisfy 'a' <= char.lower() <= 'z'
        """
        char = char.lower()
        assert 'a' <= char <= 'z'
        a = ord(char)
        a = a - ord('a') + 1
        print "send control: ", chr(a)
        return self._conn.send(chr(a))

    def run(self):
        print "### _Recv running."

        period = 0.12  # how long to send out ^C's
        n_send = 1    # number of times to send out ^C per period
        t_div = 1    # time division slice
        sleep_time = period/t_div

        while True:
            try:
                recv = self._conn.recv(1)
                newline = self._update_lines(recv)
                self.add_to_buffer(recv)
                # print "### timestamp: %s" % (time.strftime("%H:%M:%S", time.gmtime()))
                os.write(sys.stdout.fileno(), recv)
                sys.stdout.flush()

            except socket.error:

                if self._block_flag:
                    self._conn.send('\x03')
                    time.sleep(sleep_time)

                    # print "### sending ^C ###"
                    # print "PROMPT BUF: %r" % self._promptbuf
                    self.count += 1
                    press_match = re.compile('[Cc]ommand').search(self._promptbuf)
                    if press_match:
                        print "### _Recv:found match: %s ### on count #%s, start: %s, stop: %s" % \
                              (press_match.group(), self.count, self._time_start, time.strftime("%H:%M:%S", time.gmtime()))
                        self._block_flag = False
                        self.count = 0
                # else:
                #     print "### timestamp: %s" % (time.strftime("%H:%M:%S", time.gmtime()))
                # time.sleep(0.115)

    def add_to_buffer(self, data):
        """
        Add a chunk of data to the internal data buffers
        buffers implemented as lifo ring buffer
        @param data: bytes to add to the buffer
        """
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        if len(self._linebuf) > self._max_buffer_size():
            self._linebuf = self._linebuf[self._max_buffer_size()*-1:]

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        if len(self._promptbuf) > self._max_buffer_size():
            self._promptbuf = self._linebuf[self._max_buffer_size()*-1:]

    @staticmethod
    def _max_buffer_size():
        return MAX_BUFFER_SIZE

class _Direct(object):
    """
    Main program.
    """

    def __init__(self, host, port):
        """
        Establishes the connection and starts the receiving thread.
        """
        print "### connecting to %s:%s" % (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        self._sock.setblocking(0)
        self._bt = _Recv(self._sock)
        self._bt.start()
        self.sent_flag = False
        self._block_flag = False
        self.count = 0
        self._time_start = 0

    def run(self):
        #        """
        #         Dispaches user commands.
        #         """

        period = 0.12  # how long to send out ^C's
        t_div = 5000    # time division slice
        sleep_time = period/t_div
        n_send = 1000

        while True:

            try:
                cmd = sys.stdin.readline()
                cmd = cmd.strip()

                if cmd == "^C":
                    # print "### sending '%s'" % cmd
                    self.send_control('c')

                elif cmd == "^S":
                    # print "### sending '%s'" % cmd

                    # self.send('\x13')

                    # self._bt._promptbuf = ''
                    # time.sleep(0.2)   # at 8 - max rate only have to wait 1/8s
                    # if SAMPLE_REGEX.search(self._bt._promptbuf):    # got a sample, still stuck in auto mode
                    #     while True:
                    #         for n in xrange(5):
                    #             print "### sending more ^S"
                    #             self.send('\x13')
                    #             time.sleep(0.115)
                    #         if SAMPLE_REGEX.search(self._bt._promptbuf):
                    #             self._bt._promptbuf = ''
                    #         else:
                    #             break

                    # self._time_start = (time.strftime("%H:%M:%S", time.gmtime()))
                    # x = 500
                    # y = 0.115
                    # p = y/x
                    # self._bt._promptbuf = ''
                    # while True:
                    #     print "### sending '%s'" % cmd
                    #     for _ in xrange(15):
                    #         self.send('\x13')
                    #         time.sleep(.15)
                    #     if SAMPLE_REGEX.search(self._bt._promptbuf):
                    #         self._bt._promptbuf = ''
                    #     else:
                    #         break

                    self.send_control('s')

                elif cmd == "^A":
                    #print "### sending '%s'" % cmd
                    self.send_control('A')

                elif cmd == "^P":
                    #print "### sending '%s'" % cmd
                    self.send_control('P')

                elif cmd == "^U":
                    #print "### sending '%s'" % cmd
                    self.send_control('U')

                elif cmd == "^R":
                    #print "### sending '%s'" % cmd
                    self.send_control('R')

                elif cmd == "q":
                    #print "### exiting"
                    break

                else:
                    # print "### sending '%s'" % cmd
                    self.sendCharacters(cmd)
                    # time.sleep(0.3)
                    # self.send('\r\n')

            except KeyboardInterrupt:

                # self._time_start = (time.strftime("%H:%M:%S", time.gmtime()))
                self._bt._promptbuf = ''
                while True:
                    for n in xrange(n_send):
                        self.send('\x03')
                        time.sleep(sleep_time)

                    # print "### sending ^C ###"
                    # print "PROMPT BUF: %r" % self._bt._promptbuf
                    self.count += 1
                    press_match = re.compile('([Cc]ommand)').search(self._bt._promptbuf)
                    print "promptbuf: %r" % self._bt._promptbuf
                    if press_match:
                        # print "### _Direct: found match: %s ### on count #%s, start: %s, stop: %s" % (press_match, self.count, self._time_start, time.strftime("%H:%M:%S", time.gmtime()))
                        self.count = 0
                        break
        self.stop()

    def stop(self):
        self._sock.close()

    def send(self, s):
        """
        Sends a string. Returns the number of bytes written.
        """
        c = os.write(self._sock.fileno(), s)
        return c

    def send_control(self, char):
        """
        Sends a control character.
        @param char must satisfy 'a' <= char.lower() <= 'z'
        """
        char = char.lower()
        assert 'a' <= char <= 'z'
        a = ord(char)
        a = a - ord('a') + 1
        print "send control: ", chr(a)
        self.send(chr(a))

        # time.sleep(0.5)
        # print "promptbuf: %r" % self._bt._promptbuf

    def sendCharacters(self, s):
        """
        Sends a string one char at a time with a delay between each
        """
        # # self.send("    ".join(map(None, s)))


        # new send alg: send, then wait for it to appear before sending next one?
        self._bt._promptbuf = ""
        for char in s:
            self.send(char)
            while len(self._bt._promptbuf) == 0 or char not in self._bt._promptbuf[-1]:
                time.sleep(0.0015)

        exit_enter_end_char = '\x0c'
        end_char = '\r\n'
        self.send(end_char)

        if len(s) == 0:
            return

        while end_char not in self._bt._promptbuf[len(s):len(s)+2] and exit_enter_end_char not in self._bt._promptbuf[len(s):len(s)+2]:
            time.sleep(0.0015)

        # time.sleep(0.5)
        # print "promptbuf: %r" % self._bt._promptbuf[len(s):len(s)+2]

if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print USAGE
        exit()

    if len(sys.argv) == 2:
        host = 'localhost'
        port = int(sys.argv[1])
    else:
        host = sys.argv[1]
        port = int(sys.argv[2])

    direct = _Direct(host, port)
    direct.run()