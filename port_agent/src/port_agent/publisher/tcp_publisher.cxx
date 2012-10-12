/*******************************************************************************
 * Class: TCPPublisher
 * Filename: tcp_publisher.cxx
 * Author: Bill French (wfrench@ucsd.edu)
 * License: Apache 2.0
 *
 * This publisher is to set up a listener that external programs can attach
 * too.  It outputs all packets either as binary or ascii.
 *
 ******************************************************************************/
#include "tcp_publisher.h"

using namespace publisher;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: Constructor
 * Description: Default constructor
 ******************************************************************************/
TCPPublisher::TCPPublisher() {
}
