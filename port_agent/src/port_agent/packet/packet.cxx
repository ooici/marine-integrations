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

#include "packet.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "common/timestamp.h"

#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <cctype>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

using namespace std;
using namespace packet;
using namespace logger;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/
/******************************************************************************
 * Method: Constructor
 * Description: Default constructor.  Is likely never called, but wanted to
 *              define it explicitly.
 ******************************************************************************/
Packet::Packet() {
    m_tPacketType = UNKNOWN;
    m_iPacketSize = 0;
    m_iChecksum = 0;
    m_pPacket = NULL;
}

/******************************************************************************
 * Method: Constructor
 * Description: General use constructor for the the packet.  Sets up all
 *              paramaters, basically an immutable object.
 * Parameters:
 *   packetType - type of packet.  See the TPacketTypeEnum
 *   timestamp  - Timestamp when the data was initially collected.
 *   payload - the actual data stored in the packet.
 *   payloadSize - number of bytes in the payload.
 *   sentinleSequenceSize - Size of the sentinle sequences.  This is needed
 *                          because we don't know the size of the
 *                          sentinleSequence string.  We can't use a null
 *                          teminated string because \0 may be part of the
 *                          sequence.
 * Throws:
 *
 * PacketParameterOutOfRange - raised when
 *     - packet type is UNKNOWN
 *
 ******************************************************************************/
