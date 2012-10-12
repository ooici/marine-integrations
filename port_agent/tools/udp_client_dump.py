#!/usr/bin/python


# Tool to write to a UDP server
#
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
"""Use this program to write data to a UDP port and echo it back to the same port
"""

parser = OptionParser(usage=usage, description=description)
parser.add_option("-p", "--port",  dest="port", default=40000, help="specify a port", action="store", type=int, metavar="PORT")
parser.add_option("-f", "--data_file",  dest="data_file", help="data dump output file", action="store")
parser.add_option("-t", "--timeout",  dest="timeout", help="socket timeout", default=30, action="store")

(options, args) = parser.parse_args()

HOST = 'localhost'
PORT = options.port
ADDR = (HOST,PORT)
CONNECT_TIMEOUT = options.timeout
FILE = options.data_file

cli = socket(AF_INET,SOCK_DGRAM)
cli.bind(ADDR)
cli.settimeout(CONNECT_TIMEOUT)

print("recv data.")
data, addr = cli.recvfrom(2048)

print "READ: " + data
print "FILE: " + FILE
cli.close()

file = open(FILE, "w");
file.write(data)
file.close()
