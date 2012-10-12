#include "common/exception.h"
#include "common/timestamp.h"
#include "common/logger.h"
#include "common/spawn_process.h"
#include "common/util.h"
#include "network/udp_comm_socket.h"
#include "gtest/gtest.h"

#include <string>
#include <string.h>
#include <netinet/in.h>
#include <netdb.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/fcntl.h>
#include <stdio.h>
#include <stdlib.h>

using namespace logger;
using namespace network;

const uint16_t TEST_PORT=40001;
const char* TEST_HOST="localhost";
const char* BAD_HOST="this_is_a_bad_hostname_I_hope";
const int BAD_PORT=0;
const int PRIV_PORT=9;

const char* TEST_LOG="/tmp/gtest.log";
const char* FILE_LOG="/tmp/gtest.out";
const char* DATA_FILE="/tmp/gtest.dat";
const char* LOG_LEVEL="DEBUG3";

const char* TEST_DATA="Test";
const char* WRITE_DELAY="1";

class UDPSocketTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile(TEST_LOG);
            Logger::SetLogLevel(LOG_LEVEL);
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         UDP Comm Socket Test Start Up";
            LOG(INFO) << "************************************************";
	    
	    remove_file(DATA_FILE);
	    remove_file(FILE_LOG);
        }

        void TearDown() {
	    LOG(INFO) << "Tear down test";
	    
	    processWait();
	    
	    remove_file(DATA_FILE);
	    remove_file(FILE_LOG);
        }
	
	// Wait for the external process to complete
	void processWait() {
	    bool running = m_oProcess.is_running();
	    
	    while(m_oProcess.is_running()) {
		LOG(DEBUG) << "Waiting for client to die.";
		sleep(1);
	    }
	    LOG(DEBUG) << "echo client process complete.";
	    
	    if(running) {
	        LOG(DEBUG) << "Process Output: " << read_file(FILE_LOG);
	        LOG(DEBUG) << "Test File Output: " << read_file(DATA_FILE);
	    }
	}

        bool startUDPClientDump(uint16_t port) {
            stringstream cmd;
	    LOG(DEBUG) << "Start echo client";
	    LOG(DEBUG2) << "Tools dir: " << TOOLSDIR;
	    
            cmd << TOOLSDIR << "/udp_client_dump.py";
            stringstream portStr;
            portStr << port;

            // Start the echo client with a 1 second connection delay
	    SpawnProcess process(cmd.str(), 4,
				 "-p", portStr.str().c_str(), 
				 "-f", DATA_FILE );

            LOG(INFO) << "Start UDP Echo Dump: " << process.cmd_as_string();
            if(FILE_LOG) {
                LOG(DEBUG) << "Setting log file: " << FILE_LOG;
	        process.set_output_file(FILE_LOG);
            }
	
            bool result = process.run();
        
	    m_oProcess = process;
	    
	    // Give the program time to bring the socket up.
	    sleep(1);
	    
	    return process.is_running();
	}
	
	void zeroBuffer(char *buf, int size) {
	    for(int i = 0; i < size; i++) {
		buf[i] = 0;
	    }
	}
	
	protected:
	    SpawnProcess m_oProcess;

};

/*
 * Test the basic blocking socket to a random port
 *   - Start the udp dump server
 *   - Then write something to the client
 *   - check the data file to see what was read
*/
TEST_F(UDPSocketTest, BlockingConnection) {
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	int bytesRead, bytesWritten;
	UDPCommSocket socket;
	
	// Start the UDP server
	ASSERT_TRUE(startUDPClientDump(TEST_PORT));
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(TEST_PORT);
	socket.setHostname(TEST_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	// Make sure we are blocking
	int opts = fcntl(socket.getSocketFD(),F_GETFL);
	ASSERT_GT(opts, 0);
	LOG(DEBUG) << "fd: " << hex << socket.getSocketFD() << " "
	           << "sock opts: " << hex << opts << " "
	           << "non block flag: " << hex << O_NONBLOCK;
        ASSERT_FALSE(opts & O_NONBLOCK);
		
	bytesWritten = socket.writeData(expectedData.c_str(), expectedData.length());
	EXPECT_EQ(bytesWritten, 4);
	
	processWait();
	
	//Read Data file
	EXPECT_EQ(read_file(DATA_FILE), expectedData);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/* test read, should boom */
// We didn't implment reading for UDP connections so a read should blow up.
TEST_F(UDPSocketTest, ReadFailure) {
    bool exceptionRaised = false;
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	UDPCommSocket socket;
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(TEST_PORT);
	socket.setHostname(TEST_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	socket.readData(buffer, 128);
    }
    catch(NotImplemented &e) {
	exceptionRaised = true;
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test with no UDP server up */
/*
 * Since this is UDP we don't really care if anyone is actually
 * listening to what we are saying so this write call should
 * work just fine
*/
TEST_F(UDPSocketTest, NoEndPoint) {
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	int bytesRead, bytesWritten;
	UDPCommSocket socket;
	
	// Don't start the UDP server
	//ASSERT_TRUE(startUDPClientDump(TEST_PORT));
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(TEST_PORT);
	socket.setHostname(TEST_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	// Make sure we are blocking
	int opts = fcntl(socket.getSocketFD(),F_GETFL);
	ASSERT_GT(opts, 0);
	LOG(DEBUG) << "fd: " << hex << socket.getSocketFD() << " "
	           << "sock opts: " << hex << opts << " "
	           << "non block flag: " << hex << O_NONBLOCK;
        ASSERT_FALSE(opts & O_NONBLOCK);
		
	bytesWritten = socket.writeData(expectedData.c_str(), expectedData.length());
	EXPECT_EQ(bytesWritten, 4);
	
	processWait();
	
	//Read Data file
	EXPECT_NE(read_file(DATA_FILE), expectedData);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/* test with no hostname */
TEST_F(UDPSocketTest, MissingHost) {
    bool exceptionRaised = false;
    try {
        Timestamp ts;
	UDPCommSocket socket;
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(TEST_PORT);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	socket.writeData("Test", 4);
    }
    catch(SocketMissingConfig &e) {
	exceptionRaised = true;
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test with no port */
TEST_F(UDPSocketTest, MissingPort) {
    bool exceptionRaised = false;
    try {
        Timestamp ts;
	UDPCommSocket socket;
	
	// Configure the client
	socket.setBlocking(true);
	socket.setHostname(TEST_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	socket.writeData("Test", 4);
    }
    catch(SocketMissingConfig &e) {
	exceptionRaised = true;
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test with bad hostname */
TEST_F(UDPSocketTest, BadHost) {
    bool exceptionRaised = false;
    try {
        Timestamp ts;
	UDPCommSocket socket;
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(TEST_PORT);
	socket.setHostname(BAD_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	socket.writeData("Test", 4);
    }
    catch(SocketHostFailure &e) {
	exceptionRaised = true;
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test with bad port */
TEST_F(UDPSocketTest, BadPort) {
    bool exceptionRaised = false;
    try {
        Timestamp ts;
	UDPCommSocket socket;
	
	// Configure the client
	socket.setBlocking(true);
	socket.setPort(0);
	socket.setHostname(BAD_HOST);
        
	socket.initialize();
	ASSERT_TRUE(socket.connected());
	
	socket.writeData("Test", 4);
    }
    catch(SocketMissingConfig &e) {
	exceptionRaised = true;
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
    }
    
    EXPECT_TRUE(exceptionRaised);
}