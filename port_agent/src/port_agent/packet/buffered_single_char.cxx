/*******************************************************************************
 * Class: Packet
 * Filename: packet.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Functionally, this object dynamically creates a buffer for the payload data
 * when the object is instantiated.  The magic happens in the add method.  An
 * iterater is stored internally to note where the next character needs to be
 * strored.  A timestamp is captured, and the sentinal string is checked.
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

#include "buffered_single_char.h"
#include "common/logger.h"
#include "common/util.h"
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
 * Description: Default constructor.  This shouldn't be used explicitly.
 *
 ******************************************************************************/
BufferedSingleCharPacket::BufferedSingleCharPacket() : Packet::Packet() {
	LOG(INFO) << "Default BufferedSingleCharPacket called";

    m_pSentinleSequence = NULL;
    m_iSentinleSize = 0;
    m_iSentinleIndex = 0;

    m_fQuiescentTime = 0;
    m_iMaxPayloadSize = 0;
}

/******************************************************************************
 * Method: Constructor
 * Description: Extends the default constructor in the base class.  Base ctor
 *              simple sets defaults. Then this method dynamically allocates
 *              a new buffer for the packet and initializes the iterator.  Also
 *              store any of the trigger values.
 * Parameters:
 *   packetType - type of packet.  See the TPacketTypeEnum
 *   makePayloadSize - The max allowable bytes of data for the payload.  Max
 *                     value is 2^16 - HEADER_SIZE.
 *   maxQuiescentTime - max elapse time between reading a packet and now before
 *                      the ready to send is triggered.
 *   sentinleSequence - Sequence of bytes that when seen in the packet trigger
 *                      the packet ready to send.
 *   sentinleSequenceSize - Size of the sentinle sequences.  This is needed
 *                          because we don't know the size of the
 *                          sentinleSequence string.  We can't use a null
 *                          teminated string because \0 may be part of the
 *                          sequence.
 * Throws:
 *    
 * PacketParameterOutOfRange - raised when
 *     - packet type is UNKNOWN
 *     - max payload size to large
 *     - a negative max quiescent time.
 *     - sentinleSequence set, but size is 0;
 *
 ******************************************************************************/
