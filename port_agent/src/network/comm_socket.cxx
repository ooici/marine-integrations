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
    m_pSocketFD = NULL;
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
bool CommSocket::close() {
    if(m_pSocketFD == NULL)
        return true;

    fclose(m_pSocketFD);
    m_pSocketFD = NULL;

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
uint32_t CommSocket::write(const char *buffer, const uint32_t size) {
    int count;
    int total = 0;

    if(m_pSocketFD == NULL)
        throw SocketNotConnected();

    // Try to write data three times.  Throw an error if we fail.
    for( int i = 0; i < 3 && total < size; i++) {
            total += fwrite(buffer + total, 1, size - total, m_pSocketFD);
    }

    if(total != size)
            throw SocketWriteFailure();

    return true;
}



