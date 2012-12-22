"""
@file mi/idk/script/watch_data_log.py
@author Bill French
@brief Watch the port agent log for the current IDK driver
"""

__author__ = 'Bill French'


import time
import sys
import re
from xml.dom.minidom import parseString

from mi.idk.comm_config import CommConfig
from mi.idk.metadata import Metadata

DATADIR="/tmp"
SLEEP=1.0

def run():
    buffer = ""
    file = _get_file()
    for line in _follow(file):
        buffer = buffer + line
        record = _get_record(buffer)
        if(record):
            sys.stdout.write(record)
            buffer = ""

def _get_file():
    """
    build the data file name.  Then loop until the file can be open successfully
    @return: file pointer to the data file
    """
    metadata = Metadata()
    config_path = "%s/%s" % (metadata.driver_dir(), CommConfig.config_filename())
    comm_config = CommConfig.get_config_from_file(config_path)
    date = time.strftime("%Y%m%d")

    filename = "%s/port_agent_%d.%s.data" % (DATADIR, comm_config.command_port, date)

    file = None
    while(not file):
        try:
            file = open(filename)
        except Exception as e:
            sys.stderr.write("file open failed: %s\n" % e)
            time.sleep(SLEEP)

    return file

def _follow(file):
    """
    See to the end of a file and wait for a line of data to be read. Once read,
    return the line.
    @return: line of data
    """
    file.seek(0,2)      # Go to the end of the file
    while True:
        line = file.readline()
        if not line:
            time.sleep(0.1)    # Sleep briefly
            continue
        yield line

def _get_record(buffer):
    """
    Work to read a XML record.  If we can't parse then just return nothing
    @return: if an XML port agent record is found, return it's value.
    """
    try:
        dom = parseString(buffer)
        if(dom.documentElement.tagName != 'port_agent_packet'):
            sys.stderr("ERROR: unrecognized tag name: %s" % dom.documentElement.tagName)

        element = dom.getElementsByTagName('port_agent_packet')[0]
        return element.firstChild.nodeValue
    except Exception as e:
        return None


if __name__ == '__main__':
    run()