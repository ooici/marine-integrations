/*******************************************************************************
 * Class: UDPCommSocket
 * Filename: tcp_comm_socket.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * UDP Client Connection.  For the port agent we only care about UDP writes so
 * we didn't implement any read logic.
 * 
 * Usage:
 *
 * UDPCommSocket socket;
 *
 * // Set connetions information
 * socket.setPort(1029);
 * socket.setHostname("localhost");
 * 
 * // Enable blocking connections. Default is non-blocking
 * socket.setBlocking(true);
 *
 * // Initialize the connection
 * socket.initialize();
 * 
 * // Read data from a client. Ignores source address information.
 * char buffer[128];
 * int bytes_read = socket.readData(buffer, 128);
 *
 * // Write data to the client.
 * int bytes_written = socket.writeData("Hello World", strlen("Hello World"));
 *
 ******************************************************************************/

#ifndef __UDP_COMM_SOCKET_H_
#define __UDP_COMM_SOCKET_H_

#include "common/logger.h"
#include "network/comm_socket.h"

using namespace std;
using namespace logger;

namespace network {
    class UDPCommSocket : public CommSocket {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    UDPCommSocket();
    	    UDPCommSocket(const UDPCommSocket &rhs);
            virtual ~UDPCommSocket();
            
	    virtual CommBase *copy();
            
            /* Operators */
            virtual UDPCommSocket & operator=(const UDPCommSocket &rhs);

            /* Accessors */
            
            void setPort(const uint16_t port) { m_iPort = port; }
            void setHostname(const string &hostname) { m_sHostname = hostname; }
            bool connected() { return m_pSocketFD > 0; }

            /* Commands */
	    
	    // Connect to the network host
            bool initialize();
            
	    virtual uint32_t writeData(const char *buffer, uint32_t size);
            virtual uint32_t readData(char *buffer, uint32_t size);

        protected:

        private:
            // Does this object have a complete configuration?
            bool isConfigured();

        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
             string m_sHostname;
             uint16_t m_iPort;
    };
}

#endif //__UDP_COMM_LISTENER_H_
