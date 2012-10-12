/*******************************************************************************
 * Filename: util.cpp
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * Utility functions - Mostly for tests
 ******************************************************************************/

#include "logger.h"
#include "exception.h"

#include <sstream>
#include <fstream>
#include <iostream>
#include <string>
#include <stdio.h>
#include <sys/stat.h>
#include <execinfo.h>

using namespace std;

/******************************************************************************
 * Method: stackTrace
 * Description: return a stack trace in a \n delimeted string.
 *
 * Parameters:
 *   levels - how many levels of the stack to look back on?
 *
 * Return:
 *   unsigned int padded with 0s
 ******************************************************************************/
string stackTrace(const unsigned int levels = 99) {
    ostringstream out;
    size_t stack_depth;
    void *stack_addrs[levels];
    char **stack_strings;

    stack_depth = backtrace(stack_addrs, levels);
    stack_strings = backtrace_symbols(stack_addrs, stack_depth);

    for (size_t i = 1; i < stack_depth; i++) {
        out << "\t" << stack_strings[i] << endl;
    }

    free(stack_strings); // malloc()ed by backtrace_symbols

    return out.str();
}


/******************************************************************************
 * Method: byteToUnsignedInt
 * Description: Convert a byte to unsigned integer.
 * 
 * Parameters:
 *   byte to convert
 *   
 * Return:
 *   unsigned int padded with 0s
 ******************************************************************************/
uint16_t byteToUnsignedInt(uint8_t b) {
    return (b < 0) ? 256 + b : b;
}

/******************************************************************************
 * Method: file_exists
 * Description: does a file exists
 * Parameters:
 *   string filename
 * Return:
 *   bool true if the file exists and is readable.
 ******************************************************************************/
bool file_exists(const char* filename)
{
    struct stat buf;
    int result = stat(filename, &buf);
    return result >= 0;
}


/******************************************************************************
 * Method: remove_file
 * Description: remove a file from the filesystem
 * Parameters:
 *   string filename - path to the file to remove
 * Return:
 *   bool true if existed and was properly removed.
 ******************************************************************************/
bool remove_file(const char* filename)
{
    int result = remove(filename);
}
    


/******************************************************************************
 * Method: create_file
 * Description: create a file with the content passed in.
 * Parameters:
 *   string filename - path to the file to create
 *   string content - content of the file
 * Return:
 *   bool true if didn't exists and was created properly.
 ******************************************************************************/
bool create_file(const char* filename, const char* content)
{
    ofstream outfile(filename);
    if (outfile.good()) {
	outfile << content;
	outfile.flush();
	outfile.close();
	return true;
    }
    
    return false;
}


/******************************************************************************
 * Method: read_file
 * Description: Return the contents of a file in a string object
 * Parameters:
 *   string filename - path to the file to create
 * Return:
 *   string contents of the input file
 ******************************************************************************/
string read_file(const char* filename)
{
    stringstream buffer;
    string result;
    
    if(!file_exists(filename)){
        return result;
    }

    ifstream infile(filename);
    
    if(infile.good()) {
        buffer << infile.rdbuf();
    }
    else {
	throw FileIOException(filename);
    }
    
    return buffer.str();
}
