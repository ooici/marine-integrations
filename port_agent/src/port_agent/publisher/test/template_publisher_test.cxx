#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/publisher/publisher.h"
#include "port_agent/packet/buffered_single_char.h"
#include "gtest/gtest.h"

#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;

class LogPublisherTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "       LogPublisherTest Test Start Up";
            LOG(INFO) << "************************************************";
        }
};

/* Test Basic Creation */
TEST_F(LogPublisherTest, CTOR) {
}


