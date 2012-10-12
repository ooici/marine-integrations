#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "gtest/gtest.h"
#include "publisher_test.h"
#include "tcp_publisher.h"


#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

#define DATAFILE "/tmp/data.log"

class TCPPublisherTest : public FilePointerPublisherTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "       TCPPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";

            datafile = DATAFILE;
        }
};

/* Test Basic Creation and ASCII out */
TEST_F(TCPPublisherTest, SingleAsciiOut) {
	TCPPublisher publisher;
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_DRIVER, true));
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_COMMAND, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, true));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, true));
}

/* Test Single binary packet out out */
TEST_F(TCPPublisherTest, SingleBinaryOut) {
	TCPPublisher publisher;
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_DRIVER, false));
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_COMMAND, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, false));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, false));
}

/* Test publication failures */
TEST_F(TCPPublisherTest, FailureNoFile) {
	TCPPublisher publisher;
	EXPECT_TRUE(testPublishFailure(publisher, DATA_FROM_DRIVER));
}
