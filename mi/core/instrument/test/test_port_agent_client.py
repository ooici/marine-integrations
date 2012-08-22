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
import re
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket

# MI logger
from mi.core.log import get_logger ; log = get_logger()

#@unittest.skip('NOTE!!!! TestPortAgent SKIPPED!')
@attr('UNIT', group='mi')
#class TestPortAgent(unittest.TestCase):
class TestPortAgentClient():

    def setUp(self):
        self.ipaddr = "67.58.49.194"
        self.port  = 4000
    
    def myGotData(self, paPacket):
        print "Got data of length " + str(paPacket.length) + " bytes: " + str(paPacket.data)
        
    #@unittest.skip('not finished yet')
    def test_port_agent(self):
        ipaddr = "67.58.49.194"
        port  = 4000
        paClient = PortAgentClient(self.ipaddr, self.port)
        #paClient = PortAgentClient(ipaddr, port)
        paClient.init_comms(self.myGotData)
        
if __name__ == '__main__':
    app = TestPortAgent()
    app.setUp
    app.test_port_agent()