/*******************************************************************************
 * Class: PortAgentConfig
 * Filename: port_agent_config.cpp
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Configuration object for Port Agents.  This class parses options from argv
 * passed to the constructor using getopt_long. 
 ******************************************************************************/
#include "port_agent_config.h"
#include "common/logger.h"
#include "common/exception.h"

#include <ctype.h>
#include <stdlib.h>
#include <unistd.h>
#include <getopt.h>

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <list>

using namespace std;
using namespace logger;
using namespace port_agent;

/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: Construct a configuration object from command line parameters
 *              passed in from the command line using (argv).
 ******************************************************************************/
PortAgentConfig::PortAgentConfig(int argc, char* argv[]) {
    
    char c = 0;
    
    
    if(argc) 
        m_programName = string(argv[0]);
    
    LOG(INFO) << "PortAgentConfig ctor";
    
    // Initalize Defaults
    m_noDetatch = false;
    m_verbose = 0;
    m_observatoryCommandPort = 0;
    m_observatoryDataPort = 0;
    m_help = false;
    m_outputThrottle = 0;
    m_maxPacketSize = DEFAULT_PACKET_SIZE;
    
    m_instrumentConnectionType = TYPE_UNKNOWN;
    
    // Connection settings
    m_baud = 0;
    m_stopbits = 1;
    m_databits = 8;
    m_parity = 0;
    m_flow = 0;
    m_instrumentDataPort = 0;
    m_instrumentCommandPort = 0;
    
    m_piddir = DEFAULT_PID_DIR;
    m_logdir = DEFAULT_LOG_DIR;
    m_confdir = DEFAULT_CONF_DIR;
    m_datadir = DEFAULT_DATA_DIR;
            
    // the getopt string representing command line options.
    string optstr = "c:vhsp:k";
        
    // Long option equiviant of getopt string.
    static struct option long_options[] = {
        {"conffile",  required_argument, 0,  'c' },
        {"verbose",   no_argument, 0,  'v' },
        {"help",      no_argument, 0,  'h' },
        {"kill",      no_argument, 0,  'k' },
        {"single",    no_argument, 0,  's' },
        
        {"command_port",  required_argument, 0,  'p' },
        {NULL,         0,                 NULL,  0 }
    };

    LOG(DEBUG) << "Arg Count: " << argc << " Calculated Count: " << sizeof(argv) / sizeof(char*);
    
    // Reset optind so that this can be called more than once in a program.
    // Really only matters for unit tests
    optind = 1;
    
    // Parse the command line options and store their values.
    do {
        int option_index = 0;
        c = getopt_long(argc, argv, optstr.c_str(),
                        long_options, &option_index);
        
        if (c > 0) {
            if(optarg)
                LOG(DEBUG) << "SET: " << c << " VALUE: " << optarg;
            else
                LOG(DEBUG) << "SET: " << c;
            setParameter(c, optarg);
        }
    }
    while (c > 0);

    verifyCommandLineParameters();
}


/******************************************************************************
 * Method: conffile()
 * Description: return a path to the configuration file;
 * Return: formatted path string
 ******************************************************************************/
string PortAgentConfig::conffile() {
    ostringstream out;
    out << confdir() << "/" << BASE_FILENAME << "_"
        << observatoryCommandPort() << ".conf";
    
    LOG(DEBUG) << "Config path: " << out.str();
    
    return out.str();
}


/******************************************************************************
 * Method: logfile()
 * Description: return a path to the log file;
 * Return: formatted path string
 ******************************************************************************/
string PortAgentConfig::logfile() {
    ostringstream out;
    out << logdir() << "/" << BASE_FILENAME << "_"
        << observatoryCommandPort() << ".log";
    
    LOG(DEBUG) << "Log path: " << out.str();
    
    return out.str();
}


/******************************************************************************
 * Method: pidfile()
 * Description: return a path to the pid file;
 * Return: formatted path string
 ******************************************************************************/
string PortAgentConfig::pidfile() {
    ostringstream out;
    
    out << piddir() << "/" << BASE_FILENAME << "_"
        << observatoryCommandPort() << ".pid";
    
    LOG(DEBUG) << "Pid path: " << out.str();
    
    return out.str();
}


/******************************************************************************
 * Method: usage()
 * Description: Return a formatted string containing the valid options for
 *              a port agent.
 * Return: formatted usage string
 ******************************************************************************/
