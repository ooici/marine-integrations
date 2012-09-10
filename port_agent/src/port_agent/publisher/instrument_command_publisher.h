/*******************************************************************************
 * Class: InstrumentCommandPublisher
 * Filename: instrument_command_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes raw data to the instrument commanddata port.  The 
 * only packets it has a handler for is COMMAND_FROM_DRIVER packets
 *    
 ******************************************************************************/

#ifndef __INSTRUMENT_COMMAND_PUBLISHER_H_
#define __INSTRUMENT_COMMAND_PUBLISHER_H_

#include "instrument_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class InstrumentCommandPublisher : public InstrumentPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
        	InstrumentCommandPublisher();

	    const PublisherType publisherType() { return PUBLISHER_INSTRUMENT_COMMAND; }

        protected:
            virtual bool handleInstrumentCommand(Packet *packet);

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__INSTRUMENT_COMMAND_PUBLISHER_H_
