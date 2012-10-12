/*******************************************************************************
 * Class: LogPublisher
 * Filename: log_publisher.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher writes packet data directly to a log file.  The log file uses
 * LogFile object for file handling so either a filename can be used to
 * explicitly name the file or a filebase and extenstion if we want the logger
 * to role files daily.
 * 
 * One additional option can be set for this publisher, asciiMode, which will
 * output the packets as ascii instead of binary.
 *
 * Usage:
 *
 * LogPublisher log("/tmp/output.log");
 * LogPublisher log("tmp/output", "log")
 *
 * # Enables ascii logging
 * log.setAsciiMode(true);
 *
 * Handlers:
 *
 * All handlers are overloaded to write their binary representation to a file.
 *    
 ******************************************************************************/

#ifndef __LOG_PUBLISHER_H_
#define __LOG_PUBLISHER_H_

#include "file_publisher.h"
#include "common/log_file.h"

using namespace std;
using namespace logger;

namespace publisher {
    class LogPublisher : public FilePublisher {
        /********************
         *      METHODS     *
         ********************/
        
        public:
            ///////////////////////
            // Public Methods
            LogPublisher() {}

        protected:
            virtual bool handleInstrumentData(Packet *packet) { return logPacket(packet); }
            virtual bool handleDriverData(Packet *packet)     { return logPacket(packet); }
            virtual bool handleCommand(Packet *packet)        { return logPacket(packet); }
            virtual bool handleStatus(Packet *packet)         { return logPacket(packet); }
            virtual bool handleFault(Packet *packet)          { return logPacket(packet); }


        private:

            bool logPacket(Packet *packet);
        
        /********************
         *      MEMBERS     *
         ********************/
        
        protected:
            
        private:
    };
}

#endif //__LOG_PUBLISHER_H_
