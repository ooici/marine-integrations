#include "exception.h"
#include "logger.h"
#include "spawn_process.h"
#include "gtest/gtest.h"

#define LS "/bin/ls"
#define ECHO "/bin/echo"
#define OUTFILE "/tmp/data.out"

using namespace logger;
using namespace std;

class SpawnProcessTest : public testing::Test {
    
    protected:
        virtual void SetUp() {
            Logger::SetLogFile("/tmp/gtest.log");
            Logger::SetLogLevel("DEBUG");
            
            LOG(INFO) << "************************************************";
            LOG(INFO) << "            Process Test Start Up";
            LOG(INFO) << "************************************************";
            
            remove_file(OUTFILE);
        }
        
        string read_file(const string filename) {
            LOG(INFO) << "Open result file: " << filename;
            ifstream infile(filename.c_str());
            stringstream str;
            char in;
            while(infile.get(in)) {
                str << in;
            }

            LOG(INFO) << "READ FILE RESULT: " << str.str();
            return str.str();
        }
        
        void remove_file(const string filename) {
            stringstream cmd;
            cmd << "rm -f " << filename;
            LOG(INFO) << "run command: " << cmd.str();
            LOG(INFO) << "run command: " << cmd.str() << ".2";
            system(cmd.str().c_str());
        }
};

/* Test default ctor */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessCtor) {
    SpawnProcess process;
    process.set_output_file(OUTFILE);
    
    EXPECT_EQ(process.pid(), 0);
    EXPECT_EQ(process.argc(), 0);
    EXPECT_EQ(process.cmd().length(), 0);
}

/* Test ctor cmd only */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessSingleCmd) {
    SpawnProcess process(LS);
    process.set_output_file(OUTFILE);
    process.run();
    
    EXPECT_TRUE(process.pid());
    EXPECT_EQ(process.argc(), 0);
    EXPECT_EQ(process.cmd(), LS);
}


/* Test is running method */
TEST_F(SpawnProcessTest, SpawnProcessIsRunning) {
    SpawnProcess process("/bin/sleep", 1, "1");
    
    process.run();
    EXPECT_TRUE(process.is_running());
    
    LOG(DEBUG) << "Waiting for process " << process.pid() << " to die";
    sleep(2);
    
    EXPECT_FALSE(process.is_running());
}

/* Test ctor cmd with args */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessCmdWithArgs) {
    SpawnProcess process(LS, 1, "-h");
    process.set_output_file(OUTFILE);
    stringstream cmd;
    cmd << LS << " -h ";
    
    process.run();
    sleep(1);
    
    EXPECT_FALSE(process.is_running());
    
    string output = read_file(OUTFILE);
    LOG(DEBUG) << "OUTPUT: " << output;
    
    EXPECT_TRUE(process.pid());
    EXPECT_EQ(process.argc(), 1);
    EXPECT_EQ(process.cmd(), LS);
    EXPECT_EQ(process.cmd_as_string(), cmd.str());
}

/* Test ctor cmd with array args */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessCmdWithArrayArgs) {
    char *args[] = {"-h"};
    SpawnProcess process(LS, 1, args);
    
    LOG(DEBUG) << "SpawnProcessCmdWithArrayArgs";
    process.set_output_file(OUTFILE);
    stringstream cmd;
    cmd << LS << " -h ";
    
    process.run();
    sleep(1);
    
    string output = read_file(OUTFILE);
    LOG(DEBUG) << "OUTPUT: " << output;
    
    
    EXPECT_TRUE(process.pid());
    EXPECT_EQ(process.argc(), 1);
    EXPECT_EQ(process.cmd(), LS);
    EXPECT_EQ(process.cmd_as_string(), cmd.str());
    EXPECT_TRUE(output.length());
}

/* Test command line args to echo */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessCmdEcho) {
    SpawnProcess process(ECHO, 2, "testing", ">boo");
    process.set_output_file(OUTFILE);
    
    process.run();
    sleep(1);
    
    string output = read_file(OUTFILE);
    LOG(DEBUG) << "OUTPUT: " << output;
    
    EXPECT_TRUE(process.pid());
    EXPECT_EQ(process.argc(), 2);
    EXPECT_EQ(output, "testing >boo\n");
}

/* Test command line args to echo with array*/
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessCmdEchoArray) {
    char *args[] = {"testing", ">boo"};
    SpawnProcess process(ECHO, 2, args);
    process.set_output_file(OUTFILE);
    
    process.run();
    sleep(1);
    
    string output = read_file(OUTFILE);
    LOG(DEBUG) << "OUTPUT: " << output;
    
    EXPECT_TRUE(process.pid());
    EXPECT_EQ(process.argc(), 2);
    EXPECT_EQ(output, "testing >boo\n");
}

/* Test missing command */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessMissingCmd) {
    SpawnProcess process;
    process.set_output_file(OUTFILE);
    
    try {
        process.run();
    }
    catch(LaunchCommandMissing &e) {
        LOG(INFO) << "Expected exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 401);
        return;
    };
    
    EXPECT_FALSE(true);
}

/* Test command not found */
TEST_F(SpawnProcessTest, DISABLED_SpawnProcessFailedCmd) {
    SpawnProcess process("/bin/foo", 1, "-h");
    process.set_output_file(OUTFILE);
    
    try {
        process.run();
    }
    catch(LaunchCommandFailed &e) {
        LOG(INFO) << "Expected exception caught: " << e.what();
        EXPECT_EQ(e.errno(), 402);
        return;
    };
    
    EXPECT_FALSE(true);
}



