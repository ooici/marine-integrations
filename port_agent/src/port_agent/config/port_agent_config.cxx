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
#include <sstream>
#include <string>

using namespace std;
using namespace logger;

#define DEFAULT_LOG_DIR   "/var/ooi/port_agent"
#define DEFAULT_DATA_DIR  "/var/ooi/port_agent"
#define DEFAULT_PID_DIR   "/var/ooi/port_agent"

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
        m_program_name = string(argv[0]);
    
    LOG(INFO) << "PortAgentConfig ctor";
    
    // Reset optind so that this can be called more than once in a program.
    // Really only matters for unit tests
    optind = 1;
    
    
    // Initalize Defaults
    m_verbose = 0;
    m_help = false;
    m_kill = false;
    m_digi = false;
    m_serial = false;
    m_tcp = false;
    m_no_detatch = false;
    
    //Device
    m_device_port = 0;
    m_device_host = "";
    
    //Driver
    m_driver_port = 0;
    
    // Serial defaults
    m_baudrate = 0;
    m_databits = 8;
    m_stopbits = 1;
    m_parity   = 'n';
    
    // the getopt string representing command line options.
    string optstr = "kl:d:vhsabcwq:p:x:y:z:n:m:v:";
        
    // Long option equiviant of getopt string.
    static struct option long_options[] = {
        {"logfile",   required_argument, 0,  'l' },
        {"pidfile",   required_argument, 0,  'q' },
        {"datafile",  required_argument, 0,  'd' },
        {"verbose",   no_argument, 0,  'v' },
        {"help",      no_argument, 0,  'h' },
        {"kill",      no_argument, 0,  'k' },
        {"single",    no_argument, 0,  's' },
        
        {"serial",    no_argument, 0,  'a' },
        {"tcp",       no_argument, 0,  'b' },
        {"digi",      no_argument, 0,  'c' },
        
        // Driver
        {"driver_port",  required_argument, 0,  'p' },
        
        // For Serial Connections
        {"serial_device",  required_argument, 0,  'u' },
        {"baudrate",  required_argument, 0,  'z' },
        {"databits",  required_argument, 0,  'y' },
        {"parity",    required_argument, 0,  'x' },
        {"stopbits",  required_argument, 0,  'w' },
        
        // For TCP Connections
        {"device_host",  required_argument, 0,  'n' },
        {"device_port",  required_argument, 0,  'm' },
        
        {NULL,         0,                 NULL,  0 }
    };

    LOG(DEBUG) << "Arg Count: " << argc << " Calculated Count: " << sizeof(argv) / 8;
    
    // Parse the command line options and store their values.
    do {
        int option_index = 0;
        c = getopt_long(argc, argv, optstr.c_str(),
                        long_options, &option_index);
        
        if (c > 0) {
            LOG(DEBUG) << "SET: " << c;
            set_parameter(c, optarg);
        }
    }
    while (c > 0);
    
    set_common_defaults();
        
    validate();
}

void PortAgentConfig::set_common_defaults() {
    stringstream logfile;
    stringstream datafile;
    stringstream pidfile;
    
    logfile  << DEFAULT_LOG_DIR  << "/" << "port_agent_log_"  << driver_port() << ".txt";
    datafile << DEFAULT_DATA_DIR << "/" << "port_agent_data_" << driver_port() << ".txt";
    pidfile  << DEFAULT_PID_DIR  << "/" << "port_agent_"      << driver_port() << ".pid";
    
    if(!m_logfile.length() && !m_no_detatch)  m_logfile  = logfile.str();
    if(! m_datafile.length()) m_datafile = datafile.str();
    if(! m_pidfile.length())  m_pidfile  = pidfile.str();
}

/******************************************************************************
 * Method: usage()
 * Description: Return a formatted string containing the valid options for
 *              a port agent.
 * Return: formatted usage string
 ******************************************************************************/
string PortAgentConfig::usage() {
    ostringstream os;
    os << "USAGE: " << m_program_name << endl
       << "\t" << " --help" 
               << "\t\t\t- Display this message " << endl
       << "\t" << " --verbose (-v) " 
               << "\t- Increase program verbosity " << endl << endl
               
       << "\t## Common Program Options ##" << endl << endl
       
       << "\t" << " --logfile logfile "
               << "\t- Path to logfile for debug output " << endl
       
       << "\t" << " --pidfile pidfile "
               << "\t- Path to logfile for debug output " << endl
       
       << "\t" << " --driver_port" 
               << "\t- Port where the driver will connect " << endl
       << "\t" << " --single" 
               << "\t- Run in single thread mode. Do not detatch " << endl
       << "\t" << " --serial" 
               << "\t- Set device connection type to serial " << endl
       << "\t" << " --tcp" 
               << "\t\t- Set device connection type to tcp " << endl
       << "\t" << " --digi" 
               << "\t\t- Set device connection type to digi " << endl << endl
       
       << "\t## Serial Device Options ##" << endl << endl
       
       << "\t" << " --serial_device dev " 
               << "\t- Set the serial device for the device connection " << endl
       << "\t" << " --baudrate baud " 
               << "\t- Set the baud rate for the device connection " << endl
       << "\t" << " --databits int" 
               << "\t\t- Set the databits for the device connection (default: 8) " << endl
       << "\t" << " --parity char " 
               << "\t\t- Set the parity for the device connection (default: n)" << endl
       << "\t" << " --stopbits int" 
               << "\t\t- Set the stopbits for the device connection (default: 1) " << endl << endl
       
       
       << "\t## Serial Server Options ##" << endl << endl
       
       << "\t" << " --device_host hostname " 
               << "\t- Hostname for the device server" << endl
       << "\t" << " --device_port int " 
               << "\t\t- Port for the device server " << endl << endl
               
       << "\t## Publishers ##" << endl << endl
       << "\t" << " --datafile datafile " 
               << "\t- Path to data where all communications are stored " << endl << endl;
       
    return os.str();
}