Packet::Packet(TPacketType packetType, Timestamp timestamp,
               char *payload, uint16_t payloadSize) {
    
    LOG(DEBUG) << "Building a new packet";

    if(packetType == 0)
        throw PacketParamOutOfRange("invalid packet type");
    
    m_oTimestamp = timestamp;
    m_tPacketType = packetType;
    m_iPacketSize = HEADER_SIZE + payloadSize;
    m_pPacket = new char[m_iPacketSize];
    
    LOG(DEBUG1) << "Setting packet header info";
    
    if(payload) {
        LOG(DEBUG1) << "Deep copy packet payload, size: " << m_iPacketSize;
        // Deep copy the data
        for(int i = HEADER_SIZE; i < m_iPacketSize; i++)
            m_pPacket[i] = payload[i-HEADER_SIZE];
    }
    
    LOG(DEBUG1) << "Deep copy complete";
    
    m_iChecksum = calculateChecksum();
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 *
 ******************************************************************************/
Packet::Packet(const Packet& rhs) {
    LOG(DEBUG) << "Packet copy constructor";
    
    m_pPacket = NULL;
    copy(rhs);
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
Packet::~Packet() {
    if( m_pPacket ) {
        delete [] m_pPacket;
        m_pPacket = NULL;
    }
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 *
 ******************************************************************************/
Packet & Packet::operator=(const Packet &rhs) {

	if(m_pPacket) {
		delete m_pPacket;
		m_pPacket = NULL;
	}

	copy(rhs);
	return *this;
}


/******************************************************************************
 * Method: copy
 * Description: Copy data from one packet object into this one.  Ensuring we
 * deep copy when needed.
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
void Packet::copy(const Packet &copy) {
    m_oTimestamp = copy.m_oTimestamp;
    m_tPacketType = copy.m_tPacketType;
    m_iPacketSize = copy.m_iPacketSize;
    m_iChecksum = copy.m_iChecksum;

    // Deep copy the payload
    if(copy.m_pPacket) {
        m_pPacket = new char[packetSize()];
        for(int i = HEADER_SIZE; i < packetSize(); i++)
            m_pPacket[i] = copy.m_pPacket[i];
    } else {
    	m_pPacket = NULL;
    }
}


/******************************************************************************
 * Method: asAscii
 * Description: an ascii representation of the packet.
 ******************************************************************************/
string Packet::asAscii() {
    ostringstream out;

    char* packetBuffer = packet();

    out << "<" << asciiPacketLabel() << " type=\"" << asciiPacketType() << "\" "
        << "time=\"" << asciiPacketTimestamp() << "\">";

    if(packetBuffer) {
        for(int i = HEADER_SIZE; i < packetSize(); i++)
            out << packetBuffer[i];
    }

    out << "</" << asciiPacketLabel() << ">\n\r";

    return out.str();
}

/******************************************************************************
 * Method: pretty
 * Description: return a human readable ascii formatted string. Useful for
 *              logging.
 ******************************************************************************/
string Packet::pretty() {
    ostringstream out;
    
    char* packetBuffer = packet();

    // Output some pretty header information from the packet.  Ready to send
    // is not part of the packet header, but it sure is useful information.
    out << endl;
    out << "Ready to send: ";
    if(readyToSend())
        out << "true" << endl;
    else
        out << "false" << endl;
    out << "Sync: " << "0x" << hex << SYNC << dec << endl;
    out << "Type: " << m_tPacketType << " (" << typeToString(m_tPacketType) << ")" << endl;
    out << "Size: " << m_iPacketSize << endl;
    out << "Checksum: " << hex << m_iChecksum << dec << endl;
    out << "Timestamp: " << m_oTimestamp.asNumber() << endl;
    
    // Let's dump some raw data, first as ascii.
    out << "Payload (ascii): ";
    if(packetBuffer) {
        out << endl;
        for(int i = HEADER_SIZE; i < packetSize(); i++)
            if(isprint(packetBuffer[i]))
                out << packetBuffer[i];
            else
                out << "0x" << hex << byteToUnsignedInt(packetBuffer[i]);
    } else {
        out << "<NULL>" << endl;
    }
    out << endl;

    // Hex out, packet data
    out << "Payload (hex): ";
    if(packetBuffer) {
        for(int i = HEADER_SIZE; i < packetSize(); i++) {
            // Wrap lines
            if(i % 16 == 0)
                out << endl;
            out << hex << byteToUnsignedInt(packetBuffer[i]) << " ";
        }
    } else {
        out << "<NULL>" << endl;
    }
    out << endl;
    
    // Finally the full packet hex output.  Shows the header.
    out << "Full Packet (hex): ";
    if(packetBuffer) {
        for(int i = 0; i < packetSize(); i++) {
            // Wrap lines
            if(i % 16 == 0)
                out << endl;
            out << hex << setw(2) << byteToUnsignedInt(packetBuffer[i]) << " ";
        }
    } else {
        out << "<NULL>" << endl;
    }
    
    return out.str();
}

/******************************************************************************
 * Method: packet
 * Description: Reconstruct the packet header in the buffer.
 *
 * Make sure we have converted everything to big-endian!
 *
 * Return:
 *   copy - return a pointer to the actual data buffer.  Note that this is only
 *          a pointer so if this object goes out of scope the buffer will be
 *          destroyed.
 ******************************************************************************/
char* Packet::packet() {
    uint64_t ts = m_oTimestamp.asBinary();
    uint32_t sync = htonl(SYNC) >> 8;
    uint16_t size = htons(m_iPacketSize);
    uint16_t checksum;

    if(m_pPacket) {
        memcpy(m_pPacket, &sync, 3);
        m_pPacket[3] = m_tPacketType;
        memcpy(m_pPacket + 4, &size, 2);
        memcpy(m_pPacket + 8, &ts, 8);

        // For the base class recalculating the checksum may be a waste of time,
        // but for most mutable packets it's a requirements.  Since we likely
        // won't use the base packet in production taking the cycle hit seems worth
        // missing a recalculation in derived classes.
        m_iChecksum = calculateChecksum();
        checksum = htons(m_iChecksum);
        memcpy(m_pPacket + 6, &checksum, 2);
    }
    
    return m_pPacket;
}


/******************************************************************************
 *   PRIVATE METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: calculateChecksum
 * Description: calculate the checksum of the current packet buffer.
 *    TODO: Identify a good checksum algorithm to use.
 *
 * Return:
 *   a uint16_t checksum value calculated from the packet buffer.
 *
 ******************************************************************************/
uint16_t Packet::calculateChecksum() {
    uint16_t checksum = 0;
    
    if(m_pPacket) {
        LOG(DEBUG2) << "Calculating check sum";
    
        for(int i = 0; i < packetSize(); i++) {
        	// Make sure we ignore the part of the buffer where we store the
        	// checksum value.
        	if(i < 6 || i > 7)
                 checksum += m_pPacket[i];
        }
    }
        
    return checksum;
}

/******************************************************************************
 * Method: typeToString
 * Description: Convert a packet type to a string representation.
 *
 * Parameters:
 *   type - enum element packet type
 *
 * Return:
 *   string representation of that type.
 *
 ******************************************************************************/
string Packet::typeToString(TPacketType type) {
    switch(type) {
        case UNKNOWN: return string("UNKNOWN");
        case DATA_FROM_INSTRUMENT: return string("DATA_FROM_INSTRUMENT");
        case DATA_FROM_DRIVER: return string("DATA_FROM_DRIVER");
        case PORT_AGENT_COMMAND: return string("PORT_AGENT_COMMAND");
        case PORT_AGENT_STATUS: return string("PORT_AGENT_STATUS");
        case PORT_AGENT_FAULT: return string("PORT_AGENT_FAULT");
        case INSTRUMENT_COMMAND: return string("INSTRUMENT_COMMAND");
    };

    return "OUT_OF_RANGE";
}


