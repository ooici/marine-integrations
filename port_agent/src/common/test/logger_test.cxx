/*******************************************************************************
 * Filename: logger_test.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Test all of the logger library functionallity.
 ******************************************************************************/

#include "common/exception.h"
#include "common/logger.h"
#include "common/util.h"
#include "gmock/gmock.h"

#include <iostream>
#include <sstream>
#include <fstream>

using namespace std;
using namespace logger;


#define LOGFILE "/tmp/gtest_logger.log"
#define LOGBASE "/tmp/gtest_logger"

class LoggerTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::Reset();
        }
    
        virtual void TearDown() {
        }
    
        ~LoggerTest() {
        }
};

/* Test Construction and Option setting */
TEST_F(LoggerTest, CtorTest) {
    // Set the log file and check it was set correctly
    Logger::SetLogFile(LOGFILE);
    EXPECT_EQ(Logger::GetLogFile(), LOGFILE);
    
    // Test Reset
    Logger::Reset();
    EXPECT_EQ(Logger::GetLogFile(), "");
    
    // Set the log base and check it was set correctly
    Logger::SetLogBase(LOGBASE);
    EXPECT_EQ(Logger::GetLogBase(), LOGBASE);
    
    // Check the raise error flag
    EXPECT_FALSE(Logger::GetRaiseErrors());
    Logger::SetRaiseErrors(true);
    EXPECT_TRUE(Logger::GetRaiseErrors());
}


/* Test Log Level Transitions */
TEST_F(LoggerTest, LogLevelTest) {
    // Check the default log level
    EXPECT_EQ(Logger::GetLogLevel(), WARNING);
    
    // Test increase log levels
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), INFO);
    
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG);
    
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG1);
    
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG2);
    
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG3);
    
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), MESG);
    
    // We have exceeded the max log level, we should stay at the max
    Logger::IncreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), MESG);
    
    //  Lets reset so we can test decreasing the level    
    Logger::Reset();
    EXPECT_EQ(Logger::GetLogLevel(), WARNING);
    
    Logger::DecreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), ERROR);
    
    // We have exceeded the minimum log level, we should stay at error
    Logger::DecreaseLogLevel();
    EXPECT_EQ(Logger::GetLogLevel(), ERROR);
    
    //  Lets reset so we can test multi level increase
    Logger::Reset();
    EXPECT_EQ(Logger::GetLogLevel(), WARNING);
    
    Logger::IncreaseLogLevel(2);
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG);
    
    //  Lets reset so we can try to explicitly set the log level
    Logger::Reset();
    EXPECT_EQ(Logger::GetLogLevel(), WARNING);
    
    Logger::SetLogLevel("DEBUG");
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG);
    
    // Now try and set a bad debug value.  Error should be set and the log level
    // should stay as it was before the call.
    Logger::SetLogLevel("BLOWUP");
    EXPECT_EQ(Logger::GetLogLevel(), DEBUG);
    ASSERT_TRUE(Logger::GetError()); 
    //EXPECT_EQ(Logger::GetError()->errno(), 201); 
   
}

// test filename, both static and dynamic
TEST_F(LoggerTest, FilenameTest) {
    // Build a string to be what we think the logfile should be
    char buffer[11];
    time_t t;
    time(&t);
    tm r = {0};
    strftime(buffer, sizeof(buffer), "%Y%m%d", localtime_r(&t, &r));
    int currentDate = atoi(buffer);
    ostringstream out;
    out << LOGBASE << "." << currentDate << ".log";

    // Start by checking the log file, but nothing has been set.  This should be
    // an error.
    Logger::Reset();
    EXPECT_FALSE(Logger::Instance()->getLogFilename().length());
    ASSERT_TRUE(Logger::GetError());
    //EXPECT_EQ(Logger::GetError()->errno(), 202);
    
    // Set the log file and check it was set correctly
    Logger::SetLogFile(LOGFILE);
    EXPECT_EQ(Logger::Instance()->getLogFilename(), LOGFILE);
    
    // Set the log base and check to ensure we still get the original log file
    // since it takes precidence
    Logger::SetLogBase(LOGBASE);
    EXPECT_EQ(Logger::Instance()->getLogFilename(), LOGFILE);
    
    // Reset and try the log base again.  We should get a new logfile name
    Logger::Reset();
    Logger::SetLogBase(LOGBASE);
    EXPECT_TRUE(Logger::Instance()->getLogFilename().length());
    EXPECT_EQ(Logger::Instance()->getLogFilename(), out.str());
}

