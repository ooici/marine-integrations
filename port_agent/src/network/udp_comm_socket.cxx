/*******************************************************************************
 * Class: UdpCommSocket
 * Filename: udp_comm_socket.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * UDP Client Connection.  For the port agent we only care about UDP writes so
 * we didn't implement any read logic.
 * 
 * Usage:
 *
 * UDPCommSocket socket;
 *
 * // Set connetions information
 * socket.setPort(1029);
 * socket.setHostname("localhost");
 * 
 * // Enable blocking connections. Default is non-blocking
 * socket.setBlocking(true);
 *
 * // Initialize the connection
 * socket.initialize();
 * 
 * // Read data from a client. Ignores source address information.
 * char buffer[128];
 * int bytes_read = socket.readData(buffer, 128);
 *
 * // Write data to the client.
 * int bytes_written = socket.writeData("Hello World", strlen("Hello World"));
 *
 ******************************************************************************/

#include "udp_comm_socket.h"
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
UDPCommSocket::UDPCommSocket() : CommSocket() {
	m_sHostname = "";
	m_iPort = 0;
}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
UDPCommSocket::UDPCommSocket(const UDPCommSocket &rhs) {
	m_sHostname = rhs.m_sHostname;
	m_iPort = rhs.m_iPort;
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
UDPCommSocket::~UDPCommSocket() {
}

/******************************************************************************
 * Method: copy
 * Description: return a new object deep copied.
 ******************************************************************************/
CommBase * UDPCommSocket::copy() {
	return new UDPCommSocket(*this);
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
UDPCommSocket & UDPCommSocket::operator=(const UDPCommSocket &rhs) {
	m_sHostname = rhs.m_sHostname;
	m_iPort = rhs.m_iPort;

	return *this;
}


/******************************************************************************
 * Method: isConfigured
 * Description: Nothing to do here.
 ******************************************************************************/
bool UDPCommSocket::isConfigured() {
    return m_sHostname.length() && m_iPort > 0;
}

/******************************************************************************
 * Method: initalize
 * Description: Setup a UDP listener
 * Exceptions:
 *   SocketMissingConfig
 *   SocketConnectFailure
 ******************************************************************************/
bool UDPCommSocket::initialize() {
	int fflags;
	int newsock;
        struct sockaddr_in serv_addr;
        struct hostent *server;
	
	LOG(DEBUG) << "UDP Client initialize()";

	if(!isConfigured())
		throw SocketMissingConfig("missing inet port");

	LOG(DEBUG2) << "Creating INET socket";
	newsock = socket(AF_INET, SOCK_DGRAM, 0);

	if(!newsock)
		throw SocketCreateFailure("socket create failure");

        LOG(DEBUG2) << "Looking up server name";
	server = gethostbyname(m_sHostname.c_str());

	if(!server || server->h_length == 0)
		throw SocketHostFailure(m_sHostname.c_str());

	bzero((char *) &serv_addr, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	bcopy((char *)server->h_addr,
		 (char *)&serv_addr.sin_addr.s_addr,
		 server->h_length);
	serv_addr.sin_port = htons(m_iPort);
	
	if(! blocking()) {
		LOG(DEBUG3) << "set server socket non-blocking";
		fcntl(newsock, F_SETFL, O_NONBLOCK);
		int opts = fcntl(newsock, F_GETFL);
		LOG(DEBUG3) << "fd: " << hex << newsock << " "
		            << "sock opts: " << hex << opts << " "
		            << "non block flag: " << hex << O_NONBLOCK;
	}
	
	LOG(DEBUG2) << "storing new fd: " << newsock;
	m_pSocketFD = newsock;
	
	return true;
}


/******************************************************************************
 * Method: write
 * Description: Write a number of bytes to a udp socket.  We don't sent to
 * specific hosts, but blast to everyone.  Direct host traffic isn't needed
 * and if it is try using a TCP connection.
 *
 * Parameters:
 *   buffer - the data to write
 *   size - the size of the buffer array
 * Return:
 *   returns the number of bytes written.
 * Exceptions:
 *   SocketNotInitialized
 *   SocketWriteFailure
 ******************************************************************************/
uint32_t UDPCommSocket::writeData(const char *buffer, const uint32_t size) {
    int count;
    struct sockaddr_in serv_addr;
    struct hostent *server;
    socklen_t sendsize = sizeof(serv_addr);

    if(! connected())
        throw(SocketNotInitialized());

    LOG(DEBUG2) << "Looking up server name";
    server = gethostbyname(m_sHostname.c_str());

    if(!server || server->h_length == 0)
        throw SocketHostFailure(m_sHostname.c_str());
    
    bzero((char *) &serv_addr, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    bcopy((char *)server->h_addr, (char *)&serv_addr.sin_addr.s_addr,
          server->h_length);
    serv_addr.sin_port = htons(m_iPort);
	
    LOG(DEBUG) << "WRITE DEVICE: " << buffer;
    int res = sendto(m_pSocketFD, buffer, size, 0, (struct sockaddr*)&serv_addr, sendsize);
    
    if(res < 0) {
	throw SocketWriteFailure(strerror(errno));
    }
    LOG(DEBUG) << "bytes written: " << res;

    return size;
}


/******************************************************************************
 * Method: readData
 * Description: the port agent doesn't currently need to read UDP so we didn't
 * implement code to do that.  Just one more thing to test if we did. 
 *
 * Parameters:
 *   buffer - where to store the read data
 *   size - max number of bytes to read
 * Return:
 *   A big BOOM
 * Exceptions:
 *   NotImplemented
 ******************************************************************************/
uint32_t UDPCommSocket::readData(char *buffer, const uint32_t size) {
    throw NotImplemented();
}