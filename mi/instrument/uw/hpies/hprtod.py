#!/usr/bin/env python
# hprtod.py -- send time of day out serial port
# John Dunlap, APL/UW
# updated Apr 02, 2014

from __future__ import print_function

import sys
import os
import time
from datetime import datetime

import psutil
import serial
from crclib import chksumnmea


# make a tty lock file
def lock_tty(tty):
    if sys.platform != 'linux2':
        return
    if tty == None:
        return

    tty = tty.split('/')
    tty = tty[-1]

    filename = '/var/lock/LCK..' + tty

    if os.path.exists(filename):
        ifp = open(filename, 'rt')
        buf = ifp.readline()
        ifp.close()
        pid = int(buf.strip())
        if psutil.pid_exists(pid):
            print('a process with pid {0} exists'.format(pid))
            print('not removing lock file=', filename)
            cleanup()
        else:
            #     print('a process with pid {0} does not exist'.format(pid))
            print('removing stale lock file,', filename)
            os.remove(filename)

    ofp = open(filename, 'wt')
    pid = os.getpid()
    ofp.write(str.format('{0:d}\n', pid))
    ofp.close()


# remove a tty lock file
def unlock_tty(tty):
    if sys.platform != 'linux2':
        return
    if tty == None:
        return

    tty = tty.split('/')
    tty = tty[-1]

    filename = '/var/lock/LCK..' + tty

    try:
        os.remove(filename)
    except OSError:
        print('cannot remove lock file ' + filename)

# main

if __name__ == '__main__':

    tod_tty = '/dev/ttyR2'  # time of day
    lock_tty(tod_tty)
    tod_ser = serial.Serial(tod_tty, 9600, timeout=0)

    while True:
        # $GPZDA,hhmmss.ss,dd,mm,yyyy,xx,yy*CC
        now = datetime.utcnow()
        hms = now.strftime("%H%M%S")
        dmy = now.strftime("%d,%m,%Y")
        hun = now.strftime("%f")[:2]
        s = 'GPZDA,' + hms + '.' + hun + ',' + dmy + ',00,00'
        s = '$' + s + '*' + str.format('{0:02X}', chksumnmea(s))
        #   print(s)
        tod_ser.write(s + '\r\n')

        time.sleep(0.999)

