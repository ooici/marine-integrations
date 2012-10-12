/*******************************************************************************
 * Class: InstrumentPublisher
 * Filename: instrument_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base class for publishers writing to instrument connections.  These
 * publishers don't write packet data, but just output the raw payload of the
 * packet.  Therefore, we don't really care about ascii mode or not.
 *    
 ******************************************************************************/

#ifndef __INSTRUMENT_PUBLISHER_H_
#define __INSTRUMENT_PUBLISHER_H_

#include "file_pointer_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class InstrumentPublisher : public FilePointerPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:

    	InstrumentPublisher() {}

        protected:

            virtual bool handleInstrumentData(Packet *packet)     { return true; }
            virtual bool handleDriverData(Packet *packet)         { return true; }
            virtual bool handleCommand(Packet *packet)            { return true; }
            virtual bool handleStatus(Packet *packet)             { return true; }
            virtual bool handleFault(Packet *packet)              { return true; }
            virtual bool handleInstrumentCommand(Packet *packet)  { return true; }

            bool logPacket(Packet *packet);

       private:

         /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__INSTRUMENT_PUBLISHER_H_
