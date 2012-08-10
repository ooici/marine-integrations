/*******************************************************************************
 * Class: UDPCommListener
 * Filename: udp_comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage TCP listeners
 *
 ******************************************************************************/

#include "udp_comm_listener.h"
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
UDPCommListener::UDPCommListener() {

}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
UDPCommListener::UDPCommListener(const UDPCommListener &rhs) {
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
UDPCommListener::~UDPCommListener() {
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
UDPCommListener & UDPCommListener::operator=(const UDPCommListener &rhs) {
	return *this;
}



