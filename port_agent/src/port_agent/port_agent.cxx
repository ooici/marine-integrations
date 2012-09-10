/*******************************************************************************
 * Class: PortAgent
 * Filename: port_agent.cpp
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Main controlling class for the port agent
 ******************************************************************************/
#include "port_agent.h"
#include "config/port_agent_config.h"
#include "connection/observatory_connection.h"
#include "connection/instrument_tcp_connection.h"
#include "packet/packet.h"
#include "packet/buffered_single_char.h"

#include <iostream>
#include <string.h>
#include <netinet/in.h>
#include <netdb.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/fcntl.h>
#include <stdio.h>
#include <stdlib.h>

using namespace std;
using namespace packet;
using namespace network;
using namespace port_agent;

/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Default Constructor
 ******************************************************************************/
PortAgent::PortAgent() {
    m_pObservatoryConnection = NULL;
    m_pInstrumentConnection = NULL;
    
    m_pConfig = NULL;
    m_oState = STATE_UNKNOWN;
}

/******************************************************************************
 * Method: Constructor
 * Description: Construct a configuration object from command line parameters
 *              passed in from the command line using (argv).
 ******************************************************************************/
PortAgent::PortAgent(int argc, char *argv[]) {
    // Setup the log file if we are running as a daemon
    if(no_daemon())
        Logger::SetLogFile("/dev/stderr");
    else
        Logger::SetLogFile(m_pConfig->logfile());
        
    LOG(DEBUG) << "Initialize port agent with args";
    
    m_pConfig = new PortAgentConfig(argc, argv);
    setState(STATE_STARTUP);
    
    m_pInstrumentConnection = NULL;
    m_pObservatoryConnection = NULL;
    
}

/******************************************************************************
 * Method: Destructor
 * Description: Clear dynamic memory
 ******************************************************************************/
PortAgent::~PortAgent() {
    if(m_pObservatoryConnection)
        delete m_pObservatoryConnection;
        
    if(m_pInstrumentConnection)
        delete m_pInstrumentConnection;
        
    if(m_pConfig)
        delete m_pConfig;
        
    m_pConfig = NULL;
}

/******************************************************************************
 * Method: daemon_command
 * Description: Overloaded virtual method from the Daemon Process class.
 * Defines the command used to launch the daemon process.
 ******************************************************************************/
const string PortAgent::daemon_command() {
    throw NotImplemented();
}

/******************************************************************************
 * Method: no_daemon
 * Description: Tell the parent class if we should daemonize or not.
 * Returns true if we want to run in signle thread mode
 ******************************************************************************/
bool PortAgent::no_daemon() {
    return m_pConfig ? m_pConfig->noDetatch() : true;
}

/******************************************************************************
 * Method: pid_file
 * Description: Overloaded virtual method from the Daemon Process class.
 * Returns the path to the daemon process PID file.
 ******************************************************************************/
const string PortAgent::pid_file() {
    return m_pConfig ? m_pConfig->pidfile() : "";
}


/******************************************************************************
 * Method: start
 * Description: Overloaded the base class method to check for different
 * commands, specifically kill and help.
 ******************************************************************************/
bool PortAgent::start() {
    
    if(m_pConfig->help())
        cout << "USAGE: " << PortAgentConfig::Usage() << endl;
        
    else if(m_pConfig->kill())
        kill_process();
    else {
        return DaemonProcess::start();
    }
    
    return true;
}

/******************************************************************************
 * Method: initialize
 * Description: Bring the process up from an unknown state to unconfigured.
 ******************************************************************************/
void PortAgent::initializeObservatoryDataConnection() {
    int port;
    ObservatoryConnection *connection = (ObservatoryConnection*)m_pObservatoryConnection;
    TCPCommListener *listener = NULL;
    
    if(connection) {
        listener = (TCPCommListener *)(connection->dataConnectionObject());
    
        // If we are initialized already ensure the ports match.  If not, reinit
        if(listener) {
            if( listener->getListenPort() != m_pConfig->observatoryDataPort()) 
                listener->disconnect();
        }
    }
    
    // Create the connection object
    if(! m_pObservatoryConnection) {
        m_pObservatoryConnection = new ObservatoryConnection();
        connection = (ObservatoryConnection*)m_pObservatoryConnection;
    }
    
    // Initialize!
    connection->setDataPort(m_pConfig->observatoryCommandPort());
    
    if(! connection->dataInitialized())
        connection->initialize();
}