string PortAgentConfig::Usage() {
    ostringstream os;
    os << "USAGE: " << "port_agent" << endl
       << "\t" << " --help" 
               << "\t\t\t- Display this message " << endl
       << "\t" << " --kill" 
               << "\t\t\t- Kill a daemon processes associated to a command port " << endl
       << "\t" << " --verbose (-v) " 
               << "\t- Increase program verbosity " << endl << endl
               
       << "\t" << " --conffile (-c) config_file "
               << "\t- Path to port_agent config file" << endl
       
       << "\t" << " --command_port (-p) port" 
               << "\t- Observatory command port number " << endl
       
       << "\t" << " --single (-s)" 
               << "\t- Run in single thread mode. Do not detatch " << endl;
       
    return os.str();
}

/******************************************************************************
 * Method: getCommand()
 * Description: Return a command from the FIFO command queue.
 * Return: The oldest command if there are any in the queue, otherwise return
 *         0.
 ******************************************************************************/
PortAgentCommand PortAgentConfig::getCommand() {
    if(m_commands.empty()) {
        return CMD_UNKNOWN;
    } else {
        PortAgentCommand cmd = m_commands.front();
        m_commands.pop_front();
        return cmd;
    }
}

/******************************************************************************
 * Method: saveConfig()
 * Description: Return a command from the FIFO command queue.
 * Return: The oldest command if there are any in the queue, otherwise return
 *         0.
 ******************************************************************************/
void PortAgentConfig::saveConfig() {
    string configFile = conffile();
    
}

/******************************************************************************
 * Method: parse()
 * Description: parse a string of characters into commands.  If they are
 *              set parameters then also set the appropriate member variable.
 * Return: return true if all bytes were successfully parsed into config
 *         commands.
 ******************************************************************************/
bool PortAgentConfig::parse(const string &commands) {
    istringstream iss(commands);
    char buffer[1024];
    
    while(iss.getline(buffer, 1024)) {
        string cmd(buffer);
        LOG(DEBUG) << "Config CMD: " << cmd;
        
        if(!processCommand(cmd)) {
            LOG(DEBUG) << "failed to parse: " << cmd;
            return false;
        }
    }
    
    return true;
}

/******************************************************************************
 * Method: isConfigured()
 * Description: determine if we have enough information to run the port agent.
 * Return: return true we are ready for a port agent state change
 ******************************************************************************/
bool PortAgentConfig::isConfigured() {
    bool ready = true;
    
    if(! instrumentConnectionType()) {
        LOG(DEBUG) << "Missing instrument connection type";
        ready = false;
    }
    
    if(! observatoryCommandPort()) {
        LOG(DEBUG) << "Missing observatory command port";
        ready = false;
    }

    if(! observatoryDataPort()) {
        LOG(DEBUG) << "Missing observatory data port";
        ready = false;
    }

    if(instrumentConnectionType() == TYPE_TCP ||
       instrumentConnectionType() == TYPE_RSN) {
        if(! instrumentAddr().length()) {
            LOG(DEBUG) << "Missing instrument address";
            ready = false;
        }
        
        if(! instrumentDataPort()) {
            LOG(DEBUG) << "Missing instrument data port";
            ready = false;
        }
    }
    
    if(instrumentConnectionType() == TYPE_RSN) {
        if(! instrumentCommandPort()) {
            LOG(DEBUG) << "Missing instrument command port";
            ready = false;
        }
    }
    
    if(instrumentConnectionType() == TYPE_SERIAL) {
        if(! baud()) {
            LOG(DEBUG) << "Missing baud rate";
            ready = false;
        }
    }
    
    return ready;
}

/******************************************************************************
 * Method: readConfig()
 * Description: Read a config file and store the content in this object
 * Return: return true if all lines were read successfully
 ******************************************************************************/
bool PortAgentConfig::readConfig(const string & filename) {
    ifstream infile(filename.c_str());
    char buffer[128];
    bool success = true;
    
    if(!infile)
        throw FileIOException();
    
    while(infile.getline(buffer, 128)) {
        if(! parse(buffer) )
            success = false;     
    }
    
    return success;
}

/******************************************************************************
 * Method: getConfig()
 * Description: return a string dump of the current configuration which can
 *              be read in by the port agent to return state.
 * Return: string dump of the current config
 ******************************************************************************/
