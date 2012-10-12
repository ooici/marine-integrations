/*******************************************************************************
 * Class: Publisher
 * Filename: publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * A publisher implements the out bound communications from the port agent.  It
 * accepts packets and implements handlers to write each packet type to
 * something.  Those handers and output methods are implemented in the derived
 * classes.
 *    
 ******************************************************************************/

#include "publisher.h"
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
 * Method: Constructor
 * Description: Default constructor.
 ******************************************************************************/
Publisher::Publisher() {
    m_oError = NULL;
    m_bAsciiOut = false;
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 *
 ******************************************************************************/
Publisher::Publisher(const Publisher& rhs) {
    LOG(DEBUG) << "Publisher copy constructor";
    clearError();
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
Publisher::~Publisher() {
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 *
 ******************************************************************************/
Publisher & Publisher::operator=(const Publisher &rhs) {
	clearError();
	return *this;
}

/******************************************************************************
 * Method: publish
 * Description: publish a packet (run it throgh all known handlers.
 *
 * Parameters:
 *   packet - a Packet object or one of it's derivatives
 *
 ******************************************************************************/
bool Publisher::publish(Packet *packet) {
	clearError();


    // We want to check log level here because we don't want to actually call
    // the pretty method unless we have too.
    if(Logger::GetLogLevel() == MESG) {
        LOG(MESG) << "Publishing Packet:" << endl
                  << packet->pretty() << endl;
    }

	try {
		switch(packet->packetType()) {
		case DATA_FROM_INSTRUMENT:
		    return handleInstrumentData(packet);

		case DATA_FROM_DRIVER:
            return handleDriverData(packet);

		case PORT_AGENT_COMMAND:
            return handleCommand(packet);

		case PORT_AGENT_STATUS:
            return handleStatus(packet);

		case PORT_AGENT_FAULT:
            return handleFault(packet);

		case INSTRUMENT_COMMAND:
            return handleInstrumentCommand(packet);

		default:
			throw UnknownPacketType();
		};
	}
	catch(OOIException & e) {
		clearError(); // better safe than sorry.
		m_oError = new OOIException(e);
		return false;
	}

	return true;
}


/******************************************************************************
 * Method: setAsciiMode
 * Description: Enable or disable ascii output mode.
 * Parameter: enabled - true if output ascii false to output binary
 ******************************************************************************/
void Publisher::setAsciiMode(bool enabled) {
    m_bAsciiOut = enabled;
}

/******************************************************************************
 * Method: error
 * Description: Access to the error queue.  This queue is cleared with every
 * call to publish.
 *
 * Return:
 *   a pointer to the error from the last publish comand.  NULL if no error
 *   occurred
 *
 ******************************************************************************/
OOIException * Publisher::error() {
    return m_oError;
}

/******************************************************************************
 * Method: clearError
 * Description: Clear all errors out of the error list.
 ******************************************************************************/
void Publisher::clearError() {
	if(m_oError) delete m_oError;
	m_oError = NULL;
}

