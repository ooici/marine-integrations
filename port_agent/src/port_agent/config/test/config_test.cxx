#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "common/spawn_process.h"
#include "gtest/gtest.h"

#include "port_agent/config/port_agent_config.h"

using namespace logger;
using namespace port_agent;

#define TEST_PORT "4001"
#define CONFIG_PATH "/tmp/port_agent_test.cfg"

class CommonTest : public testing::Test {
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "            Common Test Start Up";
            LOG(INFO) << "************************************************";
        }
    
        virtual void TearDown() {
            LOG(INFO) << "CommonTest TearDown";
        }
    
        ~CommonTest() {
            LOG(INFO) << "CommonTest dtor";
        }
};

////////////////////////////////////////////////////////////////////////////////
// First lets test constructors with various command line arguments
////////////////////////////////////////////////////////////////////////////////

/* Test basic construction with help */
TEST_F(CommonTest, CommandArgsHelp ) {
    char* argv[] = { "port_agent_config_test", "--help" };
    int argc = sizeof(argv) / sizeof(char*);
    
    PortAgentConfig config(argc, argv);
    EXPECT_EQ(config.getCommand(), CMD_HELP);
    EXPECT_TRUE(config.help());
}


/* Test the minimal command line args with command port */
TEST_F(CommonTest, CommandArgsMinimalWithPort ) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    stringstream logfile, conffile, pidfile;
    
    PortAgentConfig config(argc, argv);
    conffile << DEFAULT_CONF_DIR  << "/" << "port_agent_"  << config.observatoryCommandPort() << ".conf";
    logfile  << DEFAULT_LOG_DIR  << "/" << "port_agent_"  << config.observatoryCommandPort() << ".log";
    pidfile  << DEFAULT_PID_DIR  << "/" << "port_agent_"      << config.observatoryCommandPort() << ".pid";
    
    EXPECT_FALSE(config.noDetatch());
    EXPECT_FALSE(config.verbose());
    EXPECT_EQ(config.observatoryCommandPort(), atoi(TEST_PORT));
    EXPECT_EQ(config.programName(), "port_agent_config_test");
    EXPECT_EQ(config.logfile(), logfile.str());
    EXPECT_EQ(config.conffile(), conffile.str());
    EXPECT_EQ(config.pidfile(), pidfile.str());
}

/* Test the minimal command line args without command port (failure state) */
TEST_F(CommonTest, CommandArgsMinimalNoPort ) {
    bool exceptionSeen = false;
    
    char* argv[] = { "port_agent_config_test" };
    int argc = sizeof(argv) / sizeof(char*);
    
    try {
        PortAgentConfig config(argc, argv);
    }
    catch(ParameterRequired &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        exceptionSeen = true;
    }
    
    EXPECT_TRUE(exceptionSeen);
}
    
/* Test all command line parameters */
TEST_F(CommonTest, CommandArgsSetting ) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT,
                     "-v", "-v",
                     "--single" };
    int argc = sizeof(argv) / sizeof(char*);
    stringstream logfile, conffile, pidfile;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_TRUE(config.noDetatch());
    EXPECT_EQ(config.verbose(), 2);
    EXPECT_EQ(config.observatoryCommandPort(), atoi(TEST_PORT));
    EXPECT_EQ(config.programName(), "port_agent_config_test");
}

/* Test command queue is FIFO */
TEST_F(CommonTest, CommandArgsQueue ) {
    char* argv[] = { "port_agent_config_test", 
                     "-v", "-h" };
    int argc = sizeof(argv) / sizeof(char*);
    stringstream logfile, conffile, pidfile;
    
    PortAgentConfig config(argc, argv);
    
    // The help command was second
    EXPECT_EQ(config.getCommand(), CMD_HELP);
    
    // There should be no more commands in the queue
    EXPECT_FALSE(config.getCommand());
}

