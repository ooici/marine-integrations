/*******************************************************************************
 * Class: DriverDataPublisher
 * Filename: driver_data_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes raw data to the driver data port.
 ******************************************************************************/

#ifndef __DRIVER_DATA_PUBLISHER_H_
#define __DRIVER_DATA_PUBLISHER_H_

#include "driver_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class DriverDataPublisher : public DriverPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            DriverDataPublisher();
	   
	    const PublisherType publisherType() { return PUBLISHER_DRIVER_DATA; }

        protected:
            virtual bool handleInstrumentData(Packet *packet)     { return logPacket(packet); }
            virtual bool handleDriverData(Packet *packet)         { return true; }
            virtual bool handleCommand(Packet *packet)            { return true; }
            virtual bool handleStatus(Packet *packet)             { return logPacket(packet); }
            virtual bool handleFault(Packet *packet)              { return logPacket(packet); }
            virtual bool handleInstrumentCommand(Packet *packet)  { return true; }

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__DRIVER_DATA_PUBLISHER_H_
