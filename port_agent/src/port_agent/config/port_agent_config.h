/*******************************************************************************
 * Class: PortAgentConfig
 * Filename: port_agent_config.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Configuration object for Port Agents.
 *
 * This class:
 *   * parses options from argc and argv
 *     passed to the constructor using getopt_long.
 *   * parses options read from the observatory command interface
 *   * store configuration parameters
 ******************************************************************************/

#ifndef PORT_AGENT_CONFIG_H_
#define PORT_AGENT_CONFIG_H_

#include <string>
#include <list>

using namespace std;

#define DEFAULT_PACKET_SIZE   1024
#define MAX_PACKET_SIZE       65472

#define BASE_FILENAME "port_agent"

#define DEFAULT_LOG_DIR   "/var/ooi/port_agent"
#define DEFAULT_CONF_DIR  "/var/ooi/port_agent"
#define DEFAULT_PID_DIR   "/var/ooi/port_agent"
#define DEFAULT_DATA_DIR  "/var/ooi/port_agent"


namespace port_agent {
    //////////////////////////////
    // Port Agent Commands
    typedef enum PortAgentCommand
    {
        CMD_UNKNOWN                 = 0x00000000,
        CMD_HELP                    = 0x00000001,
        CMD_COMM_CONFIG_UPDATE      = 0x00000002,
        CMD_PUBLISHER_CONFIG_UPDATE = 0x00000003,
        CMD_PATH_CONFIG_UPDATE      = 0x00000004,
        CMD_SAVE_CONFIG             = 0x00000005,
        CMD_GET_CONFIG              = 0x00000006,
        CMD_GET_STATE               = 0x00000007,
        CMD_PING                    = 0x00000008,
        CMD_BREAK                   = 0x00000009,
        CMD_SHUTDOWN                = 0x00000010
    } PortAgentCommand;
    typedef list<PortAgentCommand>  CommandQueue;
    
    typedef enum InstrumentConnectionType
    {
        TYPE_UNKNOWN           = 0x00000000,
        TYPE_SERIAL            = 0x00000001,
        TYPE_TCP               = 0x00000002,
        TYPE_RSN               = 0x00000003
    } InstrumentConnectionType;
    
    class PortAgentConfig {
        public:
            ///////////////////////
            // Constructors
            PortAgentConfig() {}
            PortAgentConfig(int argc, char *argv[]);
            
            ///////////////////////
            // Public Methods
            
            ///////////////////////
            // Accessors
            static string Usage();
            PortAgentCommand getCommand();
            
            // Commands
            void saveConfig();
            string getConfig();
            bool readConfig(const string & filename);
            
            bool isConfigured();
            
            bool parse(const string &commands);
            
            // Set methods
            bool setObservatoryDataPort(const string &param);
            bool setObservatoryCommandPort(const string &param);
            bool setInstrumentConnectionType(const string &param);
            bool setSentinleSequence(const string &param);
            bool setOutputThrottle(const string &param);
            bool setMaxPacketSize(const string &param);
            bool setLogLevel(const string &param);
            bool setBaud(const string &param);
            bool setStopbits(const string &param);
            bool setDatabits(const string &param);
            bool setParity(const string &param);
            bool setFlow(const string &param);
            bool setInstrumentDataPort(const string &param);
            bool setInstrumentCommandPort(const string &param);
            
            // Common Config
            string programName() { return m_programName; }
            bool help() { return m_help; }
            bool kill() { return m_kill; }
            
            string logfile();
            string pidfile();
            string conffile();
            
            string logdir() { return m_logdir; }
            string piddir() { return m_piddir; }
            string confdir() { return m_confdir; }
            string datadir() { return m_datadir; }
            
            bool noDetatch() { return m_noDetatch; }
            unsigned short verbose() { return m_verbose; }
            unsigned int observatoryCommandPort() { return m_observatoryCommandPort; }
            unsigned int observatoryDataPort() { return m_observatoryDataPort; }
            
            InstrumentConnectionType instrumentConnectionType() { return m_instrumentConnectionType; }
            const string & sentinleSequence() { return m_sentinleSequence; }
            uint32_t outputThrottle() { return m_outputThrottle; }
            uint32_t maxPacketSize() { return m_maxPacketSize; }
            
            
            uint32_t baud() { return m_baud; }
 	    uint16_t stopbits() { return m_stopbits; }
 	    uint16_t databits() { return m_databits; }
 	    uint16_t parity() { return m_parity; }
 	    uint16_t flow() { return m_flow; }
	    const string & instrumentAddr() { return m_instrumentAddr; }
 	    uint16_t instrumentDataPort() { return m_instrumentDataPort; }
            uint16_t instrumentCommandPort() { return m_instrumentCommandPort; }
            
        private:
            void setParameter(char option, char *value);
            void addCommand(PortAgentCommand command);
            bool processCommand(const string & command);
            bool splitCommand(const string & raw, string & cmdResult, string & parameter);
            
            void verifyCommandLineParameters();
            
            ///////////////////////
            // Private Data
            
            // storage for the commands processed by this object
            CommandQueue m_commands;
            
            // Command line options, not all of these can be changed via
            // public methods post construction.
            bool m_help;
            bool m_kill;
            string m_programName;
            
            string m_pidfile;
            string m_logfile;
            string m_conffile;
            
            string m_piddir;
            string m_logdir;
            string m_confdir;
            string m_datadir;
            
            bool m_noDetatch;
            unsigned short m_verbose;
            
            uint16_t m_observatoryCommandPort;
            uint16_t m_observatoryDataPort;
            string m_sentinleSequence;
            
            uint32_t m_outputThrottle;
            uint32_t m_maxPacketSize;
            
            InstrumentConnectionType m_instrumentConnectionType;
            
            uint32_t m_baud;
 	    uint16_t m_stopbits;
 	    uint16_t m_databits;
 	    uint16_t m_parity;
 	    uint16_t m_flow;
	    string m_instrumentAddr;
 	    uint16_t m_instrumentDataPort;
            uint16_t m_instrumentCommandPort;
    };
}


#endif //PORT_AGENT_CONFIG_H_
