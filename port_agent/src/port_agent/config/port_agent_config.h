/*******************************************************************************
 * Class: PortAgentConfig
 * Filename: port_agent_config.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Configuration object for Port Agents.  This class parses options from argv
 * passed to the constructor using getopt_long. 
 ******************************************************************************/

#ifndef PORT_AGENT_CONFIG_H_
#define PORT_AGENT_CONFIG_H_

#include <string>
using namespace std;

class PortAgentConfig {
    public:
        ///////////////////////
        // Constructors
        PortAgentConfig() {}
        PortAgentConfig(int argc, char *argv[]);
        
        ///////////////////////
        // Public Methods
        
        // Return a string containing program options
        string usage();
        
        ///////////////////////
        // Accessors
        string program_name() { return m_program_name; }
        
        // Commands
        bool serial() { return m_serial; }
        bool tcp() { return m_tcp; }
        bool digi() { return m_digi; }
        bool help() { return m_help; }
        bool kill() { return m_kill; }
        
        // Common Config
        string logfile() { return m_logfile; }
        string pidfile() { return m_pidfile; }
        string datafile() { return m_datafile; }
        bool no_detatch() { return m_no_detatch; }
        unsigned short verbose() { return m_verbose; }
        
        // Driver Config
        unsigned int driver_port() { return m_driver_port; }
        
        // Serial Config
        string serial_device() { return m_serial_device; }
        unsigned int baudrate() { return m_baudrate; }
        unsigned short databits() { return m_databits; }
        char parity() { return m_parity; }
        unsigned short stopbits() { return m_stopbits; }
        
        // Network Config
        string device_host() { return m_device_host; }
        unsigned int device_port() { return m_device_port; }
        
    private:
        void set_parameter(char option, char *value);
        void set_common_defaults();
        void set_serial_defaults();
        
        ///////////////////////
        // Validation Methods
        bool validate();
        bool validate_serial();
        bool validate_tcp();
        bool validate_digi();
        
        ///////////////////////
        // Private Data
        string m_program_name;
        string m_pidfile;
        string m_logfile;
        string m_datafile;
        
        bool m_help;
        bool m_kill;
        bool m_no_detatch;
        bool m_serial;
        bool m_tcp;
        bool m_digi;
        
        unsigned short m_verbose;
        
        // Driver Info
        unsigned int m_driver_port;
        
        // Serial
        string m_serial_device;
        unsigned int m_baudrate;
        unsigned short m_databits;
        char m_parity;
        unsigned short m_stopbits;
        
        // TCP/IP
        string m_device_host;
        
        unsigned int m_device_port;
};


#endif //PORT_AGENT_CONFIG_H_