/******************************************************************************
 * Method: initialize
 * Description: Bring the process up from an unknown state to unconfigured.
 ******************************************************************************/
void PortAgent::initializeObservatoryCommandConnection() {
    int port;
    ObservatoryConnection *connection = (ObservatoryConnection*)m_pObservatoryConnection;
    TCPCommListener *listener = NULL;
    
    if(connection) {
        listener = (TCPCommListener *)(connection->commandConnectionObject());
    
        // If we are initialized already ensure the ports match.  If not, reinit
        if(listener) {
            if( listener->getListenPort() != m_pConfig->observatoryCommandPort()) 
                listener->disconnect();
        }
    }
    
    // Create the connection object
    if(! m_pObservatoryConnection) {
        LOG(DEBUG2) << "create a new observatory connection object";
        m_pObservatoryConnection = new ObservatoryConnection();
        connection = (ObservatoryConnection*)m_pObservatoryConnection;
    }
    
    // Initialize!
    connection->setCommandPort(m_pConfig->observatoryCommandPort());
    
    if(! connection->commandInitialized())
        connection->initialize();
}

/******************************************************************************
 * Method: initializeInstrumentConnection
 * Description: Attempt to connect to the instrument.  This class will attempt
 * to connect to the data port and command port if needed.  If both are not
 * successful then we enter a disconnected state, otherwise we transition to
 * connected.
 *
 * Currently the only connection type we are supporting is TCP.  Eventually
 * this method will need to support more types.
 ******************************************************************************/
void PortAgent::initializeInstrumentConnection() {
    if(m_pConfig->instrumentConnectionType() == TYPE_TCP)
        initializeTCPInstrumentConnection();
}

/******************************************************************************
 * Method: initializeTCPInstrumentConnection
 * Description: Connect to a TCP type instrument.  There is no command port
 * for this bad boy.
 *
 * State Transitions:
 *  Connected - if we can connect to an instrument
 *  Disconnected - if we fail to connect to an instrument
 ******************************************************************************/
void PortAgent::initializeTCPInstrumentConnection() {
    InstrumentTCPConnection *connection = (InstrumentTCPConnection *)m_pInstrumentConnection;
    
    // Clear if we have already initialized the wrong type
    if(connection && connection->connectionType() != PACONN_INSTRUMENT_TCP) {
        LOG(INFO) << "Detected connection type change.  rebuilding connection.";
        delete connection;
        connection = NULL;
    }
    
    // Create the connection object
    if(!connection)
        m_pInstrumentConnection = connection = new InstrumentTCPConnection();
       
    // If we have changed out configuration the set the new values and try to connect
    if(connection->dataHost() != m_pConfig->instrumentAddr() ||
       connection->dataPort() != m_pConfig->instrumentDataPort() ) {
        LOG(INFO) << "Detected connection configuration change.  reconfiguring.";
        
        connection->disconnect();
        
        connection->setDataHost(m_pConfig->instrumentAddr());
        connection->setDataPort(m_pConfig->instrumentDataPort());
    }
    
    if(!connection->connected()) {
        LOG(DEBUG) << "Instrument not connected, attempting to reconnect";
        LOG(DEBUG2) << "host: " << connection->dataHost() << " port: " << connection->dataPort();
        
        setState(STATE_DISCONNECTED);
        
        try {
            connection->initialize();
        }
        catch(SocketConnectFailure &e) {
            connection->disconnect();
            string msg = e.what();
            LOG(ERROR) << msg;
        };
        
        // Let everything connect
        sleep(SELECT_SLEEP_TIME);
    }
    
    
    if(connection->connected())
        setState(STATE_CONNECTED);
}


/******************************************************************************
 * Method: handlePortAgentCommand
 * Description: This method is called outside of the normal packet publishing
 * process to affect change on the port agent from port agnet commands passed
 * in via the observatory command port.
 *
 * This method can accept multiple commands at once delimeted by newlines
 * Parameter:
 *   commands - newline delimeted string of port agent commands.
 ******************************************************************************/