/******************************************************************************
 *   PRIVATE METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: validate
 * Description: Validate parameters set are valid. Invalid options throw an
 *              exception.
 * Exceptions:
 *     InvalidParameters()
 * Return:
 *     return true if options are valid.
 ******************************************************************************/
bool PortAgentConfig::validate() {
    int cmd_count = 0;
    
    LOG(INFO) << "PortAgentConfig::validate";
    // Help donesn't require any validation
    if(help())
        return true;
    
    // Serial, Digi, and TCP are mutually exclusive options
    if(serial()) cmd_count++;
    if(digi()) cmd_count++;
    if(tcp()) cmd_count++;
    if(kill()) cmd_count++;
    
    if(cmd_count == 0)
        throw InvalidParameter("must specify serial, digi, or tcp");
        
    if(cmd_count > 1)
        throw InvalidParameter("serial, digi, or tcp options are mutually exclusive");
        
    // Ensure we have specified a driver port
    if(! driver_port())
        throw InvalidParameter("driver_port required");
        
    // Ensure we have a log files specified if we are a daemon
    if(!no_detatch() && !logfile().length())
        throw InvalidParameter("logfile required");
        
    // Command specific validation
    if(serial()) validate_serial();
    if(tcp()) validate_tcp();
    
    return true;
}

/******************************************************************************
 * Method: validate_serial
 * Description: Validate parameters set are valid for a serial port agent.
 * Exceptions:
 *     InvalidParameters()
 * Return:
 *     return true if options are valid.
 *****************************************************************************/
bool PortAgentConfig::validate_serial() {
    if(serial_device().length() == 0)
        throw InvalidParameter("serial_device required");
        
    // We can set the baudrate to positive int
    if(baudrate() == 0)
        throw InvalidParameter("baudrate required");
        
    // parity according to wikipedia
    if(!(m_parity == 'n' || m_parity == 'e' || m_parity == 'o' || m_parity == 'm' || m_parity == 's'))
        throw InvalidParameter("Invalid parity. (VALID: n, e, o, m, s)");
    
    if(!(m_stopbits == 0 || m_stopbits == 1 || m_stopbits == 2))
        throw InvalidParameter("Invalid stopbits. (VALID: 0, 1, 2)");
    
    if(!(m_databits >= 5 && m_databits <= 9))
        throw InvalidParameter("Invalid databits. (VALID: >= 5 <= 9)");
    
    return true;
}

/******************************************************************************
 * Method: validate_tcp
 * Description: Validate parameters set are valid for a tcp port agent.
 * Exceptions:
 *     InvalidParameters()
 * Return:
 *     return true if options are valid.
 *****************************************************************************/
bool PortAgentConfig::validate_tcp() {
    if(device_host().length() == 0)
        throw InvalidParameter("device_host required");
    
    if(device_port() == 0)
        throw InvalidParameter("device_port required");
        
    return true;
}

/******************************************************************************
 * Method: set_parameter(char option, char *value)
 * Description: Set the object parameter
 * Exceptions:
 *     ParameterRequired()
 * Return:
 *     return true if options are valid.
 *****************************************************************************/
void PortAgentConfig::set_parameter(char option, char *value) {
    switch(option) {
        case 'q':
            m_pidfile = value; break;
        case 'l':
            m_logfile = value; break;
        case 'd':
            m_datafile = value; break;
        case 'p':
            m_driver_port = atoi(value); break;
        case 's':
            m_no_detatch = true; break;
        case 'a':
            m_serial = true; break;
        case 'b':
            m_tcp = true; break;
        case 'c':
            m_digi = true; break;
        case 'k':
            m_kill = true; break;
        case 'h':
            m_help = true; break;
        case 'u':
            m_serial_device = value; break;
        case 'z':
            m_baudrate = atoi(value); break;
        case 'y':
            m_databits = atoi(value); break;
        case 'x':
            m_parity = value[0]; break;
        case 'w':
            m_stopbits = atoi(value); break;
        case 'n':
            m_device_host = value; break;
        case 'm':
            if(value) m_device_port = atoi(value);
            break;
        case 'v':
            m_verbose++; break;
        case '?':
            throw ParameterRequired();
    };
}

