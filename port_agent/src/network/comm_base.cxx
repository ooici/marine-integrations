/*******************************************************************************
 * Class: CommBase
 * Filename: comm_base.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * CommBase is the base class for network socket communications.  From this
 * class we will derive classes to setup TCP and UDP socket and listeners.
 *
 ******************************************************************************/

#include "comm_base.h"
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
CommBase::CommBase() {
    // Default behavior for sockets is non-blocking
    m_bBlocking = false;
    m_bConnected = false;
}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
CommBase::CommBase(const CommBase &rhs) {
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
CommBase::~CommBase() {
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
CommBase & CommBase::operator=(const CommBase &rhs) {
	return *this;
}



