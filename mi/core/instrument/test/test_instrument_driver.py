#!/usr/bin/env python
"""
@package mi.core.instrument.test.test_instrument_driver
@file mi/core/instrument/test/test_instrument_driver.py
@author Edward Hunter
@brief Test cases for R2 instrument driver.

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $$ bin/test_driver
       $$ bin/test_driver -u
       $$ bin/test_driver -i
       $$ bin/test_driver -q

   * From pyon
       $$ bin/nosetests -s -v mi.core.instrument.test.test_instrument_driver
       $$ bin/nosetests -s -v mi.core.instrument.test.test_instrument_driver -a UNIT
       $$ bin/nosetests -s -v mi.core.instrument.test.test_instrument_driver -a INT
       $$ bin/nosetests -s -v mi.core.instrument.test.test_instrument_driver -a QUAL
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from base64 import standard_b64encode
from struct import pack

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.core.instrument.instrument_driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'base_instrument_driver',
    instrument_agent_name = 'base_instrument_driver_agent',
    instrument_agent_packet_config = {},
    instrument_agent_stream_definition = {}
)


# Import pyon first for monkey patching.
#from pyon.public import log

# Standard imports.
import time
import os
import signal
import time
import unittest
import json
from datetime import datetime

# 3rd party imports.
from nose.plugins.attrib import attr
from mock import Mock, call, DEFAULT, patch

# ION imports.
# from pyon.public import CFG

# MI imports.
from mi.core.instrument.driver_int_test_support import DriverIntegrationTestSupport
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.core.instrument.instrument_driver import InstrumentDriver
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverDataPublishKey
from mi.core.instrument.instrument_driver import DriverDataPublishValue

# JSON data example
TIMESTAMP_A = "1342826285.991474"
TIMESTAMP_B = "1342826284.981474"
TIMESTAMP_C = "1342826283.741474"

GOOD_PYTHON_DATA = {DriverDataPublishKey.PKT_FORMAT_ID : DriverDataPublishValue.JSON_DATA,
                    DriverDataPublishKey.PKT_VER : 1,
                    DriverDataPublishKey.TYPE : DriverDataPublishValue.TYPE_PARSED,
                    DriverDataPublishKey.INST_ID : "ABC-123",
                    DriverDataPublishKey.INT_TIME : standard_b64encode(TIMESTAMP_A),
                    DriverDataPublishKey.PORT_TIME : standard_b64encode(TIMESTAMP_B),
                    DriverDataPublishKey.DRIVER_TIME : standard_b64encode(TIMESTAMP_C),
                    DriverDataPublishKey.PREF_TIME : DriverDataPublishValue.TIME_PORT,
                    DriverDataPublishKey.QUALITY : DriverDataPublishValue.QUALITY_OK,
                    DriverDataPublishKey.VALUES :
                        [{DriverDataPublishKey.VALUE_ID : "temp",
                          DriverDataPublishKey.VALUE : 123.456},
                         {DriverDataPublishKey.VALUE_ID : "cond",
                          DriverDataPublishKey.VALUE : 15.9},
                         {DriverDataPublishKey.VALUE_ID : "depth",
                          DriverDataPublishKey.VALUE : 305.1}]
                    }   

#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitTestInstrumentDriver(InstrumentDriverUnitTestCase):
    """
    Test cases for instrument driver base class. Functions in this class provide
    instrument driver tests.
    """ 
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)
        

    def test_driver_agent_comms_format(self):
        """
        Test driver/agent communications format.
        """
        # Establish a driver of some sort with the proper call back
        # Make a base driver to work with
        base_driver = InstrumentDriver(self._check_valid_data)

        base_driver._driver_event(DriverAsyncEvent.SAMPLE, GOOD_PYTHON_DATA)

        # Mock it up so that the protocol returns a given string of data
        # Snag the data and compare it to a known good value
        
    def test_ntp_conversion(self):
        base_driver = InstrumentDriver(self._check_valid_data)

        test_time = 1342826285.991474 # Jul 20th, 2012, 2318ish
        self.assertEquals(base_driver._time_to_int(test_time), 1342826285)
        self.assertEquals(base_driver._time_to_frac(test_time), 4258348032)
        self.assertEquals(base_driver._system_to_ntp_time(test_time),
                          3551815085.991474)
        self.assertEquals(base_driver._ascii_ntp_time(test_time),
                          standard_b64encode(pack('d', base_driver._system_to_ntp_time(test_time))))        
        
    def _check_valid_data(self, event):
        """ Verify data is valid for an event that is called back here """
        self.assertTrue(event)
        self.assertEquals(event['type'], DriverAsyncEvent.SAMPLE)
        self.assertTrue(event['value'])
        self.assertNotEquals(event['value'], None)
        json_sample_str = json.loads(event['value'])
        # make sure we made it out and back okay
        self.assertEquals(json_sample_str, json.loads(json.dumps(GOOD_PYTHON_DATA)))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    ###
    #    Add instrument specific qualification tests
    ###