void PortAgent::handlePortAgentCommand(const char * commands) {
    LOG(DEBUG2) << "DATA: " << commands;
    
    if(!m_pConfig)
        return;
    
    m_pConfig->parse(commands);
    
    processPortAgentCommands();
    // TODO: Add code for commands. i.e. Configuration Update, shutdown, etc...
    
    if(m_pConfig->isConfigured())
        setState(STATE_CONFIGURED);
}

/******************************************************************************
 * Method: processPortAgentCommands
 * Description: Loop through all the queued commands in the port agent
 * configuration object and handle each command.
 ******************************************************************************/
void PortAgent::processPortAgentCommands() {
    PortAgentCommand cmd;

    while(cmd = m_pConfig->getCommand()) {
        switch (cmd) {
            case CMD_COMM_CONFIG_UPDATE:
                LOG(DEBUG) << "communication config update command";
                setState(STATE_UNCONFIGURED);
                break;
            case CMD_PUBLISHER_CONFIG_UPDATE:
                LOG(DEBUG) << "publisher config update command";
                break;
            case CMD_PATH_CONFIG_UPDATE:
                LOG(DEBUG) << "path config update command";
                break;
            case CMD_SAVE_CONFIG:
                LOG(DEBUG) << "same config command";
                break;
            case CMD_GET_CONFIG:
                LOG(DEBUG) << "get config command";
                break;
            case CMD_GET_STATE:
                LOG(DEBUG) << "get state command";
                break;
            case CMD_PING:
                LOG(DEBUG) << "ping command";
                break;
            case CMD_BREAK:
                LOG(DEBUG) << "break command";
                break;
            case CMD_SHUTDOWN:
                LOG(DEBUG) << "shutdown command";
                break;
        };
    }
}


/******************************************************************************
 * Method: handleTCPConnect
 * Description: handler for processing a client trying to connect to a TCP
 * listener.
 * Parameter:
 *   listener - TCP listener object for managing the tcp connection.
 ******************************************************************************/
void PortAgent::handleTCPConnect(TCPCommListener &listener) {
    listener.acceptClient();
    
    if(! listener.connected()) {
        throw SocketConnectFailure("tcp client connect");
    }
}

/******************************************************************************
 * Method: handleStateUnconfigured
 * Description: handler for the unconfigured state
 ******************************************************************************/
void PortAgent::handleStateUnconfigured(const fd_set &readFDs) {
    LOG(DEBUG) << "start state unconfigured handler";
    
    handleObservatoryCommandAccept(readFDs);
    handleObservatoryCommandRead(readFDs);
}

/******************************************************************************
 * Method: handleStateConfigured
 * Description: handler for the configured state.  All we need to do in this
 * state is either go into connected (if we can connect to the instrument) or
 * disconnected.
 ******************************************************************************/
void PortAgent::handleStateConfigured(const fd_set &readFDs) {
    LOG(DEBUG) << "start state configured handler";
    
    initializeInstrumentConnection();
    initializeObservatoryDataConnection();
}

/******************************************************************************
 * Method: handleStateConnected
 * Description: handler for the connected state
 ******************************************************************************/
void PortAgent::handleStateConnected(const fd_set &readFDs) {
    LOG(DEBUG) << "start state connected handler";
    
    // Accept any new connections.
    handleObservatoryCommandAccept(readFDs);
    handleObservatoryDataAccept(readFDs);
    
    // Read data
    handleObservatoryCommandRead(readFDs);
    handleObservatoryDataRead(readFDs);
    handleInstrumentDataRead(readFDs);
}

/******************************************************************************
 * Method: handleStateDisconnected
 * Description: handler for the disconnected state
 ******************************************************************************/
void PortAgent::handleStateDisconnected(const fd_set &readFDs) {
    LOG(DEBUG) << "start state disconnected handler";
    
    // Accept any new connections.
    handleObservatoryCommandAccept(readFDs);
    handleObservatoryDataAccept(readFDs);
    
    // Read data
    handleObservatoryCommandRead(readFDs);
    handleObservatoryDataRead(readFDs);
    handleInstrumentDataRead(readFDs);
}

/******************************************************************************
 * Method: handleStateUnknown
 * Description: handler for the unconfigured state.  We should never get here
 * so just EXPLODE!
 ******************************************************************************/
