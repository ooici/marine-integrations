/*******************************************************************************
 * Class: ObservatoryConnection
 * Filename: observatory_connection.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manages the socket connection between the observatory and the port agent.
 * This interface consists of a TCP listener on the data port and command port
 * setup in non-blocking mode.
 *
 * Usage:
 *
 * ObservatoryConnection connection;
 *
 * connection.setDataPort(4001);
 * connection.setCommandPort(4000);
 *
 * // Is the data port configured
 * connection.dataConfigured();
 *
 * // Is the command port configured
 * connection.commandConfigured();
 *
 * // Sets up listeners if they are configured.  Subsiquent calls to this
 * // method will only initialize those connections that are uninitialized.
 * connection.initialize();
 *
 * // Is the data port initialized (listening)
 * connection.dataInitialized();
 *
 * // Is the command port initialized (listening)
 * connection.commandInitialized();
 *
 * // Is the data port connected
 * connection.dataConnected();
 *
 * // Is the command port connected
 * connection.commandConnected();
 *
 * // Get a pointer tcp data listener object
 * TCPCommListener *data = connection.dataConnectionObject();
 *    
 * // Get a pointer tcp command listener object
 * TCPCommListener *command = connection.commandConnectionObject();
 *    
 ******************************************************************************/

#ifndef __OBSERVATORY_CONNECTION_H_
#define __OBSERVATORY_CONNECTION_H_

#include "port_agent/connection/connection.h"
#include "network/tcp_comm_listener.h"

using namespace std;
using namespace network;

namespace port_agent {
    class ObservatoryConnection : public Connection {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
            ObservatoryConnection();
            ObservatoryConnection(const ObservatoryConnection &rhs);
            virtual ~ObservatoryConnection();
            
            void copy(const ObservatoryConnection &copy);
            
            /* Operators */
            ObservatoryConnection & operator=(const ObservatoryConnection &rhs);

            /* Accessors */
            
            CommBase *dataConnectionObject() { return &m_oDataSocket; }
            CommBase *commandConnectionObject() { return &m_oCommandSocket; }
            
            PortAgentConnectionType connectionType() { return PACONN_OBSERVATORY_STANDARD; }
            
            // Custom configurations for the observatory connection
            void setDataPort(uint16_t port);
            void setCommandPort(uint16_t port);
            
            /* Query Methods */
            
            // Do we have complete configuration information for each
            // socket connection?
            bool dataConfigured();
            bool commandConfigured();
            
            // Has the connection been initialized (is it listening?)
            bool dataInitialized();
            bool commandInitialized();
            
            // Has a connection been made?
            bool dataConnected();
            bool commandConnected();
            
            /* Commands */
            
            // Initialize sockets
            void initializeDataSocket();
            void initializeCommandSocket();
        
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
            TCPCommListener m_oDataSocket;
            TCPCommListener m_oCommandSocket;
            
    };
}

#endif //__OBSERVATORY_CONNECTION_H_
