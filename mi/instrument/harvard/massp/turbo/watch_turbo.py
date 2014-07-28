#!/usr/bin/env python

import sys
import time
import Queue
import socket
from threading import Thread
import argparse

NEWLINE = '\r'

DRIVE_CURRENT = 310
DRIVE_VOLTAGE = 313
TEMP_BEARING = 342
TEMP_MOTOR = 346
ROTATION_SPEED_ACTUAL = 398

names = {
    DRIVE_CURRENT: 'DRIVE_CURRENT',
    DRIVE_VOLTAGE: 'DRIVE_VOLTAGE',
    TEMP_BEARING: 'TEMP_BEARING',
    TEMP_MOTOR: 'TEMP_MOTOR',
    ROTATION_SPEED_ACTUAL: 'SPEED'
}


query_temp_bearing = '0010034202=?104' + NEWLINE
query_temp_motor = '0010034602=?108' + NEWLINE
query_speed_actual = '0010039802=?115' + NEWLINE
query_current = '0010031002=?099' + NEWLINE
response = '0011039806090000037'

set_pump_on = '0011002306111111019' + NEWLINE
set_station_on = '0011001006111111015' + NEWLINE
set_pump_off = '0011002306000000013' + NEWLINE
set_station_off = '0011001006000000009' + NEWLINE


class Receiver(Thread):
    """
    Thread to receive and print data.
    """
    def __init__(self, conn):
        Thread.__init__(self, name="receiver")
        self._conn = conn
        self.setDaemon(True)

    def run(self):
        while True:
            data = self._conn.recv(4096)
            if data:
                try:
                    value = int(data[-9:-4])
                    key = int(data[5:8])
                    if key in names:
                        print '%-15s : %d' % (names[key], value)
                    else:
                        print 'Received: %r' % data
                except ValueError:
                    pass


class Sender(Thread):
    def __init__(self, conn, q):
        Thread.__init__(self, name="receiver")
        self._conn = conn
        self.q = q
        self.setDaemon(True)

    def run(self):
        while True:
            to_send = self.q.get()
            self._conn.send(to_send)
            print 'Wrote: %r' % to_send
            time.sleep(.1)


class Poller(Thread):
    def __init__(self, conn, q):
        Thread.__init__(self, name="poller")
        self._conn = conn
        self.q = q
        self.setDaemon(True)

    def run(self):
        while True:
            self.q.put(query_temp_bearing)
            self.q.put(query_temp_motor)
            self.q.put(query_speed_actual)
            self.q.put(query_current)
            time.sleep(5)


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
        self._send_q = Queue.Queue()
        self._sock.connect((hostname, portnum))
        self._receiver = Receiver(self._sock)
        self._poller = Poller(self._sock, self._send_q)
        self._sender = Sender(self._sock, self._send_q)
        self._receiver.start()
        self._sender.start()
        self._poller.start()

    def run(self):
        while True:
            data = raw_input().strip().lower()
            start_items = [set_station_on, set_pump_on]
            stop_items = [set_station_off, set_pump_off]
            if data == 'start':
                print 'starting turbo'
                for x in start_items:
                    self._send_q.put(x)
            elif data == 'stop':
                print 'stopping turbo'
                for x in stop_items:
                    self._send_q.put(x)

        self.stop()

    def stop(self):
        self._sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--poll', action='store_true')
    parser.add_argument('host')
    parser.add_argument('port')

    args = parser.parse_args(sys.argv[1:])
    host = args.host
    port = int(args.port)

    print "### connecting to %s:%s" % (host, port)
    sock = socket.socket()
    send_q = Queue.Queue()
    sock.connect((host, port))
    receiver = Receiver(sock)
    sender = Sender(sock, send_q)
    receiver.start()
    sender.start()
    if args.poll:
        poller = Poller(sock, send_q)
        poller.start()

    while True:
        input_data = raw_input().strip().lower()
        start = [set_station_on, set_pump_on]
        stop = [set_station_off, set_pump_off]
        if input_data == 'start':
            print 'starting turbo'
            for each in start:
                send_q.put(each)
        elif input_data == 'stop':
            print 'stopping turbo'
            for each in stop:
                send_q.put(each)

    sock.close()
