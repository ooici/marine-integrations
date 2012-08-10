/*******************************************************************************
 * Class: LogFile
 * Filename: log_file.h
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

#ifndef __LOG_FILE_H__
#define __LOG_FILE_H__

#include <fstream>
#include <sstream>
#include <string>
#include <stdio.h>

#include "exception.h"

using namespace std;

namespace logger {
	class LogFile
	{
		public:
			/******************
			 * Public Methods *
			 *****************/

		    // Ctor
		    LogFile(string filename);

    		// Ctor
	    	LogFile(string filebase, string extention);

			// Ctor
			LogFile();

			// Dtor
			virtual ~LogFile();

			// Copy constructor
			LogFile(const LogFile & rhs);

			// Overloaded assignment operator
			LogFile& operator=(const LogFile & rhs);

			// Overloading for the << operator TODO: Template function?
		    LogFile &operator<<(const string & a);
		    LogFile &operator<<(std::ostream& (*pf) (std::ostream&));

			// Return the generated logfile name.  If m_sLogFileName is set then
			// use that, otherwise try to generate a log file name from the base.
			string getFilename();

			// Return an output stream object.
			ofstream * getStreamObject();

			// Set the file name explicitly
			void setFile(string filename);

			// Set the file base name
			void setBase(string filebase, string fileext = "");

			// Explicitly close the log file handle.  Mostly used for testing.
			void close();

			// Force a buffer flush
			void flush();

			// Raw write to the output file
			bool write(const char *buffer, uint16_t size);

			// Get a date to use for file rotation.
			int fileDate();

		private:
			void copy(const LogFile & rhs);

			/******************
			 * Public Members *
			 *****************/

		protected:

		private:

		    ofstream * m_pOutStream;

		    string m_sFileName;
		    string m_sFileBase;
		    string m_sFileExtention;

	};

    // overload the output operator
	void operator<< (LogFile& log, int data);
}

#endif //__LOG_FILE_H__
    
