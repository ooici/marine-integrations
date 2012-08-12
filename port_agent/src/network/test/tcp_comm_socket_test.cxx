#include "common/exception.h"
#include "common/logger.h"
#include "network/tcp_comm_socket.h"
#include "network_test.h"

#include <string>

using namespace logger;
using namespace network;

const uint16_t TEST_PORT=4001;
const char* TEST_HOST="localhost";

class TCPSocketTest : public NetworkTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG3");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "         TCP Comm Socket Test Start Up";
            LOG(INFO) << "************************************************";

            m_pid = 0;
        }

        void TearDown() {
        	//stopProcess(m_pid);
        }

        bool startTCPServer() {
        	//m_pid = startTCPEchoServer(TEST_PORT);

        	return true;
        	return m_pid > 0;
        }

    private:
        uint16_t m_pid;
};

/* Test the basic connection */
TEST_F(TCPSocketTest, Connection) {
	string testData = "Test Data";
	char buffer[128];
	uint16_t writeCount, readCount;
	TCPCommSocket socket;

	// Configure the socket
    socket.setHostname(TEST_HOST);
    socket.setPort(TEST_PORT);

    // Start the TCP echo server
    ASSERT_TRUE(startTCPServer());

    try{
    	// Set connection information
        EXPECT_TRUE(socket.initialize());

 	    // Write some data
        writeCount = socket.writeData(testData.c_str(), testData.length());
        EXPECT_EQ(testData.size(), writeCount);

        LOG(DEBUG) << "Bytes written: " << writeCount;
        sleep(10);

        if(writeCount > 0) {
            LOG(DEBUG) << "Reading echo returned";
        	//readCount = socket.readData(buffer, 128);
            EXPECT_EQ(readCount, 9);
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
}

/* Test Exceptions */
// Connection
// - Not configured
// - Bad hostname
// - Bad port
// - write failure (closed connection?)
