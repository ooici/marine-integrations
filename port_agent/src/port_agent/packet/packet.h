/*******************************************************************************
 * Class: Packet
 * Filename: packet.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Basic packet object for the port agent.  Packets are teh communication
 * protocol for the port agent to outside interfaces via the data and command
 * port.  They are transmitted as binary datagrams with the following structure.
 *
 * This is the most basic type of packet.  Data is given in the constructor
 * and the packet is created.  Once created there is no need to modify the
 * packet and it should be sent immediately.
 *
 * NOTE: This packet will likely never directly be used in code, but extended
 * to handle different input methods.  That said, it could be used if we know
 * the entire content of the packet before it is created.
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

#ifndef __PACKET_H_
#define __PACKET_H_

#include "common/timestamp.h"

#include <string>
#include <stdint.h>

using namespace std;

namespace packet {
    
    /* Known packet types */
    enum TPacketType {
        UNKNOWN,  
        DATA_FROM_INSTRUMENT,
        DATA_FROM_DRIVER,
        PORT_AGENT_COMMAND,
        PORT_AGENT_STATUS,
        PORT_AGENT_FAULT,
        INSTRUMENT_COMMAND
    };

    const uint32_t SYNC = 0xA39D7A;
    const short    HEADER_SIZE = 16;


    class Packet {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
            Packet();
            Packet(TPacketType packet_type, Timestamp timestamp,
                   char *payload, uint16_t payload_size);
            Packet(const Packet &rhs);
            virtual ~Packet();
            
            /* Operators */
            virtual Packet & operator=(const Packet &rhs);

            /* Accessors */
            TPacketType packetType() { return m_tPacketType; }
            uint16_t packetSize()    { return m_iPacketSize; }
            uint16_t payloadSize()   { return m_iPacketSize - HEADER_SIZE; }
            uint16_t checksum()      { return m_iChecksum; }
            Timestamp timestamp()    { return m_oTimestamp; }
            char* payload()          { return m_pPacket + HEADER_SIZE; }
            char* packet();
            
            // return a ASCII string representation of the packet
            string asAscii();

            // return a pretty string representation of the packet
            string pretty();
            
            // The basic packets are always ready to send.  This will need to be
            // overloaded for buffered packets.
            virtual bool readyToSend() { return true; }

            // Convert a TPacketType to a string representation
            string typeToString(TPacketType type);
        protected:

            // Calculate a checksum of the packet buffer.
            virtual uint16_t calculateChecksum();

            // deep copy a packet object
            virtual void copy(const Packet &copy);

            // ascii packet label
            string asciiPacketLabel() { return "port_agent_packet"; }
            string asciiPacketTimestamp() { return m_oTimestamp.asNumber(); }
            string asciiPacketType() { return typeToString(m_tPacketType); }


        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
            TPacketType m_tPacketType;
            uint16_t m_iPacketSize;
            uint16_t m_iChecksum;
            Timestamp m_oTimestamp;
            char *m_pPacket;

    };
}

#endif //__PACKET_H_
