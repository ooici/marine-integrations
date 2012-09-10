/*******************************************************************************
 * Class: TcpCommSocket
 * Filename: tcp_comm_socket.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage a TCP connection to a network server.
 *
 ******************************************************************************/

#include "tcp_comm_socket.h"
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
TCPCommSocket::TCPCommSocket() {
	m_sHostname = "";
	m_iPort = 0;
}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
TCPCommSocket::TCPCommSocket(const TCPCommSocket &rhs) {
	m_sHostname = rhs.m_sHostname;
	m_iPort = rhs.m_iPort;
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
TCPCommSocket::~TCPCommSocket() {
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
TCPCommSocket & TCPCommSocket::operator=(const TCPCommSocket &rhs) {
	m_sHostname = rhs.m_sHostname;
	m_iPort = rhs.m_iPort;

	return *this;
}

/******************************************************************************
 * Method: copy
 * Description: return a new object deep copied.
 ******************************************************************************/
CommBase * TCPCommSocket::copy() {
	return new TCPCommSocket(*this);
}


/******************************************************************************
 * Method: connect
 * Description: Connect to a network server
 * Exceptions:
 *   SocketMissingConfig
 ******************************************************************************/
bool TCPCommSocket::initialize() {
	int fflags;
	struct sockaddr_in serv_addr;
	struct hostent *server;

	LOG(DEBUG) << "TCP Port Agent init_comms_device()";

	if(!isConfigured())
		throw SocketMissingConfig("missing port or hostname");

	LOG(DEBUG2) << "Creating INET socket";
	m_pSocketFD = socket(AF_INET, SOCK_STREAM, 0);

	if(!m_pSocketFD)
		throw SocketCreateFailure("socket create failure");

	LOG(DEBUG2) << "Looking up server name";
	server = gethostbyname(m_sHostname.c_str());

	if(!server)
		throw SocketHostFailure(m_sHostname.c_str());

	bzero((char *) &serv_addr, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	bcopy((char *)server->h_addr,
		 (char *)&serv_addr.sin_addr.s_addr,
		 server->h_length);
	serv_addr.sin_port = htons(m_iPort);

	LOG(DEBUG2) << "Connecting to server";
	int retval = connect(m_pSocketFD,(struct sockaddr *) &serv_addr,sizeof(serv_addr));
	if (retval < 0)
	    if(errno != EINPROGRESS ) // ignore EINPROGRESS error because we are NON-Blocking
                throw(SocketConnectFailure(strerror(errno)));

	LOG(DEBUG3) << "Connect result: " << retval;
	
	if(! blocking()) {
		LOG(DEBUG3) << "set socket non-blocking";
		fcntl(m_pSocketFD, F_SETFL, O_NONBLOCK);
	}

	m_bConnected = true;
	
	return true;
}

/******************************************************************************
 * Method: isConfigured
 * Description: Does this class have enough config info?
 ******************************************************************************/
bool TCPCommSocket::isConfigured() {
    return m_sHostname.length() && m_iPort > 0;
}
