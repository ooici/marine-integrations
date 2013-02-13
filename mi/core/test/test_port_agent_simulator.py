#!/usr/bin/env python

"""
@package ion.services.mi.test.test_port_agent_simulator
@file ion/services/mi/test/test_port_agent_simulator.py
@author Bill French
@brief Tests for the port agent simulator
"""

# Needed because we import the time module below.  With out this '.' is search first
# and we import ourselves.
from __future__ import absolute_import

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import time

from mi.core.unit_test import MiUnitTest
from nose.plugins.attrib import attr
from mi.core.port_agent_simulator import TCPSimulatorServer
from mi.core.port_agent_simulator import TCPSimulatorClient

# MI logger
from mi.core.log import get_logger ; log = get_logger()

@attr('UNIT', group='mi')
class TestTCPInstrumentSimulator(MiUnitTest):
    def setUp(self):
        pass

    def test_simulator_startup(self):
        # start the server
        server = TCPSimulatorServer()
        self.addCleanup(server.close)

        self.assertGreater(server.port, 0)
        log.debug("Simulator up")

        # connect to the server
        client = TCPSimulatorClient(server.port)
        self.addCleanup(client.close)

        # Now send some data and see if we can read it.
        result = ""
        orig_data = "some data"
        server.send(orig_data)
        for i in range(0, 10):
            bytes_read = client.read()
            if(bytes_read != None):
                result += bytes_read

            if(result != orig_data):
                time.sleep(1)

        self.assertEqual(result, orig_data)


