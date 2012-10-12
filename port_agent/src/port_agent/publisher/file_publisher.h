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

#ifndef __FILE_PUBLISHER_H_
#define __FILE_PUBLISHER_H_

#include "publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class FilePublisher : public Publisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:

    	    FilePublisher() {}

            // Explicitly set the output file
            void setFilename(string filename);

            // Set the file path and extension for rolling logs
            void setFilebase(string filebase, string fileext = "");

            // Explicitly close the log file
            void close() { m_oLogger.close(); }

	    const PublisherType publisherType() { return PUBLISHER_FILE; }

        protected:

            LogFile &logger() { return m_oLogger; }
        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            LogFile m_oLogger;
    };
}

#endif //__FILE_PUBLISHER_H_
