/*******************************************************************************
 * Class: CommSocket
 * Filename: comm_socket.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base clase for making network connection to TCP or UDP servers
 *
 ******************************************************************************/

#include "comm_socket.h"
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
CommSocket::CommSocket() {
    m_pSocketFD = 0;
}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
CommSocket::CommSocket(const CommSocket &rhs) {
	m_pSocketFD = rhs.m_pSocketFD;
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
CommSocket::~CommSocket() {
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
CommSocket & CommSocket::operator=(const CommSocket &rhs) {
	m_pSocketFD = rhs.m_pSocketFD;
	return *this;
}


/******************************************************************************
 * Method: close
 * Description: close the connection and reselt the file descriptor.  Don't
 * know if we can do this from the base class, but we will start here.
 *
 * Return:
 *   returns true if the socket wasn't open or it closed successfully.
 ******************************************************************************/
bool CommSocket::disconnect() {
    if(!m_pSocketFD)
        return true;

    LOG(DEBUG) << "Shutdown socket";
    shutdown(m_pSocketFD, 1);
    
    LOG(DEBUG) << "Close socket";
    close(m_pSocketFD);
    
    m_pSocketFD = 0;

    m_bConnected = false;
    
    return true;
}

/******************************************************************************
 *   PROTECTED METHODS
 ******************************************************************************/

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
 *   SocketNotConnected
 *   SocketWriteFailure
 ******************************************************************************/
uint32_t CommSocket::writeData(const char *buffer, const uint32_t size) {
    int bytesWritten = 0;
    int bytesRemaining = size;
    int count;

    if(! connected())
        throw(SocketWriteFailure("not connected"));
    
    while( bytesRemaining > 0 ) {
        LOG(DEBUG) << "WRITE DEVICE: " << buffer;
        count = write(m_pSocketFD, buffer + bytesWritten, bytesRemaining );
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
 *   SocketNotConnected
 *   SocketReadFailure
 ******************************************************************************/
uint32_t CommSocket::readData(char *buffer, const uint32_t size) {
    int bytesRead = 0;

    if(! connected())
        throw(SocketReadFailure("not connected"));
    
    if ((bytesRead = read(m_pSocketFD, buffer, size)) <= 0) {
        if(errno != EAGAIN && errno != EINPROGRESS) {
            LOG(ERROR) << "read_device: " << strerror(errno) << "(errno: " << errno << ")";
            throw(SocketReadFailure(strerror(errno)));
        }
        if(errno == EAGAIN || errno == EINPROGRESS) {
            LOG(DEBUG2) << "Error Ignored: " << strerror(errno);
        }

        LOG(DEBUG2) << "read bytes: " << bytesRead;
    }
    else if(bytesRead == 0) {
        LOG(INFO) << " -- Device connection closed. zero bytes recv.";
        disconnect();
    }
    else
        LOG(DEBUG) << "READ DEVICE: " << buffer;

    return bytesRead < 0 ? 0 : bytesRead;
}


