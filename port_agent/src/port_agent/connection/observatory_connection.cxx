/*******************************************************************************
 * Class: ObservatoryConnection
 * Filename: observatory_connection.cxx
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
 * // Sets up listeners if they are configured
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

#include "observatory_connection.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "network/tcp_comm_listener.h"

using namespace std;
using namespace logger;
using namespace network;
using namespace port_agent;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/
/******************************************************************************
 * Method: Constructor
 * Description: Default constructor.  Is likely never called, but wanted to
 *              define it explicitly.
 ******************************************************************************/
ObservatoryConnection::ObservatoryConnection() : Connection() {
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
ObservatoryConnection::ObservatoryConnection(const ObservatoryConnection& rhs) {
    copy(rhs);
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
ObservatoryConnection::~ObservatoryConnection() {
}

/******************************************************************************
 * Method: Assignemnt operator
 * Description: Deep copy
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
ObservatoryConnection & ObservatoryConnection::operator=(const ObservatoryConnection &rhs) {
    copy(rhs);
    return *this;
}


/******************************************************************************
 * Method: copy
 * Description: Copy data from one packet object into this one.  Ensuring we
 * deep copy when needed.
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
void ObservatoryConnection::copy(const ObservatoryConnection &copy) {
    m_oDataSocket = copy.m_oDataSocket;
    m_oCommandSocket = copy.m_oCommandSocket;
}

/******************************************************************************
 * Method: setDataPort
 * Description: Set the data socket listener port.  First we want to see if the
 * port is bound and is listening on a port other than the target port we are
 * setting up.  If it is different, then we need to disconnect so it can be
 * bound to a new port.
 ******************************************************************************/
void ObservatoryConnection::setDataPort(uint16_t port) {
    m_oDataSocket.setPort(port);
    
    if(m_oDataSocket.listening() && m_oDataSocket.port() != m_oDataSocket.getListenPort()) {
	m_oDataSocket.initialize();
    }
}

/******************************************************************************
 * Method: setCommandPort
 * Description: Set the command socket listener port
 ******************************************************************************/
void ObservatoryConnection::setCommandPort(uint16_t port) {
    m_oCommandSocket.setPort(port);
}

/******************************************************************************
 * Method: dataConfigured
 * Description: Do we have enough configuration information to initialize the
 * data socket?
 *
 * Return: 
 *   True if we have enough configuration information
 ******************************************************************************/
bool ObservatoryConnection::dataConfigured() {
    return m_oDataSocket.isConfigured();
}

/******************************************************************************
 * Method: commandConfigured
 * Description: Do we have enough configuration information to initialize the
 * command socket?
 *
 * Return: 
 *   True if we have enough configuration information
 ******************************************************************************/
bool ObservatoryConnection::commandConfigured() {
    return m_oCommandSocket.port() && m_oCommandSocket.isConfigured();
}

/******************************************************************************
 * Method: dataInitialized
 * Description: Has the data socket been initialized yet? Is it listening?
 *
 * Return:
 *   True if the socket has been configured and is bound to a port listening
 ******************************************************************************/
bool ObservatoryConnection::dataInitialized() {
    return m_oDataSocket.listening();
}

/******************************************************************************
 * Method: commandInitialized
 * Description: Has the command socket been initialized yet? Is it listening?
 *
 * Return:
 *   True if the socket has been configured and is bound to a port listening
 ******************************************************************************/
bool ObservatoryConnection::commandInitialized() {
    return m_oCommandSocket.listening();
}

/******************************************************************************
 * Method: dataConnected
 * Description: Is a client connected to the data socket connection
 *
 * Return:
 *   True if the data socket is connected
 ******************************************************************************/
bool ObservatoryConnection::dataConnected() {
    return m_oDataSocket.connected();
}

/******************************************************************************
 * Method: commandConnected
 * Description: Is a client connected to the command connection?
 *
 * Return:
 *   True if the command socket is connected
 ******************************************************************************/
bool ObservatoryConnection::commandConnected() {
    return m_oCommandSocket.connected();
}

/******************************************************************************
 * Method: initializeDataSocket
 * Description: Initialize the data socket
 ******************************************************************************/
void ObservatoryConnection::initializeDataSocket() {
    m_oDataSocket.initialize();
}

/******************************************************************************
 * Method: initializeCommandSocket
 * Description: Initialize the command socket
 ******************************************************************************/
void ObservatoryConnection::initializeCommandSocket() {
    m_oCommandSocket.initialize();
}


