/*******************************************************************************
 * Filename: util.h
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Utility functions - Mostly for tests
 ******************************************************************************/

#ifndef __UTIL_H__
#define __UTIL_H__

#include <string>

using namespace std;

uint16_t byteToUnsignedInt(uint8_t b);

string stackTrace(const unsigned int levels = 99);

/* File functions
 * These are inteded for use in tests.  Careful consideration
 * should be employed before using these in production code. */
bool remove_file(const char* filename);
bool file_exists(const char* filename);
bool create_file(const char* filename, const char* content);
string read_file(const char* filename);

#endif __UTIL_H__

