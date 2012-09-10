/*******************************************************************************
 * Class: CommListener
 * Filename: comm_listener.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * base class to manage network listeners
 *
 ******************************************************************************/

#ifndef __COMM_LISTENER_H_
#define __COMM_LISTENER_H_

#include "common/logger.h"
#include "network/comm_base.h"

using namespace std;
using namespace logger;

namespace network {
    class CommListener : public CommBase {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
    	    CommListener();
    	    CommListener(const CommListener &rhs);
            virtual ~CommListener();
            
            /* Operators */
            virtual CommListener & operator=(const CommListener &rhs);

            /* Accessors */
            bool listening() { return m_pServerFD > 0; }
            bool connected() { return m_pClientFD > 0; }
	    
	    int serverFD() { return m_pServerFD; }
	    int clientFD() { return m_pClientFD; }
            
            void setPort(const uint16_t port) { m_iPort = port; }
	    
	    uint16_t port() { return m_iPort; }
	    
	    uint16_t getListenPort();
	    
	    /* Commands */
	    bool disconnect();
	    bool disconnectClient();
	    
	    bool acceptClient();
	    
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            uint16_t m_iPort;
	    
	    int m_pServerFD;
	    int m_pClientFD;
            
    };
}

#endif //__COMM_LISTENER_H_
