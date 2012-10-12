#include "publisher_test.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "port_agent/publisher/publisher_list.h"

#include "gtest/gtest.h"

#include <sstream>
#include <string.h>
#include <stdio.h>

using namespace std;
using namespace logger;
using namespace publisher;
using namespace packet;

class PublisherListTest : public testing::Test {
};

TEST_F(PublisherListTest, CTOR) {
    PublisherList list;
    LOG(DEBUG) << "HERE";
}

