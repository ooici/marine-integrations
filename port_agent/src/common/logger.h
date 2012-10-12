/*******************************************************************************
 * Class: Logger
 * Filename: logger.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Log object (singleton) for writting program logs.  Errors, by default, are
 * only stored internally as exceptions.  However the logger can be configured
 * to raise exceptions.
 *
 * The logger can also be configured to roll log files daily.  The date and
 * default log extension will automatically be added to the log file base name.
 *
 * Log Levels (default WARNING):
 *    ERROR, WARNING, INFO, DEBUG, DEBUG1, DEBUG2, DEBUG3, MESG
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
 *   Logger::SetRaiseErrors(true)
 ******************************************************************************/

#ifndef __LOGGER_H__
#define __LOGGER_H__

#include <fstream>
#include <sstream>
#include <string>
#include <stdio.h>

#include "exception.h"

using namespace std;

namespace logger {

	enum TLogLevel {ERROR, WARNING, INFO, DEBUG, DEBUG1, DEBUG2, DEBUG3, MESG};
	const TLogLevel DEFAULT_LOG_LEVEL = WARNING;
	#define LOG_EXTENSION "log"

	class Logger
	{
	public:
		/******************
		 * Public Methods *
		 *****************/

		// Ctor
		Logger();

		// Dtor
		virtual ~Logger();

		// Get a reference to an ostringstream object to store the log message in
		ostringstream& Get(TLogLevel level, const string &file, int line);

		// Return the generated logfile name.  If m_sLogFileName is set then
		// use that, otherwise try to generate a log file name from the base.
		string getLogFilename();

		// Explicitly close the log file handle.  Mostly used for testing.
		void close();
                
                void setCaller(const char *file, const char *function, int linenum);


		/******************
		 * Static Methods *
		 *****************/

		// Return a pointer to the singleton logger instance.
		static Logger* Instance();

		// Set the explict file name of the log to write too
		static void SetLogFile(const string& file);

		// Get the current logfile name
		static string GetLogFile();

		// Set the basename of the log file to facilitate log rotation (daily)
		static void SetLogBase(const string& file);

		// Get the current logbase name
		static string GetLogBase();

		// Set the log level using a string.  Note: default log level is INFO
		static void SetLogLevel(const string& file);

		// Set the logger so that it raises errors
		static void SetRaiseErrors(bool raise_error);

		// Get the raise error status
		static bool GetRaiseErrors();

		// Get the last exception
		static OOIException* GetError();

		// Incriment the current log level
		static void IncreaseLogLevel(const unsigned short levels = 1);

		// Decrease the current log level
		static void DecreaseLogLevel(const unsigned short levels = 1);

		// Get the current log level
		static TLogLevel GetLogLevel();

		// Get the current log level as a string
		static string ToString(TLogLevel level);

		// Write the current log buffer to the file
		static void Flush();

		// Write a message to the log file right away
		static void WriteLog(string message);

		// Clear the current singleton
		static void Reset();


		// Get the log level from a string.
		TLogLevel levelFromString(const string& level);

		// Get the log level from the enum.
		string levelToString(const TLogLevel level);

	protected:
		static Logger* m_pInstance;

		ostringstream* m_sLogoutStream;
		ofstream* m_sLogfileStream;

                string m_sCallerFile;
                string m_sCallerFunction;
                int m_iCallerLine;
                
		TLogLevel m_tLogLevel;
		string m_sLogFileBase;
		string m_sLogFileName;

		int m_iLastLogDate;

		bool m_bRaiseErrors;
		OOIException* m_pException;

	private:
		// Copy constructor
		Logger(const Logger&);

		// Overloaded assignment operator
		Logger& operator =(const Logger&);

		// Reset the error field.
		void clearError();

		// Get / Create a ofstream object to write the log file.
		ofstream* getLogStream();

		// Return a formatted date/time string for the log message
		string nowTime();

		// Return a formatted date for the log file name.
		int fileDate();
                
	};
}



#define LOG(level) \
    if (level > logger::Logger::GetLogLevel()) ; \
    else logger::Logger().Get(level, __FILE__, __LINE__)

#endif //__LOGGER_H__
    
