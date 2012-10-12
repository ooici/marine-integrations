/*******************************************************************************
 * Class: DaemonProcess
 * Filename: daemon_process.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Base class for daemon processes. This class must be extended because it
 * contains virtual classes. 
 *
 * Processes using this class have the ability (default behavior) to run in
 * daemon mode.  When operating in this mode the process is detached from the
 * current process and attatches to the init.  All STDIO streams are closed
 * so don't write to these streams.
 *
 * This process run controlled so it only can run one instance of this process
 * which is controlled by the pid file.
 *
 * It is also possible to run this process in a single thread which does not
 * detatch.  If the no_daemon method returns true the proess is run in single
 * thread mode.
 ******************************************************************************/

#ifndef DAEMON_PROCESS_H
#define DAEMON_PROCESS_H

#include <string>
using namespace std;

#define DEFAULT_SLEEP_TIME 1

class DaemonProcess {
    public:
        DaemonProcess() : server_pid(0) {}
        unsigned int pid();
        
        bool start();
        int launch_process();
        int kill_process();
        bool is_running();
        
    protected:
        bool daemonize();
        bool run();
        
        virtual void initialize();
        
        void init_logfile();
        void init_pidfile();
        void init_signal_trap();
        
        virtual const string pid_file() = 0;
        
        static void signal_callback_handler(int signum);
        void execution_loop();
        virtual void poll();
        
        bool stop_process();
        virtual void shutdown();

        virtual const string daemon_command_path(const string path=".");
        virtual const string daemon_command() = 0;
        
        void remove_pidfile();
        virtual bool is_configured();
        
        void daemon_sleep();
        virtual float sleep_time() { return float(DEFAULT_SLEEP_TIME); }
        
        virtual void duplicate_check();
        
        virtual bool no_daemon();
        
    private:
        int read_pidfile();
        
        unsigned server_pid;
        static unsigned int trapped_signal;
        
};

#endif //DAEMON_PROCESS_H

