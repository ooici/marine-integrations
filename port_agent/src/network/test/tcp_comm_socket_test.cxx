#include "common/exception.h"
#include "common/timestamp.h"
#include "common/logger.h"
#include "common/spawn_process.h"
#include "network/tcp_comm_socket.h"
#include "gtest/gtest.h"

#include <string>

using namespace logger;
using namespace network;

const uint16_t TEST_PORT=4000;
const char* TEST_HOST="localhost";
const char* BAD_HOST="this_is_a_bad_hostname_I_hope";
const int BAD_PORT=0;
const int PRIV_PORT=9;

const char* TEST_LOG="/tmp/gtest.log";
const char* FILE_LOG="/tmp/gtest.out";
const char* LOG_LEVEL="DEBUG3";

class TCPSocketTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile(TEST_LOG);
            Logger::SetLogLevel(LOG_LEVEL);
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         TCP Comm Socket Test Start Up";
            LOG(INFO) << "************************************************";
    
            // Start the TCP echo server
           startTCPEchoServer();
           ASSERT_TRUE(m_oProcess.is_running());
        }

        void TearDown() {
	    while(m_oProcess.is_running()) {
		LOG(DEBUG) << "Waiting for server to die.";
		sleep(0.5);
	    }
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
	
	void zeroBuffer(char *buf, int size) {
	    for(int i = 0; i < size; i++) {
		buf[i] = 0;
	    }
	}
	
	protected:
	    SpawnProcess m_oProcess;

};

/* Test the basic blocking connection */
TEST_F(TCPSocketTest, BlockingConnection) {
    string testData = "Test";
    char buffer[128];
    uint16_t writeCount, readCount;
    
    try{
        TCPCommSocket socket;
        socket.setBlocking(true);

        // Configure the socket
        socket.setHostname(TEST_HOST);
        socket.setPort(TEST_PORT);
    
    	// Set connection information
        EXPECT_TRUE(socket.initialize());
        EXPECT_TRUE(socket.connected());

        // Write some data
        writeCount = socket.writeData(testData.c_str(), testData.length());
        EXPECT_EQ(testData.size(), writeCount);

        LOG(DEBUG) << "Bytes written: " << writeCount;
        sleep(1);

        if(writeCount > 0) {
	    zeroBuffer(buffer, 128);
            LOG(DEBUG) << "Reading echo returned";
            readCount = socket.readData(buffer, 128);
            EXPECT_EQ(readCount, 4);
            EXPECT_EQ(testData, buffer);
        }
    
        socket.disconnect();
        EXPECT_FALSE(socket.connected());
    }
    catch(exception &e) {
    	string msg = e.what();
    	LOG(ERROR) << "Unexepected exception: " << msg;

    	// This will cause this test to fail because if we are here msg should never
    	// be an empty string.
    	EXPECT_EQ(msg, "");
    };

}

/* Test the non blocking connection */
TEST_F(TCPSocketTest, NonBlockingConnection) {
    Timestamp ts;
    string testData = "Test";
    char buffer[128];
    uint16_t writeCount, readCount;
    TCPCommSocket socket;

    // Configure the socket
    socket.setHostname(TEST_HOST);
    socket.setPort(TEST_PORT);

    try{
    	// Set connection information
        EXPECT_TRUE(socket.initialize());
        EXPECT_TRUE(socket.connected());

 	    // Write some data
        writeCount = socket.writeData(testData.c_str(), testData.length());
        EXPECT_EQ(testData.size(), writeCount);

        LOG(DEBUG) << "Bytes written: " << writeCount;

        // Try to read after write.  Note the server is doing a delayed
	// ready.
	if(writeCount > 0) {
            LOG(DEBUG) << "Reading echo returned";
            readCount = socket.readData(buffer, 128);
            EXPECT_EQ(readCount, 0);
	    
	    // The echo server does a delayed read.  Non blocking should ignore
	    // this delay.  So our elapse time should be pretty small.
	    EXPECT_LT(ts.elapseTime(), 0.01);
        }

	// Wait for the server to complete read
	sleep(1);
	
        // Try to read after write.  Note the server is doing a delayed
	// ready.
	if(writeCount > 0) {
            LOG(DEBUG) << "Reading echo returned";
	    zeroBuffer(buffer, 128);
            readCount = socket.readData(buffer, 128);
            EXPECT_EQ(readCount, 4);
            EXPECT_EQ(testData, buffer);
        }
	
    }
    catch(exception &e) {
    	string msg = e.what();
    	LOG(ERROR) << "Unexepected exception: " << msg;

    	// This will cause this test to fail because if we are here msg should never
    	// be an empty string.
    	EXPECT_EQ(msg, "");
    };

    socket.disconnect();
    EXPECT_FALSE(socket.connected());
}

