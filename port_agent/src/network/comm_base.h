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
            
            /* Operators */
            virtual CommBase & operator=(const CommBase &rhs);

            /* Accessors */
            
        protected:

        private:
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
    };
}

#endif //__COMM_BASE_H_
