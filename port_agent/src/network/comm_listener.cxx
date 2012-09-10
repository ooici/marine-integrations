/*******************************************************************************
 * Class: CommListener
 * Filename: comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * base class for network listeners
 *
 ******************************************************************************/

#include "comm_listener.h"
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
CommListener::CommListener() {
    m_iPort = 0;
	    
    m_pServerFD = 0;
    m_pClientFD = 0;
}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
CommListener::CommListener(const CommListener &rhs) {
    m_iPort = rhs.m_iPort;
	    
    m_pServerFD = rhs.m_pServerFD;
    m_pClientFD = rhs.m_pClientFD;
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
CommListener::~CommListener() {
    disconnect();
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
CommListener & CommListener::operator=(const CommListener &rhs) {
    m_iPort = rhs.m_iPort;
	    
    m_pServerFD = rhs.m_pServerFD;
    m_pClientFD = rhs.m_pClientFD;
    
    return *this;
}


/******************************************************************************
 * Method: disconnect
 * Description: Disconnect a client and server
 * Exceptions:
 *   SocketMissingConfig
 ******************************************************************************/
bool CommListener::disconnect() {
    LOG(DEBUG) << "Shutdown server";
    
    disconnectClient();
    
    if(listening()) {
        LOG(DEBUG2) << "Closing server connection";
	shutdown(m_pServerFD,2);
	close(m_pServerFD);
	m_pServerFD = 0;
    }
    
    return true;
}

/******************************************************************************
 * Method: disconnectClient
 * Description: Disconnect a client
 ******************************************************************************/
bool CommListener::disconnectClient() {
    if(connected()) {
        LOG(DEBUG2) << "Disconnecting client";
	shutdown(m_pClientFD,2);
	close(m_pClientFD);
	m_pClientFD = 0;
    }
    
    return true;
}

/******************************************************************************
 * Method: acceptClient
 * Description: Accept a client connection and create a new FD
 * Exceptions:
 *   SocketNotInitialized
 *   SocketAlreadyConnected
 ******************************************************************************/
bool CommListener::acceptClient() {
    socklen_t clilen;
    struct sockaddr_in cli_addr;
    
    int newsockfd;
    
    if(!listening())
        throw SocketNotInitialized();

    if(connected())
        throw SocketAlreadyConnected();

    LOG(DEBUG) << "accepting client connection";
     
    clilen = sizeof(cli_addr);
    newsockfd = accept(m_pServerFD, 
                (struct sockaddr *) &cli_addr, 
                &clilen);
     
    LOG(DEBUG2) << "client FD: " << newsockfd;
    
    if (newsockfd < 0) {
	if(errno == EAGAIN  || errno == EWOULDBLOCK) {
	    LOG(DEBUG2) << "Non-blocking error ignored: " << strerror(errno) << "(" << errno << ")";
	    return false;
	}
	else {
            throw SocketConnectFailure(strerror(errno));
	}
    }
    
    // Set the client to non blocking if needed
    if(! blocking()) {
	LOG(DEBUG3) << "set client non-blocking";
	fcntl(newsockfd, F_SETFL, O_NONBLOCK);
    }
    
    m_pClientFD = newsockfd;
    return true;
}

/******************************************************************************
 * Method: getListenPort
 * Description: Return the port the server is actually listening on.
 * Exceptions:
 *   SocketNotInitialized
 ******************************************************************************/
uint16_t CommListener::getListenPort() {
    struct sockaddr_in sin;
    socklen_t len = sizeof(sin);
    
    LOG(DEBUG) << "Fetch listen port";
    
    if(!listening())
        throw SocketNotInitialized();

    LOG(DEBUG2) << "get port from FD " << m_pServerFD;

    if (getsockname(m_pServerFD, (struct sockaddr *)&sin, &len) == -1)
        throw SocketConnectFailure(strerror(errno));
        
    return ntohs(sin.sin_port);
}
