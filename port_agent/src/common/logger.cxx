/*******************************************************************************
 * Class: Logger
 * Filename: logger.cpp
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Log object for writting program logs.  By default all messages are sent to
 * stdout. 
 *
 * Log Levels (default WARNING):
 *    ERROR, WARNING, INFO, DEBUG, MESG
 * 
 * Usage:
 *
 *   #include "logger.h"
 *
 *   //  Explicitly set the log file name
 *   Logger::SetLogFile("/tmp/gtest.log");
 *
 *   // Set the base logfile path so that the logger can roll files.  When
 *   // using this interface the logger will automatically append a date and
 *   // extension to the file name.  If SetLogFile is called, then this option
 *   // is ignored.
 *   Logger::SetLogBase("/tmp/gtest");
 *   
 *   Logger::SetLogLevel("DEBUG");
 *   Logger::IncrementLogLevel(3);
 *
 *   LOG(DEBUG) << "This is a log message";
 *
 *   Error Handling
 *
 *   Log errors are stored internally and can be accessed via an interface.
 *
 *   // Return true if the last call caused an error
 *   Logger::HasError();
 *
 *   // Returns an exception
 *   Logger::LastError();
 *
 *   Optionally, errors can be raised if the logger is configured to do so.
 *   The default behavior is to *NOT* raise errors.  This is so writing the
 *   log doesn't cause a port agent to stop working.  Because of this it is the
 *   downstream processes' job to check for errors.
 *
 *   Logger::RaiseErrors(true)
 * 
 ******************************************************************************/

#include "logger.h"
#include "util.h"
#include "exception.h"

#include <sstream>
#include <iostream>
#include <fstream>
#include <string>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#include <sys/time.h>

using namespace std;
using namespace logger;

// Global static pointer used to ensure a single instance of the class.
Logger* Logger::m_pInstance = NULL;

/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: Just set some default values.
 ******************************************************************************/
Logger::Logger()
{
    m_tLogLevel = DEFAULT_LOG_LEVEL;
    m_bRaiseErrors = false;
    m_pException = NULL;
    m_iLastLogDate = 0;
    m_sLogoutStream = new ostringstream();
    m_sLogfileStream = NULL;
}


/******************************************************************************
 * Method: Destructor
 * Description: This is the mechanism we use to acutally write the log message.
 * Write messages to the log that are stored in the stringstream buffer.
 ******************************************************************************/
Logger::~Logger() {
    Flush();
}

/******************************************************************************
 * Method: close
 * Description: Force the log file handle to close if it is open.
 ******************************************************************************/
void Logger::close()
{
    if(m_sLogfileStream) {
    	//m_sLogfileStream->close();
	    delete m_sLogfileStream;
	    m_sLogfileStream = NULL;
    }
}

/******************************************************************************
 * Method: getLogFilename
 * Description: Get the filename to write logs too.  This is a derived name
 * if a log file name is specified then use that, otherwise generate a name
 * using the basename.
 * Return:
 *   string path to a log file.
 ******************************************************************************/
string Logger::getLogFilename() {
    ostringstream out;
    
    if(m_sLogFileName.length())
        return m_sLogFileName;
    
    if(m_sLogFileBase.length()) {
        out << m_sLogFileBase << "." << fileDate() << "." << LOG_EXTENSION;
	return out.str();
    }
    
    // We have made it this far.  So it must be an error
    if(m_bRaiseErrors) {
        clearError();
	throw LoggerFileNotSet();
    } else {
	m_pException = new LoggerFileNotSet();
    }
    
    return string();
}

/******************************************************************************
 *   STATIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Flush
 * Description: If we have anything in our buffer, write it to the log and then
 * reset the buffer.
 ******************************************************************************/
void Logger::Flush() {
    Logger* instance = Logger::Instance();
    instance->clearError();
    
    WriteLog(instance->m_sLogoutStream->str());
    
    if(instance->m_sLogoutStream)
        delete instance->m_sLogoutStream;
        
    instance->m_sLogoutStream = new ostringstream();
}

/******************************************************************************
 * Method: WriteLog
 * Description: Write a log message to the log file
 ******************************************************************************/
void Logger::WriteLog(string message) {
    Logger* instance = Logger::Instance();
    
    instance->clearError();
    
    if(message.length()) {
        ofstream* logout = instance->getLogStream();
        if(logout){
	    *logout << message << endl;
	    if(logout->good())
	        return;
    
            // We have made it this far.  So it must be an error
            if(instance->m_bRaiseErrors) {
	        throw LoggerWriteError();
            } else {
                instance->clearError();
		instance->close();
	        instance->m_pException = new LoggerWriteError();
            }
        }
    }
}

/******************************************************************************
 * Method: Instance
 * Description: Get a pointer to the logger singleton instance.
 * Return:
 *   Logger * pointer to the instance.
 ******************************************************************************/
