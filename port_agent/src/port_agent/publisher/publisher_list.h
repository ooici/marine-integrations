/*******************************************************************************
 * Class: PublisherList
 * Filename: publisher_list.h
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
 * SomePublisher publisher(fileDescriptor);
 *
 * list.add(&publisher);
 *
 * list.publish(packet);
 *    
 ******************************************************************************/

#ifndef __PUBLISHER_LIST_H_
#define __PUBLISHER_LIST_H_

#include "common/exception.h"
#include "common/timestamp.h"
#include "port_agent/publisher/publisher.h"

#include <list>
#include <string>


using namespace std;
using namespace packet;


namespace publisher {
    typedef list<Publisher *> PublisherObjectList;
    
    class PublisherList {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods

    	    PublisherList();

            virtual ~PublisherList();
            
            /*  Commands */
            bool publish(Packet *packet);
            
	    void add(Publisher *publisher);

            /* Accessors */

        protected:


        private:
	    
	    void addUnique(Publisher *publisher);
	    void addPublisher(Publisher *publisher);
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            PublisherObjectList m_oPublishers;

    };
}

#endif //__PUBLISHER_H_
