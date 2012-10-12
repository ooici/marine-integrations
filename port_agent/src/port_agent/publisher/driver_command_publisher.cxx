/*******************************************************************************
 * Class: DriverCommandPublisher
 * Filename: driver_command_publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Publish data to the driver command port.
 *
 ******************************************************************************/

#include "driver_command_publisher.h"
#include "common/logger.h"
#include "common/exception.h"
#include "port_agent/packet/packet.h"

#include <sstream>
#include <string>

#include <stdio.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: default constructor
 ******************************************************************************/
DriverCommandPublisher::DriverCommandPublisher() { }