/* Test commands are only added once */
TEST_F(CommonTest, CommandArgsQueueDuplicates ) {
    char* argv[] = { "port_agent_config_test", 
                     "-v", "-h", "-h", "-v" };
    int argc = sizeof(argv) / sizeof(char*);
    stringstream logfile, conffile, pidfile;
    
    PortAgentConfig config(argc, argv);
    
    // The help command was second
    EXPECT_EQ(config.getCommand(), CMD_HELP);
    
    // There should be no more commands in the queue
    EXPECT_FALSE(config.getCommand());
}

////////////////////////////////////////////////////////////////////////////////
// Finally test config interactive mode. i.e. the parser.
////////////////////////////////////////////////////////////////////////////////

/* Test state transistions */

/* Test Port Commands */
TEST_F(CommonTest, Commands) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    
    PortAgentConfig config(argc, argv);

    // Test a single line parse
    EXPECT_TRUE(config.parse("help"));
    
    // Test a multiline parse
    ostringstream commands;
    commands << "verbose\n";
    commands << "save_config\n";
    commands << "get_config\n";
    commands << "get_state\n";
    commands << "ping\n";
    commands << "break\n";
    commands << "shutdown\n";
    
    EXPECT_TRUE(config.parse(commands.str()));
    
    EXPECT_EQ(config.getCommand(), CMD_HELP);
    EXPECT_EQ(config.getCommand(), CMD_SAVE_CONFIG);
    EXPECT_EQ(config.getCommand(), CMD_GET_CONFIG);
    EXPECT_EQ(config.getCommand(), CMD_GET_STATE);
    EXPECT_EQ(config.getCommand(), CMD_PING);
    EXPECT_EQ(config.getCommand(), CMD_BREAK);
    EXPECT_EQ(config.getCommand(), CMD_SHUTDOWN);
}
        
/* Test setting instrument connection type */
TEST_F(CommonTest, SetInstrumentConnectionType) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    
    PortAgentConfig config(argc, argv);
    
    // Check the default value (UNKNOWN)
    EXPECT_FALSE(config.instrumentConnectionType());
    
    // TCP Connection
    EXPECT_TRUE(config.parse("instrument_type tcp"));
    EXPECT_EQ(config.instrumentConnectionType(), TYPE_TCP);
    
    // Serial Connection
    EXPECT_TRUE(config.parse("instrument_type serial"));
    EXPECT_EQ(config.instrumentConnectionType(), TYPE_SERIAL);
    
    // RSN Connection
    EXPECT_TRUE(config.parse("instrument_type rsn"));
    EXPECT_EQ(config.instrumentConnectionType(), TYPE_RSN);
    
    // No parameter
    EXPECT_FALSE(config.parse("instrument_type"));
    EXPECT_FALSE(config.instrumentConnectionType());
    
    // trailing white space
    EXPECT_FALSE(config.parse("instrument_type "));
    EXPECT_FALSE(config.instrumentConnectionType());
    
    // bad parameter Connection
    EXPECT_FALSE(config.parse("instrument_type blah"));
    EXPECT_FALSE(config.instrumentConnectionType());
    
    // extra parameter Connection
    EXPECT_FALSE(config.parse("instrument_type rsn foo"));
    EXPECT_FALSE(config.instrumentConnectionType());
}

/* Test setting the sentinle sequence */
TEST_F(CommonTest, SetSentinleSequence) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_FALSE(config.sentinleSequence().length());
    
    EXPECT_TRUE(config.parse("sentinle 'ab'"));
    EXPECT_EQ(config.sentinleSequence(), "ab");
    
    EXPECT_TRUE(config.parse("sentinle '\\n\\r'"));
    buffer = config.sentinleSequence().c_str();
    EXPECT_EQ(buffer[0], 10);
    EXPECT_EQ(buffer[1], 13);
    EXPECT_EQ(buffer[2], 0);
    
    EXPECT_TRUE(config.parse("sentinle '\\n\\'"));
    buffer = config.sentinleSequence().c_str();
    EXPECT_EQ(buffer[0], 10);
    EXPECT_EQ(buffer[1], '\\');
    EXPECT_EQ(buffer[2], 0);
    
    EXPECT_TRUE(config.parse("sentinle '\\n"));
    buffer = config.sentinleSequence().c_str();
    EXPECT_EQ(buffer[0], 10);
    EXPECT_EQ(buffer[1], 0);
    
    EXPECT_TRUE(config.parse("sentinle "));
    buffer = config.sentinleSequence().c_str();
    EXPECT_EQ(buffer[0], 0);
}

