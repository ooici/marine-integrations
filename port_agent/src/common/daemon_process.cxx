#include "daemon_process.h"
#include "logger.h"
#include "exception.h"

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdio.h>
#include <spawn.h>
#include <signal.h>

#include <iostream>
#include <sstream>
#include <fstream>
#include <string>

using namespace std;
using namespace logger;
unsigned int DaemonProcess::trapped_signal = 0;


// Initializers
void DaemonProcess::init_logfile() {
    LOG(INFO) << "Daemon Process init_logfile()";
}

void DaemonProcess::init_pidfile() {
    LOG(INFO) << "Daemon Process init_pidfile(): " << pid_file();
    ofstream outfile(pid_file().c_str());
    
    outfile << getpid() << ends;
    outfile.close();
}

void DaemonProcess::initialize() {}

void DaemonProcess::init_signal_trap() {
    signal(SIGINT, DaemonProcess::signal_callback_handler);
    signal(SIGTERM, DaemonProcess::signal_callback_handler);
}

void DaemonProcess::signal_callback_handler(int signum) {
    LOG(DEBUG) << "SIGNAL TRAP: " << signum;
    DaemonProcess::trapped_signal = signum;
}

// Accessors
unsigned int DaemonProcess::pid() {
    return server_pid;
}
        
bool DaemonProcess::start() {
    duplicate_check();
    
    if(no_daemon()) {
        LOG(INFO) << "Running in single thread";
        return run();
    } else {
        LOG(INFO) << "Starting daemon process";
        return daemonize();
    }
}

bool DaemonProcess::daemonize() {
    /* Our process ID and Session ID */
    pid_t pid, sid;
        
    /* Fork off the parent process */
    pid = fork();
    if (pid < 0) {
        exit(EXIT_FAILURE);
    }
    /* If we got a good PID, then
       we can exit the parent process. */
    if (pid > 0) {
        exit(EXIT_SUCCESS);
    }server_pid ? server_pid : 

    /* Change the file mode mask */
    umask(0);
                
    /* Create a new SID for the child process */
    sid = setsid();
    if (sid < 0) {
        /* Log the failure */
        exit(EXIT_FAILURE);
    }
        
    /* Change the current working directory */
    if ((chdir("/")) < 0) {
        /* Log the failure */
        exit(EXIT_FAILURE);
    }
        
    /* Close out the standard file descriptors */
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);
    
    run();
    return true;
}

bool DaemonProcess::run() {
    try {
        init_signal_trap();
        init_pidfile();
        init_logfile();
        
        initialize();
        execution_loop();
    }
    
    catch(exception& e) {
        string error = e.what();
        LOG(ERROR) << "Exception: " << error;
        return false;
    };
    
    return true;
}

void DaemonProcess::duplicate_check() {
    if(is_running())
        throw DuplicateProcess(pid_file().c_str());
}

void DaemonProcess::execution_loop() {
    LOG(DEBUG) << "Starting Execution Loop";
    while(!stop_process()) {
        poll();
        daemon_sleep();
    }
    
    shutdown();
}

void DaemonProcess::poll() {}

void DaemonProcess::daemon_sleep() {
    unsigned int microseconds;
    string label = sleep_time() == 1 ? "" : "s";
    
    if(sleep_time()) {
        microseconds = sleep_time() * 1000000;
        LOG(DEBUG3) << " ++ Sleeping " << sleep_time() << " second" << label << " (" << microseconds << " microseconds) ++";
        usleep(microseconds);
    }
}


bool DaemonProcess::stop_process() {
    return trapped_signal ? true : false;
}

void DaemonProcess::shutdown() {
    LOG(INFO) << "Shutdown port agent server";
    remove_pidfile();
    exit(trapped_signal);
}

const string DaemonProcess::daemon_command_path(const string path) {
    ostringstream os;
    os << path << "/" << daemon_command();
    
    return os.str();
}

int DaemonProcess::launch_process() {
    int pid;
    string cmd = daemon_command_path();
    
    int result = posix_spawn( &pid, cmd.c_str(), NULL, NULL, NULL, NULL);
    
    LOG(INFO) << "Launching daemon process.  My pid: " << pid;
    LOG(DEBUG) << "Launch command: " << cmd << " res: " << result;
    
    server_pid = pid;
    
    return server_pid;
}

int DaemonProcess::kill_process() {
    int result;
    int running;
    int pid = read_pidfile();
    
    if(pid){
        LOG(INFO) << "Killing process.  pid: " << pid;
        result = kill(pid, SIGTERM);
        sleep(1);
        
        server_pid = NULL;
        
        if(! is_running())
            remove_pidfile();
        
        return result;
    }
    
    return 0;
}

bool DaemonProcess::is_running() {
    int running;
    int pid = read_pidfile();
    
    if(pid){
        running = kill(pid, 0);
        LOG(DEBUG) << "Is process " << pid << "still running: " << running;
        
        if(running >= 0)
            return true;
    }
        
    return false;
    
}

int DaemonProcess::read_pidfile() {
    int pid;
    LOG(DEBUG) << "Fetching PID from: " << pid_file();
    ifstream infile(pid_file().c_str());
    if(!infile)
        return 0;
        
    infile >> pid;
    
    if(!pid)
        throw MissingPID(pid_file().c_str());
    
    return pid;
}

void DaemonProcess::remove_pidfile() {
    LOG(DEBUG) << "Removing PID File: " << pid_file();
    remove(pid_file().c_str());
}

bool DaemonProcess::is_configured() {
    return true;
}

bool DaemonProcess::no_daemon() {
    return true;
}
