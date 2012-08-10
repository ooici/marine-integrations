/*******************************************************************************
 * Class: UDPCommListener
 * Filename: udp_comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage UDP listeners
 *
 ******************************************************************************/

#ifndef __UDP_COMM_LISTENER_H_
#define __UDP_COMM_LISTENER_H_

#include "common/logger.h"
#include "network/comm_listener.h"

using namespace std;
using namespace logger;

namespace network {
    class UDPCommListener : public CommListener {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    UDPCommListener();
    	    UDPCommListener(const UDPCommListener &rhs);
            virtual ~UDPCommListener();
            
            /* Operators */
            virtual UDPCommListener & operator=(const UDPCommListener &rhs);

            /* Accessors */
            
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
    };
}

#endif //__UDP_COMM_LISTENER_H_
