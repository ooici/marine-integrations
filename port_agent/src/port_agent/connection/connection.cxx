/*******************************************************************************
 * Class: Connection
 * Filename: connection.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base class for an instrument or observatory connection.  It is responsible
 * for setting up the socket communications for the data port as well as the
 * command port if required.
 *    
 ******************************************************************************/

#include "connection.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "network/comm_base.h"

using namespace std;
using namespace logger;
using namespace network;
using namespace port_agent;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/
/******************************************************************************
 * Method: Constructor
 * Description: Default constructor.  Is likely never called, but wanted to
 *              define it explicitly.
 ******************************************************************************/
Connection::Connection() {
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
Connection::Connection(const Connection& rhs) {
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
Connection::~Connection() {
}

/******************************************************************************
 * Method: Assignemnt operator
 * Description: Deep copy
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
Connection & Connection::operator=(const Connection &rhs) {
}


/******************************************************************************
 * Method: initialize
 * Description: Initialize any uninitialized sockets if they are configured.
 ******************************************************************************/
void Connection::initialize() {
    if(!dataConfigured())
        LOG(DEBUG) << "Data port not configured. Not initializing";
	
    if(!commandConfigured())
        LOG(DEBUG) << "Command port not configured. Not initializing";
	
    if(dataConfigured() && ! dataInitialized())
        initializeDataSocket();
	
    if(commandConfigured() && ! commandInitialized())
        initializeCommandSocket();
}