void PortAgent::handleStateUnknown() {
    LOG(DEBUG) << "start state unknown handler";
    throw UnknownState();
}


/******************************************************************************
 * Method: handleStateStartup
 * Description: handler for the startup state.  Initialize the command
 * connection.
 ******************************************************************************/
void PortAgent::handleStateStartup() {
    LOG(DEBUG) << "start state start up handler";
    initializeObservatoryCommandConnection();
    setState(STATE_UNCONFIGURED);
}

/******************************************************************************
 * Method: poll
 * Description: main program loop.  Looping structure is in base class
 ******************************************************************************/
void PortAgent::poll() {
    fd_set readFDs;
    struct timeval tv;
    int readyCount;
    int maxFD = buildFDSet(readFDs);
    
    tv.tv_sec = SELECT_SLEEP_TIME;
    tv.tv_usec = 0;
    
    // Main select to see if any incoming pipes have data.
    LOG(DEBUG) << "Start select process";
    readyCount = select(maxFD+1, &readFDs, NULL, NULL, &tv);
    LOG(DEBUG2) << "On select: ready to read on " << readyCount << " connections";
    
    LOG(DEBUG) << "CURRENT STATE: " << getCurrentStateAsString();
    LOG(DEBUG) << "CURRENT STATE: " << getCurrentStateAsString();
    LOG(DEBUG) << "CURRENT STATE: " << getCurrentStateAsString();
    LOG(DEBUG) << "CURRENT STATE: " << getCurrentStateAsString();
    
    try {
        // We don't use else if here so that the work in one state handler
        // can change the state can call a subsiquent handler without having
        // to iterate.
        if(getCurrentState() == STATE_UNCONFIGURED)
            handleStateUnconfigured(readFDs);
        
        if(getCurrentState() == STATE_CONFIGURED)
            handleStateConfigured(readFDs);
        
        if(getCurrentState() == STATE_CONNECTED)
            handleStateConnected(readFDs);
        
        if(getCurrentState() == STATE_DISCONNECTED)
            handleStateDisconnected(readFDs);
        
        if(getCurrentState() == STATE_STARTUP)
            handleStateStartup();
        
        if(getCurrentState() == STATE_UNKNOWN)
            handleStateUnknown();
    }
    catch(UnknownState &e) {
        //re-throw the exception
        throw e;
    }
    catch(OOIException &e) {
        string msg = e.what();
        LOG(ERROR) << msg;
        // TODO: publish fault packet
    }
}

/******************************************************************************
 * Method: buildFDSet
 * Description: Build a fd_set of file descriptors of all of our read lines and
 * return the max file descriptor for use in a select statement.
 *
 * We need to read from several descriptors:
 *  * Observatory Command Connection (Listener)
 *  * Observatory Connection Connection (Client)
 *  * Observatory Data Connection (Listener)
 *  * Observatory Data Connection (Client)
 *  * Instrument Data Connection (Client)
 * 
 * Return:
 *  the maximum file descriptor value.
 *  readFDs populated with all current FDs available for reading
 ******************************************************************************/
int PortAgent::buildFDSet(fd_set &readFDs) {
    int maxFD = 0;
    
    FD_ZERO(&readFDs);
    
    addObservatoryCommandListenerFD(maxFD, readFDs);
    addObservatoryCommandClientFD(maxFD, readFDs);
    addObservatoryDataListenerFD(maxFD, readFDs);
    addObservatoryDataClientFD(maxFD, readFDs);
    addInstrumentDataClientFD(maxFD, readFDs);
    
    return maxFD;
}

/******************************************************************************
 * Method: addObservatoryCommandListenerFD
 * Description: Add the observatory connection fd to the fd_set.  Also update
 * the max file descriptor.
 *
 * If the connection isn't initialized then do nothing.
 ******************************************************************************/
void PortAgent::addObservatoryCommandListenerFD(int &maxFD, fd_set &readFDs) {
    CommBase *pConnection;
    
    if(m_pObservatoryConnection) {
        pConnection = m_pObservatoryConnection->commandConnectionObject();
        int fd = 0;
    
        if(m_pObservatoryConnection->commandInitialized())
            fd = getObservatoryCommandListenerFD();
    
        if(m_pObservatoryConnection->commandInitialized() && fd) {
            LOG(DEBUG2) << "add observatory command listener FD";
            maxFD = fd > maxFD ? fd : maxFD;
            FD_SET(fd, &readFDs);
        }
        else {
            LOG(DEBUG2) << "Observatory command listener not initialized";
        }
    }
}

