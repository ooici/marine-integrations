/*******************************************************************************
 * Class: Publisher
 * Filename: publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * A container for all publishers.  Provides routines for adding publishers
 * to the lists and writing data to thos publishers.
 *
 * Some connections (instrument data/command and observatory data/command)
 * are unique and one of each is allowed in the list.  Others can have
 * multiple instances (tcp, udp, file).
 * 
 * Usage:
 *
 * PublisherList list;
 *
 * SomePublisher *publisher = SomePublisher(fileDescriptor);
 *
 * list.add(publisher);
 *
 * list.publish(packet);
 *    
 ******************************************************************************/

#include "publisher_list.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "port_agent/packet/packet.h"
#include "port_agent/publisher/driver_command_publisher.h"
#include "port_agent/publisher/driver_data_publisher.h"
#include "port_agent/publisher/instrument_command_publisher.h"
#include "port_agent/publisher/instrument_data_publisher.h"
#include "port_agent/publisher/file_publisher.h"
#include "port_agent/publisher/tcp_publisher.h"
#include "port_agent/publisher/udp_publisher.h"

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
PublisherList::PublisherList() {
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
PublisherList::~PublisherList() {
    PublisherObjectList::iterator i = m_oPublishers.begin();
    
    for(i = m_oPublishers.begin(); i != m_oPublishers.end(); i++)
        if(*i) delete *i;
}


/******************************************************************************
 * Method: publish
 * Description: publish a packet to all publishers
 *
 * Parameters:
 *   packet - a Packet object or one of it's derivatives
 *
 ******************************************************************************/
bool PublisherList::publish(Packet *packet) {
}


/******************************************************************************
 * Method: add
 * Description: Add a publisher to the list.
 ******************************************************************************/
void PublisherList::add(Publisher *publisher) {
    if(publisher->publisherType() == PUBLISHER_DRIVER_COMMAND || 
       publisher->publisherType() == PUBLISHER_DRIVER_COMMAND ||
       publisher->publisherType() == PUBLISHER_INSTRUMENT_COMMAND ||
       publisher->publisherType() == PUBLISHER_INSTRUMENT_DATA ) {
	addUnique(publisher);
    }
    else {
	addPublisher(publisher);
    }
}

/******************************************************************************
 * Method: addUnique
 * Description: Add a unique publisher to the list.
 ******************************************************************************/
void PublisherList::addUnique(Publisher *publisher) {
    PublisherObjectList::iterator i = m_oPublishers.begin();
    
    for(i = m_oPublishers.begin(); i != m_oPublishers.end(); i++) {
	if(publisher->publisherType() == (*i)->publisherType()) {
	    *(*i) = *publisher;
	    return;
	}
    }
    
    // Didn't find a match so add a new one.
    addPublisher(publisher);

}

/******************************************************************************
 * Method: addPublisher
 * Description: Add a publisher to the list.
 ******************************************************************************/
void PublisherList::addPublisher(Publisher *publisher) {
    Publisher *newPublisher = NULL;
    
    if(publisher->publisherType() == PUBLISHER_DRIVER_COMMAND)
        newPublisher = new DriverCommandPublisher(*(DriverCommandPublisher*)publisher);
    
    else if(publisher->publisherType() == PUBLISHER_DRIVER_DATA)
        newPublisher = new DriverDataPublisher(*(DriverDataPublisher*)publisher);
    
    else if(publisher->publisherType() == PUBLISHER_INSTRUMENT_COMMAND)
        newPublisher = new InstrumentCommandPublisher(*(InstrumentCommandPublisher*)publisher);
	
    else if(publisher->publisherType() == PUBLISHER_INSTRUMENT_DATA)
        newPublisher = new InstrumentDataPublisher(*(InstrumentDataPublisher*)publisher);
	
    else if(publisher->publisherType() == PUBLISHER_FILE)
        newPublisher = new FilePublisher(*(FilePublisher*)publisher);
	
    else if(publisher->publisherType() == PUBLISHER_TCP)
        newPublisher = new TCPPublisher(*(TCPPublisher*)publisher);
	
    else if(publisher->publisherType() == PUBLISHER_UDP)
        newPublisher = new UDPPublisher(*(UDPPublisher*)publisher);
	
    else
        throw UnknownPublisherType();
    
    m_oPublishers.push_back(newPublisher);
}



