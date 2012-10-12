/*******************************************************************************
 * Class: InstrumentTCPConnection
 * Filename: instrument_tcp_connection.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Manages the socket connection between the observatory and the port agent.
 * This interface consists of a TCP listener on the data port and command port
 * setup in non-blocking mode.
 *
 * Usage:
 *
 * InstrumentTCPConnection connection;
 *
 * connection.setDataPort(4001);
 *
 * // Is the data port configured
 * connection.dataConfigured();
 *
 * // This is a noop for this method.  There is nothing to initialize
 * connection.initialize();
 *
 * // Always true for this connection type.
 * connection.dataInitialized();
 *
 * // Is the data port connected
 * connection.dataConnected();
 *
 * // Always false for this connection type
 * connection.commandConnected();
 *
 * // Get a pointer tcp data listener object
 * TCPCommListener *data = connection.dataConnectionObject();
 *    
 * // Always returns null for this connection type
 * TCPCommListener *command = connection.commandConnectionObject();
 *    
 ******************************************************************************/

#include "instrument_tcp_connection.h"
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
InstrumentTCPConnection::InstrumentTCPConnection() : Connection() {
}

/******************************************************************************
 * Method: Copy Constructor
 * Description: Copy constructor ensuring we do a deep copy of the packet data.
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
InstrumentTCPConnection::InstrumentTCPConnection(const InstrumentTCPConnection& rhs) {
    copy(rhs);
}

/******************************************************************************
 * Method: Destructor
 * Description: free up our dynamically created packet data.
 ******************************************************************************/
InstrumentTCPConnection::~InstrumentTCPConnection() {
}

/******************************************************************************
 * Method: Assignemnt operator
 * Description: Deep copy
 *
 * Parameters:
 *   copy - rhs object to copy
 ******************************************************************************/
InstrumentTCPConnection & InstrumentTCPConnection::operator=(const InstrumentTCPConnection &rhs) {
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
void InstrumentTCPConnection::copy(const InstrumentTCPConnection &copy) {
    m_oDataSocket = copy.m_oDataSocket;
}

/******************************************************************************
 * Method: setDataPort
 * Description: Set the port.  If we are already connected then we need to
 * disconnect and reconnect to the new port.
 ******************************************************************************/
void InstrumentTCPConnection::setDataPort(uint16_t port) {
    uint16_t oldPort = m_oDataSocket.port();
    m_oDataSocket.setPort(port);
    
    if(m_oDataSocket.connected() && m_oDataSocket.port() != oldPort) {
	m_oDataSocket.initialize();
    }
}

/******************************************************************************
 * Method: setDataHost
 * Description: Set the host.  If we are already connected then we need to
 * disconnect and reconnect to the new port.
 ******************************************************************************/
void InstrumentTCPConnection::setDataHost(const string & host) {
    string oldhost = m_oDataSocket.hostname();
    m_oDataSocket.setHostname(host);
    
    if(m_oDataSocket.connected() && m_oDataSocket.hostname() != oldhost) {
	m_oDataSocket.initialize();
    }
}

/******************************************************************************
 * Method: dataConfigured
 * Description: Do we have enough configuration information to initialize the
 * data socket?
 *
 * Return: 
 *   True if we have enough configuration information
 ******************************************************************************/
bool InstrumentTCPConnection::dataConfigured() {
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
bool InstrumentTCPConnection::commandConfigured() {
    return false;
}

/******************************************************************************
 * Method: dataInitialized
 * Description: No initialization sequence, so if configure then we are
 * initialiaze
 *
 * Return:
 *   True if configured.
 ******************************************************************************/
bool InstrumentTCPConnection::dataInitialized() {
    return dataConfigured();
}

/******************************************************************************
 * Method: commandInitialized
 * Description: Alwasy false because there is no command interface for this
 * connection type.
 *
 * Return:
 *   False
 ******************************************************************************/
bool InstrumentTCPConnection::commandInitialized() {
    return false;
}

/******************************************************************************
 * Method: dataConnected
 * Description: Is a client connected to the data socket connection
 *
 * Return:
 *   True if the data socket is connected
 ******************************************************************************/
bool InstrumentTCPConnection::dataConnected() {
    return m_oDataSocket.connected();
}

/******************************************************************************
 * Method: commandConnected
 * Description: Alwasy false because there is no command interface for this
 * connection type.
 *
 * Return:
 *   False
 ******************************************************************************/
bool InstrumentTCPConnection::commandConnected() {
    return false;
}

/******************************************************************************
 * Method: initializeDataSocket
 * Description: Initialize the data socket
 ******************************************************************************/
void InstrumentTCPConnection::initializeDataSocket() {
    m_oDataSocket.initialize();
}

/******************************************************************************
 * Method: initializeCommandSocket
 * Description: NOOP
 ******************************************************************************/
void InstrumentTCPConnection::initializeCommandSocket() {
}

/******************************************************************************
 * Method: initialize
 * Description: Initialize any uninitialized sockets if they are configured.
 ******************************************************************************/
void InstrumentTCPConnection::initialize() {
    if(!dataConfigured())
        LOG(DEBUG) << "Data port not configured. Not initializing";
	
    if(dataConfigured() && ! dataConnected()) {
	LOG(DEBUG) << "initialize data socket";
        initializeDataSocket();
    } 
}


