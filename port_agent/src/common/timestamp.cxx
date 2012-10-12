#include "timestamp.h"
#include "logger.h"
#include "util.h"

#include <sys/time.h>
#include <stdint.h>

#include <iomanip>
#include <string>
#include <sstream>
#include <iostream>
#include <stdio.h>

using namespace std;
using namespace logger;

Timestamp::Timestamp() {
    setNow();
}

void Timestamp::setNow() {
    struct timeval now;
    gettimeofday(&now, NULL);
    setTime(&now);
}

void Timestamp::setTime(uint32_t seconds, uint32_t fraction) {
	m_seconds = seconds;
	m_fraction = fraction;
}

double Timestamp::elapseTime() {
    Timestamp currentTime;
    
    return currentTime.asDouble() - asDouble();
}

double Timestamp::asDouble(){
    double seconds = m_seconds;
    double fraction = m_fraction / (double)NTP_SCALE_FRAC;

    return seconds + fraction;
}

uint64_t Timestamp::asBinary(){
    // convert to big-endian
	uint64_t ntpts;

    ntpts = htonl(m_fraction);
    ntpts = ntpts << 32 | htonl(m_seconds);

    return ntpts;
}

string Timestamp::asNumber(){
    stringstream out;
    out << asDouble();
    return out.str();
}

string Timestamp::asHex() {
    stringstream out;
    out << hex << setfill('0') << setw(16) << asBinary();
    return out.str();
}

string Timestamp::asString() {
    stringstream out;
    out << hex << asBinary();
    return out.str();
}
  
void Timestamp::setTime(struct timeval *tv) {
    uint64_t ntpts;

    m_seconds = (uint32_t)tv->tv_sec + EPOCH;
    m_fraction = (uint32_t)((NTP_SCALE_FRAC * tv->tv_usec) / 1000000UL);
}

Timestamp & Timestamp::operator=(const Timestamp &rhs) {
    m_seconds = rhs.m_seconds;
    m_fraction = rhs.m_fraction;

    return *this;
}
