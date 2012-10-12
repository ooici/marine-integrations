#include "common/logger.h"
#include "common/timestamp.h"
#include "common/exception.h"
#include "gtest/gtest.h"

#include <iostream>
#include <fstream>
#include <string>
#include <math.h>

using namespace std;
using namespace logger;


class TimestampTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "            TimestampTest Start Up";
            LOG(INFO) << "************************************************";
        }
};


/* Test a new timestamp with an exlicit date. */
TEST_F(TimestampTest, Default) {
	// This should evaluate to 1.5 seconds
	// http://www.ntp.org/ntpfaq/NTP-s-algo.htm
	// section 5.1.2.3
	Timestamp myTime(1, 0x80000000);
    
    EXPECT_TRUE(myTime.seconds());
    EXPECT_TRUE(myTime.asNumber().length());
    EXPECT_TRUE(myTime.asHex().length());
    EXPECT_TRUE(myTime.asBinary());
    
    EXPECT_EQ(myTime.seconds(), 1);
    EXPECT_EQ(myTime.fraction(), 0x80000000);

    // GTEST was introducing rounding error in the lower bits.
    double asDouble = myTime.asDouble();
    double expectedTime = 1.5;
    double diff = asDouble > expectedTime ? asDouble - expectedTime : expectedTime - asDouble;

    EXPECT_LT(diff, 0.00000001);

    LOG(INFO) << "asNumber: " << myTime.asNumber();
    LOG(INFO) << "asHex: " << myTime.asHex();
    LOG(INFO) << "asDouble: " << asDouble;
    LOG(INFO) << "expectedDouble: " << expectedTime;
}

/* Test setNow() and SetTime() explicitly */
/* Test elapseTime() */

/* Test copy constructor and assignment operator */
TEST_F(TimestampTest, CopyCTOR) {
	Timestamp myTime(1, 0x80000000);

	LOG(INFO) << "Test the copy constructor";
	Timestamp copy(myTime);
	EXPECT_EQ(myTime.seconds(), copy.seconds());
	EXPECT_EQ(myTime.fraction(), copy.fraction());

    EXPECT_EQ(copy.seconds(), 1);
    EXPECT_EQ(copy.fraction(), 0x80000000);

	LOG(INFO) << "Test the assignment operator";
	Timestamp assigned;

	// First verify that it set the time to now.
	EXPECT_GT(assigned.seconds(), 10);

	assigned = myTime;
	EXPECT_EQ(myTime.seconds(), assigned.seconds());
	EXPECT_EQ(myTime.fraction(), assigned.fraction());

    EXPECT_EQ(assigned.seconds(), 1);
    EXPECT_EQ(assigned.fraction(), 0x80000000);
}
