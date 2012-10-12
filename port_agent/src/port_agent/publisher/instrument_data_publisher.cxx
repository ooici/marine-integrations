/*******************************************************************************
 * Class: InstrumentDataPublisher
 * Filename: instrument_Data_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes raw Data to the instrument Data port.  The only packets
 * it has a handler for is DATA_FROM_DRIVER packets
 *
 ******************************************************************************/

#include "instrument_Data_publisher.h"
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
InstrumentDataPublisher::InstrumentDataPublisher() { }

/******************************************************************************
 * Method: handleDriverData
 * Description: The only handler this publisher cares about!
 ******************************************************************************/
bool InstrumentDataPublisher::handleDriverData(Packet *packet) {
	return logPacket(packet);
}