/////////////////////
/* Test Exceptions */
/////////////////////
/* Test missing command */
TEST_F(TCPSocketTest, ExceptionNotConfigured) {
    bool exceptionRaised = false;
    TCPCommSocket noHost, noPort, noConfig;
    
    // First test an initialize with no configuration
    try {
        exceptionRaised = false;
        noConfig.initialize();
    }
    catch(SocketMissingConfig &e) {
        exceptionRaised = true;
        LOG(INFO) << "Expected exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 307);
    };
    
    EXPECT_TRUE(exceptionRaised);
    
    // Now test with a missing port
    try {
        exceptionRaised = false;
	noPort.setHostname(TEST_HOST);
        noPort.initialize();
    }
    catch(SocketMissingConfig &e) {
        exceptionRaised = true;
        LOG(INFO) << "Expected exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 307);
    };
    EXPECT_TRUE(exceptionRaised);
    
    // finally test with a missing host
    try {
        exceptionRaised = false;
	noHost.setPort(TEST_PORT);
        noHost.initialize();
    }
    catch(SocketMissingConfig &e) {
        exceptionRaised = true;
        LOG(INFO) << "Expected exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 307);
    };
    EXPECT_TRUE(exceptionRaised);
    
}

/* Test connection to a bad host name */
TEST_F(TCPSocketTest, ExceptionBadHost) {
    bool exceptionRaised = false;
    TCPCommSocket badHost;
    
    // Test connecting to a bad hostname
    try {
        exceptionRaised = false;
	badHost.setHostname(BAD_HOST);
	badHost.setPort(TEST_PORT);
        badHost.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 303);
    };
    
    EXPECT_TRUE(exceptionRaised);
}
    
/* Test connection to a bad port */
TEST_F(TCPSocketTest, ExceptionBadPort) {
    bool exceptionRaised = false;
    TCPCommSocket socket;
    
    // Test connecting to a bad hostname
    try {
        exceptionRaised = false;
	socket.setHostname(TEST_HOST);
	socket.setPort(BAD_PORT);
        socket.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 307);
    };
    
    EXPECT_TRUE(exceptionRaised);
}

/* Test connection to a priv blocking port */
TEST_F(TCPSocketTest, ExceptionPrivPortBlocking) {
    bool exceptionRaised = false;
    TCPCommSocket socket;
    
    // Test connecting to a bad hostname
    try {
	socket.setBlocking(true);
	socket.setHostname(TEST_HOST);
	socket.setPort(PRIV_PORT);
        socket.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 304);
    };

    EXPECT_TRUE(exceptionRaised);
}

/* Test connection to a priv port */
TEST_F(TCPSocketTest, ExceptionPrivPortNonBlock) {
    bool exceptionRaised = false;
    TCPCommSocket socket;
    
    // Test connecting to a bad hostname
    try {
	socket.setHostname(TEST_HOST);
	socket.setPort(PRIV_PORT);
        socket.initialize();
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 304);
    };
    
    EXPECT_TRUE(exceptionRaised);
}

/* Test write failure */
TEST_F(TCPSocketTest, ExceptionWriteFailure) {
    bool exceptionRaised = false;
    TCPCommSocket socket;
    
    // Test connecting to a bad hostname
    try {
	socket.setHostname(TEST_HOST);
	socket.setPort(TEST_PORT);
        socket.initialize();
        socket.disconnect();
	
	// For non blocking connections the error doesn't occur until
	// the write.
	int count = socket.writeData("test", 4);
	LOG(DEBUG) << "write count: " << count;
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 306);
    };
    
    EXPECT_TRUE(exceptionRaised);
}

/* Test read failure */
TEST_F(TCPSocketTest, ExceptionReadFailure) {
    string testData = "Test";
    char buffer[128];
    bool exceptionRaised = false;
    TCPCommSocket socket;
    
    // Test connecting to a bad hostname
    try {
	socket.setHostname(TEST_HOST);
	socket.setPort(TEST_PORT);
        socket.initialize();
	
	// For non blocking connections the error doesn't occur until
	// the write.
	int count = socket.writeData("test", 4);
	LOG(DEBUG) << "write count: " << count;
        
	socket.disconnect();
	count = socket.readData(buffer, 128);
    }
    catch(OOIException &e) {
        exceptionRaised = true;
	string errmsg = e.what();
        LOG(INFO) << "Expected exception caught: " << errmsg;
        EXPECT_EQ(e.errno(), 305);
    };
    
    EXPECT_TRUE(exceptionRaised);
}

