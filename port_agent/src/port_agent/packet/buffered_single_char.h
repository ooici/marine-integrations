/*******************************************************************************
 * Class: BufferedSingleCharPacket
 * Filename: buffered_single_char.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This packet extends the basic packet. The purpose of this packet is to
 * buffer input read a single character at a time. This opject is responsible
 * for knowing when the data is ready to be sent.
 *
 * So you ask, "How will the packet know when it is complete?"  When the object
 * is created you must provide a maximum packet size and optionally a max
 * quiesent time and/or a sentinal string.  If a condition is specified the
 * any afirmation of these states will mark the packet ready to be sent.
 *
 * It is possible that a packet is ready to be sent, but then you add another
 * character to the packet. It is the callers responsability to check the
 * packet status using readyToSend().
 *
 * If you try to write passed the max packet size an overflow exception will
 * be thrown.
 * 
 * A binary packet contains:
 *
 * sync series      24 bits
 * message type     8 bits
 * packet size      16 bits (including the header)
 * checksum         16 bits
 * timestamp        64 bits
 * payload          variable size
 *
 * NOTE: all binary values are little endian.
 * 
 * Usage:
 *
 * // Only max packet size is required.
 * BufferedSingleCharPacket packet(maxPacketSize, sentinalString, maxQuiescent)
 *
 * char buffer;
 *
 * read(infile, &buffer);
 * packet.add(buffer);
 * 
 * if(packet.readyToSend())
 *    write(packet.packet(), packet().packetSize());
 * 
 * Exceptions:
 *
 * PacketParameterOutOfRange - raised when
 *     - max payload size to large
 *     - a negative max quiescent time.
 *     - sentinleSequence set, but size is 0;
 *    
 * PacketOverflow - from add method when attempting to write after the max
 *                  packet size has been reached.
 *    
 ******************************************************************************/

#ifndef __BUFFERED_SINGLE_CHAR_H_
#define __BUFFERED_SINGLE_CHAR_H_

#include "common/timestamp.h"
#include "packet.h"

#include <string>
#include <stdint.h>

using namespace std;

namespace packet {
    class BufferedSingleCharPacket : public Packet {
        /********************
         *      METHODS     *
         ********************/
        
        public:
         	// Constructor
         	BufferedSingleCharPacket();

            // Constructor.
            BufferedSingleCharPacket( TPacketType packetType,
                                      uint16_t maxPayloadSize,
                                      float maxQuiescentTime = 0,
                                      const char* sentinleSequence = NULL,
                                      uint16_t sentinleSequenceSize = 0 );
        
            // Copy Constructor.
            BufferedSingleCharPacket( BufferedSingleCharPacket& copy );
            
            // Destructor
            ~BufferedSingleCharPacket();
            
            // overloaded assignment
            virtual BufferedSingleCharPacket & operator=(const BufferedSingleCharPacket &rhs);

            // Add a character to the packet buffer, time is set to now implicitly
            void add(char input);

            // Add a character to the packet buffer
            void add(char input, const Timestamp &timestamp);
            
            // Overloaded readyToSend method
            bool readyToSend();
            
            // Set the sentinle sequence
            void setSentinle(const char* sentinleSequence, uint16_t sentinleSequenceSize);
            
            // Set the max quiescent time
            void setQuiescentTime(float maxQuiecentTime);
            
            // Get the sentinle sequence, used for testing.
            char* sentinle() { return m_pSentinleSequence; }
        
            // Get the sentinle sequence, used for testing.
            uint16_t sentinleSize() { return m_iSentinleSize; }
        
        protected:

        private:
        
            // Setup the packet buffer.  This is private because I don't want
            // people to change this after the object is instantiated. 
            void setMaxPayloadSize(uint16_t maxPayloadSize);
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            // members for sentinle triggering
            char* m_pSentinleSequence;
            uint16_t m_iSentinleSize;
            uint16_t m_iSentinleIndex;
            
            // members for quiescent triggering
            float m_fQuiescentTime;
            Timestamp m_oLastAddTimestamp;
            
            // member for max payload size triggering
            uint16_t m_iMaxPayloadSize;
    };
}

#endif //__BUFFERED_SINGLE_CHAR_H_
