#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "port_agent/publisher/log_publisher.h"
#include "port_agent/packet/buffered_single_char.h"
#include "gtest/gtest.h"
#include "publisher_test.h"

#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

#define DATAFILE "/tmp/data.log"

class LogPublisherTest : public PublisherTest {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "       LogPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";
            remove_file(DATAFILE);
        }
};

/* Test Basic Creation and ASCII out */
TEST_F(LogPublisherTest, SingleAsciiOut) {
    LogPublisher publisher;
    char result[1024];
    int count;
    char *expected = "<port_agent_packet type=\"DATA_FROM_DRIVER\" time=\"1.5\">data</port_agent_packet>\n\r";

    publisher.setFilename(DATAFILE);
    publisher.setAsciiMode(true);

    Timestamp ts(1, 0x80000000);
	Packet packet(DATA_FROM_DRIVER, ts, "data", 4);

    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();

    count = rawRead(DATAFILE, result, 1024);
    ASSERT_EQ(count, 80);
    EXPECT_TRUE(rawCompare(expected, result, count));
}

/* Test two records ASCII out */
TEST_F(LogPublisherTest, TwoAsciiOut) {
    LogPublisher publisher;
    char result[1024];
    int count;
    char *expected = "<port_agent_packet type=\"DATA_FROM_DRIVER\" time=\"1.5\">data</port_agent_packet>\n\r<port_agent_packet type=\"DATA_FROM_DRIVER\" time=\"1.5\">data</port_agent_packet>\n\r";

    publisher.setFilename(DATAFILE);
    publisher.setAsciiMode(true);

    Timestamp ts(1, 0x80000000);
	Packet packet(DATA_FROM_DRIVER, ts, "data", 4);

    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();
    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();

    count = rawRead(DATAFILE, result, 1024);
    ASSERT_EQ(count, 160);
    EXPECT_TRUE(rawCompare(expected, result, count));
}

/* Test Single binary packet out out */
TEST_F(LogPublisherTest, SingleBinaryOut) {
    LogPublisher publisher;
    char result[1024];
    int count;
    char expected[20] = { 0xa3, 0x9d, 0x7a,  0x02, 0x00,  0x14, 0x00,  0xeb,  0x00,  0x00,
    		              0x00, 0x01,  0x80, 0x00,  0x00,  0x00, 0x64, 0x61, 0x74, 0x61 };

    publisher.setFilename(DATAFILE);

    Timestamp ts(1, 0x80000000);
	Packet packet(DATA_FROM_DRIVER, ts, "data", 4);

    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();

    count = rawRead(DATAFILE, result, 1024);
    ASSERT_EQ(count, 20);
    EXPECT_TRUE(rawCompare(expected, result, count));
}

/* Test Double binary packet out out */
TEST_F(LogPublisherTest, DoubleBinaryOut) {
    LogPublisher publisher;
    char result[1024];
    int count;
    char expected[40] = { 0xa3, 0x9d, 0x7a,  0x02, 0x00,  0x14, 0x00,  0xeb, 0x00, 0x00,
                          0x00, 0x01,  0x80, 0x00,  0x00,  0x00, 0x64, 0x61, 0x74, 0x61,
                          0xa3, 0x9d, 0x7a,  0x02, 0x00,  0x14, 0x00,  0xeb, 0x00, 0x00,
                		  0x00, 0x01,  0x80, 0x00,  0x00,  0x00, 0x64, 0x61, 0x74, 0x61 };

    publisher.setFilename(DATAFILE);

    Timestamp ts(1, 0x80000000);
	Packet packet(DATA_FROM_DRIVER, ts, "data", 4);

    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();
    EXPECT_TRUE(publisher.publish(&packet));
    publisher.close();

    count = rawRead(DATAFILE, result, 1024);
    ASSERT_EQ(count, 40);
    EXPECT_TRUE(rawCompare(expected, result, count));
}

// NOTE: We are only testing one packet type because they all call the same
// interface.

/* Test publication failures */
TEST_F(LogPublisherTest, FailureNoFile) {
    LogPublisher publisher;

    Timestamp ts(1, 0x80000000);
	Packet packet(DATA_FROM_DRIVER, ts, "data", 4);

    EXPECT_FALSE(publisher.publish(&packet));
}
