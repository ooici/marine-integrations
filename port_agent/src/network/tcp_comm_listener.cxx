/*******************************************************************************
 * Class: TcpCommListener
 * Filename: tcp_comm_listener.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage a TCP listener.
 *
 ******************************************************************************/

#include "tcp_comm_listener.h"
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
TCPCommListener::TCPCommListener() {

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
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
TCPCommListener & TCPCommListener::operator=(const TCPCommListener &rhs) {
	return *this;
}