/* Test setting the output throttle parametere */
TEST_F(CommonTest, SetOutputThrottle) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_FALSE(config.outputThrottle());
    
    EXPECT_TRUE(config.parse("output_throttle 1"));
    EXPECT_EQ(config.outputThrottle(), 1);
    
    EXPECT_FALSE(config.parse("output_throttle -11"));
    EXPECT_EQ(config.outputThrottle(), 0);
    
    EXPECT_FALSE(config.parse("output_throttle ab"));
    EXPECT_EQ(config.outputThrottle(), 0);
    
    EXPECT_FALSE(config.parse("output_throttle"));
    EXPECT_EQ(config.outputThrottle(), 0);
    
    EXPECT_FALSE(config.parse("output_throttle "));
    EXPECT_EQ(config.outputThrottle(), 0);
}


/* Test setting the max packet size parameter */
TEST_F(CommonTest, SetMaxPacketSize) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("max_packet_size 1"));
    EXPECT_EQ(config.maxPacketSize(), 1);
        
    EXPECT_FALSE(config.parse("max_packet_size 0"));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("max_packet_size 65472"));
    EXPECT_EQ(config.maxPacketSize(), 65472);
    
    EXPECT_FALSE(config.parse("max_packet_size 65473"));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_FALSE(config.parse("max_packet_size -11"));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_FALSE(config.parse("max_packet_size ab"));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_FALSE(config.parse("max_packet_size"));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_FALSE(config.parse("max_packet_size "));
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
}

/* Test setting the observatory data port parameter */
TEST_F(CommonTest, SetObservatoryDataPort) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("data_port 1"));
    EXPECT_EQ(config.observatoryDataPort(), 1);
        
    EXPECT_TRUE(config.parse("data_port 65535"));
    EXPECT_EQ(config.observatoryDataPort(), 65535);
    
    EXPECT_FALSE(config.parse("data_port 65536"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port 0"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port 65537"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port -11"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port ab"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port"));
    EXPECT_EQ(config.observatoryDataPort(), 0);
    
    EXPECT_FALSE(config.parse("data_port "));
    EXPECT_EQ(config.observatoryDataPort(), 0);
}

/* Test setting the observatory command port parameter */
TEST_F(CommonTest, SetObservatoryCommandPort) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("command_port 1"));
    EXPECT_EQ(config.observatoryCommandPort(), 1);
        
    EXPECT_TRUE(config.parse("command_port 65535"));
    EXPECT_EQ(config.observatoryCommandPort(), 65535);
    
    EXPECT_FALSE(config.parse("command_port 65536"));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("command_port 0"));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("command_port -11"));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("command_port ab"));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("command_port"));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("command_port "));
    EXPECT_EQ(config.observatoryCommandPort(), 0);
}

/* Test setting the instrument command port parameter */
TEST_F(CommonTest, SetInstrumentCommandPort) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("instrument_command_port 1"));
    EXPECT_EQ(config.instrumentCommandPort(), 1);
        
    EXPECT_TRUE(config.parse("instrument_command_port 65535"));
    EXPECT_EQ(config.instrumentCommandPort(), 65535);
    
    EXPECT_FALSE(config.parse("instrument_command_port 65536"));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_command_port 0"));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_command_port -11"));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_command_port ab"));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_command_port"));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_command_port "));
    EXPECT_EQ(config.instrumentCommandPort(), 0);
}

