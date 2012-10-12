#include "spawn_process.h"
#include "logger.h"
#include "exception.h"

#include <sys/stat.h>
#include <spawn.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>

#include <iostream>
#include <sstream>
#include <string>
#include <string.h>

using namespace std;
using namespace logger;


SpawnProcess::SpawnProcess(string cmd, unsigned int argc, char *first_arg, ...) {
    m_pid = 0;
    m_cmd = cmd;
    
    m_cmd_argv.push_back(first_arg);
    
    va_list listPointer;
    va_start( listPointer, first_arg );
    
    for(int i = 0; i < argc - 1; i++) {
        char *arg = va_arg( listPointer, char* );
        LOG(DEBUG) << " -- push arg: " << arg;
        m_cmd_argv.push_back(arg);
    }
    
    va_end( listPointer );
}

SpawnProcess::SpawnProcess(string cmd, unsigned int argc, char **argv) {
    int i;
    
    m_pid = 0;
    m_cmd = cmd;
    
    for(int i = 0; i < argc; i++) {
        LOG(DEBUG) << " -- push arg: " << argv[i];
        m_cmd_argv.push_back(argv[i]);
    }
}

unsigned int SpawnProcess::argc() {
    return m_cmd_argv.size();
}

string SpawnProcess::cmd_as_string() {
    stringstream cmd;
    list<string>::iterator i;
    
    LOG(DEBUG) << "cma_as_string: size: " << m_cmd_argv.size();
    cmd << m_cmd << " ";
    for(i=m_cmd_argv.begin(); i != m_cmd_argv.end(); ++i)
        cmd << *i << " "; 
    
    //cmd << ends;
    
    return cmd.str();
}

bool SpawnProcess::is_running() {
    int retval;
    int status = -1;

    if(! m_pid)
        return false;
    
    int wpid = waitpid(m_pid, &status, WNOHANG);
    LOG(DEBUG) << "PID: " << m_pid
               << " pid ret: " << wpid 
               << " status: " << status; 
    
    return wpid == 0 ? true : false;
}

bool SpawnProcess::run() {
    int pid;
    char **argv = new char*[m_cmd_argv.size()+2];
    list<string>::iterator i;
    int result;
    int j = 0;
    
    LOG(DEBUG) << "Spawn process: " << cmd_as_string();
    
    if(! m_cmd.length())
        throw LaunchCommandMissing();
    
    //
    // Build the argv array
    //
    argv[j++] = strdup(m_cmd.c_str());
    
    for(i=m_cmd_argv.begin(); i != m_cmd_argv.end(); ++i)
        argv[j++] = strdup(i->c_str());
        
    // The last argument in argv needs to be a null element.
    argv[j] = NULL;
 
    // Setup file IO
    posix_spawn_file_actions_t file_actions;
    posix_spawn_file_actions_init(&file_actions);
    
    if(m_output_file.length()) {
        LOG(INFO) << "Writing output to " << m_output_file;
        result = posix_spawn_file_actions_addopen(&file_actions, 1, m_output_file.c_str(), O_WRONLY|O_CREAT, S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH);
        LOG(DEBUG) << "addopen result: " << result;
    }
    
    result = posix_spawn_file_actions_adddup2(&file_actions, 1, 2);
    LOG(DEBUG) << "adddup2 result: " << result;

    result = posix_spawn_file_actions_addclose(&file_actions, 0);
    LOG(DEBUG) << "addclose result: " << result;
    
    result = posix_spawnp(&pid, m_cmd.c_str(), &file_actions, NULL, argv, NULL);
    LOG(DEBUG) << "posix_spawn result: " << result << " PID: " << m_pid;
    
    if(result == 0) 
        m_pid = pid;
    else
        throw LaunchCommandFailed();
    
    
    // Garbage collection
    if(argv) {
        for(j = 0; j < m_cmd_argv.size(); j++)
            if(argv[j])
                delete [] argv[j];
        
        delete [] argv;
    }
    posix_spawn_file_actions_destroy(&file_actions);
    
    return result == 0 ? true : false;
}

