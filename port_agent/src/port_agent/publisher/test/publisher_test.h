#ifndef __PUBLISHER_TEST_H_
#define __PUBLISHER_TEST_H_

#include "publisher.h"
#include "common/logger.h"
#include "common/util.h"
#include "port_agent/packet/packet.h"
#include "port_agent/packet/buffered_single_char.h"

#include "gtest/gtest.h"

#include <sstream>
#include <string.h>
#include <stdio.h>

using namespace std;
using namespace logger;
using namespace publisher;

class PublisherTest : public testing::Test {

    protected:
        int rawRead(const char *file, char *buffer, int size) {
        	ifstream is;
        	is.open (file, ios::binary );

        	// get length of file:
        	is.seekg (0, ios::end);
        	int length = is.tellg();
        	is.seekg (0, ios::beg);

         	// read data as a block:
        	is.read (buffer,length);
        	is.close();

            return length;
        }

        bool rawCompare(char *lhs, char *rhs, int size) {
            LOG(INFO) << "Start raw compare, size: " << size;

        	for(int i = 0; i < size; i++)
                if( rhs[i] != lhs[i] ) {
                	LOG(ERROR) << "byte " << i << " mismatch: "
                			   << hex << byteToUnsignedInt(rhs[i]) << " != "
                			   << hex << byteToUnsignedInt(lhs[i]);
                	return false;
                }

        	return true;
        }

};

class FilePointerPublisherTest : public PublisherTest {
    protected:
	    void close(FILE *fd) {
	    	fclose(fd);
	    }

	    // Build a string that we would expect to see from an ascii packet publish
	    virtual size_t expectedAsciiPacket(char *buffer, const TPacketType &type) {
	    	ostringstream out;
	        out << "<port_agent_packet type=\""
	            << Packet().typeToString(type)
	            << "\" time=\"1.5\">data</port_agent_packet>\n\r";

	        strcpy(buffer, out.str().c_str());
	        return out.str().length();
	    }

	    // Build a string that we would expect to see from a binary packet publish
	    virtual size_t expectedBinaryPacket(char *buffer, const TPacketType &type) {
	        char expected[20] = { 0xa3, 0x9d, 0x7a,  type, 0x00,  0x14, 0x00,  0x00,  0x00,  0x00,
	        		              0x00, 0x01,  0x80, 0x00,  0x00,  0x00, 0x64, 0x61, 0x74, 0x61 };

	        uint16_t checksum = 0;

	        for(int i = 0; i < 20; i++) {
	        	if(i < 6 || i > 7)
	        	    checksum += expected[i];

	        	buffer[i] = expected[i];
	        }

	        checksum = htons(checksum);

	        memcpy(buffer + 6, &checksum, 2);

	        return 20;
	    }

	    /* Tests */

	    // Test to see if a packet is published.  Packet type and ascii mode are
	    // parameters used for packet creation and publish mode.
	    // This test will fail if a packet is not published for a given type or
	    // the expected packet doesn't match what is actually published.
	    template <class T>
	    bool testPublish(T &publisher, const TPacketType &packetType, bool ascii) {
	        char result[1024];
	        char expected[1024];
	        int count;
	        int expectedSize;
	        Timestamp ts(1, 0x80000000);
	    	Packet packet(packetType, ts, "data", 4);

            LOG(INFO) << "***************************************************************";
	        LOG(INFO) << "Testing publish with packet type: " << Packet().typeToString(packetType);
            LOG(INFO) << "***************************************************************" << endl;

	        if(ascii)
	        	expectedSize = expectedAsciiPacket(expected, packetType);
	        else
	        	expectedSize = expectedBinaryPacket(expected, packetType);

            LOG(DEBUG2) << "remove the date file: " << datafile;
            remove_file(datafile.c_str());

	        LOG(DEBUG) << "Open file: " << datafile;
	        FILE * pFile = fopen (datafile.c_str(),"w");
	        EXPECT_TRUE(pFile);

            if(pFile == NULL)
            	return false;

            LOG(DEBUG) << "File is open, setup the publisher";

	        publisher.setFilePointer(pFile);
	        publisher.setAsciiMode(ascii);

            LOG(DEBUG) << "Publish a packet";
	    	EXPECT_TRUE(publisher.publish(&packet));

	    	if(publisher.error()) {
	    	    string err = publisher.error()->what();
	    		LOG(ERROR) << "Publish Packet Error: " << err;
	    		return false;
	    	}

 	        close(pFile);

	        count = rawRead(datafile.c_str(), result, 1024);

	        LOG(DEBUG) << "expected size: " << expectedSize << " read size: " << count;
	        EXPECT_EQ(count, expectedSize);
	        if(count == expectedSize)
	            EXPECT_TRUE(rawCompare(expected, result, count));

	        return true;
	    }


