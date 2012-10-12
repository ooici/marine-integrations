/*******************************************************************************
 * Class: TcpCommListener
 * Filename: tcp_comm_listener.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage a TCP listener.
 *
 * Usage:
 *
 * TCPCommListener ts;
 *
 * // Statically assign the port.  If not assigned then us a random port.
 * ts.setPort(1024);
 *
 * // Enable blocking connections. Default is non-blocking
 * ts.setBlocking(true);
 *
 * // Initialize the server
 * ts.initalize();
 *
 * // Get the port the server is actually listening on.  Useful when using
 * // random ports.
 * uint16_t port = ts.getListenPort();
 * 
 * // Accept client connections
 * ts.acceptClient();
 *
 * // Read data from the client. Honors the blocking flag set earlier.
 * char buffer[128];
 * int bytes_read = ts.readData(buffer, 128);
 *
 * // Write data to the client.
 * int bytes_written = ts.writeData("Hello World", strlen("Hello World"));
 *
 * // When using non-blocking you may want to use a select read loop to monitor
 * // the file descriptors.  They are exposed via accessors
 * int serverFD = ts.getServerFD();
 * int clientFD = ts.getServerFD();
 ******************************************************************************/

#include "tcp_comm_listener.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"

#include <netinet/in.h>
#include <netdb.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/fcntl.h>
#include <stdio.h>
#include <stdlib.h>


using namespace std;
using namespace logger;
using namespace network;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: Default constructor.
 ******************************************************************************/
TCPCommListener::TCPCommListener() : CommListener() {

}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
TCPCommListener::TCPCommListener(const TCPCommListener &rhs) {
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
TCPCommListener::~TCPCommListener() {
}

/******************************************************************************
 * Method: copy
 * Description: return a new object deep copied.
 ******************************************************************************/
CommBase * TCPCommListener::copy() {
	return new TCPCommListener(*this);
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
TCPCommListener & TCPCommListener::operator=(const TCPCommListener &rhs) {
	return *this;
}


/******************************************************************************
 * Method: isConfigured
 * Description: Nothing to do here.
 ******************************************************************************/
bool TCPCommListener::isConfigured() {
    return true;
}

/******************************************************************************
 * Method: initalize
 * Description: Setup a TCP listener
 * Exceptions:
 *   SocketMissingConfig
 *   SocketConnectFailure
 ******************************************************************************/
bool TCPCommListener::initialize() {
	int fflags;
	struct sockaddr_in serv_addr;
	struct hostent *server;
        int retval;
	int newsock;
	
	LOG(DEBUG) << "TCP Listener initialize()";

	if(!isConfigured())
		throw SocketMissingConfig("missing inet port");

	LOG(DEBUG2) << "Creating INET socket";
	newsock = socket(AF_INET, SOCK_STREAM, 0);

	if(!newsock)
		throw SocketCreateFailure("socket create failure");

	bzero((char *) &serv_addr, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_addr.s_addr = INADDR_ANY;
	serv_addr.sin_port = htons(m_iPort);

	LOG(DEBUG2) << "bind to port " << m_iPort;
	if (bind(newsock, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0) 
            SocketConnectFailure(strerror(errno));
	    
	LOG(DEBUG2) << "Starting server";
	retval = listen(newsock, 5);
	LOG(DEBUG3) << "listen return value: " << retval;
	
	if (retval < 0)
	    if(errno != EINPROGRESS ) // ignore EINPROGRESS error because we are NON-Blocking
                throw(SocketConnectFailure(strerror(errno)));

	if(! blocking()) {
		LOG(DEBUG3) << "set server socket non-blocking";
		fcntl(newsock, F_SETFL, O_NONBLOCK);
		int opts = fcntl(newsock, F_GETFL);
		LOG(DEBUG3) << "fd: " << hex << newsock << " "
		            << "sock opts: " << hex << opts << " "
		            << "non block flag: " << hex << O_NONBLOCK;
	}
	
	LOG(DEBUG2) << "storing new fd: " << newsock;
	m_pServerFD = newsock;
	
	// Fail if we tried to bind to a specific port, but it gave us a random
	// port instead.
	if(m_iPort && getListenPort() != m_iPort)
	    throw SocketConnectFailure("bind to port failed");
	
	LOG(DEBUG2) << "startup complete.  host port " << getListenPort();
	return true;
}


/******************************************************************************
 * Method: write
 * Description: write a number of bytes to the socket connection.  Currently we
 * try to write three times before we fail.  We might want to update this retry
 * so that it keeps retrying if it see progress being made?
 *
 * Parameters:
 *   buffer - the data to write
 *   size - the size of the buffer array
 * Return:
 *   returns the actual number of bytes written.
 * Exceptions:
 *   SocketNotInitialized
 *   SocketNotConnected
 *   SocketWriteFailure
 ******************************************************************************/
uint32_t TCPCommListener::writeData(const char *buffer, const uint32_t size) {
    int bytesWritten = 0;
    int bytesRemaining = size;
    int count;

    if(! listening())
        throw(SocketNotInitialized());

    if(! connected())
        throw(SocketNotConnected());
    
    while( bytesRemaining > 0 ) {
        LOG(DEBUG) << "WRITE DEVICE: " << buffer;
        count = write(m_pClientFD, buffer + bytesWritten, bytesRemaining );
        LOG(DEBUG1) << "bytes written: " << count << " remaining: " << bytesRemaining;
        if(count < 0) {
            LOG(ERROR) << strerror(errno) << "(errno: " << errno << ")";
            throw(SocketWriteFailure(strerror(errno)));
        }

        bytesWritten += count;
        bytesRemaining -= count;

        LOG(DEBUG2) << "wrote bytes: " << count << " bytes remaining: " << bytesRemaining;
    }

    return bytesWritten;
}


/******************************************************************************
 * Method: read
 * Description: read a number of bytes to the socket connection.
 *
 * Parameters:
 *   buffer - where to store the read data
 *   size - max number of bytes to read
 * Return:
 *   returns the actual number of bytes read.
 * Exceptions:
 *   SocketNotInitialized
 *   SocketNotConnected
 *   SocketReadFailure
 ******************************************************************************/
uint32_t TCPCommListener::readData(char *buffer, const uint32_t size) {
    int bytesRead = 0;

    if(! listening())
        throw(SocketNotInitialized());

    if(! connected())
        throw(SocketNotConnected());
    
    if ((bytesRead = read(m_pClientFD, buffer, size)) <= 0) {
        if(errno == EAGAIN || errno == EINPROGRESS) {
            LOG(DEBUG2) << "Error Ignored: " << strerror(errno);
	} else if( errno = ETIMEDOUT ) {
            LOG(DEBUG) << " -- socket read timeout. disconnecting client.";
            disconnectClient();
	} else {
            LOG(ERROR) << "read_device: " << strerror(errno) << "(errno: " << errno << ")";
            throw(SocketReadFailure(strerror(errno)));
        }

        LOG(DEBUG2) << "read bytes: " << bytesRead;
    }
    else if(bytesRead == 0) {
        LOG(INFO) << " -- Device connection closed. zero bytes recv.";
        disconnectClient();
    }
    else
        LOG(DEBUG) << "READ DEVICE: " << buffer;

    return bytesRead < 0 ? 0 : bytesRead;
}