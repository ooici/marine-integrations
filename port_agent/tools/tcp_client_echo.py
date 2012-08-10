#!/usr/bin/python


# Tool to read from a TCP socket then write it back
#
# The host information is hardcoded to match the tcp test 
# server program

from optparse import OptionParser
from socket import *
import sys
from subprocess import call
call(["touch", "/tmp/file"])

usage = \
"""
%prog [options]
"""
description = \
"""Use this program to write data to a TCP port and echo it back to the same port
"""

parser = OptionParser(usage=usage, description=description)
parser.add_option("-p", "--port", dest="port", default=40000, help="specify a port", action="store", type=int, metavar="PORT")
parser.add_option("-d", "--data", dest="data", help="data to send", action="store")

(options, args) = parser.parse_args()

HOST = 'localhost'
PORT = options.port
ADDR = (HOST,PORT)


cli = socket( AF_INET,SOCK_STREAM)
cli.connect((ADDR))

if(options.data):
	cli.send(options.data)

data = cli.recv(4096)

if(options.data):
	print data
else:
       	cli.send(data)

cli.close()
