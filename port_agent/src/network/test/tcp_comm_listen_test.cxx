#include "common/exception.h"
#include "common/timestamp.h"
#include "common/logger.h"
#include "common/spawn_process.h"
#include "network/tcp_comm_listener.h"
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
const char* LOG_LEVEL="DEBUG3";

const char* TEST_DATA="Test";
const char* WRITE_DELAY="1";

class TCPListenerTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile(TEST_LOG);
            Logger::SetLogLevel(LOG_LEVEL);
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         TCP Comm Listener Test Start Up";
            LOG(INFO) << "************************************************";
        }

        void TearDown() {
	    LOG(INFO) << "Tear down test";
	    
	    while(m_oProcess.is_running()) {
		LOG(DEBUG) << "Waiting for client to die.";
		sleep(1);
	    }
	    
	    LOG(DEBUG) << "echo client process complete.";
        }

        void startTCPEchoClient(uint16_t port, uint16_t connectDelay,
				uint16_t writeDelay, uint16_t readDelay,
				const char *testData) {
            stringstream cmd;
	    LOG(DEBUG) << "Start echo client";
	    LOG(DEBUG2) << "Tools dir: " << TOOLSDIR;
	    
            cmd << TOOLSDIR << "/tcp_client_echo.py";
            stringstream portStr;
            portStr << port;
            
	    stringstream delayStr;
            delayStr << connectDelay;

	    stringstream writeDelayStr;
            writeDelayStr << connectDelay;

	    stringstream readDelayStr;
            readDelayStr << connectDelay;

            // Start the echo client with a 1 second connection delay
	    SpawnProcess process(cmd.str(), 10,
				 "-p", portStr.str().c_str(), 
				 "-t", delayStr.str().c_str(),
				 "-d", testData,
				 "-w", writeDelayStr.str().c_str(),
				 "-r", readDelayStr.str().c_str() ); 

            LOG(INFO) << "Start TCP Echo Client: " << process.cmd_as_string();
            if(FILE_LOG) {
                LOG(DEBUG) << "Setting log file: " << FILE_LOG;
	        process.set_output_file(FILE_LOG);
            }
	
            bool result = process.run();
        
	    m_oProcess = process;
	}
	
	void zeroBuffer(char *buf, int size) {
	    for(int i = 0; i < size; i++) {
		buf[i] = 0;
	    }
	}
	
	protected:
	    SpawnProcess m_oProcess;

};

TEST_F(TCPListenerTest, TestCopy) {
	TCPCommListener server;
	server.setBlocking(true);
	
	CommBase *copy = server.copy();
	
	ASSERT_NE(copy, &server);
}

