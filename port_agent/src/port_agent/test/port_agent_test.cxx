/*******************************************************************************
 * Filename: port_agent_test.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Unit tests for the port agent class.  Integration tests are in a different
 * file.
 *
 ******************************************************************************/

#include "common/exception.h"
#include "common/logger.h"
#include "common/spawn_process.h"
#include "port_agent/port_agent.h"
#include "gtest/gtest.h"

using namespace logger;
using namespace std;
using namespace port_agent;

#define TEST_PORT "4001"
const char* TEST_LOG="/tmp/gtest.log";
const char* FILE_LOG="/tmp/gtest.out";

class PortAgentUnitTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile(TEST_LOG);
            Logger::SetLogLevel("DEBUG3");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         Port Agent Unit Test Start Up";
            LOG(INFO) << "************************************************";
        }
    
        virtual void TearDown() {
            LOG(INFO) << "Tear down test";
	    
	    while(m_oProcess.is_running()) {
		LOG(DEBUG) << "Waiting for client to die.";
		sleep(1);
	    }
	    
	    LOG(DEBUG) << "echo client process complete.";
        }
    
        ~PortAgentUnitTest() {
            LOG(INFO) << "CommonTest dtor";
        }

        void startTCPEchoServer() {
            stringstream cmd;
            cmd << TOOLSDIR << "/tcp_server_echo.py";
            stringstream portStr;
            portStr << TEST_PORT;

            SpawnProcess process(cmd.str(), 7, "-s", "-p",
				 portStr.str().c_str(), "-t",
				 "1", "-d", "0.1"); 

            LOG(INFO) << "Start TCP Echo Server: " << process.cmd_as_string();
            if(FILE_LOG) {
                LOG(DEBUG) << "Setting log file: " << FILE_LOG;
	        process.set_output_file(FILE_LOG);
            }
	
            bool result = process.run();
            sleep(1);
        
	    m_oProcess = process;
	}
	
        protected:
	    SpawnProcess m_oProcess;
};


/* Basic CTOR test */
TEST_F(PortAgentUnitTest, CTOR) {
    char* argv[] = { "port_agent_test", "-p", TEST_PORT };
    int argc = sizeof(argv) / sizeof(char*);
    stringstream logfile, conffile, pidfile;
    
    PortAgent pa(argc, argv);
}

/* Test the initialization sequence */
TEST_F(PortAgentUnitTest, PortAgentInitialize) {
    try {
        char* argv[] = { "port_agent_test", "-p", TEST_PORT };
        int argc = sizeof(argv) / sizeof(char*);
        stringstream logfile, conffile, pidfile;
        
        PortAgent pa(argc, argv);
        
        EXPECT_EQ(pa.getCurrentState(), STATE_UNCONFIGURED);
        
        // Configure the port agent to work with a TCP instrument
        //pa.handlePortAgentCommand("instrument_type tcp");
        //pa.handlePortAgentCommand("instrument_addr 127.0.0.1");
        //pa.handlePortAgentCommand("instrument_data_port 4000");
        
        // This assumes that there is no instrument listening on the port specified
        // which would leave us in the disconnected state. 
        //EXPECT_EQ(pa.getCurrentState(), STATE_DISCONNECTED);
        
        // Start an tcp listener to simulate the instrument interface, the
        // port agent should automatically connect when available and transition
        // to connected.
        //startTCPEchoServer();
        //EXPECT_EQ(pa.getCurrentState(), STATE_CONNECTED);
    }
    catch(OOIException &e) {
        string msg = e.what();
    	LOG(ERROR) << "Unexepected exception: " << msg;
    }
}

/////////////////////////////////////////////////////////////////////////////////
// Integration Tests
/////////////////////////////////////////////////////////////////////////////////

/* Test startup sequence and failures */
// Successful start should end in the unconfigured state

/* Test TCP port agent */
/* Walk through port agent states */
// Make sure we try disonnect and make config changes to transition to unconfigured