string PortAgentConfig::getConfig() {
    ostringstream out;
    const char *buffer;
    string loglevel = Logger::Instance()->levelToString(Logger::GetLogLevel());

    out << "pid_dir " << m_piddir << endl
        << "log_dir " << m_logdir << endl
        << "conf_dir " << m_confdir << endl
        << "data_dir " << m_datadir << endl
        
        << "log_level " << loglevel << endl
        
        << "command_port " << m_observatoryCommandPort << endl
        << "data_port " << m_observatoryDataPort << endl;
        
        if(m_instrumentConnectionType) {
            out << "instrument_type ";
            
            if(m_instrumentConnectionType == TYPE_SERIAL)
                out << "serial";
            else if(m_instrumentConnectionType == TYPE_TCP)
                out << "tcp";
            else if(m_instrumentConnectionType == TYPE_RSN)
                out << "rsn";
            
            out << endl;
        }
        
        buffer = m_sentinleSequence.c_str(); 
        out << "sentinle '";
        for(int i = 0; i < m_sentinleSequence.length(); i++) {
            if(buffer[i] == '\n')
                out << "\\n";
            else if(buffer[i] == '\r')
                out << "\\r";
            else
                out << buffer[i];
        }
        out << "'" << endl;
        
        out << "output_throttle " << m_outputThrottle << endl
            << "max_packet_size " << m_maxPacketSize << endl
            << "baud " << m_baud << endl
            << "stopbits " << m_stopbits << endl
            << "databits " << m_databits << endl
            << "parity " << m_parity << endl
            << "flow " << m_flow << endl
            << "instrument_addr " << m_instrumentAddr << endl
            << "instrument_data_port " << m_instrumentDataPort << endl
            << "instrument_command_port " << m_instrumentCommandPort << endl;
        
    return out.str();
}


//////
// Set Methods
//////
/******************************************************************************
 * Method: setInstrumentConnectionType
 * Description: Set the configuration instrument connection type
 * Return:
 *     return true if the type was set correctly, otherwise false for unknown
 *     types.
 *****************************************************************************/
bool PortAgentConfig::setInstrumentConnectionType(const string &param) {
    m_instrumentConnectionType = TYPE_UNKNOWN;
    
    if(param == "serial") {
        LOG(INFO) << "connection type set to serial";
        m_instrumentConnectionType = TYPE_SERIAL;
    }
    
    else if(param == "tcp") {
        LOG(INFO) << "connection type set to tcp";
        m_instrumentConnectionType = TYPE_TCP;
    }
    
    else if(param == "rsn") {
        LOG(INFO) << "connection type set to rsn";
        m_instrumentConnectionType = TYPE_RSN;
    }
    
    else {
        LOG(ERROR) << "unknown connection type: " << param;
        m_instrumentConnectionType = TYPE_UNKNOWN;
        return false;
    }
    
    return true;
}

