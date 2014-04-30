# locktty.py -- make and remove lock files for /dev/tty...

from __future__ import print_function

import sys
import os
from subprocess import call

import psutil


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
            return
        else:
            #     print('a process with pid {0} does not exist'.format(pid))
            print('removing stale lock file,', filename)
            #     os.remove(filename)
            call(["rm", "-f", filename])

    ofp = open(filename, 'wt')
    pid = os.getpid()
    ofp.write(str.format('{0:d}\n', pid))
    ofp.close()


# fp = open(filename, 'w')
# try:
#   fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
# except IOError:
#   print('cannot make lock file ' + filename))
#   cleanup()

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
        # os.remove(filename)
        call(["rm", "-f", filename])
    except OSError:
        print('cannot remove lock file ' + filename)