// Test log writes at different levels
TEST_F(LoggerTest, LogOutputTest) {
    string result;
    remove_file(LOGFILE);
    
    // First let's true to write when no file has been set.  This should
    // set an error.
    LOG(ERROR) << "Error Message";
    EXPECT_FALSE(Logger::Instance()->getLogFilename().length());
    ASSERT_TRUE(Logger::GetError());
    //EXPECT_EQ(Logger::GetError()->errno(), 202);
    
    // That worked so let's set the log file and try to write something.
    Logger::SetLogFile(LOGFILE);
    LOG(ERROR) << "Error Message";
    result = read_file(LOGFILE);
    EXPECT_THAT(result, testing::EndsWith("ERROR: Error Message\n"));
    
    // Try to log a message above our current log level
    remove_file(LOGFILE);
    Logger::Reset();
    Logger::SetLogFile(LOGFILE);
    LOG(DEBUG) << "Debug Message";
    result = read_file(LOGFILE);
    EXPECT_EQ(result.length(), 0);
    
    // Now increase the log level and try again.
    Logger::SetLogLevel("DEBUG");
    LOG(DEBUG) << "Debug Message";
    result = read_file(LOGFILE);
    EXPECT_TRUE(result.length());
}

// test log write on a closed file handle
TEST_F(LoggerTest, ClosedFileTest) {
    string result;
    
    // Now let's make sure that the file is appending not overwriting.  Just check for two \n
    Logger::Reset();
    remove_file(LOGFILE);
    Logger::SetLogFile(LOGFILE);
    LOG(ERROR) << "Error Message";
    Logger::Instance()->close();
    LOG(ERROR) << "Error Message";
    result = read_file(LOGFILE);
    

}    

// test log write when file removed
TEST_F(LoggerTest, RemovedFileTest) {
    string result;
    
    // Start a log file and log a message
    Logger::SetLogFile(LOGFILE);
    LOG(ERROR) << "Error Message";
    result = read_file(LOGFILE);
    EXPECT_THAT(result, testing::EndsWith("ERROR: Error Message\n"));
    
    // Remove the file and the logger should self repair and open the file again.
    remove_file(LOGFILE);
    LOG(ERROR) << "Error Message";
    result = read_file(LOGFILE);
    EXPECT_THAT(result, testing::EndsWith("ERROR: Error Message\n"));
}

// test log write when file exists
TEST_F(LoggerTest, FileExistsTest) {
    string result;
    
    remove_file(LOGFILE);
    Logger::SetLogFile(LOGFILE);
    LOG(ERROR) << "Error Message";
    Logger::Reset();
    Logger::SetLogFile(LOGFILE);
    LOG(ERROR) << "Error Message";
    result = read_file(LOGFILE);
    EXPECT_THAT(result, testing::MatchesRegex(".*\n.*\n"));
}

// test permission denied
TEST_F(LoggerTest, PermissionDeniedTest) {
    string result;
    Logger::SetLogFile("/tmp");
    LOG(ERROR) << "Error Message";
    ASSERT_TRUE(Logger::GetError());
    //EXPECT_EQ(Logger::GetError()->errno(), 204);
}

// test writing to a derived filename
TEST_F(LoggerTest, DerivedLogFileTest) {
    string result;
    // Build a string to be what we think the logfile should be
    char buffer[11];
    time_t t;
    time(&t);
    tm r = {0};
    strftime(buffer, sizeof(buffer), "%Y%m%d", localtime_r(&t, &r));
    int currentDate = atoi(buffer);
    ostringstream out;
    out << LOGBASE << "." << currentDate << ".log";
    
    Logger::SetLogBase(LOGBASE);
    LOG(ERROR) << "Error Message";
    result = read_file(out.str().c_str());
    EXPECT_THAT(result, testing::EndsWith("ERROR: Error Message\n"));
}