/******************************************************************************
 * Method: setSentinleSequence
 * Description: Set the sentinle sequence
 * Param:
 *     command - the entire command string to set the sentinle.  We do this
 *     because we need to do custom parsing for this command in case there is
 *     a CR or LF embedded in the sentinle. 
 * Return:
 *     return true if the sequence was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setSentinleSequence(const string &command) {
    istringstream iss(command);
    
    string cmd, param, dump;
    m_sentinleSequence = param;
    
    char buffer[128];
    
    iss >> cmd;
    iss.getline(buffer, 128, '\'');
    
    // if buffer is empty then no single quote was found.
    if(!buffer[0]) {
        LOG(ERROR) << "Failed to parse sentinle string: " << command;
        return false;
    }
    
    iss.getline(buffer, 128, '\'');
    
    // Iterate through the buffer and substitute \n and \r strings
    for(int i = 0; i < 128 && buffer[i]; i++) {
        if(buffer[i] == '\\') {
            if( i >= 127 || (buffer[i+1] != 'n' && buffer[i+1] != 'r') ) {
                LOG(DEBUG) << "Sentinle backslash ignored";
                param += buffer[i];
            }
            else if(buffer[i+1] == 'n') {
                LOG(DEBUG) << "Sentinle sub: \n";
                param += "\n";
                i++;
            }
            else if(buffer[i+1] == 'r') {
                LOG(DEBUG) << "Sentinle sub: \r";
                param += "\r";
                i++;
            }
        } else {
            LOG(DEBUG) << "add sentinle char: " << buffer[i];
            param += buffer[i];
        }
    }
    
    LOG(DEBUG) << "Sentinle string length: " << param.length();
    
    m_sentinleSequence = param;
    
    return true;
}

/******************************************************************************
 * Method: setOutputThrottle
 * Description: Set the output throttle
 * Param:
 *     param - string represention of the value of the throttle.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the throttle was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setOutputThrottle(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    m_outputThrottle = 0;
    
    if(value == 0 && v[0] != '0') {
        LOG(ERROR) << "invalid output throttle parameter, " << param;
        return false;
    }
    
    if(value < 0) {
        LOG(ERROR) << "attempt to set output throttle to a negative.  0 instead.";
        return false;
    }
    
    LOG(INFO) << "set output throttle to " << value;
    m_outputThrottle = value;
    return true;
}

/******************************************************************************
 * Method: setObervatoryDataPort
 * Description: Set the observatory data port
 * Param:
 *     param - string represention of the value of the port.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the throttle was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setObservatoryDataPort(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    m_observatoryDataPort = 0;
    
    if(value <= 0 || value > 65535) {
        LOG(ERROR) << "Invalid port specification, setting to 0";
        return false;
    }
    
    LOG(INFO) << "set observatory data port to " << value;
    m_observatoryDataPort = value;
    return true;
}

/******************************************************************************
 * Method: setObervatoryCommandPort
 * Description: Set the observatory command port
 * Param:
 *     param - string represention of the value of the port.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the throttle was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setObservatoryCommandPort(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    m_observatoryCommandPort = 0;
    
    if(value <= 0 || value > 65535) {
        LOG(ERROR) << "Invalid port specification, setting to 0";
        return false;
    }
    
    LOG(INFO) << "set observatory command port to " << value;
    m_observatoryCommandPort = value;
    return true;
}

/******************************************************************************
 * Method: setInstrumentDataPort
 * Description: Set the instrument data port
 * Param:
 *     param - string represention of the value of the port.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the port was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setInstrumentDataPort(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    m_instrumentDataPort = 0;
    
    if(value <= 0 || value > 65535) {
        LOG(ERROR) << "Invalid port specification, setting to 0";
        return false;
    }
    
    LOG(INFO) << "set instrument data port to " << value;
    m_instrumentDataPort = value;
    return true;
}

/******************************************************************************
 * Method: setInstrumentCommandPort
 * Description: Set the instrument command port
 * Param:
 *     param - string represention of the value of the port.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the port was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setInstrumentCommandPort(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    m_instrumentCommandPort = 0;
    
    if(value <= 0 || value > 65535) {
        LOG(ERROR) << "Invalid port specification, setting to 0";
        return false;
    }
    
    LOG(INFO) << "set instrument command port to " << value;
    m_instrumentCommandPort = value;
    return true;
}

/******************************************************************************
 * Method: setMaxPacketSize
 * Description: Set the max packet size
 * Param:
 *     param - string represention of the value of the throttle.  If it is not
 *     a number the value will be set to 0.
 * Return:
 *     return true if the throttle was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setMaxPacketSize(const string &param) {
    const char* v = param.c_str();
    
    int value = atoi(v);
    
    if(value <= 0) {
        LOG(ERROR) << "Invalid max packet size.  using default " << DEFAULT_PACKET_SIZE;
        m_maxPacketSize = DEFAULT_PACKET_SIZE;
        return false;
    }
    
    if(value > MAX_PACKET_SIZE) {
        LOG(ERROR) << "packet size exceeds maximum value, " << MAX_PACKET_SIZE
                   << " using default " << DEFAULT_PACKET_SIZE;
        m_maxPacketSize = DEFAULT_PACKET_SIZE;
        return false;
    }
    
    LOG(INFO) << "set max packet size to " << value;
    m_maxPacketSize = value;
    return true;
}

/******************************************************************************
 * Method: setLogLevel
 * Description: Change the log level
 * Return:
 *     return true if the log level was set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setLogLevel(const string &param) {
    string str = param;
    transform(str.begin(), str.end(),str.begin(), ::toupper);
    
    if(str == "WARN")
        str = "WARNING";
        
    Logger::SetLogLevel(str);
    
    if(Logger::GetError()) {
        return false;
    }
    
    return true;
}

/******************************************************************************
 * Method: setBaud
 * Description: Change the baud
 * Return:
 *     return true if set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setBaud(const string &param) {
    uint32_t baud = atoi(param.c_str());
    
    if( baud != 1200 && baud != 2400 && baud != 4800 && baud != 9600 && 
       baud != 19200 && baud != 38400 && baud != 57600 && baud != 115200 ) {
        LOG(ERROR) << "Invalid baud rate: " << baud;
        m_baud = 0;
        return false;
    }
    
    m_baud = baud;
    return true;
}

/******************************************************************************
 * Method: setStopbits
 * Description: Change the stopbits
 * Return:
 *     return true if set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setStopbits(const string &param) {
    uint32_t bits = atoi(param.c_str());
    
    if( bits != 1  && bits != 2 ) {
        LOG(ERROR) << "Invalid stop bits: " << bits;
        m_stopbits = 1;
        return false;
    }
    
    m_stopbits = bits;
    return true;
}

/******************************************************************************
 * Method: setDatabits
 * Description: Change the data bits
 * Return:
 *     return true if set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setDatabits(const string &param) {
    uint32_t bits = atoi(param.c_str());
    
    if( bits != 5 && bits != 6 && bits != 7 && bits != 8 ) {
        LOG(ERROR) << "Invalid data bits: " << bits;
        m_databits = 8;
        return false;
    }
    
    m_databits = bits;
    return true;
}

/******************************************************************************
 * Method: setParity
 * Description: Change the parity
 * Return:
 *     return true if set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setParity(const string &param) {
    uint32_t parity = atoi(param.c_str());
    const char *buffer = param.c_str();
    
    if( (buffer[0] != '0' && parity == 0) ||
        (parity != 0 && parity != 1 && parity != 2) ) {
        LOG(ERROR) << "Invalid parity: " << parity;
        m_parity = 0;
        return false;
    }
    
    m_parity = parity;
    return true;
}


/******************************************************************************
 * Method: setFlow
 * Description: Change the flow control
 * Return:
 *     return true if set correctly, otherwise false.
 *****************************************************************************/
