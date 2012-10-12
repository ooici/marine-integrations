/*******************************************************************************
 * Class: InstrumentCommandPublisher
 * Filename: instrument_command_publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes raw data to the instrument commanddata port.  The
 * only packets it has a handler for is COMMAND_FROM_DRIVER packets
 *
 ******************************************************************************/

#include "instrument_command_publisher.h"
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
InstrumentCommandPublisher::InstrumentCommandPublisher() { }

/******************************************************************************
 * Method: handleDriverData
 * Description: The only handler this publisher cares about!
 ******************************************************************************/
bool InstrumentCommandPublisher::handleInstrumentCommand(Packet *packet) {
	return logPacket(packet);
}
