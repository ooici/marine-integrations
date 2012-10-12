/*******************************************************************************
 * Class: SerialCommSocket
 * Filename: udp_comm_socket.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage connecting to serial devices
 *
 ******************************************************************************/

#ifndef __SERIAL_COMM_SOCKET_H_
#define __SERIAL_COMM_SOCKET_H_

#include "common/logger.h"
#include "network/comm_socket.h"

using namespace std;
using namespace logger;
using namespace network;

namespace network {
    class SerialCommSocket : public CommBase {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    SerialCommSocket();
    	    SerialCommSocket(const SerialCommSocket &rhs);
            virtual ~SerialCommSocket();
            
	    virtual CommBase *copy();
	    
            virtual bool initialize() { return false; }
	    
            virtual uint32_t writeData(const char *buffer, uint32_t size) { return 0; }
            virtual uint32_t readData(char *buffer, uint32_t size) { return 0; }
            
            /* Operators */
            virtual SerialCommSocket & operator=(const SerialCommSocket &rhs);

            /* Accessors */
            
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
    };
}

#endif //__SERIAL_COMM_SOCKET_H_
