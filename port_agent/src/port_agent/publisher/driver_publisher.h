/*******************************************************************************
 * Class: DriverPublisher
 * Filename: driver_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base class for publishers writing to driver connections.  These
 * publishers don't write packet data, but just output the raw payload of the
 * packet.  Therefore, we don't really care about ascii mode or not.
 *    
 ******************************************************************************/

#ifndef __DRIVER_PUBLISHER_H_
#define __DRIVER_PUBLISHER_H_

#include "file_pointer_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class DriverPublisher : public FilePointerPublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:

    	DriverPublisher();

        protected:

        private:

         /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:

    };
}

#endif //__DRIVER_PUBLISHER_H_
