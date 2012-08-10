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
 * Method: connect
 * Description: Connect to a network server
 * Exceptions:
 *   SocketMissingConfig
 ******************************************************************************/
bool TCPCommSocket::connect() {
	return true;
}


