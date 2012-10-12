/*******************************************************************************
 * Filename: exception.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Exception definitions.
 *
 * Usage:
 *
 * throw FileIOException("Some error");
 ******************************************************************************/

#ifndef EXCEPTION_H_
#define EXCEPTION_H_

#include <string>
#include <sstream>
#include <exception>

using namespace std;

/*******************************************************************************
 * Main exception base class
 ******************************************************************************/
class OOIException : public exception {
    public:
        OOIException() : m_type("unknown exception"), m_msg(""), m_errno(0) {}
        OOIException(const OOIException &copy) : m_type(copy.m_type), m_msg(copy.m_msg), m_errno(copy.m_errno) {}
        OOIException(const char* type, unsigned int errno, const char* msg = "") : m_errno(errno), m_type(type), m_msg(msg) {}
        virtual ~OOIException() throw() {}
        virtual const char* what() const throw() {
                ostringstream os;
                os << "error code " << m_errno << ": " << m_type;
                if(m_msg.length())
                    os << " (" << m_msg << ")";
                    
                return os.str().c_str();
        }
        
        int errno() { return m_errno; }
        const char* type() { return m_type.c_str(); }
        const char* msg() { return m_msg.c_str(); }
        
    protected:
        string m_type;
        string m_msg;
        int m_errno;
};

class FileIOException : public OOIException {
    public: FileIOException(const char* msg = "") :
        OOIException("File open failed", 101, msg) {}
};

class ParameterRequired : public OOIException {
    public: ParameterRequired(const char* msg = "") :
        OOIException("Command line parameter required", 102, msg) {}
};

class InvalidParameter : public OOIException {
    public: InvalidParameter(const char* msg) :
        OOIException("Invalid command line parameter", 103, msg) {}
};

class NotConfigured : public OOIException {
    public: NotConfigured(const char* msg) :
        OOIException("Missing Configuration Parameters", 104, msg) {}
};

class MissingPID : public OOIException {
    public: MissingPID(const char* msg) :
        OOIException("No pid read", 105, msg) {}
};

class UnknownPortAgentType : public OOIException {
    public: UnknownPortAgentType(const char* msg = "") :
        OOIException("Unknow Port Agent Type", 106, msg) {}
};

class DuplicateProcess : public OOIException {
    public: DuplicateProcess(const char* msg = "") :
        OOIException("Duplicate Process Detected", 107, msg) {}
};

class NotImplemented : public OOIException {
    public: NotImplemented(const char* msg = "") :
        OOIException("Command Not Implmented", 108, msg) {}
};

/*******************************************************************************
 * Logger Exceptions
 ******************************************************************************/
class LoggerUnknownLevel : public OOIException {
    public: LoggerUnknownLevel(const char* msg = "") :
        OOIException("Unknown Log Level", 201, msg) {}
};

class LoggerFileNotSet : public OOIException {
    public: LoggerFileNotSet(const char* msg = "") :
        OOIException("logfile name or base not specified", 202, msg) {}
};

class LoggerWriteError : public OOIException {
    public: LoggerWriteError(const char* msg = "") :
        OOIException("Failed to write to log file", 203, msg) {}
};

class LoggerOpenFailure : public OOIException {
    public: LoggerOpenFailure(const char* msg = "") :
        OOIException("Failed to open log file", 204, msg) {}
};


/*******************************************************************************
 * Socket Exceptions
 ******************************************************************************/
class SocketCreateFailure : public OOIException {
    public: SocketCreateFailure(const char* msg = "") :
        OOIException("Failed Socket Create:", 301, msg) {}
};

class SocketSelectFailure : public OOIException {
    public: SocketSelectFailure(const char* msg = "") :
        OOIException("Failed to select on socket:", 302, msg) {}
};

class SocketHostFailure : public OOIException {
    public: SocketHostFailure(const char* msg = "") :
        OOIException("Failed Host Lookup:", 303, msg) {}
};

class SocketConnectFailure : public OOIException {
    public: SocketConnectFailure(const char* msg = "") :
        OOIException("Failed Socket Connect:", 304, msg) {}
};


class SocketReadFailure : public OOIException {
    public: SocketReadFailure(const char* msg = "") :
        OOIException("Failed Socket Read:", 305, msg) {}
};

class SocketWriteFailure : public OOIException {
    public: SocketWriteFailure(const char* msg = "") :
        OOIException("Failed Socket Write:", 306, msg) {}
};

class SocketMissingConfig : public OOIException {
    public: SocketMissingConfig(const char* msg = "") :
        OOIException("Failed Socket Misconfigured:", 307, msg) {}
};

class SocketNotConnected : public OOIException {
    public: SocketNotConnected(const char* msg = "") :
        OOIException("Failed Socket Write:", 308, msg) {}
};

class SocketAlreadyConnected : public OOIException {
    public: SocketAlreadyConnected(const char* msg = "") :
        OOIException("Socket Already Connected:", 309, msg) {}
};

class SocketNotInitialized : public OOIException {
    public: SocketNotInitialized(const char* msg = "") :
        OOIException("Socket Not Initialized:", 310, msg) {}
};

/*******************************************************************************
 * Processes Launch Exceptions
 ******************************************************************************/
class LaunchCommandMissing : public OOIException {
    public: LaunchCommandMissing(const char* msg = "") :
        OOIException("No command specified in Spawn Process:", 401, msg) {}
};

class LaunchCommandFailed : public OOIException {
    public: LaunchCommandFailed(const char* msg = "") :
        OOIException("Failed To Spawn Process:", 402, msg) {}
};


/*******************************************************************************
 * Test Exceptions
 ******************************************************************************/
class TestPrereqFailed : public OOIException {
    public: TestPrereqFailed(const char* msg = "") :
        OOIException("Test Setup Failure:", 501, msg) {}
};


/*******************************************************************************
 * Packet Exceptions
 ******************************************************************************/
class PacketOverflow : public OOIException {
    public: PacketOverflow(const char* msg = "") :
        OOIException("Max packet size exceeded", 601, msg) {}
};

class PacketParamOutOfRange : public OOIException {
    public: PacketParamOutOfRange(const char* msg = "") :
        OOIException("parameter out of range", 603, msg) {}
};

class UnknownPacketType : public OOIException {
    public: UnknownPacketType(const char* msg = "") :
        OOIException("unknown packet type", 603, msg) {}
};



/*******************************************************************************
 * Publisher Exceptions
 ******************************************************************************/
class FileDescriptorNULL : public OOIException {
    public: FileDescriptorNULL(const char* msg = "") :
        OOIException("file descriptor is not set", 701, msg) {}
};

class PacketPublishFailure : public OOIException {
    public: PacketPublishFailure(const char* msg = "") :
        OOIException("failed to publish packet", 702, msg) {}
};

class UnknownPublisherType : public OOIException {
    public: UnknownPublisherType(const char* msg = "") :
        OOIException("unknown publisher type", 703, msg) {}
};

/*******************************************************************************
 * Port Agent Exceptions
 ******************************************************************************/
class UnknownState : public OOIException {
    public: UnknownState(const char* msg = "") :
        OOIException("We have landed in an unknown state ... kaboom!", 801, msg) {}
};

class NotInitialized : public OOIException {
    public: NotInitialized(const char* msg = "") :
        OOIException("Uninitialized socket operation", 802, msg) {}
};

#endif //EXCEPTION_H_
