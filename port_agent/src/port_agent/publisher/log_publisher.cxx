/*******************************************************************************
 * Class: Packet
 * Filename: packet.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Basic packet object for the port agent.  Packets are teh communication
 * protocol for the port agent to outside interfaces via the data and command
 * port.  They are transmitted as binary datagrams with the following structure.
 *
 * This is the most basic type of packet.  Data is given in the constructor
 * and the packet is created.  Once created there is no need to modify the
 * packet and it should be sent immediatly.
 * 
 * A packet contains:
 *
 * sync series      24 bits
 * message type     8 bits
 * packet size      16 bits (including the header)
 * checksum         16 bits
 * timestamp        64 bits
 * payload          variable size
 *
 * Usage:
 *
 * Packet packet(DATA_FROM_DRIVER, timestamp, payload, length);
 *
 * if(packet.readyToSend())
 *    write(packet.packet(), packet().packetSize());
 *    
 ******************************************************************************/

#include "log_publisher.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "port_agent/packet/packet.h"

#include <sstream>
#include <string>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: logPacket
 * Description: Write a packet to the output file.  We need to determine the
 * output mode, then we write bytes directly to the file.
 *
 * Return:
 *   If we successfully write then return true. Otherwise we can return false
 *   or throw an exception.
 *
 *   Note: Exceptions are caught in the publisher and won't hault execution.
 ******************************************************************************/
bool LogPublisher::logPacket(Packet *packet) {

	if(m_bAsciiOut) {
		logger() << packet->asAscii();
	} else {
		logger().write(packet->packet(), packet->packetSize());
	}

	return true;
}
