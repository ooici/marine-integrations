/*******************************************************************************
 * Class: LogFile
 * Filename: log_file.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Object used for opening and rolling log files.  If an explicit file name is
 * given then we always open that file.  If a basename is given then we will
 * roll files daily.
 *
 * A useful feature of this class is that it will store the ofstream object in
 * the class so the file isn't reopened for every write.  It checks to see if
 * the file we should be writting too still exists, if not it will reopen the
 * file.  We are attempting to put all the safe file handling code in this
 * object.
 *
 * This class also overloads the stream insertion operator << so logs can
 * simply use this object to write to the log.
 * 
 * Usage:
 *
 *   #include "log_file.h"
 *
 *   LogFile file;
 *
 *   //  Explicitly set the log file name
 *   file.setFile("/tmp/testfile.log");
 *
 *   // Set basename for logs that will be rolled
 *   // the second option (extension) is optional
 *   file.setBase("/tmp/testfile", "log");
 *   
 *   // Get the stream object.
 *   ofstream outfile = file.getStreamObject();
 *
 *   // Or just use the stream insertion operator
 *   file << "Write something to the file";
 *
 ******************************************************************************/

#include "log_file.h"
#include "util.h"
#include "logger.h"
#include "exception.h"

#include <sstream>
#include <fstream>
#include <string>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#include <sys/time.h>

using namespace std;
using namespace logger;

/******************************************************************************
 * Method: Default Constructor
 * Description: Default constructor.
 ******************************************************************************/
LogFile::LogFile() {
	m_pOutStream = NULL;
}

/******************************************************************************
 * Method: Constructor
 * Description: Constructor to set log filename
 ******************************************************************************/
LogFile::LogFile(string filename) {
	m_pOutStream = NULL;
	setFile(filename);
}

/******************************************************************************
 * Method: Constructor
 * Description: Constructor to set log basename
 ******************************************************************************/
LogFile::LogFile(string filebase, string extention) {
	m_pOutStream = NULL;
	setBase(filebase, extention);
}

/******************************************************************************
 * Method: Constructor
 * Description: We only need to copy the strings becuase the file handle will
 * lazily open.
 ******************************************************************************/
LogFile::LogFile(const LogFile & rhs) {
	m_pOutStream = NULL;
	copy(rhs);
}

/******************************************************************************
 * Method: assignment operator
 * Description: We only need to copy the strings becuase the file handle will
 * lazily open.
 ******************************************************************************/
LogFile& LogFile::operator=(const LogFile & rhs) {
	copy(rhs);
	return *this;
}

/******************************************************************************
 * Method: copy
 * Description: Copy one LogFile object to another.
 ******************************************************************************/
void LogFile::copy(const LogFile & rhs) {
	m_sFileName = rhs.m_sFileName;
	m_sFileBase = rhs.m_sFileBase;
	m_sFileExtention = rhs.m_sFileExtention;

	m_pOutStream = NULL;
}

/******************************************************************************
 * Method: Destructor
 * Description: This is the mechanism we use to acutally write the log message.
 * Write messages to the log that are stored in the stringstream buffer.
 ******************************************************************************/
LogFile::~LogFile() {
	close();
}

/******************************************************************************
 * Method: close
 * Description: Force the log file handle to close if it is open.
 ******************************************************************************/
void LogFile::close()
{
    if(m_pOutStream) {
    	m_pOutStream->close();
    	delete m_pOutStream;
    	m_pOutStream = NULL;
    }
}

/******************************************************************************
 * Method: flush
 * Description: Force an iostream buffer flush
 ******************************************************************************/
void LogFile::flush()
{
    if(m_pOutStream)
        m_pOutStream->flush();
}

/******************************************************************************
 * Method: getLogFilename
 * Description: Get the filename to write logs too.  This is a derived name
 * if a log file name is specified then use that, otherwise generate a name
 * using the basename.
 * Return:
 *   string path to a log file.
 ******************************************************************************/
string LogFile::getFilename() {
    ostringstream out;
    
    if(m_sFileName.length())
        return m_sFileName;
    
    if(m_sFileBase.length()) {
        out << m_sFileBase << "." << fileDate();

        if(m_sFileExtention.length())
        	out << "." << m_sFileExtention;

    	return out.str();
    }
    
    // We have made it this far.  So it must be an error
	throw LoggerFileNotSet();

	// Just clearing a warning, but we will never get here.
    return string();
}

/******************************************************************************
 * Method: fileDate
 * Description: Build a date for the log file
 * Return:
 *   int serialized date YYYYMMDD
 ******************************************************************************/
int LogFile::fileDate()
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
 *   ofstream reference to an ofstream object appending to the log file.
 *
 * Exceptions:
 *   LoggerOpenFailure
 *   LoggerFileNotSet
 ******************************************************************************/
ofstream * LogFile::getStreamObject() {
	string file = getFilename();

	// If we have a log file to write to then lets work on getting the ostream
    if(! file.length())
        throw LoggerFileNotSet();

    // If we don't have an output stream create one.
    if(!m_pOutStream) {
    	m_pOutStream = new ofstream(file.c_str(), ios::out | ios::app);

    	if(!m_pOutStream || m_pOutStream->fail())
	        throw LoggerOpenFailure(strerror( errno ));
    }

    // Close the file if we havedetected an error
    if(m_pOutStream->fail())
    	close();

    // Explicitly check to see if the file still exists.  This will
    // protect us if the file is removed or the file name has changed
    // because it's time to roll.
    if(! file_exists(file.c_str()))
		close();
	
    // We can fall into this if the logfile was closed above OR this is
	// our first call to this method.
	if(! m_pOutStream->good() ) {
    	m_pOutStream = new ofstream(file.c_str(), ios::out | ios::app);
	    
	    if(m_pOutStream->fail())
	        throw LoggerOpenFailure();
	}
	    
    return m_pOutStream;
}

/******************************************************************************
 * Method: setFile
 * Description: Set the file name where log data should be written
 * Parameter:
 *   path - path to a file to write
 ******************************************************************************/
void LogFile::setFile(string path) {
	m_sFileName = path;
}

/******************************************************************************
 * Method: setBase
 * Description: Set the file name base and extenstion
 * Parameter:
 *   path - path to a file to write
 *   ext  - extention to add to the generated filename
 ******************************************************************************/
void LogFile::setBase(string path, string ext) {
	m_sFileBase = path;
	if(ext.length())
		m_sFileExtention = ext;
}

/******************************************************************************
 * Method: write
 * Description: Raw write to the log file.  Intended for binary data.
 * Parameter:
 *   buffer  - what we need to write.
 *   size - how big the buffer is
 ******************************************************************************/
bool LogFile::write(const char *buffer, uint16_t size) {
    ofstream *out = getStreamObject();
    out->write(buffer, size);
	return true;
}

/******************************************************************************
 * Method: operator<<
 * Description: overloaded stream operator so we can do logfile << "out";
 * Parameter:
 *   a  - what we need to write.
 ******************************************************************************/
LogFile & LogFile::operator<<(const string & a) {
	ofstream *out = getStreamObject();
    *out << a;
    return *this;
}

LogFile & LogFile::operator<<(std::ostream& (*pf) (std::ostream&)){
	ofstream *out = getStreamObject();
    *out << pf;
    return *this;
}
