/*******************************************************************************
 * Class: FilePointerPublisher
 * Filename: file_pointer_publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This is a base packet for publishing packets to a c-style FILE*.  This
 * should work for tcp, udp, and serial connections.
 *
 * We will default to all handlers writting all packet data to the file pointer.
 * The specialized classes can disable handlers that they don't want.
 *
 ******************************************************************************/

#include "file_pointer_publisher.h"
#include "common/logger.h"
#include "common/exception.h"
#include "port_agent/packet/packet.h"

#include <sstream>
#include <string>
#include <errno.h>

#include <stdio.h>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: Set the comm object
 * Parameter:
 *    CommBase* pointer to a comm object
 ******************************************************************************/
FilePointerPublisher::FilePointerPublisher() {
    m_pFilePointer = NULL;
    m_oCommSocket = NULL;
}

/******************************************************************************
 * Method: Constructor
 * Description: Set the comm object
 * Parameter:
 *    CommBase* pointer to a comm object
 ******************************************************************************/
FilePointerPublisher::FilePointerPublisher(CommBase* comm) {
    m_pFilePointer = NULL;
    setCommObject(comm);
}

/******************************************************************************
 * Method: setFilePointer
 * Description: Set the private file pointer (deep copy)
 * Parameter:
 *    FILE* referencing a file descriptor.
 ******************************************************************************/
void FilePointerPublisher::setCommObject(CommBase* comm) {
    m_oCommSocket = comm->copy();
}

/******************************************************************************
 * Method: setFilePointer
 * Description: Set the private file pointer
 * Parameter:
 *    FILE* referencing a file descriptor.
 ******************************************************************************/
void FilePointerPublisher::setFilePointer(FILE* file) {
    m_pFilePointer = file;
}

/******************************************************************************
 * Method: logPacket
 * Description: Write a packet of data to the internal file pointer.  Raise an
 * error if we don't have a file pointer.
 *
 * Parameter:
 *    Packet* - Pointer to a packet of data we need to write to the FILE*
 ******************************************************************************/
bool FilePointerPublisher::logPacket(Packet *packet) {
    string output;

	if(m_bAsciiOut) {
        output = packet->asAscii();
        return write(output.c_str(), output.length());
    }

	// Must be binary
	return write(packet->packet(), packet->packetSize());
}

/******************************************************************************
 * Method: write
 * Description: Write a buffer the the internal FILE*.  It attempts to write
 * the buffer three times.  Exceptions are thrown if the FILE* is not set or
 * we fail to write the entire packet.
 *
 * Parameter:
 *    char* - the buffer that we are writting.
 *    size - how many bytes?
 *
 * Exceptions:
 *    FileDescriptorNULL
 *    PacketPublishFailure
 ******************************************************************************/
bool FilePointerPublisher::write(const char *buffer, uint32_t size) {
	int count;
	int total = 0;

	if(m_pFilePointer == NULL)
		throw FileDescriptorNULL();

	// Try to write data three times.  Throw an error if we fail.
	for( int i = 0; i < 3 && total < size; i++) {
		total += fwrite(buffer + total, 1, size - total, m_pFilePointer);
	}

	if(total != size) {
		LOG(INFO) << "Publish failed.  Intended bytes: " << size << " actual write: " << total;
 		throw PacketPublishFailure(strerror(errno));
	}

	return true;
}



