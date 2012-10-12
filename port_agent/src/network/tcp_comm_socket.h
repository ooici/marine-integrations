/*******************************************************************************
 * Class: TCPCommSocket
 * Filename: tcp_comm_socket.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manage connections to TCP servers.
 *
 ******************************************************************************/

#ifndef __TCP_COMM_SOCKET_H_
#define __TCP_COMM_SOCKET_H_

#include "common/logger.h"
#include "comm_socket.h"

using namespace std;
using namespace logger;

namespace network {
    class TCPCommSocket : public CommSocket {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    TCPCommSocket();
    	    TCPCommSocket(const TCPCommSocket &rhs);
            virtual ~TCPCommSocket();
            
	    virtual CommBase *copy();
            
            /* Operators */
            virtual TCPCommSocket & operator=(const TCPCommSocket &rhs);

            /* Accessors */
            void setHostname(const string &hostname) {m_sHostname = hostname;}
            void setPort(const uint16_t port) {m_iPort = port;}
	    
	    uint16_t port() { return m_iPort; }
	    const string & hostname() { return m_sHostname; }
            
            // Connect to the network host
            bool initialize();

            // Does this object have a complete configuration?
            bool isConfigured();
	    
        protected:

        private:

        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            string m_sHostname;
            uint16_t m_iPort;
    };
}

#endif //__TCP_COMM_SOCKET_H_