BufferedSingleCharPacket::BufferedSingleCharPacket( TPacketType packetType,
                                                    uint16_t maxPayloadSize,
                                                    float maxQuiescentTime,
                                                    const char* sentinleSequence,
                                                    uint16_t sentinleSequenceSize ) :
    Packet::Packet() {
    
    if(packetType == 0)
        throw PacketParamOutOfRange("invalid packet type");
    
    LOG(DEBUG) << "Creating a new BufferedSingleCharPacket";
    
    m_tPacketType = packetType;
    m_pSentinleSequence = NULL;
        
    setSentinle(sentinleSequence, sentinleSequenceSize);
    setQuiescentTime(maxQuiescentTime);
    setMaxPayloadSize(maxPayloadSize);

    // Time should be set by the first call to add.  So we will just put a place
    // holder in for time now.
    m_oTimestamp.setTime(0,0);
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Extends the default copy constructor from the base class.  
 *              The base class should handle the deep copy of the packet data
 *              so all we have to worry about are our specialized private data.
 ******************************************************************************/
BufferedSingleCharPacket::BufferedSingleCharPacket( BufferedSingleCharPacket& copy ) :
    Packet::Packet(copy) {
        
    LOG(DEBUG) << "BufferedSingleCharPacket copy constructor";
    m_pSentinleSequence = NULL;
    
    setSentinle(copy.m_pSentinleSequence, copy.m_iSentinleSize);
    setQuiescentTime(copy.m_fQuiescentTime);
    setMaxPayloadSize(copy.m_iMaxPayloadSize);
}

/******************************************************************************
 * Method: Destructor
 * Description: Clean up the dynamically created sentinle string and the packet
 *  data.
 ******************************************************************************/
BufferedSingleCharPacket::~BufferedSingleCharPacket() {
    if(m_pSentinleSequence) {
        delete [] m_pSentinleSequence;
        m_pSentinleSequence = NULL;
    }
}

/******************************************************************************
 * Method: operator=
 * Description: overloaded assingment operator ensuring a deep copy.
 *
 * Parameters:
 *   copy - rhs object to copy
 *
 ******************************************************************************/
BufferedSingleCharPacket & BufferedSingleCharPacket::operator=(const BufferedSingleCharPacket &rhs) {

	if(m_pSentinleSequence) {
		delete m_pSentinleSequence;
		m_pSentinleSequence = NULL;
	}

    setSentinle(rhs.m_pSentinleSequence, rhs.m_iSentinleSize);
    setQuiescentTime(rhs.m_fQuiescentTime);
    setMaxPayloadSize(rhs.m_iMaxPayloadSize);

    return *this;
}


/******************************************************************************
 * Method: add
 * Description: Add a new character to the end of the packet data and update
 *              all of the internal trigger values.  Timestamp is set to now.
 *
 * Throws:
 *
 * PacketOverflow - from add method when attempting to write after the max
 *                  packet size has been reached.
 * 
 ******************************************************************************/
void BufferedSingleCharPacket::add( char input ) {
	add(input, Timestamp());
}

/******************************************************************************
 * Method: add
 * Description: Add a new character to the end of the packet data and update
 *              all of the internal trigger values.
 *
 *              Timestamp is explicit.  This is the preferred method to add.
 *
 *              - If this is the first data item we have seen set the packet
 *                timestamp.
 *              - Store the data
 *              - Set the last seen timestamp
 *              - Update the sentinle index count
 *
 * Throws:
 *
 * PacketOverflow - from add method when attempting to write after the max
 *                  packet size has been reached.
 *
 ******************************************************************************/
void BufferedSingleCharPacket::add( char input, const Timestamp &timestamp ) {
	// Check for overflow
    if(packetSize() >= m_iMaxPayloadSize + HEADER_SIZE)
        throw PacketOverflow("boom");

    // Set the packet time if this is our first data element
    if(packetSize() == HEADER_SIZE)
        m_oTimestamp = timestamp;

    // First just add the data to the buffer
    m_pPacket[m_iPacketSize] = input;
    m_iPacketSize++;

    // If we are triggering on time then set the last seen timestamp
    if(m_fQuiescentTime)
        m_oLastAddTimestamp = timestamp;

    // Check for a sentinle character match
    if(m_pSentinleSequence) {
        if(m_pSentinleSequence[m_iSentinleIndex] == input)
            m_iSentinleIndex++;
        else
            m_iSentinleIndex = 0;
    }
}

/******************************************************************************
 * Method: readyToSend
 * Description: This is where the magic happens.  We need to check all of the
 *              trigger values to see if we meet *ANY* condition that would
 *              indicate that our packet is complete.
 *
 *              - Check to see if the max packet size has been reached
 *              - Check to see if the difference between the last packet seen
 *                timestamp and now is greater than the max allowed
 *                quiescent time.
 *              - Check to see if the sentinle index is equal to the sentinle
 *                string size, meaning we have seen all the sentinle characters.
 ******************************************************************************/
bool BufferedSingleCharPacket::readyToSend() {
    // If we haven't added a payload the packet is never ready to send.
    if(m_iPacketSize == HEADER_SIZE)
        return false;
    
    // Check if the max packet size has been reached.
    if(m_iPacketSize >= m_iMaxPayloadSize + HEADER_SIZE)
        return true;
    
    // Check the timestamp of last read elapse time
    if(m_fQuiescentTime && m_oLastAddTimestamp.elapseTime() >= m_fQuiescentTime)
        return true;
    
    if(m_iSentinleSize && m_iSentinleIndex == m_iSentinleSize)
        return true;
    
    return false;
}


/******************************************************************************
 * Method: setSentinle
 * Description: Set or change the current sentinle sequence.  The sequence can
 *              also be unset by passing NULL, and 0 as the parameters.
 * Parameters:
 *   sentinleSequence - Sequence of bytes that when seen in the packet trigger
 *                      the packet ready to send.
 *   sentinleSequenceSize - Size of the sentinle sequences.  This is needed
 *                          because we don't know the size of the
 *                          sentinleSequence string.  We can't use a null
 *                          teminated string because \0 may be part of the
 *                          sequence.
 * Throws:
 *    
 * PacketParameterOutOfRange - raised when
 *     - sentinleSequence set, but size is 0;
 ******************************************************************************/
void BufferedSingleCharPacket::setSentinle(const char* sentinleSequence,
                                           uint16_t sentinleSequenceSize) {
    LOG(DEBUG1) << "Setting the sentinle sequence";
    
    if(sentinleSequence && sentinleSequenceSize == 0) 
        throw PacketParamOutOfRange("sentinle sequence provided, but size == 0");
    
    // Reset all of the sentinle parameters to nothing.
    if(m_pSentinleSequence)
        delete [] m_pSentinleSequence;
    m_iSentinleSize = 0;
    m_iSentinleIndex = 0;
    
    // Now we can safely set new parameters if needed.
    if(sentinleSequence) {
        m_iSentinleSize = sentinleSequenceSize;
        m_pSentinleSequence = new char[sentinleSequenceSize];
        
        for(int i = 0; i < m_iSentinleSize; i++)
            m_pSentinleSequence[i] = sentinleSequence[i];
    }
}
            
            
/******************************************************************************
 * Method: setQuiescentTime
 * Description: Set or change the max quiescent elapse time from last read.  To
 *              unset this option pass in a value of 0.
 *              
 * Parameters:
 *   maxQuiescentTime - max elapse time between reading a packet and now before
 *                      the ready to send is triggered.
 *
 * Throws:
 *    
 * PacketParameterOutOfRange - raised when
 *     - a negative max quiescent time.
 *
 ******************************************************************************/
void BufferedSingleCharPacket::setQuiescentTime(float maxQuiecentTime) {
    LOG(DEBUG1) << "Setting the max quiescent time";
    
    if(maxQuiecentTime < 0)
        throw PacketParamOutOfRange("quiecent time must be >= 0");
    
    m_fQuiescentTime = maxQuiecentTime;
}


/******************************************************************************
 *   PRIVATE METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: setMaxPayloadSize
 * Description: Set the max packet size and allocate memory for the packet buffer.
 *              
 * Parameters:
 *   makePayloadSize - The max allowable bytes of data for the payload.  Max
 *                     value is 2^16 - HEADER_SIZE.
 * Throws:
 *    
 * PacketParameterOutOfRange - raised when
 *     - max payload size to large
 *
 ******************************************************************************/
void BufferedSingleCharPacket::setMaxPayloadSize(uint16_t maxPayloadSize) {
    LOG(DEBUG1) << "Setting the max payload size and allocating a packet buffer";
    
    if(maxPayloadSize == 0)
        throw PacketParamOutOfRange("payload size must be > 0");
    
    if(maxPayloadSize > 0xFFEF)
        throw PacketParamOutOfRange("payload size too large");
    
    m_iMaxPayloadSize = maxPayloadSize;
    m_iPacketSize = HEADER_SIZE;
    
    if(m_pPacket)
        delete [] m_pPacket;
        
    m_pPacket = new char[m_iPacketSize + maxPayloadSize];
}
