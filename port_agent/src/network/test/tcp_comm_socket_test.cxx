#include "common/exception.h"
#include "common/logger.h"
#include "network/tcp_comm_socket.h"
#include "gtest/gtest.h"

using namespace logger;
using namespace network;

#define TEST_PORT 4001
#define TEST_HOST "localhost"

class TCPSocketTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         TCP Comm Socket Test Start Up";
            LOG(INFO) << "************************************************";
        }

        bool startTCPServer() {
        	return true;
        }

        bool stopTCPServer() {
        	return true;
        }
};

/* Test the basic connection */
TEST_F(TCPSocketTest, Connection) {
	string testData = "Test Data";
	TCPCommSocket socket;

	// Configure the socket
    socket.setHostname(TEST_HOST);
    socket.setPort(TEST_PORT);

    // Start the TCP echo server
    ASSERT_TRUE(startTCPServer());

    try {
    	// Set connection information
        EXPECT_TRUE(socket.connect());

 	    // Write some data
        EXPECT_EQ(testData.size(), socket.write(testData.c_str(), testData.length()));
    }
    catch(exception &e) {
    	string msg = e.what();
    	LOG(ERROR) << "Unexepect exception: " << msg;

    	// This will cause this test to fail because if we are here msg should never
    	// be an empty string.
    	EXPECT_EQ(msg, "");
    };

    socket.close();

    EXPECT_TRUE(stopTCPServer());
}

/* Test Exceptions */
// Connection
// - Not configured
// - Bad hostname
// - Bad port
// - write failure (closed connection?)
