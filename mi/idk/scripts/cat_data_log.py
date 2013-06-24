"""
@file mi/idk/script/watch_data_log.py
@author Bill French
@brief Watch the port agent log for the current IDK driver
"""

__author__ = 'Bill French'


import time
import sys
import binascii
import fileinput

from mi.idk.comm_config import CommConfig
from mi.idk.metadata import Metadata
from mi.core.instrument.port_agent_client import PortAgentPacket, HEADER_SIZE

DATADIR="/tmp"
SLEEP=1.0
SENTINLE=binascii.unhexlify('A39D7A')

def run():
    buffer = None

    for line in fileinput.input():
        if(buffer == None): buffer = ""
        buffer = buffer + line
        (record, buffer) = _get_record(buffer)
        if(record):
            _write_packet(record)

def _write_packet(record):
    if(record.get_header_type() == PortAgentPacket.DATA_FROM_INSTRUMENT):
        sys.stdout.write(record.get_data())
    elif(record.get_header_type() == PortAgentPacket.DATA_FROM_DRIVER):
        #sys.stdout.write(">>> %s" % record.get_data())
        pass

def _get_record(buffer):
    """
    Work to read a XML record.  If we can't parse then just return nothing
    @return: if an XML port agent record is found, return it's value.
    """
    remaining = None
    data_start = 0
    data_end = 0

    index = buffer.find(SENTINLE)

    if(index < 0):
        return (None, buffer)

    packet = _get_header(buffer[index:])
    if packet:
        remaining = _get_remaining(buffer[index:], packet)
        if(_read_data(buffer[index:], packet)):
            return (packet, remaining)
        else:
            if(remaining):
                return (None, buffer[index+1:])
            else:
                return (None, buffer)
    else:
        return (None, buffer)

def _get_header(buffer):
    packet = PortAgentPacket()
    if(len(buffer) < HEADER_SIZE): return None

    header = buffer[0:HEADER_SIZE]
    packet.unpack_header(header)

    if(packet.get_data_length() < 0): return None

    print "time: %f" % packet.get_timestamp()

    return packet

def _read_data(buffer, packet):
    if(len(buffer) < HEADER_SIZE + packet.get_data_length()): return False
    data = buffer[HEADER_SIZE:HEADER_SIZE+packet.get_data_length()]
    packet.attach_data(data)

    return True

def _get_remaining(buffer, packet):
    if(len(buffer) == HEADER_SIZE + packet.get_data_length()): return None
    return buffer[HEADER_SIZE+packet.get_data_length():]


if __name__ == '__main__':
    run()
