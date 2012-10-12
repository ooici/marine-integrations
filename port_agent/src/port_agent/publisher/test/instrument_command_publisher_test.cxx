#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "gtest/gtest.h"
#include "publisher_test.h"
#include "instrument_command_publisher.h"


#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

#define DATAFILE "/tmp/data.log"

class InstrumentCommandPublisherTest : public FilePointerPublisherTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "   InstrumentCommandPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";

            datafile = DATAFILE;
        }


        // For the instrument command we just write raw command, not packets.
	    size_t expectedAsciiPacket(char *buffer, const TPacketType &type) {
	        strcpy(buffer, "data");
	        return 4;
	    }

	    size_t expectedBinaryPacket(char *buffer, const TPacketType &type) {
	        return expectedAsciiPacket(buffer, type);
	    }
};

/* Test Basic Creation and ASCII out */
TEST_F(InstrumentCommandPublisherTest, SingleAsciiOut) {
	InstrumentCommandPublisher publisher;
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_DRIVER));
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_INSTRUMENT));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_COMMAND));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_STATUS));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_FAULT));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, true));
}

/* Test Single binary packet out out */
TEST_F(InstrumentCommandPublisherTest, SingleBinaryOut) {
	InstrumentCommandPublisher publisher;

	// It shouldn't matter if the binary flag is set, but let's test anyway.
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_DRIVER));
	EXPECT_TRUE(testNoPublish(publisher, DATA_FROM_INSTRUMENT));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_COMMAND));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_STATUS));
	EXPECT_TRUE(testNoPublish(publisher, PORT_AGENT_FAULT));
	EXPECT_TRUE(testPublish(publisher, INSTRUMENT_COMMAND, false));
}

/* Test publication failures */
TEST_F(InstrumentCommandPublisherTest, FailureNoFile) {
	InstrumentCommandPublisher publisher;
	EXPECT_TRUE(testPublishFailure(publisher, INSTRUMENT_COMMAND));
}