/* Test setting the instrument data port parameter */
TEST_F(CommonTest, SetInstrumentDataPort) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.maxPacketSize(), DEFAULT_PACKET_SIZE);
    
    EXPECT_TRUE(config.parse("instrument_data_port 1"));
    EXPECT_EQ(config.instrumentDataPort(), 1);
        
    EXPECT_TRUE(config.parse("instrument_data_port 65535"));
    EXPECT_EQ(config.instrumentDataPort(), 65535);
    
    EXPECT_FALSE(config.parse("instrument_data_port 65536"));
    EXPECT_EQ(config.instrumentDataPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_data_port 0"));
    EXPECT_EQ(config.instrumentDataPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_data_port -11"));
    EXPECT_EQ(config.instrumentDataPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_data_port ab"));
    EXPECT_EQ(config.instrumentDataPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_data_port"));
    EXPECT_EQ(config.instrumentDataPort(), 0);
    
    EXPECT_FALSE(config.parse("instrument_data_port "));
    EXPECT_EQ(config.instrumentDataPort(), 0);
}

/* Test setting the log level */
TEST_F(CommonTest, SetLogLevel) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    string current = Logger::Instance()->levelToString(Logger::GetLogLevel());
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_TRUE(config.parse("log_level error"));
    EXPECT_EQ(Logger::GetLogLevel(), ERROR);
    
    EXPECT_TRUE(config.parse("log_level warn"));
    EXPECT_EQ(Logger::GetLogLevel(), WARNING);
    
    EXPECT_TRUE(config.parse("log_level info"));
    EXPECT_EQ(Logger::GetLogLevel(), INFO);
    
    EXPECT_TRUE(config.parse("log_level debug"));
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG);
    
    EXPECT_TRUE(config.parse("log_level mesg"));
    EXPECT_EQ(Logger::GetLogLevel(), MESG);
    
    Logger::SetLogLevel(current);
}

/* Test setting the dirs */
TEST_F(CommonTest, SetDirs) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_TRUE(config.parse("log_dir /tmp"));
    EXPECT_EQ(config.logdir(), "/tmp");

    EXPECT_TRUE(config.parse("data_dir /tmp"));
    EXPECT_EQ(config.logdir(), "/tmp");

    EXPECT_TRUE(config.parse("conf_dir /tmp"));
    EXPECT_EQ(config.logdir(), "/tmp");

    EXPECT_TRUE(config.parse("pid_dir /tmp"));
    EXPECT_EQ(config.logdir(), "/tmp");
}

/* Test baud parameter */
TEST_F(CommonTest, SetBaud) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_FALSE(config.baud());
    
    EXPECT_TRUE(config.parse("baud 1200"));
    EXPECT_EQ(config.baud(), 1200);
    
    EXPECT_TRUE(config.parse("baud 2400"));
    EXPECT_EQ(config.baud(), 2400);
    
    EXPECT_TRUE(config.parse("baud 4800"));
    EXPECT_EQ(config.baud(), 4800);
    
    EXPECT_TRUE(config.parse("baud 9600"));
    EXPECT_EQ(config.baud(), 9600);
    
    EXPECT_TRUE(config.parse("baud 19200"));
    EXPECT_EQ(config.baud(), 19200);
    
    EXPECT_TRUE(config.parse("baud 38400"));
    EXPECT_EQ(config.baud(), 38400);
    
    EXPECT_TRUE(config.parse("baud 57600"));
    EXPECT_EQ(config.baud(), 57600);
    
    EXPECT_TRUE(config.parse("baud 115200"));
    EXPECT_EQ(config.baud(), 115200);
    
    EXPECT_FALSE(config.parse("baud 300"));
    EXPECT_EQ(config.baud(), 0);
    
    EXPECT_FALSE(config.parse("baud "));
    EXPECT_EQ(config.baud(), 0);
}

/* Test stopbit parameter */
TEST_F(CommonTest, SetStopbits) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.stopbits(), 1);
    
    EXPECT_TRUE(config.parse("stopbits 1"));
    EXPECT_EQ(config.stopbits(), 1);
    
    EXPECT_TRUE(config.parse("stopbits 2"));
    EXPECT_EQ(config.stopbits(), 2);
    
    EXPECT_FALSE(config.parse("stopbits 0"));
    EXPECT_EQ(config.stopbits(), 1);
    
    EXPECT_FALSE(config.parse("stopbits "));
    EXPECT_EQ(config.stopbits(), 1);
}

