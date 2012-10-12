#include "port_agent.h"
#include "common/exception.h"

#include <iostream>
#include <sstream>
#include <string>
#include <exception>

#include <stdlib.h>

using namespace std;
using namespace port_agent;

int main(int argc, char *argv[]) {
    ostringstream msg;
    string errmsg;
    PortAgent *agent = NULL;
    
    try {
        agent = new PortAgent(argc, argv);
    
        agent->start();
    }
    catch(DuplicateProcess &e) {
        msg << "ERROR: Duplicate process detected";
        errmsg = msg.str();
        
        LOG(ERROR) << e.what();
        cerr << errmsg << endl;
        
        return EXIT_FAILURE;
    }
    catch(ParameterRequired &e) {
        msg << "Parameter required (must specific a command port on the command line or in a conf file)";
        errmsg = msg.str();
    }
    catch(exception &e) {
        msg << "Unhandled exception caught: " << e.what();
        errmsg = msg.str();
    };
    
    if(errmsg.length()) {
        LOG(ERROR) << errmsg;
        cerr << "ERROR: " << errmsg << endl;
        cerr << "USAGE: " << agent->usage() << endl;
        
        return EXIT_FAILURE;
    }
    
    if(agent) delete agent;

    return EXIT_SUCCESS;
}
