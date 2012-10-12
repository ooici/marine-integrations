/*******************************************************************************
 * Class: CommBase
 * Filename: comm_base.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * CommBase is the base class for network socket communications.  From this
 * class we will derive classes to setup TCP and UDP socket and listeners.
 *
 ******************************************************************************/

#ifndef __COMM_BASE_H_
#define __COMM_BASE_H_

#include "common/logger.h"

using namespace std;
using namespace logger;

namespace network {
    class CommBase {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
            CommBase();
            CommBase(const CommBase &rhs);
            virtual ~CommBase();
            
            virtual CommBase *copy() = 0;
            
            /* Operators */
            virtual CommBase & operator=(const CommBase &rhs);

            /* Accessors */
            bool blocking() {return m_bBlocking;}
            virtual bool connected() {return m_bConnected;}
            
            /* Methods */
            void setBlocking(bool block) {m_bBlocking = block;}
            virtual bool initialize() = 0;
	    
            virtual uint32_t writeData(const char *buffer, uint32_t size) = 0;
            virtual uint32_t readData(char *buffer, uint32_t size) = 0;
            
            virtual uint16_t getListenPort() { return 0; }




        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        private:
            bool m_bBlocking;
            
        protected:
            bool m_bConnected;
            
    };
}

#endif //__COMM_BASE_H_
