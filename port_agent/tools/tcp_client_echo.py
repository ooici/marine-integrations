#!/usr/bin/python


# Tool to read from a TCP socket then write it back
#
# The host information is hardcoded to match the tcp test 
# server program

from optparse import OptionParser
from socket import *
import sys
import time
from subprocess import call

usage = \
"""
%prog [options]
"""
description = \
"""Use this program to write data to a TCP port and echo it back to the same port
"""

parser = OptionParser(usage=usage, description=description)
parser.add_option("-p", "--port",  dest="port", default=40000, help="specify a port", action="store", type=int, metavar="PORT")
parser.add_option("-d", "--data",  dest="data", help="data to send", action="store")
parser.add_option("-t", "--delay", dest="delay", help="delay tcp connection", type=int, action="store")
parser.add_option("-r", "--read_delay", dest="read_delay", help="delay tcp read", type=int, action="store")
parser.add_option("-w", "--write_delay", dest="write_delay", help="delay tcp write", type=int, action="store")

(options, args) = parser.parse_args()

HOST = 'localhost'
PORT = options.port
ADDR = (HOST,PORT)
DELAY = options.delay
CONNECT_TIMEOUT = 5

print "DATA: " + options.data

if(DELAY):
    time.sleep(DELAY)

cli = socket(AF_INET,SOCK_STREAM)
cli.settimeout(CONNECT_TIMEOUT)

cli.connect((ADDR))

print "Connect to %s %d" % ADDR

if(options.data):
    if(options.write_delay):
        time.sleep(options.write_delay)

    print("Send data." )
    cli.send(options.data)

if(options.read_delay):
    time.sleep(options.read_delay)

print("recv data.")
data = cli.recv(4096)

if(data):
    cli.send(data);

cli.close()
