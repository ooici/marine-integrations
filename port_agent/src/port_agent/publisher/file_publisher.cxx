
#include "file_publisher.h"
#include "common/util.h"
#include "common/logger.h"
#include "common/exception.h"
#include "port_agent/packet/packet.h"

#include <sstream>
#include <string>

using namespace std;
using namespace packet;
using namespace logger;
using namespace publisher;
    
/******************************************************************************
 *   PUBLIC METHODS
 ******************************************************************************/

/******************************************************************************
 * Method: setFilename
 * Description: Set the filename to write data too.
 * Parameter:
 *    filename - path to the output file
 ******************************************************************************/
void FilePublisher::setFilename(string filename) {
    m_oLogger = LogFile(filename.c_str());
}

/******************************************************************************
 * Method: setFilebase
 * Description: set the logfile base name and optionally the extenstion for a
 * rolled log file.  A date will be appended to the log file base followed by
 * the extension if specified.
 *
 * Parameter:
 *    filebase - path to the base of a log file name (the first part)
 *    fileext  - the extension to add on to the filename
 ******************************************************************************/
void FilePublisher::setFilebase(string filebase, string fileext) {
    m_oLogger = LogFile(filebase.c_str(), fileext.c_str());
}



