

#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.direct
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/direct.py
@author Carlos Rueda
@brief Simple program to read in and parse an incoming stream from the
instrument.

Usage examples:
 direct.py 10.180.80.178 2101
 direct.py 10.180.80.178 2101 pd0_sample.bin
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import re
import os
import sys
import socket
from threading import Thread

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.coroutine import coroutine
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import timestamp_filter
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.pd0_filter import pd0_filter


def receive(sock, bufsize, pd0_file, out_file):
    """
    The routine for the receiving thread.
    Sets up and runs the processing of the incoming stream.
    The sink of the pipeline simply prints received timestamps,
    PD0 ensembles, and info about unprocessed fragments.

    @param sock sock.recv(bufsize) is called repeatily to read in the
           stream and push each read buffer into the pipeline.
    @param bufsize used for the sock read operation. Different values of
           this parameter allow to exercise the parsing algorithm.
    @param pd0_file If not None, the first received PD0 ensemble
                is written to this file.
    @param out_file If not None, all received data is written to this file.
    """

    global show_string

    @coroutine
    def sink(pd0_file, prefix=''):
        """
        @param pd0_file First received PD0 will be written to this file
        @param prefix String to use as prefix in some of the reported info.
        """
        while True:
            xelems, buffer = (yield)
            ts = xelems.get('latest_ts', None)
            if ts:
                print "{%sTIMESTAMP=%s}" % (prefix, ts)

            pd0 = xelems.get('pd0', None)
            if pd0:
                print "{%sPD0=\n\t|%s}" % (prefix,
                                           str(pd0).replace('\n', '\n\t|'))
                if pd0_file:
                    pd0_file.write(pd0.data)
                    pd0_file.flush()
                    pd0_file.close()
                    pd0_file = None
                    print "\n*** First received ensemble written to file ***\n"

            if buffer:
                # show something about the unprocessed buffer
                if 's' in show_string:
                    sys.stdout.write(buffer)
                    sys.stdout.flush()

                elif 'r' in show_string:
                    print '%s%r' % (prefix, buffer)

    pipeline = timestamp_filter(pd0_filter(sink(pd0_file)))

    # note that the order of the filters in the pipeline should no matter:
    # uncomment this line and the one in the loop below to compare the outputs:
#    pipeline2 = pd0_filter(timestamp_filter(sink(pd0_file, 'B:')))

    # read and push received data into the pipeline:
    while True:
        recv = sock.recv(bufsize)
        pipeline.send(({}, recv))
#        pipeline2.send(({}, recv))

        if out_file:
            out_file.write(recv)
            out_file.flush()


def user_loop(sock):
    """
    Sends user commands to the socket.
    """

    def send(s):
        c = os.write(sock.fileno(), s)
        return c

    def send_control(char):
        char = char.lower()
        assert 'a' <= char <= 'z'
        a = ord(char)
        a = a - ord('a') + 1
        return send(chr(a))

    global show_string
    show_string = 's'
    while True:
        cmd = sys.stdin.readline()
        cmd = cmd.strip()
        if cmd == "q":
            print "### quiting"
            break
        if re.match(r'(s|r)+', cmd):
            show_string = cmd
            print "### show_string = '%s'" % show_string
        elif cmd == "":
            print "### sending '^m'"
            send_control('m')
        else:
            print "### sending '%s' + ^m" % cmd
            send(cmd)
            send_control('m')

    sock.close()


if __name__ == '__main__':
    if not 3 <= len(sys.argv) <= 4:
        print """
USAGE:
  direct.py address port [pd0_file]

Connects to instrument on address:port. Parses and displays all received
timestamps and PD0 ensembles. Also displays some info about unprocessed
fragments from the incoming stream. It writes the first received PD0 ensemble
into the given file, if any. It also sends user commands to the socket.

Examples:
  direct.py 10.180.80.178 2101
  direct.py 10.180.80.178 2101 pd0_sample.bin
        """
        exit()

    host = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3] if len(sys.argv) == 4 else None

    pd0_file = file(filename, 'w') if filename else None

    global out_file
    out_file = file('direct_recv.txt', 'w')

    print "### connecting to %s:%s" % (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # start the receiving thread:
    bufsize = 4096
    t = Thread(target=receive, args=(sock, bufsize, pd0_file, out_file))
    t.setDaemon(True)
    t.start()

    # run interaction:
    try:
        user_loop(sock)
    except KeyboardInterrupt:
        pass