Logger* Logger::Instance()
{
    if(!m_pInstance)
        m_pInstance = new Logger();
	
    return m_pInstance;
}

/******************************************************************************
 * Method: Reset
 * Description: Clear out the current logger singleton.  Useful for testing.
 ******************************************************************************/
void Logger::Reset()
{
    if(m_pInstance)
        delete m_pInstance;
	
    m_pInstance = new Logger();
}

/******************************************************************************
 * Method: SetLogFile
 * Description: Set the logfile name
 * Parameters:
 *   string file - path to the log file
 ******************************************************************************/
void Logger::SetLogFile(const string& file) {
    Logger::Instance()->m_sLogFileName = file;
}

/******************************************************************************
 * Method: GetLogFile
 * Description: Get the current logfile name
 ******************************************************************************/
string Logger::GetLogFile() {
    return Logger::Instance()->m_sLogFileName;
}

/******************************************************************************
 * Method: SetLogBase
 * Description: Set the logbase name
 * Parameters:
 *   string file - path to the log base
 ******************************************************************************/
void Logger::SetLogBase(const string& file) {
    Logger::Instance()->m_sLogFileBase = file;
}

/******************************************************************************
 * Method: GetLogBase
 * Description: Get the current logbase name
 ******************************************************************************/
string Logger::GetLogBase() {
    return Logger::Instance()->m_sLogFileBase;
}

/******************************************************************************
 * Method: GetLogLevel
 * Description: Get the current log level
 ******************************************************************************/
TLogLevel Logger::GetLogLevel() {
    return Logger::Instance()->m_tLogLevel;
}

/******************************************************************************
 * Method: IncreaseLogLevel
 * Description: Increment the current log level.  
 * Parameters:
 *   unsigned short levels - number of levels to increase the log level.
 ******************************************************************************/
void Logger::IncreaseLogLevel(const unsigned short levels) {
    Logger* instance = Logger::Instance();
    
    int index = instance->m_tLogLevel + levels > 7 ? 7 : instance->m_tLogLevel + levels;
    instance->m_tLogLevel = TLogLevel(index);
}

/******************************************************************************
 * Method: DecreaseLogLevel
 * Description: Decrease the current log level.  
 * Parameters:
 *   unsigned short levels - number of levels to decrease the log level.
 ******************************************************************************/
void Logger::DecreaseLogLevel(const unsigned short levels) {
    Logger* instance = Logger::Instance();
    
    int index = instance->m_tLogLevel - levels < 0 ? 0 : instance->m_tLogLevel - levels;
    instance->m_tLogLevel = TLogLevel(index);
}

/******************************************************************************
 * Method: SetLogLevel
 * Description: Set the log level to the string passed in.
 * Parameters:
 *   string level - String representation of the desired log level
 *
 * Error:
 *   
 ******************************************************************************/
void Logger::SetLogLevel(const string& level) {
    Logger* instance = Logger::Instance();
    instance->clearError();
    
    TLogLevel newLevel = instance->levelFromString(level);
    
    if(!GetError())
        instance->m_tLogLevel = newLevel;
}
    
/******************************************************************************
 * Method: SetRaiseErrors
 * Description: Set the raise errors flag
 * Parameters:
 *   bool raise_error - should errors be raised?
 ******************************************************************************/
void Logger::SetRaiseErrors(bool raise_error) {
    Logger* instance = Logger::Instance();
    
    instance->m_bRaiseErrors = raise_error;
}

/******************************************************************************
 * Method: GetRaiseErrors
 * Description: Get the raise errors flag
 * Return:
 *   bool raise error status
 ******************************************************************************/
bool Logger::GetRaiseErrors() {
    Logger* instance = Logger::Instance();
    
    return instance->m_bRaiseErrors;
}

/******************************************************************************
 * Method: GetError
 * Description: Get the last error
 * Return:
 *   OOIException* the last exception object created
 ******************************************************************************/
OOIException* Logger::GetError() {
    Logger* instance = Logger::Instance();
    return instance->m_pException;
}



/******************************************************************************
 * Method: Get
 * Description: Construct a log message timestamp using an ostringstream.
 *              DEBUG messages get indented.
 * Parameters:
 *   TLogLevel level - Log level of the current message
 *   file - filename of caller
 *   fun - function name of caller
 *   line - line number of caller
 * Return:^^
 *   ostringstream object with the message buffered.
 ******************************************************************************/
ostringstream& Logger::Get(TLogLevel level, const string &file, int line)
{
    Logger* instance = Logger::Instance();
    ostringstream *os = instance->m_sLogoutStream;
    
    if(level <= GetLogLevel()) {
        *os << instance->nowTime() << " " << file << " " << " [" << line << "] ";
        *os << " " << instance->levelToString(level) << ": ";
    
        // Indent debug messages
	if(level < MESG && level >= DEBUG)
            *os << string(level > DEBUG ? level - DEBUG : 0, '\t');
    }
    
    return *os;
}


