#!/usr/bin/python
#
# Utility that accepts TCP socket connections and spits out a 
# random stream of data.
#

import socket 
import errno 
import sys 
import time
 
##let's set up some constants
HOST = ''    #we are the host
PORT = 40002    #arbitrary port not currently in use
ADDR = (HOST,PORT)    #we need a tuple for the address
BUFSIZE = 4096    #reasonably sized buffer for data
TIMEOUT = 30         # Socket timeout

## now we create a new socket object (serv)
## see the python docs for more information on the socket types/flags
serv = socket.socket( socket.AF_INET,socket.SOCK_STREAM)    
 
##bind our socket to the address
serv.bind((ADDR))    #the double parens are to create a tuple with one element
serv.listen(5)
serv.settimeout(TIMEOUT)

conn,addr = serv.accept() #accept the connection


while True:
	try:
		conn.send("%19.9f\n" % time.time() );
		time.sleep(1);
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
