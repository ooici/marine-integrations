#!/usr/bin/python
#
# This tool it used to test TCP clients.  It listens on a tcp port and 
# allows clients to connect.  Bytes are read a single character at a time
# until the buffer is empty.  Then the bytes read are sent back to the 
# original sender.
#
# Options:
# 
#  -h, --help - Display the program help screen
#  -s, --single - Accept one client connection then kill the server.
#  -p PORT, --port PORT - Indicate what port to listen on.  Default: 40000
#  -t TIMEOUT, --timeout TIMEOUT - How long should we wait for a client connection?
#                                  set to 0 for no timeout, default 30
#  -d DELAY, --delay DELAY - sleep X number of seconds (fractions ok) before reading
#                            the net byte of data.  This is useful for testing 
#                            blocking vs. non-blocking reads.
#  -o, --stdout - enable this option if the server should output the buffer read to 
#                 stdout after it is read.
#

import socket
import fcntl
import errno 
import sys
import argparse
import time
import os

DEFAULT_TIMEOUT = 30
DEFAULT_PORT    = 40000
DEFAULT_DELAY   = 0

def parseArgs():
    parser = argparse.ArgumentParser(description="TCP Echo Server")
    parser.add_argument("-s", '--single', dest='single', action="store_true",
        help="only accept one connection then quit" )
    parser.add_argument('-p', '--port', dest='port', type=int, default=40000, help='specify the INET port to bind')
    parser.add_argument('-t', '--timeout', dest='timeout', type=int, default=DEFAULT_TIMEOUT, help='listen timeout')
    parser.add_argument('-d', '--delay', dest='delay', type=float, default=DEFAULT_DELAY, help='delay between reading characters from the stream')
    parser.add_argument('-o', '--stdout', dest='stdout', action="store_true", help='write bytes read to stdout')

    return parser.parse_args()


def run_server(serv, opts):
    conn,addr = serv.accept() #accept the connection
    print("client connected");
    
    data = read_tcp(conn, opts.delay);
    if(opts.stdout): print data
    send_tcp(conn, data)

    # Do a final read to handle echoing clients (for tests)
    data = read_tcp(conn, opts.delay);

    try:
        print "closing connection"
        conn.close()
        
    except Exception, e:
        raise e

def send_tcp(conn, buffer):
    print("Sending data: " + buffer)
    result = conn.send(buffer)
    print("result: %d" % result)
    

def read_tcp(conn, read_delay):
    result = ""
    print("read data from client")

    conn.settimeout(0.1);
    while True:
        try:
            data = conn.recv(1)
            if(read_delay): time.sleep(read_delay)
            if(data):
                print("READ: " + data)
                result = result + data
            else:
                print "read complete";
                break
        except socket.timeout:
            print("socket timeout.  read done")
            break
        
        except socket.error as e:
            # [Errno 35] Resource temporarily unavailable.
            if e.errno == errno.EAGAIN:
                print("eagain")
                pass
            
            # [Errno 54] Connection reset by peer.  Because we are reading a single
            # byte at a time we read until we fail.
            elif e.errno == errno.ECONNRESET:
                print("connection reset")
                pass
            else:
                print("read/write error (errno: %d)" % e.errno)
                raise e

    return result



opts = parseArgs()

##let's set up some constants
hostname = ''    #we are the host
portnum = opts.port    #arbitrary port not currently in use
address = (hostname,portnum)    #we need a tuple for the address
buffer_size = 1    #reasonably sized buffer for data
timeout = opts.timeout         # Socket timeout

## now we create a new socket object (serv)
## see the python docs for more information on the socket types/flags
serv = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

##bind our socket to the address
serv.bind((address))    #the double parens are to create a tuple with one element
print("listening")
serv.listen(5)
print("ready for connections")

if(timeout):
    serv.settimeout(timeout)
        
while(1):
    run_server(serv, opts)
    if opts.single:
        break
