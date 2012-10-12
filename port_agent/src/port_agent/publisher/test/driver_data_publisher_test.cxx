#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "gtest/gtest.h"
#include "publisher_test.h"
#include "driver_data_publisher.h"


#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

#define DATAFILE "/tmp/data.log"

class DriverDataPublisherTest : public FilePointerPublisherTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "   DriverDataPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";

            datafile = DATAFILE;
        }
};

/* Test Basic Creation and ASCII out */
TEST_F(DriverDataPublisherTest, SingleAsciiOut) {
	DriverDataPublisher publisher;
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, true));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, true));
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_DRIVER));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_COMMAND));
	EXPECT_TRUE(testNoPublish(publisher, INSTRUMENT_COMMAND));
}

/* Test Single binary packet out out */
TEST_F(DriverDataPublisherTest, SingleBinaryOut) {
	DriverDataPublisher publisher;

	// It shouldn't matter if the binary flag is set, but let's test anyway.
	EXPECT_TRUE(testPublish(publisher, DATA_FROM_INSTRUMENT, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_STATUS, false));
	EXPECT_TRUE(testPublish(publisher, PORT_AGENT_FAULT, false));
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_DRIVER));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_COMMAND));
	EXPECT_TRUE(testNoPublish(publisher, INSTRUMENT_COMMAND));
}

/* Test publication failures */
TEST_F(DriverDataPublisherTest, FailureNoFile) {
	DriverDataPublisher publisher;
	EXPECT_TRUE(testPublishFailure(publisher, DATA_FROM_INSTRUMENT));
}