	    // Test is similar to the previous test except the packet we generate should be
	    // a packet the class ignores.  Therefore we are testing that NOTHING is publish
	    // in this test.
	    template <class T>
	    bool testNoPublish(T &publisher, const TPacketType &packetType) {
	        char result[1024];
	        int count;
	        Timestamp ts(1, 0x80000000);
	    	Packet packet(packetType, ts, "data", 4);

            LOG(INFO) << "***************************************************************";
	        LOG(INFO) << "Testing non-published with packet type: "
	        		  << Packet().typeToString(packetType);
            LOG(INFO) << "***************************************************************" << endl;


            LOG(DEBUG2) << "remove the date file: " << datafile;
            remove_file(datafile.c_str());

	        LOG(DEBUG) << "Open file: " << datafile;
	        FILE * pFile = fopen (datafile.c_str(),"w");
	        EXPECT_TRUE(pFile);

            if(pFile == NULL)
            	return false;

            LOG(DEBUG) << "File is open, setup the publisher";
	        publisher.setFilePointer(pFile);

            LOG(DEBUG) << "Publish a packet";
	    	EXPECT_TRUE(publisher.publish(&packet));

	    	if(publisher.error()) {
	    	    string err = publisher.error()->what();
	    		LOG(ERROR) << err;
	    		return false;
	    	}
 	        close(pFile);

	        count = rawRead(datafile.c_str(), result, 1024);

	        LOG(DEBUG) << "expected size: " << 0 << " read size: " << count;
	        EXPECT_EQ(count, 0);

	        return true;
	    }

	    // Test the failure states for publishing.  Two ways to fail,
	    // - Write before calling setFilePointer
	    // - Write to a bad file handle
	    template <class T>
	    bool testPublishFailure(T &publisher, const TPacketType &packetType) {
	        Timestamp ts(1, 0x80000000);
	    	Packet packet(packetType, ts, "data", 4);
	    	string errorMessage;
	    	int errorNumber;

	    	LOG(INFO) << "***************************************************************";
	        LOG(INFO) << "Testing publishing failures with packet type: "
	        		  << Packet().typeToString(packetType);
            LOG(INFO) << "***************************************************************" << endl;

	        LOG(DEBUG) << "Open file: " << datafile;
	        FILE * pFile = fopen (datafile.c_str(),"w");
	        EXPECT_TRUE(pFile);

            if(pFile == NULL)
            	return false;

            // Let's try to publish before we set the file handle.
	    	EXPECT_FALSE(publisher.publish(&packet));
            EXPECT_TRUE(publisher.error());

            if(publisher.error()) {
                errorMessage = publisher.error()->what();
                errorNumber = publisher.error()->errno();
                LOG(DEBUG)  << "Exception seen: " << errorMessage;
                EXPECT_EQ(errorNumber, 701);
            }
            else {
            	return false;
            }

            // Now let's close the file handle and then try to write.
            publisher.setFilePointer(pFile);
            fclose(pFile);
	    	EXPECT_FALSE(publisher.publish(&packet));
            EXPECT_TRUE(publisher.error());

            if(publisher.error()) {
                errorMessage = publisher.error()->what();
                errorNumber = publisher.error()->errno();
                LOG(DEBUG)  << "Exception seen: " << errorMessage;
                EXPECT_EQ(errorNumber, 702);
            }
            else {
            	return false;
            }

            return true;
	    }

    protected:
	    string datafile;
};

#endif //__PUBLISHER_TEST_H_
