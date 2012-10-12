#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "gtest/gtest.h"

#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace packet;
using namespace logger;

class PortAgentPacketTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("MESG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "      Port Agent Basic Packet Test Start Up";
            LOG(INFO) << "************************************************";
        }
};

/* Test Basic Creation */
TEST_F(PortAgentPacketTest, CTOR) {
	// Set time to 1.5 seconds past the epoch
	Timestamp timestamp(1, 0x80000000);

    char *payload = strdup("ad");
    int length = strlen(payload);
    
    Packet packet(DATA_FROM_DRIVER, timestamp, payload, length);
    char* packetBuffer = packet.packet();
    
    EXPECT_EQ(packet.packetType(), DATA_FROM_DRIVER);
    EXPECT_EQ(packet.packetSize(), length + HEADER_SIZE);
    EXPECT_EQ(packet.payloadSize(), length);
    EXPECT_EQ(packet.timestamp().seconds(), 1);
    EXPECT_EQ(packet.timestamp().fraction(), 0x80000000);
    EXPECT_TRUE(packet.checksum());
    EXPECT_TRUE(packet.packet());
        
    // Check the sync sequence
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[0]), 0xA3);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[1]), 0x9D);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[2]), 0x7A);

    // Check the message type
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[3]), 0x02);

    // Check the packetBuffer size
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[4]), 0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[5]), 0x12);

    // Check the checksum
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[6]), 0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[7]), 0x14);

    // Check the timestamp
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[8]),  0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[9]),  0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[10]), 0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[11]), 0x01);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[12]), 0x80);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[13]), 0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[14]), 0x00);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[15]), 0x00);

    // Check the payload
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[16]), 0x61);
    EXPECT_EQ(byteToUnsignedInt(packetBuffer[17]), 0x64);

    delete [] payload;
}

/* Test the copy constructor with a payload */
TEST_F(PortAgentPacketTest, CopyCTORWithData) {
	char *lhsPacket;
	char *rhsPacket;

	// Set time to 1.5 seconds past the epoch
	Timestamp timestamp(1, 0x80000000);

    char *payload = strdup("ad");
    int length = strlen(payload);

    Packet packet(DATA_FROM_DRIVER, timestamp, payload, length);

    // Explicitly call the copy constructor
    Packet copy(packet);

    EXPECT_EQ(packet.packetType(), copy.packetType());
    EXPECT_EQ(packet.packetSize(), copy.packetSize());
    EXPECT_EQ(packet.payloadSize(), copy.payloadSize());
    EXPECT_EQ(packet.checksum(), copy.checksum());
    EXPECT_EQ(packet.timestamp().seconds(), copy.timestamp().seconds());
    EXPECT_EQ(packet.timestamp().fraction(), copy.timestamp().fraction());

    lhsPacket = packet.packet();
    rhsPacket = copy.packet();

    // These should point to different memory locations
    EXPECT_NE(lhsPacket, rhsPacket);
    ASSERT_EQ(packet.packetSize(), copy.packetSize());

    // But the content should be the same
    for(int i = 0; i < packet.packetSize(); i++ )
    	EXPECT_EQ(lhsPacket[i], rhsPacket[i]);

    delete [] payload;
}

/* Test the copy constructor without a payload */
TEST_F(PortAgentPacketTest, CopyCTORWithOutData) {
	char *lhsPacket;
	char *rhsPacket;

	// Set time to 1.5 seconds past the epoch
	Timestamp timestamp(1, 0x80000000);

    Packet packet(DATA_FROM_DRIVER, timestamp, NULL, 0);
    char* packetBuffer = packet.packet();

    // Explicitly call the copy constructor
    Packet copy(packet);

    EXPECT_EQ(packet.packetType(), copy.packetType());
    EXPECT_EQ(packet.packetSize(), copy.packetSize());
    EXPECT_EQ(packet.payloadSize(), copy.payloadSize());
    EXPECT_EQ(packet.checksum(), copy.checksum());
    EXPECT_EQ(packet.timestamp().seconds(), copy.timestamp().seconds());
    EXPECT_EQ(packet.timestamp().fraction(), copy.timestamp().fraction());

    lhsPacket = packet.packet();
    rhsPacket = copy.packet();

    // These should point to different memory locations
    EXPECT_NE(lhsPacket, rhsPacket);
    ASSERT_EQ(packet.packetSize(), copy.packetSize());

    // But the content should be the same
    for(int i = 0; i < packet.packetSize(); i++ )
    	EXPECT_EQ(lhsPacket[i], rhsPacket[i]);
}

/* Test the assignment operator */
TEST_F(PortAgentPacketTest, PacketAssignment) {
	char *lhsPacket;
	char *rhsPacket;

	// Set time to 1.5 seconds past the epoch
	Timestamp timestamp(1, 0x80000000);

    char *payload = strdup("ad");
    int length = strlen(payload);

    Packet packet(DATA_FROM_DRIVER, timestamp, payload, length);

    Packet copy = packet;

    EXPECT_EQ(packet.packetType(), copy.packetType());
    EXPECT_EQ(packet.packetSize(), copy.packetSize());
    EXPECT_EQ(packet.payloadSize(), copy.payloadSize());
    EXPECT_EQ(packet.checksum(), copy.checksum());
    EXPECT_EQ(packet.timestamp().seconds(), copy.timestamp().seconds());
    EXPECT_EQ(packet.timestamp().fraction(), copy.timestamp().fraction());

    lhsPacket = packet.packet();
    rhsPacket = copy.packet();

    // These should point to different memory locations
    EXPECT_NE(lhsPacket, rhsPacket);
    ASSERT_EQ(packet.packetSize(), copy.packetSize());

    // But the content should be the same
    for(int i = 0; i < packet.packetSize(); i++ )
    	EXPECT_EQ(lhsPacket[i], rhsPacket[i]);

    delete [] payload;
}


/* Test typeToString */
TEST_F(PortAgentPacketTest, PacketTypeToText) {
    Packet packet;

    EXPECT_EQ(packet.typeToString(UNKNOWN), "UNKNOWN");
    EXPECT_EQ(packet.typeToString(DATA_FROM_INSTRUMENT), "DATA_FROM_INSTRUMENT");
    EXPECT_EQ(packet.typeToString(DATA_FROM_DRIVER), "DATA_FROM_DRIVER");
    EXPECT_EQ(packet.typeToString(PORT_AGENT_COMMAND), "PORT_AGENT_COMMAND");
    EXPECT_EQ(packet.typeToString(PORT_AGENT_STATUS), "PORT_AGENT_STATUS");
    EXPECT_EQ(packet.typeToString(PORT_AGENT_FAULT), "PORT_AGENT_FAULT");
    EXPECT_EQ(packet.typeToString(INSTRUMENT_COMMAND), "INSTRUMENT_COMMAND");
}

/* Test the ascii output */
TEST_F(PortAgentPacketTest, AsciiOutput) {
	// Set time to 1.5 seconds past the epoch
	Timestamp timestamp(1, 0x80000000);

    char *payload = strdup("ad");
    int length = strlen(payload);

    Packet packet(DATA_FROM_DRIVER, timestamp, payload, length);

    string expected = "<port_agent_packet type=\"DATA_FROM_DRIVER\" time=\"1.5\">ad</port_agent_packet>\n\r";
    string result = packet.asAscii();

    EXPECT_EQ(expected, result);
    LOG(DEBUG) << result;

    LOG(DEBUG) << packet.pretty();

    delete [] payload;
}

