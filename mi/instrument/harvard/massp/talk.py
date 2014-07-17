#!/usr/bin/env python

USAGE = """

Generic tcp socket connection utility

"""

__author__ = 'Giora Proskurowski modified original Carlos Rueda'
__license__ = 'Apache 2.0'

import sys
import socket
import os
import time

from threading import Thread

NEWLINE = '\r'


class _Recv(Thread):
    """
    Thread to receive and print data.
    """

    def __init__(self, conn):
        Thread.__init__(self, name="_Recv")
        self._conn = conn
        self._last_line = ''
        self._new_line = ''
        self.last_time = time.time()
        self.setDaemon(True)

    def _update_lines(self, recv):
        if recv == NEWLINE:
            self._last_line = self._new_line
            self._new_line = ''
            return True
        else:
            self._new_line += recv
            return False

    def run(self):
        print "### _Recv running."
        while True:
            recv = self._conn.recv(4096)
            now = time.time()
            elapsed = now - self.last_time
            self.last_time = now
            print 'Elapsed [%6.2fs]: %r' % (elapsed, recv)


class _Direct(object):
    """
    Main program.
    """

    def __init__(self, hostname, portnum):
        """
        Establishes the connection and starts the receiving thread.
        """
        print "### connecting to %s:%s" % (hostname, portnum)
        self._sock = socket.socket()
        self._sock.connect((hostname, portnum))
        self._bt = _Recv(self._sock)
        self._bt.start()

    def run(self):
        """
        Dispatches user commands.
        """
        while True:

            cmd = sys.stdin.readline()

            cmd = cmd.strip()

            if cmd == "^C":
                #print "### sending '%s'" % cmd
                self.send_control('c')

            elif cmd == "^S":
                #print "### sending '%s'" % cmd
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
                cmd += NEWLINE
                print >> sys.stderr, 'SEND: %r' % cmd
                #self.send_characters(cmd)
                self.send(cmd)

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
        return self.send(chr(a))

    def send_characters(self, s):
        """
        Sends a string one char at a time with a delay between each
        """
        for c in s:
            self.send(c)
            sys.stdout.write(c)
            sys.stdout.flush()
            time.sleep(.2)


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
