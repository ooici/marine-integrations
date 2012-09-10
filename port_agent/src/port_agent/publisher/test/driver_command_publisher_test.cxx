#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "gtest/gtest.h"
#include "publisher_test.h"
#include "driver_command_publisher.h"
#include "network/tcp_comm_socket.h"


#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

#define DATAFILE "/tmp/data.log"

class DriverCommandPublisherTest : public FilePointerPublisherTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "   DriverCommandPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";

            datafile = DATAFILE;
        }
};

/* Test Basic Creation and ASCII out */
TEST_F(DriverCommandPublisherTest, SingleAsciiOut) {
	DriverCommandPublisher publisher;
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_DRIVER, true));
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_COMMAND, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, true));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, true));
}

/* Test Single binary packet out out */
TEST_F(DriverCommandPublisherTest, SingleBinaryOut) {
	DriverCommandPublisher publisher;

	// It shouldn't matter if the binary flag is set, but let's test anyway.
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_DRIVER, false));
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_COMMAND, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, false));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, false));
}

/* Test publication failures */
TEST_F(DriverCommandPublisherTest, FailureNoFile) {
	DriverCommandPublisher publisher;
	EXPECT_TRUE(testPublishFailure(publisher, INSTRUMENT_COMMAND));
}

/* Test with a tcp comm socket */
TEST_F(DriverCommandPublisherTest, CommSocketWrite) {
	
	TCPCommSocket socket;
	socket.setHostname("localhost");
	socket.setPort(4001);
	
//	DriverCommandPublisher publisher(&socket);
	
//      EXPECT_TRUE(testPublishCommSocket(publisher, DATA_FROM_DRIVER));
}
