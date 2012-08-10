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
            FILE * socket() { return m_pSocketFD; }
            
            // Connect, must be overloaded in the derived class
            virtual bool connect() = 0;

            // close
            virtual bool close();

            virtual uint32_t write(const char *buffer, uint32_t size);

        protected:

            void setSocket(FILE * fd) { m_pSocketFD = fd; }

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            FILE * m_pSocketFD;

    };
}

#endif //__COMM_SOCKET_H_
