/*******************************************************************************
 * Class: InstrumentDataPublisher
 * Filename: instrument_data_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes raw data to the instrument data port.  The only packets
 * it has a handler for is DATA_FROM_DRIVER packets
 *    
 ******************************************************************************/

#ifndef __INSTRUMENT_DATA_PUBLISHER_H_
#define __INSTRUMENT_DATA_PUBLISHER_H_

#include "instrument_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class InstrumentDataPublisher : public InstrumentPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
        	InstrumentDataPublisher();

	    const PublisherType publisherType() { return PUBLISHER_INSTRUMENT_DATA; }

        protected:
            virtual bool handleDriverData(Packet *packet);

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__INSTRUMENT_DATA_PUBLISHER_H_
