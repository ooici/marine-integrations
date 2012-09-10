/*******************************************************************************
 * Class: TCPPublisher
 * Filename: tcp_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher is to set up a listener that external programs can attach
 * too.  It outputs all packets either as binary or ascii.
 *    
 * Nothing to really extend here, but the call is here if we need it.
 ******************************************************************************/

#ifndef __TCP_PUBLISHER_H_
#define __TCP_PUBLISHER_H_

#include "file_pointer_publisher.h"

using namespace std;
using namespace logger;

namespace publisher {
    class TCPPublisher : public FilePointerPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:

    	    TCPPublisher();

	    const PublisherType publisherType() { return PUBLISHER_TCP; }

        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__FILE_PUBLISHER_H_