/******************************************************************************
 * Method: addObservatoryCommandClientFD
 * Description: Add the observatory connection fd to the fd_set.  Also update
 * the max file descriptor.
 *
 * If the connection isn't initialized then do nothing.
 ******************************************************************************/
void PortAgent::addObservatoryCommandClientFD(int &maxFD, fd_set &readFDs) {
    CommBase *pConnection;
    
    if(m_pObservatoryConnection) {
        pConnection = m_pObservatoryConnection->commandConnectionObject();
        int fd = 0;
        
        if(m_pObservatoryConnection->commandInitialized())
            fd = getObservatoryCommandClientFD();
        
        if(m_pObservatoryConnection->commandInitialized() && fd) {
            LOG(DEBUG2) << "add observatory command client FD";
            maxFD = fd > maxFD ? fd : maxFD;
            FD_SET(fd, &readFDs);
        }
        else {
            LOG(DEBUG2) << "Observatory data client not initialized";
        }    
    }
}

/******************************************************************************
 * Method: addObservatoryDataListenerFD
 * Description: Add the observatory data fd to the fd_set.  Also update
 * the max file descriptor.
 *
 * If the connection isn't initialized then do nothing.
 ******************************************************************************/
void PortAgent::addObservatoryDataListenerFD(int &maxFD, fd_set &readFDs) {
    CommBase *pConnection;
    
    if(m_pObservatoryConnection) {
        pConnection = m_pObservatoryConnection->dataConnectionObject();
        int fd = 0;
    
        if(m_pObservatoryConnection->dataInitialized())
            fd = getObservatoryDataListenerFD();
    
        if(m_pObservatoryConnection->dataInitialized() && fd) {
            LOG(DEBUG2) << "add observatory data listener FD";
            maxFD = fd > maxFD ? fd : maxFD;
            FD_SET(fd, &readFDs);
        }
        else {
            LOG(DEBUG2) << "Observatory data listener not initialized";
        }
    }
}

/******************************************************************************
 * Method: addObservatoryCommandClientFD
 * Description: Add the observatory data fd to the fd_set.  Also update
 * the max file descriptor.
 *
 * If the connection isn't initialized then do nothing.
 ******************************************************************************/
void PortAgent::addObservatoryDataClientFD(int &maxFD, fd_set &readFDs) {
    CommBase *pConnection;
    
    if(m_pObservatoryConnection) {
        pConnection = m_pObservatoryConnection->dataConnectionObject();
        int fd = 0;
        
        fd = getObservatoryDataClientFD();
        
        if(fd) {
            LOG(DEBUG2) << "add observatory data client FD";
            maxFD = fd > maxFD ? fd : maxFD;
            FD_SET(fd, &readFDs);
        }
        else {
            LOG(DEBUG2) << "Observatory data client not initialized";
        }    
    }
}

/******************************************************************************
 * Method: addInstrumentDataClientFD
 * Description: Add the instrument client fd to the fd_set.  Also update
 * the max file descriptor.
 *
 * If the connection isn't initialized then do nothing.
 ******************************************************************************/
void PortAgent::addInstrumentDataClientFD(int &maxFD, fd_set &readFDs) {
    CommBase *pConnection;
    
    if(m_pInstrumentConnection) {
        pConnection = m_pInstrumentConnection->dataConnectionObject();
        int fd = 0;
        
        fd = getObservatoryCommandClientFD();
        
        if(fd) {
            LOG(DEBUG2) << "add instrument data client FD";
            maxFD = fd > maxFD ? fd : maxFD;
            FD_SET(fd, &readFDs);
        }
        else {
            LOG(DEBUG2) << "Observatory data client not initialized";
        }    
    }
}

/******************************************************************************
 * Method: getObservatoryCommandListenerFD
 * Description: Get the file descriptor
 ******************************************************************************/
int PortAgent::getObservatoryCommandListenerFD() {
    CommBase *pConnection = m_pObservatoryConnection->commandConnectionObject();
    if(m_pObservatoryConnection->commandInitialized() && ! m_pObservatoryConnection->commandConnected()) {
        return ((TCPCommListener*)pConnection)->serverFD();
    }
    
    return 0;
}

