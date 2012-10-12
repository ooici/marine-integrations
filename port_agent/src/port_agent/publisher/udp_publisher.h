/*******************************************************************************
 * Class: UDPPublisher
 * Filename: udp_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher is to set up a listener that external programs can attach
 * too.  It outputs all packets either as binary or ascii.
 *    
 * Nothing to really extend here, but the call is here if we need it.
 ******************************************************************************/

#ifndef __UDP_PUBLISHER_H_
#define __UDP_PUBLISHER_H_

#include "file_pointer_publisher.h"

using namespace std;
using namespace logger;

namespace publisher {
    class UDPPublisher : public FilePointerPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:

    	    UDPPublisher();

	    const PublisherType publisherType() { return PUBLISHER_UDP; }

        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__UDP_PUBLISHER_H_
