/*******************************************************************************
 * Class: TCPCommListener
 * Filename: tcp_comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Start a TCP Server listening on all interfaces.
 *
 * Usage:
 *
 * TCPCommListener ts;
 *
 * // Statically assign the port.  If not assigned then us a random port.
 * ts.setPort(1024);
 *
 * // Enable blocking connections. Default is non-blocking
 * ts.setBlocking(true);
 *
 * // Initialize the server
 * ts.initalize();
 *
 * // Get the port the server is actually listening on.  Useful when using
 * // random ports.
 * uint16_t port = ts.getListenPort();
 * 
 * // Accept client connections
 * ts.acceptClient();
 *
 * // Read data from the client. Honors the blocking flag set earlier.
 * char buffer[128];
 * int bytes_read = ts.readData(buffer, 128);
 *
 * // Write data to the client.
 * int bytes_written = ts.writeData("Hello World", strlen("Hello World"));
 *
 * // When using non-blocking you may want to use a select read loop to monitor
 * // the file descriptors.  They are exposed via accessors
 * int serverFD = ts.getServerFD();
 * int clientFD = ts.getServerFD();
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
            
	    virtual CommBase *copy();
            
            /* Operators */
            virtual TCPCommListener & operator=(const TCPCommListener &rhs);

            /* Accessors */

            /* Commands */
	    
	    // Connect to the network host
            bool initialize();
            
	    virtual uint32_t writeData(const char *buffer, uint32_t size);
            virtual uint32_t readData(char *buffer, uint32_t size);

            // Does this object have a complete configuration?
            bool isConfigured();
        protected:

        private:

        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            
    };
}

#endif //__TCP_COMM_LISTENER_H_
