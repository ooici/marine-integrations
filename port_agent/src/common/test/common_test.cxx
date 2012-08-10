#include "exception.h"
#include "logger.h"
#include "spawn_process.h"
#include "gtest/gtest.h"

using namespace logger;

class CommonTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "            Common Test Start Up";
            LOG(INFO) << "************************************************";
        }
    
        virtual void TearDown() {
            LOG(INFO) << "CommonTest TearDown";
        }
    
        ~CommonTest() {
            LOG(INFO) << "CommonTest dtor";
        }
};

/* Test NOOP */
TEST_F(CommonTest, NOOP) {
}