bool PortAgentConfig::setFlow(const string &param) {
    uint32_t flow = atoi(param.c_str());
    const char *buffer = param.c_str();
    
    if( (buffer[0] != '0' && flow == 0) ||
        (flow != 0 && flow != 1 && flow != 2) ) {
        LOG(ERROR) << "Invalid flow: " << flow;
        m_flow = 0;
        return false;
    }
    
    m_flow = flow;
    return true;
}

/******************************************************************************
 *   PRIVATE METHODS
 ******************************************************************************/
/******************************************************************************
 * Method: setParameter(char option, char *value)
 * Description: Set the object parameter
 * Exceptions:
 *     ParameterRequired()
 * Return:
 *     return true if options are valid.
 *****************************************************************************/
void PortAgentConfig::setParameter(char option, char *value) {
    switch(option) {
        case 'c':
            readConfig(value);
            m_conffile = value; break;
        case 'p':
            m_observatoryCommandPort = atoi(value); break;
        case 's':
            m_noDetatch = true; break;
        case 'h':
            addCommand(CMD_HELP);
            m_help = true;
            break;
        case 'k':
            addCommand(CMD_SHUTDOWN);
            m_kill = true;
            break;
        case 'v':
            m_verbose++;
            Logger::IncreaseLogLevel(1);
            break;
        case '?':
            throw ParameterRequired();
    };
}


/******************************************************************************
 * Method: verifyCommandLineParameters()
 * Description: Verify we have all the information we need to start from the
 *              command line.  
 * Exceptions:
 *     ParameterRequired()
 *****************************************************************************/
void PortAgentConfig::verifyCommandLineParameters() {
    // If help then no verification needed.
    if(m_help == CMD_HELP)
        return;

    // Ensure we have an observatory command port because that's is the
    // port agent's unique identifier.
    if(observatoryCommandPort() == 0)
        throw ParameterRequired("observatoryCommandPort");
        
}


/******************************************************************************
 * Method: addCommand()
 * Description: Add a command to the command queue.  First search the queue,
 * if the command already exists, don't add it again.
 ******************************************************************************/
void PortAgentConfig::addCommand(PortAgentCommand command) {
    bool cmdFound = false;
    list<PortAgentCommand>::iterator i = m_commands.begin();
    for(i = m_commands.begin(); i != m_commands.end(); i++)
        if(*i == command)
            cmdFound = true;
    
    if(! cmdFound) {
        LOG(DEBUG) << "Command added: " << command;
        m_commands.push_back(command);
    }
    else {
        LOG(DEBUG) << "Command already in command queue.  not adding again";
    }
}