/* Test databits parameter */
TEST_F(CommonTest, SetDatabits) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.databits(), 8);
    
    EXPECT_TRUE(config.parse("databits 5"));
    EXPECT_EQ(config.databits(), 5);
    
    EXPECT_TRUE(config.parse("databits 6"));
    EXPECT_EQ(config.databits(), 6);
    
    EXPECT_TRUE(config.parse("databits 7"));
    EXPECT_EQ(config.databits(), 7);
    
    EXPECT_TRUE(config.parse("databits 8"));
    EXPECT_EQ(config.databits(), 8);
    
    EXPECT_FALSE(config.parse("databits 0"));
    EXPECT_EQ(config.databits(), 8);
    
    EXPECT_FALSE(config.parse("databits "));
    EXPECT_EQ(config.databits(), 8);
}

/* Test parity parameter */
TEST_F(CommonTest, SetParity) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.parity(), 0);
    
    EXPECT_TRUE(config.parse("parity 0"));
    EXPECT_EQ(config.parity(), 0);
    
    EXPECT_TRUE(config.parse("parity 1"));
    EXPECT_EQ(config.parity(), 1);
    
    EXPECT_TRUE(config.parse("parity 2"));
    EXPECT_EQ(config.parity(), 2);
    
    EXPECT_FALSE(config.parse("parity 3"));
    EXPECT_EQ(config.parity(), 0);
    
    EXPECT_FALSE(config.parse("parity "));
    EXPECT_EQ(config.parity(), 0);
}

/* Test flow control parameter */
TEST_F(CommonTest, SetFlowControl) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_EQ(config.flow(), 0);
    
    EXPECT_TRUE(config.parse("flow 0"));
    EXPECT_EQ(config.flow(), 0);
    
    EXPECT_TRUE(config.parse("flow 1"));
    EXPECT_EQ(config.flow(), 1);
    
    EXPECT_TRUE(config.parse("flow 2"));
    EXPECT_EQ(config.flow(), 2);
    
    EXPECT_FALSE(config.parse("flow 3"));
    EXPECT_EQ(config.flow(), 0);
    
    EXPECT_FALSE(config.parse("flow "));
    EXPECT_EQ(config.flow(), 0);
}

/* Test Unknown Command */
TEST_F(CommonTest, UnknownCommand) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    const char* buffer;
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_FALSE(config.parse("failure 0"));
}


////////////////////////////////////////////////////////////////////////////////
// Test reading configurations from a file
////////////////////////////////////////////////////////////////////////////////

/* Test config dump */
TEST_F(CommonTest, ConfigDump) {
    char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    
    PortAgentConfig config(argc, argv);
    
    EXPECT_TRUE(config.parse("sentinle '\\n\\r'"));
    EXPECT_TRUE(config.parse("instrument_type tcp"));
    EXPECT_TRUE(config.parse("instrument_addr 127.0.0.1"));
    EXPECT_TRUE(config.parse("instrument_data_port 1270"));
    
    string cfg = config.getConfig();
    LOG(DEBUG) << "Config Dump:\n" << cfg;
}

/* Test config save to file */
TEST_F(CommonTest, ReadConfig) {
    try {
        char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
        int argc = sizeof(argv) / sizeof(char*);
    
        PortAgentConfig config(argc, argv);
    
        EXPECT_TRUE(config.parse("sentinle '\\n\\r'"));
        EXPECT_TRUE(config.parse("instrument_type tcp"));
        EXPECT_TRUE(config.parse("instrument_addr 127.0.0.1"));
        EXPECT_TRUE(config.parse("instrument_data_port 1270"));
    
        string cfg = config.getConfig();
        LOG(DEBUG) << "Config Dump:\n" << cfg;
    
        create_file(CONFIG_PATH, cfg.c_str());
    
        char* newARGV[] = { "port_agent_config_test", "-c", CONFIG_PATH };
        argc = sizeof(argv) / sizeof(char*);
        
        PortAgentConfig newConfig(argc, newARGV);
        
        EXPECT_EQ(newConfig.instrumentConnectionType(), TYPE_TCP);
    }
    catch(ParameterRequired &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        ASSERT_FALSE(true);
    }
    
    remove_file(CONFIG_PATH);
}

