/*******************************************************************************
 * Class: Timestamp
 * Filename: timestamp.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Class for creating and manipulating timestamps for the port agent. We use
 * timestamps following the NTPv4 64bit standard
 * 
 * Standard Definition:
 *   - http://www.ietf.org/rfc/rfc5905.txt
 * 
 ******************************************************************************/

#ifndef TIMESTAMP_H
#define TIMESTAMP_H

#include <sys/time.h>
#include <stdint.h>

#include <string>
using namespace std;

const unsigned long long EPOCH = 2208988800ULL;
const unsigned long long NTP_SCALE_FRAC = 4294967295ULL;

class Timestamp {
    public:
        Timestamp();
        Timestamp(const Timestamp &copy) : m_seconds(copy.m_seconds), m_fraction(copy.m_fraction) {}
        Timestamp(const uint32_t seconds, const uint32_t fraction) : m_seconds(seconds), m_fraction(fraction) {}

        Timestamp & operator=(const Timestamp &rhs);
        
        // Set the current timestamp to now.
        void setNow();

        void setTime(uint32_t seconds, uint32_t fraction);

        // Get elapse time between the stored timestamp and now.
        double elapseTime();
        
        uint32_t seconds() { return m_seconds; }
        uint32_t fraction() { return m_fraction; }
        
        double asDouble();
        uint64_t asBinary();
        string asNumber();
        string asHex();
        string asString();

    private:
        void setTime(struct timeval *tv);
        uint32_t m_seconds;
        uint32_t m_fraction;
};

#endif //TIMESTAMP_H

