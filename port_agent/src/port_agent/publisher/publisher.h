/*******************************************************************************
 * Class: Publisher
 * Filename: publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * A publisher implements the out bound communications from the port agent.  It
 * accepts packets and implements handlers to write each packet type to
 * something.  Those handers and output methods are implemented in the derived
 * classes.
 *
 * Handlers:
 * 
 *   bool handleInstrumentData(Packet *packet)
 *   bool handleDataData(Packet *packet)
 *   bool handleCommand(Packet *packet)
 *   bool handleStatus(Packet *packet)
 *   bool handleFault(Packet *packet)
 *   bool handleInstrumentCommand(Packet *packet)
 *
 * Usage:
 *
 * This is a pure virtual class so it must be specialized in a derived class.
 *
 *   SomePublisher publisher(fileDescriptor);
 *   Packet packet("Some data");  // or one of it's derived packet types
 *
 *   if(!publisher.publish(packet))
 *       handleFailure(publish.error());
 *
 * Exceptions:
 *
 *   Exceptions are only thrown from constructors.
 *   If an error is thrown from publication then it is stored in the object.
 *    
 ******************************************************************************/

#ifndef __PUBLISHER_H_
#define __PUBLISHER_H_

#include "common/exception.h"
#include "common/timestamp.h"
#include "port_agent/packet/packet.h"

#include <list>
#include <string>
#include <stdint.h>


using namespace std;
using namespace packet;


namespace publisher {
    typedef enum PublisherType {
	UNKNOWN,
        PUBLISHER_DRIVER_COMMAND,
        PUBLISHER_DRIVER_DATA,
        PUBLISHER_INSTRUMENT_COMMAND,
        PUBLISHER_INSTRUMENT_DATA,
        PUBLISHER_FILE,
        PUBLISHER_UDP,
        PUBLISHER_TCP
    } PulisherType;
    
    class Publisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods

    	    // Default constructor.  Make this a pure virtual class.
    	    Publisher();

            Publisher(const Publisher &rhs);
            virtual ~Publisher();
            
            /* Operators */
            virtual Publisher & operator=(const Publisher &rhs);

            /*  Commands */
            virtual bool publish(Packet *packet);

            /* Accessors */
	    
	    virtual const PublisherType publisherType() = 0;

            // Get the error from the last publish call
            OOIException * error();

            // Enable/Disable ascii output mode
            void setAsciiMode(bool enabled = true);

        protected:
            // Clear all errors out of the error list.
            void clearError();

            /* Handlers */

            // Handlers are used to process and ultimately write the packet
            // data somewhere.  By default the handler does nothing.  Then
            // each specialized publisher can implement the handlers needed.
            virtual bool handleInstrumentData(Packet *packet)     { return true; }
            virtual bool handleDriverData(Packet *packet)         { return true; }
            virtual bool handleCommand(Packet *packet)            { return true; }
            virtual bool handleStatus(Packet *packet)             { return true; }
            virtual bool handleFault(Packet *packet)              { return true; }
            virtual bool handleInstrumentCommand(Packet *packet)  { return true; }


        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            bool m_bAsciiOut;

            
        private:
            OOIException * m_oError;

    };
}

#endif //__PUBLISHER_H_
