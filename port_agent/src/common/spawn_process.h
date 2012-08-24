#ifndef SPAWN_PROCESS_H
#define SPAWN_PROCESS_H

#include <string>
#include <list>

#define SH "/bin/sh"

using namespace std;

class SpawnProcess {
    public:
        SpawnProcess() : m_pid(0) {}
        SpawnProcess(string cmd) : m_pid(0), m_cmd(cmd) {}
        SpawnProcess(string cmd, unsigned int argc, char *first_arg,...); 
        SpawnProcess(string cmd, unsigned int argc, char **argv );
        
        void set_output_file(string outfile) {m_output_file = outfile;}
        unsigned int pid() { return m_pid; }
        string cmd() { return m_cmd; }
        unsigned int argc();
        
        string cmd_as_string();
        
        bool is_running();
        
        bool run();
        
    private:
        unsigned int m_pid;
        string m_cmd;
        string m_output_file;
        list<string> m_cmd_argv;
};

#endif //SPAWN_PROCESS_H

