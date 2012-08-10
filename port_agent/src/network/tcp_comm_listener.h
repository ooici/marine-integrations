/*******************************************************************************
 * Class: TCPCommListener
 * Filename: tcp_comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage TCP listeners
 *
 ******************************************************************************/

#ifndef __TCP_COMM_LISTENER_H_
#define __TCP_COMM_LISTENER_H_

#include "common/logger.h"
#include "network/comm_listener.h"

using namespace std;
using namespace logger;

namespace network {
    class TCPCommListener : public CommListener {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    TCPCommListener();
    	    TCPCommListener(const TCPCommListener &rhs);
            virtual ~TCPCommListener();
            
            /* Operators */
            virtual TCPCommListener & operator=(const TCPCommListener &rhs);

            /* Accessors */
            
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
    };
}

#endif //__TCP_COMM_LISTENER_H_