/******************************************************************************
 * Method: getObservatoryCommandClientFD
 * Description: Get the file descriptor
 ******************************************************************************/
int PortAgent::getObservatoryCommandClientFD() {
    CommBase *pConnection = m_pObservatoryConnection->commandConnectionObject();
    if(m_pObservatoryConnection->commandConnected()) {
        return ((TCPCommListener*)pConnection)->clientFD();
    }
    
    return 0;
}

/******************************************************************************
 * Method: getObservatoryDataListenerFD
 * Description: Get the file descriptor
 ******************************************************************************/
int PortAgent::getObservatoryDataListenerFD() {
    CommBase *pConnection = m_pObservatoryConnection->dataConnectionObject();
    if(m_pObservatoryConnection->dataInitialized() && ! m_pObservatoryConnection->dataConnected()) {
        return ((TCPCommListener*)pConnection)->clientFD();
    }
    
    return 0;  
}

/******************************************************************************
 * Method: getObservatoryDataClientFD
 * Description: Get the file descriptor
 ******************************************************************************/
int PortAgent::getObservatoryDataClientFD() {
    CommBase *pConnection = m_pObservatoryConnection->dataConnectionObject();
    if(m_pObservatoryConnection->dataConnected()) {
        return ((TCPCommListener*)pConnection)->clientFD();
    }
    
    return 0;
}

/******************************************************************************
 * Method: getInstrumentDataClientFD
 * Description: Get the file descriptor
 ******************************************************************************/
int PortAgent::getInstrumentDataClientFD() {
    CommBase *pConnection = m_pInstrumentConnection->dataConnectionObject();
    if(m_pObservatoryConnection->dataConnected()) {
        return ((TCPCommListener*)pConnection)->clientFD();
    }
    
    return 0;    
}

/******************************************************************************
 * Method: publishFault
 * Description: Generate a fault packet and send it to the publishers.
 ******************************************************************************/
void PortAgent::publishFault(const string &msg) {
    Timestamp ts;
    Packet packet(PORT_AGENT_FAULT, ts, (char *)(msg.c_str()), msg.length());

    LOG(ERROR) << "Port Agent Fault: " << msg;
    publishPacket(&packet);
}

/******************************************************************************
 * Method: publishPacket
 * Description: Publish a packet. Just iterate over all publisher and call
 * the publish method.  Easy Peasy
 ******************************************************************************/
void PortAgent::publishPacket(const Packet *packet) {
    // TODO: write the pulisher loop.
}

/******************************************************************************
 * Method: handleObservatoryCommandConnect
 * Description: Accept connection to the TCP command connection.
 ******************************************************************************/
void PortAgent::handleObservatoryCommandAccept(const fd_set &readFDs) {
    CommBase *pConnection = m_pObservatoryConnection->commandConnectionObject();
    int serverFD = getObservatoryCommandListenerFD();
    
    LOG(DEBUG) << "handleObservatoryCommandAccept - do we need to accept a new connection?";
    LOG(DEBUG2) << "Server FD: " << serverFD;
        
    // Accept a new observatory command client
    if(serverFD && FD_ISSET(serverFD, &readFDs)) {
        LOG(DEBUG) << "Observatory command listener has data";
        handleTCPConnect(*((TCPCommListener*)pConnection));
    }
}

/******************************************************************************
 * Method: handleObservatoryCommandRead
 * Description: Read from the observatory command port
 ******************************************************************************/
void PortAgent::handleObservatoryCommandRead(const fd_set &readFDs) {
    CommBase *pConnection = m_pObservatoryConnection->commandConnectionObject();
    int clientFD = getObservatoryCommandClientFD();
    int bytesRead = 0;
    char buffer[1024];
    
    LOG(DEBUG) << "handleObservatoryCommandRead - do we need to read from the observatory command";
    LOG(DEBUG2) << "Client FD: " << clientFD;
        
    if(clientFD && FD_ISSET(clientFD, &readFDs)) {
        LOG(DEBUG) << "Read data from observatory command socket";
        bytesRead = ((TCPCommListener*)pConnection)->readData(buffer, 1023);
        buffer[bytesRead] = '\0';
        
        if(bytesRead) {
            LOG(DEBUG2) << "Bytes read: " << bytesRead;
            handlePortAgentCommand(buffer);
        }
    }
}

