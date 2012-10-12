#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/buffered_single_char.h"
#include "gtest/gtest.h"

#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;

class BufferedPacketTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "    Port Agent Buffered Packet Test Start Up";
            LOG(INFO) << "************************************************";
        }
};

/* Test Basic Creation.  Not testing any of the read to send  rules, just
   testing packet creation and data storage. */
TEST_F(BufferedPacketTest, CTOR) {
    char *packet = NULL;
    
    // create a packet
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 2, 3, "FOOBAR", 6);
    
    // Ensure our timestamp is set to the default
    EXPECT_EQ(myPacket.timestamp().seconds(), 0);
    EXPECT_EQ(myPacket.timestamp().fraction(), 0);
    
    // we shouldn't be ready to send yet because the buffer isn't full.
    EXPECT_FALSE(myPacket.readyToSend());
    
    // add some characters
    Timestamp firstTimestamp;
    myPacket.add('a', firstTimestamp);

    // Check to ensure the packet timestamp was set because this was our first data element
    EXPECT_EQ(myPacket.timestamp().seconds(), firstTimestamp.seconds());
    EXPECT_EQ(myPacket.timestamp().fraction(), firstTimestamp.fraction());

    sleep(1);

    // check the packet size, adding 16 bytes for the header
    EXPECT_EQ(myPacket.packetSize(), 16 + 1);
    EXPECT_FALSE(myPacket.readyToSend());
    
    // add another character and test
    Timestamp secondTimestamp;
    myPacket.add('b', secondTimestamp);
    EXPECT_EQ(myPacket.packetSize(), 16 + 2);

    // Check to ensure the packet timestamp is still set to our first time.
    EXPECT_EQ(myPacket.timestamp().seconds(), firstTimestamp.seconds());
    EXPECT_EQ(myPacket.timestamp().fraction(), firstTimestamp.fraction());
    
    // we are at our packet size limit.  Let's check our status
    EXPECT_TRUE(myPacket.readyToSend());
    
    // check the binary result produced.
    packet = myPacket.packet();    
    LOG(MESG) << myPacket.pretty();
    
    // Check that we can setup a packet with the max packet size
    // an error is thrown if the packet size is out of range so there is nothing
    // to actually test here.
    BufferedSingleCharPacket otherPacket(DATA_FROM_INSTRUMENT, 0xFFEF);
    
    // Binary structure tested in basic_packet_test
    
}


// Test that the copy constructor works and is doing a deep copy
TEST_F(BufferedPacketTest, CopyCTORWithDataAndSentinle) {
	LOG(INFO) << "Testing the copy constructor";
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 2, 3, "FOOBAR", 6);

    // Sleep for a second so we can ensure timestamps are being copied, not just set to now
    sleep(1);

    // Explicitly calling a copy constructor
    BufferedSingleCharPacket copy(myPacket);
    
    char *packet = myPacket.packet();
    char *copyPacket = copy.packet();
    
    char *sentinle = myPacket.sentinle();
    char *copySentinle = copy.sentinle();
    
    // Make sure we are looking at different addresses
    EXPECT_NE(packet, copyPacket);
    EXPECT_NE(sentinle, copySentinle);
    
    // Fail if the sizes are the same so we don't segfault
    ASSERT_EQ(myPacket.packetSize(), copy.packetSize());
    ASSERT_EQ(myPacket.sentinleSize(), copy.sentinleSize());
    
    LOG(DEBUG) << "Original Packet: " << myPacket.pretty();
    LOG(DEBUG) << "Copied Packet: " << copy.pretty();

    // Deep insepction of the packet
    for(int i = 0; i < myPacket.packetSize(); i++)
        EXPECT_EQ(packet[i], copyPacket[i]);
    
    for(int i = 0; i < myPacket.sentinleSize(); i++)
        EXPECT_EQ(sentinle[i], copySentinle[i]);

}

