/*******************************************************************************
 * Class: CommSocket
 * Filename: comm_socket.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * base class to manage connections to other network services
 *
 ******************************************************************************/

#ifndef __COMM_SOCKET_H_
#define __COMM_SOCKET_H_

#include <stdio.h>

#include "common/logger.h"
#include "network/comm_base.h"

using namespace std;
using namespace logger;

namespace network {
    class CommSocket : public CommBase {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    CommSocket();
    	    CommSocket(const CommSocket &rhs);
            virtual ~CommSocket();
            
            /* Operators */
            virtual CommSocket & operator=(const CommSocket &rhs);

            /* Accessors */
            int getSocketFD() { return m_pSocketFD; }
            
            // Connect, must be overloaded in the derived class
            virtual bool initialize() = 0;

            // close
            virtual bool disconnect();

            virtual uint32_t writeData(const char *buffer, uint32_t size);
            virtual uint32_t readData(char *buffer, uint32_t size);

        protected:

            void setSocket(int fd) { m_pSocketFD = fd; }

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            int m_pSocketFD;
            
        private:

    };
}

#endif //__COMM_SOCKET_H_