/* Test config file with non-existant file */
TEST_F(CommonTest, ReadConfigNoFile) {
    bool exceptionRaised = false;
    
    try {
        char* argv[] = { "port_agent_config_test", "-c", "/tmp/blow_up_no_file" };
        int argc = sizeof(argv) / sizeof(char*);
    
        PortAgentConfig config(argc, argv);
    }
    catch(FileIOException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        exceptionRaised = true;
    }
    
    EXPECT_TRUE(exceptionRaised);
}
    

/* Test config file override from command line */
TEST_F(CommonTest, ReadConfigCMDOverload) {
    try {
        char* argv[] = { "port_agent_config_test", "-c", CONFIG_PATH, "-p", "4001" };
        int argc = sizeof(argv) / sizeof(char*);
        ostringstream cfg;
        
        remove_file(CONFIG_PATH);
    
        cfg << "command_port " << 4000;
        create_file(CONFIG_PATH, cfg.str().c_str());
        
        PortAgentConfig config(argc, argv);
    
        EXPECT_EQ(config.observatoryCommandPort(), 4001);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        ASSERT_FALSE(true);
    }
    
    remove_file(CONFIG_PATH);
}

/* Test config load from file without command port*/
TEST_F(CommonTest, ReadConfigWithoutPort) {
    bool exceptionRaised = false;
    
    try {
        char* argv[] = { "port_agent_config_test", "-c", CONFIG_PATH };
        int argc = sizeof(argv) / sizeof(char*);
        ostringstream cfg;
    
        remove_file(CONFIG_PATH);

        cfg << "instrument_type tcp";
        create_file(CONFIG_PATH, cfg.str().c_str());
        
        PortAgentConfig config(argc, argv);
    }
    catch(ParameterRequired &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        exceptionRaised = true;
    }
        
    ASSERT_TRUE(exceptionRaised);
    
    remove_file(CONFIG_PATH);
}

/* Test isConfigured method */
TEST_F(CommonTest, IsConfiguredRSN) {
    try {
        char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
        int argc = sizeof(argv) / sizeof(char*);
        ostringstream cfg;
        
        PortAgentConfig config(argc, argv);
        
        EXPECT_TRUE(config.parse("instrument_type rsn"));
        EXPECT_TRUE(config.parse("data_port 4000"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_addr 127.0.0.1"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_command_port 1271"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_data_port 1270"));
        
        EXPECT_TRUE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_type serial"));
        EXPECT_FALSE(config.isConfigured());
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        ASSERT_FALSE(true);
    }
}

/* Test isConfigured method */
TEST_F(CommonTest, IsConfiguredTCP) {
    try {
        char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
        int argc = sizeof(argv) / sizeof(char*);
        ostringstream cfg;
        
        PortAgentConfig config(argc, argv);
        
        EXPECT_TRUE(config.parse("instrument_type tcp"));
        EXPECT_TRUE(config.parse("data_port 4000"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_addr 127.0.0.1"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_data_port 1270"));
        
        EXPECT_TRUE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_type rsn"));
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_command_port 1271"));
        EXPECT_TRUE(config.isConfigured());
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        ASSERT_FALSE(true);
    }
}

/* Test isConfigured method */
TEST_F(CommonTest, IsConfiguredSerial) {
    try {
        char* argv[] = { "port_agent_config_test", "-p", TEST_PORT };
        int argc = sizeof(argv) / sizeof(char*);
        ostringstream cfg;
        
        PortAgentConfig config(argc, argv);
        
        EXPECT_TRUE(config.parse("instrument_type serial"));
        EXPECT_TRUE(config.parse("data_port 4000"));
        
        EXPECT_FALSE(config.isConfigured());
        EXPECT_TRUE(config.parse("baud 2400"));
        
        EXPECT_TRUE(config.isConfigured());
        EXPECT_TRUE(config.parse("instrument_type tcp"));
        EXPECT_FALSE(config.isConfigured());
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
        ASSERT_FALSE(true);
    }
}

