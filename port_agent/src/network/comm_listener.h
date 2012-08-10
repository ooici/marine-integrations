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
            
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
    };
}

#endif //__COMM_LISTENER_H_
