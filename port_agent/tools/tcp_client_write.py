#!/usr/bin/python
#
# Tool to write to a TCP socket.  Read from STDIN and dump
# to a TCP socket.  
#
# The host information is hardcoded to match the tcp test 
# server program

from optparse import OptionParser
from socket import *
import sys
import time
 
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

time.sleep(1);

while(1):
	line = sys.stdin.readline()
	if not line:
		break
	cli.send(line)

cli.close()