/******************************************************************************
 *   PRIVATE METHODS
 ******************************************************************************/


/******************************************************************************
 * Method: NowTime
 * Description: Build a timestamp for the log message
 * Return:
 *   string with time stamp
 ******************************************************************************/
string Logger::nowTime()
{
    char buffer[32];
    time_t t;
    time(&t);
    tm r = {0};
    strftime(buffer, sizeof(buffer), "%Y-%b-%d %X", localtime_r(&t, &r));
    struct timeval tv;
    gettimeofday(&tv, 0);
    char result[100] = {0};
    sprintf(result, "%s.%03ld", buffer, (long)tv.tv_usec / 1000); 
    return result;
}

/******************************************************************************
 * Method: fileDate
 * Description: Build a date for the log file
 * Return:
 *   int serialized date YYYYMMDD
 ******************************************************************************/
int Logger::fileDate()
{
    char buffer[11];
    time_t t;
    time(&t);
    tm r = {0};
    strftime(buffer, sizeof(buffer), "%Y%m%d", localtime_r(&t, &r));
    return atoi(buffer);
}

/******************************************************************************
 * Method: getLogStream
 * Description: return a pointer to an ofstream object for writing to a log
 * file (in append mode).  If the failure bit is set, or the log file no longer
 * exists we will create a new ofstream object.
 * 
 * Return:
 *   ofstream* pointer to an ofstream object appending to the log file.
 *
 * Exceptions:
 *   LoggerOpenFailure
 *   LoggerFileNotSet
 ******************************************************************************/
ofstream* Logger::getLogStream() {
    string file = getLogFilename();
    
    // If we have a log file to write to then lets work on getting the ostream
    if(file.length()) {
	// We already have a file handle.  Let's try to see if it's good.
	if(m_sLogfileStream) {
	    
	    // The fail bit is set for some reason.
	    if(m_sLogfileStream->fail()) {
		close();
	    }
	    
	    // Explicitly check to see if the file still exists.  This will
	    // protect us if the file is removed or the file name has changed
	    // because it's time to roll.
	    if(! file_exists(file.c_str())) {
		close();
	    }
	}
	
        // We can fall into this if the logfile was closed above OR this is
	// our first call to this method.
	if(!m_sLogfileStream) {
	    m_sLogfileStream = new ofstream;
	    m_sLogfileStream->open(file.c_str(), ios::out | ios::app);
	    
	    if(m_sLogfileStream->fail()) {
                if(m_bRaiseErrors) {
                    clearError();
	            throw LoggerOpenFailure();
                } else {
	            m_pException = new LoggerOpenFailure();
                }
	    }
	}
	    
        return m_sLogfileStream;
    }
    
    // We have made it this far.  So it must be an error
    if(m_bRaiseErrors) {
        clearError();
	throw LoggerFileNotSet();
    } else {
	m_pException = new LoggerFileNotSet();
    }
    
    return NULL;
}


/******************************************************************************
 * Method: clearError
 * Description: Clear the last exception out of the instance.
 ******************************************************************************/
void Logger::clearError() {
    if(m_pException) 
        delete m_pException;
    m_pException = NULL;
}

/******************************************************************************
 * Method: levelToString
 * Description: Convert a log level to a string representation
 * Parameters:
 *   TLogLevel level - Log level of the current message
 * Return:
 *   string representation of the log level
 ******************************************************************************/
string Logger::levelToString(TLogLevel level)
{
    static const char* const buffer[] = {"ERROR", "WARNING", "INFO", "DEBUG",
                                         "DEBUG1", "DEBUG2", "DEBUG3", "MESG"};
    return buffer[level];
}

/******************************************************************************
 * Method: levelFromString
 * Description: Get a log level from a string. Unknown log levels will cause an
 * error and the log level will not be changed.
 * Parameters:
 *   string level - log level
 * Return:
 *   TLogLevel value returned
 ******************************************************************************/
TLogLevel Logger::levelFromString(const string& level)
{
    if (level == "MESG")
        return MESG;
    if (level == "DEBUG3")
        return DEBUG3;
    if (level == "DEBUG2")
        return DEBUG2;
    if (level == "DEBUG1")
        return DEBUG1;
    if (level == "DEBUG")
        return DEBUG;
    if (level == "INFO")
        return INFO;
    if (level == "WARNING")
        return WARNING;
    if (level == "ERROR")
        return ERROR;
    
    LOG(ERROR) << "Unknown log level: " << level;

    // We have made it this far.  So it must be an error
    if(m_bRaiseErrors) {
	    throw LoggerUnknownLevel();
    } else {
	    clearError();
	    m_pException = new LoggerUnknownLevel();
    }

    return WARNING;
}

void Logger::setCaller(const char *file, const char *function, int lineno) {
    m_sCallerFile = file;
    m_sCallerFunction = function;
    m_iCallerLine = lineno;
    
}
