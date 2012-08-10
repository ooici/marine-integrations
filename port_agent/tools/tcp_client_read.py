#!/usr/bin/python
#
# Tool to read from a TCP socket.  
#
# The host information is hardcoded to match the tcp test 
# server program

from socket import *
import sys
 
HOST = 'localhost'
PORT = 4010    #our port from before
ADDR = (HOST,PORT)
 
cli = socket( AF_INET,SOCK_STREAM)
cli.connect((ADDR))

while(1):
	data = cli.recv(4096)
	print data.rstrip();

cli.close()