/******************************************************************************
 * Method: processCommand()
 * Description: Read a command from a string and then process it.  This would
 *              be setting the configuration parameter if needed and adding a
 *              command to the queue if needed.
 * Return: true if successfully parsed.
 ******************************************************************************/
bool PortAgentConfig::processCommand(const string & command) {
    string cmd, param;
    splitCommand(command, cmd, param);
    
    ///////////////////////////
    // First look for commands
    ///////////////////////////
    if( command == "help" )
        addCommand(CMD_HELP);
        
    else if( command == "verbose" )
        Logger::IncreaseLogLevel(1);
        
    else if( command == "save_config" )
        addCommand(CMD_SAVE_CONFIG);
        
    else if( command == "get_config" )
        addCommand(CMD_GET_CONFIG);
        
    else if( command == "get_state" )
        addCommand(CMD_GET_STATE);
        
    else if( command == "ping" )
        addCommand(CMD_PING);
        
    else if( command == "break" )
        addCommand(CMD_BREAK);
        
    else if( command == "shutdown" )
        addCommand(CMD_SHUTDOWN);
        
    
    ///////////////////////////
    // Check for parameters
    ///////////////////////////
    
    else if(cmd == "instrument_type") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setInstrumentConnectionType(param);
    }
    
    else if(cmd == "sentinle") {
        // We pass the entire command string to this incase there are \n or \r
        // embedded in the sentinle string.
        addCommand(CMD_PUBLISHER_CONFIG_UPDATE);
        return setSentinleSequence(command);
    }
    
    else if(cmd == "output_throttle") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setOutputThrottle(param);
    }
    
    else if(cmd == "max_packet_size") {
        addCommand(CMD_PUBLISHER_CONFIG_UPDATE);
        return setMaxPacketSize(param);
    }
    
    else if(cmd == "data_port") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setObservatoryDataPort(param);
    }
    
    else if(cmd == "command_port") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setObservatoryCommandPort(param);
    }
    
    else if(cmd == "instrument_data_port") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setInstrumentDataPort(param);
    }
    
    else if(cmd == "instrument_command_port") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setInstrumentCommandPort(param);
    }
    
    else if(cmd == "log_level") {
        return setLogLevel(param);
    }
    
    else if(cmd == "log_dir") {
        addCommand(CMD_PATH_CONFIG_UPDATE);
        m_logdir = param;
    }
    
    else if(cmd == "pid_dir") {
        addCommand(CMD_PATH_CONFIG_UPDATE);
        m_piddir = param;
    }
    
    else if(cmd == "data_dir") {
        addCommand(CMD_PATH_CONFIG_UPDATE);
        m_datadir = param;
    }
    
    else if(cmd == "conf_dir") {
        addCommand(CMD_PATH_CONFIG_UPDATE);
        m_confdir = param;
    }
    
    else if(cmd == "log_dir") {
        addCommand(CMD_PATH_CONFIG_UPDATE);
        m_logdir = param;
    }
    
    else if(cmd == "instrument_addr") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        m_instrumentAddr = param;
    }
    
    else if(cmd == "baud") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setBaud(param);
    }
    
    else if(cmd == "stopbits") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setStopbits(param);
    }
    
    else if(cmd == "databits") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setDatabits(param);
    }
    
    else if(cmd == "parity") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setParity(param);
    }
    
    else if(cmd == "flow") {
        addCommand(CMD_COMM_CONFIG_UPDATE);
        return setFlow(param);
    }
    
    // Couldn't parse this command
    else {
        return false;
    }
    
    return true;
        
}

/******************************************************************************
 * Method: splitCommand()
 * Description: Split a command string into a command and parameter.
 * Return: return true if we could successfully parse.
 ******************************************************************************/
bool PortAgentConfig::splitCommand(const string &raw, string & cmdResult, string & paramResult) {
    string cmd, param, dump;
    istringstream iss(raw);
    
    // Read the command
    iss >> cmd;
    
    // Read a parameter if it exists
    iss >> param;
    
    // If there are any trailing tokens it's an error
    iss >> dump;
    if(dump.length()) {
        LOG(ERROR) << "trailing config tokens found in: " << raw;
        return false;
    }
    
    // We made it through the parser, store the results
    cmdResult = cmd;
    paramResult = param;
    return true;
}