/* Test copy constructor with out sentinle */
TEST_F(BufferedPacketTest, CopyCTORWithoutSentinle) {
	LOG(INFO) << "Testing the copy constructor";
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 2, 3);

    // Sleep for a second so we can ensure timestamps are being copied, not just set to now
    sleep(1);

    // Explicitly calling a copy constructor
    BufferedSingleCharPacket copy(myPacket);

    char *packet = myPacket.packet();
    char *copyPacket = copy.packet();

    char *sentinle = myPacket.sentinle();
    char *copySentinle = copy.sentinle();

    // Make sure we are looking at different addresses
    EXPECT_NE(packet, copyPacket);

    // Fail if the sizes are the same so we don't segfault
    ASSERT_EQ(myPacket.packetSize(), copy.packetSize());
    ASSERT_EQ(myPacket.sentinleSize(), copy.sentinleSize());

    LOG(DEBUG) << "Original Packet: " << myPacket.pretty();
    LOG(DEBUG) << "Copied Packet: " << copy.pretty();

    // Deep insepction of the packet
    for(int i = 0; i < myPacket.packetSize(); i++)
        EXPECT_EQ(packet[i], copyPacket[i]);

    EXPECT_FALSE(sentinle);
    EXPECT_FALSE(copySentinle);
}

/* Test the assignment operator */
TEST_F(BufferedPacketTest, PacketAssignment) {
	LOG(INFO) << "Testing the assignment operator";
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 2, 3, "FOOBAR", 6);

    // Sleep for a second so we can ensure timestamps are being copied, not just set to now
    sleep(1);

    // Explicitly calling a copy constructor
    BufferedSingleCharPacket copy = myPacket;

    char *packet = myPacket.packet();
    char *copyPacket = copy.packet();

    char *sentinle = myPacket.sentinle();
    char *copySentinle = copy.sentinle();

    // Make sure we are looking at different addresses
    EXPECT_NE(packet, copyPacket);
    EXPECT_NE(sentinle, copySentinle);

    // Fail if the sizes are the same so we don't segfault
    ASSERT_EQ(myPacket.packetSize(), copy.packetSize());
    ASSERT_EQ(myPacket.sentinleSize(), copy.sentinleSize());

    LOG(DEBUG) << "Original Packet: " << myPacket.pretty();
    LOG(DEBUG) << "Copied Packet: " << copy.pretty();

    // Deep insepction of the packet
    for(int i = 0; i < myPacket.packetSize(); i++)
        EXPECT_EQ(packet[i], copyPacket[i]);

    for(int i = 0; i < myPacket.sentinleSize(); i++)
        EXPECT_EQ(sentinle[i], copySentinle[i]);

}

/* Test Sentinle String Trigger. */
TEST_F(BufferedPacketTest, SentinleTrigger) {
    LOG(INFO) << "Testing Quiescent Time Trigger";
    
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 11, 0, "ab", 2);
    
    myPacket.packet();
    LOG(DEBUG) << "Initial packet: " << myPacket.pretty();
    
    LOG(DEBUG) << "Ensure that we are reporting not ready to send";
    EXPECT_FALSE(myPacket.readyToSend());
    
    LOG(DEBUG) << "Add the first sentinle character";
    myPacket.add('a');
    EXPECT_FALSE(myPacket.readyToSend());
    EXPECT_EQ(myPacket.packetSize(), 16 + 1);
    
    LOG(DEBUG) << "Add the last sentinle character";
    myPacket.add('b');
    EXPECT_TRUE(myPacket.readyToSend());
    EXPECT_EQ(myPacket.packetSize(), 16 + 2);
    
    LOG(DEBUG) << "Now lets try to add aab to ensure the sentinle resets correctly";
    myPacket.add('a');
    EXPECT_FALSE(myPacket.readyToSend());
    myPacket.add('a');
    myPacket.add('b');
    EXPECT_TRUE(myPacket.readyToSend());
    
    LOG(DEBUG) << "try to add 'azb' to ensure it doesn't match";
    myPacket.add('a');
    EXPECT_FALSE(myPacket.readyToSend());
    myPacket.add('z');
    myPacket.add('b');
    EXPECT_FALSE(myPacket.readyToSend());
    
    LOG(DEBUG) << "make sure we can get back to ready do send";
    myPacket.add('a');
    myPacket.add('b');
    EXPECT_TRUE(myPacket.readyToSend());
    
    LOG(DEBUG) << "last check is to show that max packet size will still trigger";
    myPacket.add('w');
    EXPECT_TRUE(myPacket.readyToSend());
    
    myPacket.packet();
    LOG(DEBUG) << "Final packet: " << myPacket.pretty();
}

