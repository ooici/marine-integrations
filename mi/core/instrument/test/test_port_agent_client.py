#!/usr/bin/env python

"""
@package ion.services.mi.test.test_port_agent_client
@file ion/services/mi/test/test_port_agent_client.py
@author David Everett
@brief Some unit tests for R2 port agent client
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import logging
import unittest
#from mi.core.unit_test import MiUnitTest
import re
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket

# MI logger
from mi.core.log import get_logger ; log = get_logger()

@unittest.skip('BROKEN - Useful in past, likely in future, but not just now')
@attr('UNIT', group='mi')
#class TestPortAgent(MiUnitTest):
class TestPortAgentClient():

    def setUp(self):
        self.ipaddr = "67.58.49.194"
        self.port  = 4000
    
    def myGotData(self, paPacket):
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())
        
    #@unittest.skip('not finished yet')
    def test_port_agent_client_receive(self):
        ipaddr = "67.58.49.194"
        port  = 4000
        paClient = PortAgentClient(self.ipaddr, self.port)
        #paClient = PortAgentClient(ipaddr, port)
        paClient.init_comms(self.myGotData)
        
    def test_port_agent_client_send(self):
        ipaddr = "67.58.49.194"
        port  = 4000
        paClient = PortAgentClient(self.ipaddr, self.port)
        #paClient = PortAgentClient(ipaddr, port)
        paClient.init_comms(self.myGotData)
        
        paClient.send('this is a test\n')
        
if __name__ == '__main__':
    app = TestPortAgent()
    app.setUp
    app.test_port_agent_client_receive()