/******************************************************************************
 * Method: handleObservatoryDataAccept
 * Description: Accept connection to the TCP data connection.
 ******************************************************************************/
void PortAgent::handleObservatoryDataAccept(const fd_set &readFDs) {
    CommBase *pConnection = m_pObservatoryConnection->dataConnectionObject();
    int serverFD = getObservatoryDataListenerFD();
    
    LOG(DEBUG) << "handleObservatoryDataAccept - do we need to accept a new connection?";
    LOG(DEBUG2) << "Server FD: " << serverFD;
        
    // Accept a new observatory command client
    if(serverFD && FD_ISSET(serverFD, &readFDs)) {
        LOG(DEBUG) << "Observatory data listener has data";
        handleTCPConnect(*((TCPCommListener*)pConnection));
    }
}

/******************************************************************************
 * Method: handleObservatoryDataRead
 * Description: Read from the observatory data port
 ******************************************************************************/
void PortAgent::handleObservatoryDataRead(const fd_set &readFDs) {
    CommBase *pConnection = m_pObservatoryConnection->dataConnectionObject();
    int clientFD = getObservatoryDataClientFD();
    int bytesRead = 0;
    char buffer[1024];
    
    LOG(DEBUG) << "handleObservatoryDataRead - do we need to read from the observatory data";
    LOG(DEBUG2) << "Client FD: " << clientFD;
        
    if(clientFD && FD_ISSET(clientFD, &readFDs)) {
        LOG(DEBUG) << "Read data from observatory data socket";
        bytesRead = ((TCPCommListener*)pConnection)->readData(buffer, 1023);
        buffer[bytesRead] = '\0';
        
        if(bytesRead) {
            LOG(DEBUG2) << "Bytes read: " << bytesRead;
            // TODO: Add handler code
        }
    }
}

/******************************************************************************
 * Method: handleInstrumentDataRead
 * Description: Read from the instrument data port
 ******************************************************************************/
void PortAgent::handleInstrumentDataRead(const fd_set &readFDs) {
    CommBase *pConnection = m_pInstrumentConnection->dataConnectionObject();
    int clientFD = getInstrumentDataClientFD();
    int bytesRead = 0;
    char buffer[1024];
    
    LOG(DEBUG) << "handleInstrumentDataRead - do we need to read from the instrument data";
    
    if(! clientFD) {
        LOG(DEBUG2) << "instrument not connected, attempting to re-init the socket";
        initializeInstrumentConnection();
        clientFD = getInstrumentDataClientFD();
    }
    
    LOG(DEBUG2) << "Client FD: " << clientFD;
        
    if(clientFD && FD_ISSET(clientFD, &readFDs)) {
        LOG(DEBUG) << "Read data from instrument data socket";
        bytesRead = pConnection->readData(buffer, 1023);
        buffer[bytesRead] = '\0';
        
        if(bytesRead) {
            LOG(DEBUG2) << "Bytes read: " << bytesRead;
            // TODO: Add handler code
        }
    }
}

/******************************************************************************
 * Method: getCurrentStateAsString
 * Description: return the current state as a string object
 ******************************************************************************/
const string PortAgent::getCurrentStateAsString() {
    if(getCurrentState() == STATE_UNCONFIGURED)
        return "UNCONFIGURED";
    else if(getCurrentState() == STATE_CONFIGURED)
        return "CONFIGURED";
    else if(getCurrentState() == STATE_CONNECTED)
        return "CONNECTED";
    else if(getCurrentState() == STATE_DISCONNECTED)
        return "DISCONNECTED";
    else if(getCurrentState() == STATE_STARTUP)
        return "STARTUP";
    else
        return "UNKNOWN";
}

/******************************************************************************
 * Method: setState
 * Description: State the port agent intrument connection state
 ******************************************************************************/
void PortAgent::setState(const PortAgentState &state) {
    const string previousState = getCurrentStateAsString();
    
    m_oState = state;

    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
    LOG(DEBUG2) << "State transition from " << previousState << " TO " << getCurrentStateAsString();
}
