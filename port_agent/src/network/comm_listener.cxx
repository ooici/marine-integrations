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

}


/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor.
 ******************************************************************************/
CommListener::CommListener(const CommListener &rhs) {
}


/******************************************************************************
 * Method: Destructor
 * Description: destructor.
 ******************************************************************************/
CommListener::~CommListener() {
}


/******************************************************************************
 * Method: assignment operator
 * Description: overloaded assignment operator.
 ******************************************************************************/
CommListener & CommListener::operator=(const CommListener &rhs) {
	return *this;
}