/* Test Quiescent Time Trigger. */
TEST_F(BufferedPacketTest, QuiescentTimeTrigger) {
    LOG(INFO) << "Testing Quiescent Time Trigger";
    
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 3, 0.5);
    
    LOG(DEBUG) << "Ensure empty packets are never ready to send";
    EXPECT_FALSE(myPacket.readyToSend());
    sleep(1);
    EXPECT_FALSE(myPacket.readyToSend());
    
    LOG(DEBUG) << "Add some data and wait for a trigger";
    myPacket.add('a');
    EXPECT_FALSE(myPacket.readyToSend());
    sleep(1);
    EXPECT_TRUE(myPacket.readyToSend());
    
    LOG(DEBUG) << "Check that the ready to send resets on add";
    myPacket.add('b');
    EXPECT_FALSE(myPacket.readyToSend());
    sleep(1);
    EXPECT_TRUE(myPacket.readyToSend());
}
    
/* Constructor Throw Tests */
// These happen when setting parameters
TEST_F(BufferedPacketTest, CTORThrowTests) {
    bool exceptionCaught;
    
    try {
        LOG(DEBUG) << "Check for invalid message type";
        exceptionCaught = false;
        BufferedSingleCharPacket myPacket(UNKNOWN, 3);
    }
    catch(PacketParamOutOfRange & e) {
        exceptionCaught = true;
        LOG(DEBUG1) << "exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 603);
    }
    EXPECT_TRUE(exceptionCaught);
    
    try {
        LOG(DEBUG) << "Check for empty payload size";
        exceptionCaught = false;
        BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 0, 0, "ab", 2);
    }
    catch( PacketParamOutOfRange & e) {
        exceptionCaught = true;
        LOG(DEBUG1) << "exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 603);
    }
    EXPECT_TRUE(exceptionCaught);
    
    try {
        // 0xFFF0 is one more than the max payload size of 0xFFFF - HEADER_SIZE
        LOG(DEBUG) << "Check for too large payload size";
        exceptionCaught = false;
        BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 0xFFF0, 0, "ab", 2);
    }
    catch( PacketParamOutOfRange & e) {
        exceptionCaught = true;
        LOG(DEBUG1) << "exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 603);
    }
    EXPECT_TRUE(exceptionCaught);
    
    try {
        LOG(DEBUG) << "Check for negative wait time";
        exceptionCaught = false;
        BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 11, -1, "ab", 2);
    }
    catch( PacketParamOutOfRange & e) {
        exceptionCaught = true;
        LOG(DEBUG1) << "exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 603);
    }
    EXPECT_TRUE(exceptionCaught);
    
    try {
        LOG(DEBUG) << "Check for bad sentinle sequence size";
        exceptionCaught = false;
        BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 11, 0, "ab", 0);
    }
    catch( PacketParamOutOfRange & e) {
        exceptionCaught = true;
        LOG(DEBUG1) << "exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 603);
    }
    EXPECT_TRUE(exceptionCaught);
}

/* Test for data overflow */
// Ensure we throw an exception when we try to write past our max packet size.
TEST_F(BufferedPacketTest, OverflowTest) {
    bool exceptionCaught;
    BufferedSingleCharPacket myPacket(DATA_FROM_INSTRUMENT, 3, 0, "ff", 2);
    
    try {
        LOG(DEBUG) << "Check for packet overflow exception";
        exceptionCaught = false;
        myPacket.add('a');
        myPacket.add('a');
        myPacket.add('a');
        LOG(DEBUG) << "About to blow up!";
        myPacket.add('a');
        LOG(DEBUG) << "BOOM!!!";
    }
    catch(PacketOverflow & e) {
        LOG(DEBUG1) << "exception caught: " << e.what();
        exceptionCaught = true;
        EXPECT_EQ(e.errno(), 601);
    }
    LOG(DEBUG) << "Made it out alive!";

    EXPECT_EQ(myPacket.packetSize(), 16+3);
}

/* Test exceptions from public set methods */

