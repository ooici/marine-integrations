/*******************************************************************************
 * Class: InstrumentPublisher
 * Filename: instrument_publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base class for publishers writing to instrument connections.  These
 * publishers don't write packet data, but just output the raw payload of the
 * packet.  Therefore, we don't really care about ascii mode or not.
 *
 ******************************************************************************/

#include "instrument_publisher.h"
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
 * Method: logPacket
 * Description: Write a packet of data to the internal file pointer.  Raise an
 * error if we don't have a file pointer.
 *
 * Parameter:
 *    Packet* - Pointer to a packet of data we need to write to the FILE*
 ******************************************************************************/
bool InstrumentPublisher::logPacket(Packet *packet) {
    return write(packet->payload(), packet->payloadSize());
}

