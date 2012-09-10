#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/connection/observatory_connection.h"
#include "gtest/gtest.h"

#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace logger;
using namespace port_agent;

#define TEST_DATA_PORT "4001"
#define TEST_COMMAND_PORT "4000"

class ObservatoryConnectionTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "     Observatory Connection Test Start Up";
            LOG(INFO) << "************************************************";
        }
};

/* Test Normal Observatory Connection */
TEST_F(ObservatoryConnectionTest, NormalConnection) {
    ObservatoryConnection connection;
    Connection *pConnection = &connection;
    
    EXPECT_EQ(pConnection->connectionType(), PACONN_OBSERVATORY_STANDARD);
    
    connection.setCommandPort(4000);
    
    connection.initialize();
    
    EXPECT_TRUE(connection.dataInitialized());
    EXPECT_TRUE(connection.commandInitialized());
    
    EXPECT_FALSE(connection.dataConnected());
    EXPECT_FALSE(connection.commandConnected());
    
    ASSERT_TRUE(connection.dataConnectionObject());
    ASSERT_TRUE(connection.commandConnectionObject());
    
    EXPECT_EQ(connection.commandConnectionObject()->getListenPort(), atoi(TEST_COMMAND_PORT));
    
    EXPECT_NE(connection.dataConnectionObject()->getListenPort(), atoi(TEST_DATA_PORT));
    connection.setDataPort(atoi(TEST_DATA_PORT));
    EXPECT_EQ(connection.dataConnectionObject()->getListenPort(), atoi(TEST_DATA_PORT));
}

