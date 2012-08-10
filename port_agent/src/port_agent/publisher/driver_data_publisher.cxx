/*******************************************************************************
 * Class: DriverDataPublisher
 * Filename: driver_Data_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Write packets to the driver data port.
 *
 ******************************************************************************/

#include "driver_data_publisher.h"
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
DriverDataPublisher::DriverDataPublisher() { }
