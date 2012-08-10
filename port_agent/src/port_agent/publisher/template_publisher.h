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

#ifndef __PUBLISHER_H_
#define __PUBLISHER_H_

#include "common/timestamp.h"

#include <string>
#include <stdint.h>

using namespace std;

namespace publisher {
    class Publisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
            Publisher();
            Publisher(const Publisher &rhs);
            virtual ~Publisher();
            
            /* Operators */
            virtual Publisher & operator=(const Publisher &rhs);

            /* Accessors */

        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__PUBLISHER_H_