/*
 * Test the basic blocking listener to a random port
 *   - Start the server and listen on a random port.
 *   - Accept a client connection.  This is a blocking
 *     request so there should be a delay
 *   - Then read what the client sent and send it
 *     back to the calling client.
*/
TEST_F(TCPListenerTest, BlockingConnection) {
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	int bytesRead, bytesWritten;
	
	TCPCommListener server;
	server.setBlocking(true);
        
	server.initialize();
	
	EXPECT_LT(ts.elapseTime(), 0.01);
	
	// Ensure we have a good port
	ASSERT_GT(server.getListenPort(), 0);
	
	// Start the tcp echo client with a delay.
	startTCPEchoClient(server.getListenPort(), 1, 0, 0, TEST_DATA);
	
	// Accept a connection.  Should be a delay because the echo
	// client is configured to delay the connection and this is
	// a blocking request.
	server.acceptClient();
	EXPECT_GT(ts.elapseTime(), 1);
	
	zeroBuffer(buffer, 128);
	bytesRead = server.readData(buffer, 128);
	EXPECT_EQ(bytesRead, expectedData.length());
	EXPECT_EQ(expectedData, buffer);
	
	bytesWritten = server.writeData(buffer, bytesRead);
	EXPECT_EQ(bytesRead, bytesWritten);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/* Test call to a blocking staticly assigned port.
 * This is much like the previous test except we will assign a port.
 * It should throw an exception if it couldn't bind to that port.
*/
TEST_F(TCPListenerTest, BlockingStaticConnection) {
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	int bytesRead, bytesWritten;
	
	TCPCommListener server;
	server.setBlocking(true);
	
	// Set the port
	server.setPort(TEST_PORT);
        
	server.initialize();
	
	EXPECT_LT(ts.elapseTime(), 0.01);
	
	// Ensure we have a good port
	ASSERT_GT(server.getListenPort(), 0);
	EXPECT_EQ(TEST_PORT, server.getListenPort());
	
	// Start the tcp echo client with a delay.
	startTCPEchoClient(server.getListenPort(), 1, 0, 0, TEST_DATA);
	
	// Accept a connection.  Should be a delay because the echo
	// client is configured to delay the connection and this is
	// a blocking request.
	server.acceptClient();
	EXPECT_GT(ts.elapseTime(), 1);
	
	zeroBuffer(buffer, 128);
	bytesRead = server.readData(buffer, 128);
	EXPECT_EQ(bytesRead, expectedData.length());
	EXPECT_EQ(expectedData, buffer);
	
	bytesWritten = server.writeData(buffer, bytesRead);
	EXPECT_EQ(bytesRead, bytesWritten);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/* Test the non blocking listener */
/* Like the first test, but using a non-blocking connection. So we will still
 * use the client delay, but we should see it pass by the client accept
 * connections the first time.  Then sleep and try again.
 *
 * NOTE: We need to test that both the server FD and client FD are non-blocking.
 * 
 * This wouldn't be the best way to implement a non-blocking server, see the
 * next test using select.
*/
TEST_F(TCPListenerTest, BlockingNonBlockingConnection) {
    try {
        Timestamp ts;
	char buffer[128];
	string expectedData = TEST_DATA;
	int bytesRead, bytesWritten;
	
	// Default is bind to a random port and non-blocking.
	TCPCommListener server;
	
	// Initialize the server
	server.initialize();
	
	EXPECT_LT(ts.elapseTime(), 0.01);
	
	// Ensure we have a good port
	ASSERT_GT(server.getListenPort(), 0);
	
	// Start the tcp echo client with a delay.
	startTCPEchoClient(server.getListenPort(), 1, 1, 1, TEST_DATA);
	
	// Accept a connection.  This should e a non-blocking call now. 
	// The client is delaying the connection so this call should return false
	// and there should be minimal delay.
	EXPECT_FALSE(server.acceptClient());
	EXPECT_LT(ts.elapseTime(), 0.01);
	
	// Watch for connections
	while(true) {
	    // try to bind client, but timeout after 5 seconds.
	    if(server.acceptClient() || ts.elapseTime() > 5)
	        break;
	    
	    sleep(1);
	}
	ASSERT_TRUE(server.connected());
    
        LOG(DEBUG) << "Connected.  Now try to read from the client";
	
	// Test a non-blocking read.  We've told the client to delay the write
	// so the first read should not block and should have read nothing.
	ts.setNow();
	zeroBuffer(buffer, 128);
	bytesRead = server.readData(buffer, 128);
	ASSERT_EQ(bytesRead, 0);
	EXPECT_LT(ts.elapseTime(), 0.01);
        
	LOG(DEBUG2) << "First read returned nothing as expected.  Woot!";
	
	// Now lets try to read until we see something.
	while(true) {
	    bytesRead = server.readData(buffer, 128);
	    
	    // timeout after 5 seconds
	    if(bytesRead > 0 || ts.elapseTime() > 5)
	        break;
	    
	    sleep(1);
	}
	EXPECT_EQ(bytesRead, expectedData.length());
	EXPECT_EQ(expectedData, buffer);
	
	
	// Test a non-blocking write
	ts.setNow();
	bytesWritten = server.writeData(buffer, bytesRead);
	EXPECT_EQ(bytesRead, bytesWritten);
	EXPECT_LT(ts.elapseTime(), 0.01);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/* Test non-blocking using select */
/* This test is an example of how we would likely use the TCP listener in
 * non-blocking mode.
 * - Initialize the server.
 * - Setup a small select loop to watch the listener FD and the client FD if
 *   it is initialized.
*/
TEST_F(TCPListenerTest, BlockingNonBlockingSelect) {
    try {
        Timestamp ts;
        char buffer[128];
        string expectedData = TEST_DATA;
        int bytesRead = 0;
        int maxFD;
	int readyCount;
	fd_set readFDs;
	int opts;
	
	// Select timeout 0.5 second
        struct timeval tv;
        tv.tv_sec = 1;
        tv.tv_usec = 0;

	
	TCPCommListener server;
	server.initialize();
	
	ASSERT_TRUE(server.listening());
	
	// Start the echo client to send some data
	startTCPEchoClient(server.getListenPort(), 1, 2, 1, TEST_DATA);
	
	LOG(INFO) << "Starting select loop";
        // Sit in a select loop until a client has connected and bytes have
        // been read.
        while(true) {
	    maxFD = server.serverFD() > server.clientFD() ? server.serverFD() : server.clientFD();
	    LOG(DEBUG) << "Initalize FD array";
	    FD_ZERO(&readFDs);
	    
	    if(server.serverFD()) {
		LOG(DEBUG) << "listener FD detected.  Adding to readDFs";
		// Ensure our socket is non-blocking
		opts = fcntl(server.serverFD(),F_GETFL);
	        ASSERT_GT(opts, 0);
		LOG(DEBUG) << "fd: " << hex << server.serverFD() << " "
		           << "sock opts: " << hex << opts << " "
		           << "non block flag: " << hex << O_NONBLOCK;
                ASSERT_TRUE(opts & O_NONBLOCK);
		
		// add the FD to the set
		FD_SET(server.serverFD(), &readFDs);
	    }
	    
	    if(server.clientFD()) {
		LOG(DEBUG) << "client FD detected.  Adding to readDFs";
		
		// Ensure our socket is non-blocking
		opts = fcntl(server.serverFD(),F_GETFL);
	        ASSERT_GT(opts, 0);
		LOG(DEBUG) << "sock opts: " << hex << opts << " "
		           << "non block flag: " << hex << O_NONBLOCK;
                ASSERT_TRUE(opts & O_NONBLOCK);
		
		// add the FD to the set
		FD_SET(server.clientFD(), &readFDs);
	    }
	    
	    LOG(DEBUG) << "Start select process";
	    readyCount = select(maxFD+1, &readFDs, NULL, NULL, &tv);
	    LOG(DEBUG2) << "On select: ready to read on " << readyCount << " connections";
	    
	    if(FD_ISSET(server.serverFD(), &readFDs)) {
		LOG(DEBUG2) << "New client connection detected.";
		server.acceptClient();
		ASSERT_TRUE(server.connected());
	    }
	    
	    if(FD_ISSET(server.clientFD(), &readFDs)) {
		LOG(DEBUG2) << "Client data read to be read";
	        zeroBuffer(buffer, 128);
	        bytesRead = server.readData(buffer, 128);
	    }
    	    
	    // Temination case
            if(bytesRead) {
		LOG(DEBUG) << "We read some bytes: " << bytesRead;
		break;
	    }
	    
	    if(ts.elapseTime() > 5) {
		LOG(ERROR) << "read timeout";
	        break;
	    }
        }
    
        // Check to see that we have actually read data.
	EXPECT_EQ(bytesRead, expectedData.length());
        EXPECT_EQ(expectedData, buffer);
    }
    catch(OOIException &e) {
	string errmsg = e.what();
	LOG(ERROR) << "EXCEPTION: " << errmsg;
	
	// We don't want to see exeptions here.
	ASSERT_FALSE(true);
    }
}

/////////////////////
/* Test Exceptions */
/////////////////////

/* test statically assigned port twice, second should fail */
TEST_F(TCPListenerTest, DoublePortAssignment) {
    bool exceptionRaised = false;
    TCPCommListener server, anotherServer;
    
    server.setPort(TEST_PORT);
    anotherServer.setPort(TEST_PORT);
    
    server.initialize();
    ASSERT_TRUE(server.listening());
    
    try {
        anotherServer.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 304);
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test binding to a priv port (< 1024) */
TEST_F(TCPListenerTest, PrivPortAssignment) {
    bool exceptionRaised = false;
    TCPCommListener server;
    
    try {
        server.setPort(1);
        server.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 304);
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test accept connection, but not initialized  SocketNotInitialized */
TEST_F(TCPListenerTest, NotInitialized) {
    bool exceptionRaised = false;
    TCPCommListener server;
    
    try {
        server.acceptClient();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 310);
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test write on non-initialized server, SocketNotInitialized */
TEST_F(TCPListenerTest, NotInitializedWrite) {
    bool exceptionRaised = false;
    TCPCommListener server;
    
    try {
        server.writeData("Boom", 4);
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 310);
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test write on initialized server, but no client connection, SocketNotConnected */
TEST_F(TCPListenerTest, NotInitializedNotConnectedWrite) {
    bool exceptionRaised = false;
    TCPCommListener server;
    
    try {
        server.initialize();
	ASSERT_TRUE(server.listening());
	
	server.writeData("Boom", 4);
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 308);
    }
    
    EXPECT_TRUE(exceptionRaised);
}


/* test read on non-initialized server, SocketNotInitialized */
TEST_F(TCPListenerTest, NotInitializedRead) {
    bool exceptionRaised = false;
    char buffer[128];
    TCPCommListener server;
    
    try {
        server.readData(buffer, 4);
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 310);
    }
    
    EXPECT_TRUE(exceptionRaised);
}

/* test read on initialized server, but no client connection, SocketNotConnected */
TEST_F(TCPListenerTest, NotInitializedNotConnectedRead) {
    bool exceptionRaised = false;
    char buffer[128];
    TCPCommListener server;
    
    try {
        server.initialize();
	ASSERT_TRUE(server.listening());
	
	server.readData(buffer, 4);
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        //EXPECT_EQ(e.errno(), 308);
    }
    
    EXPECT_TRUE(exceptionRaised);
}