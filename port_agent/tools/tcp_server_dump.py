#!/usr/bin/python
#
# Utility that listens on a TCP socket recieves a packet of data
# and then writes that line to stdout.  
#
# The server will exit if no data is sent in the timeout period

import socket 
import errno 
import sys 
 
##let's set up some constants
HOST = ''    #we are the host
PORT = 40000    #arbitrary port not currently in use
ADDR = (HOST,PORT)    #we need a tuple for the address
BUFSIZE = 4096    #reasonably sized buffer for data
TIMEOUT = 30         # Socket timeout

if len(sys.argv) > 1:
	OUTPUT_FILE = sys.argv[1];
else:
	OUTPUT_FILE = "/dev/stdout"
 
## now we create a new socket object (serv)
## see the python docs for more information on the socket types/flags
serv = socket.socket( socket.AF_INET,socket.SOCK_STREAM)    
 
##bind our socket to the address
serv.bind((ADDR))    #the double parens are to create a tuple with one element
serv.listen(5)
serv.settimeout(TIMEOUT)

conn,addr = serv.accept() #accept the connection

FILE = open(OUTPUT_FILE, "w");

while True:
	try:
		data = conn.recv(BUFSIZE)
		if not data: break
		FILE.write(data);
	except socket.error as e:
		# [Errno 35] Resource temporarily unavailable.
		if e.errno == errno.EAGAIN:
			pass
		else:
			raise e


try:
	conn.close()
except Exception, e:
	raise e
