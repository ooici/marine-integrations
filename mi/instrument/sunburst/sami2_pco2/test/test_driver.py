"""
@package mi.instrument.sunburst.sami2_pco2.ooicore.test.test_driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/ooicore/driver.py
@author Christopher Wingard
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Christopher Wingard & Kevin Stiemke'
__license__ = 'Apache 2.0'

import unittest
import time

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.sami2_pco2.driver import ScheduledJob
from mi.instrument.sunburst.sami2_pco2.driver import ProtocolState
from mi.instrument.sunburst.sami2_pco2.driver import ProtocolEvent
# from mi.instrument.sunburst.driver import ProtocolEvent
from mi.instrument.sunburst.sami2_pco2.driver import Capability
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import NEWLINE

# Added Imports (Note, these pick up some of the base classes not directly imported above)
from mi.instrument.sunburst.test.test_driver import SamiMixin
from mi.instrument.sunburst.test.test_driver import SamiUnitTest
from mi.instrument.sunburst.test.test_driver import SamiIntegrationTest
from mi.instrument.sunburst.test.test_driver import SamiQualificationTest


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

###
# Driver constant definitions
###

TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT
STATES = ParameterTestConfigKey.STATES

###############################################################################
#                           DRIVER TEST MIXIN                                 #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                            #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class Pco2DriverTestMixinSub(SamiMixin):
    '''
    Mixin class used for storing data particle constants and common data
    assertion methods.
    '''

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS:      {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.AUTOSAMPLE]},
        Capability.ACQUIRE_SAMPLE:      {STATES: [ProtocolState.COMMAND]},
        Capability.ACQUIRE_BLANK_SAMPLE:{STATES: [ProtocolState.COMMAND]},
        Capability.START_AUTOSAMPLE:    {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.AUTOSAMPLE]},
        Capability.STOP_AUTOSAMPLE:     {STATES: [ProtocolState.AUTOSAMPLE,
                                                  ProtocolState.COMMAND]}
    }

###############################################################################
#                                UNIT TESTS                                   #
#         Unit Tests: test the method calls and parameters using Mock.        #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class Pco2DriverUnitTest(SamiUnitTest, Pco2DriverTestMixinSub):

    capabilities_test_dict = {
        ProtocolState.UNKNOWN:          ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.WAITING:          ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND:          ['DRIVER_EVENT_GET',
                                         'DRIVER_EVENT_SET',
                                         'DRIVER_EVENT_START_DIRECT',
                                         'DRIVER_EVENT_ACQUIRE_STATUS',
                                         'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE',
                                         'DRIVER_EVENT_START_AUTOSAMPLE'],
        ProtocolState.AUTOSAMPLE:       ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE',
                                         'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                         'DRIVER_EVENT_ACQUIRE_STATUS'],
        ProtocolState.DIRECT_ACCESS:    ['EXECUTE_DIRECT',
                                         'DRIVER_EVENT_STOP_DIRECT'],
        ProtocolState.POLLED_SAMPLE:     ['PROTOCOL_EVENT_TAKE_SAMPLE',
                                          'PROTOCOL_EVENT_SUCCESS',
                                          'PROTOCOL_EVENT_TIMEOUT',
                                          'DRIVER_EVENT_ACQUIRE_STATUS',
                                          'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                          'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE'],
        ProtocolState.POLLED_BLANK_SAMPLE: ['PROTOCOL_EVENT_TAKE_SAMPLE',
                                            'PROTOCOL_EVENT_SUCCESS',
                                            'PROTOCOL_EVENT_TIMEOUT',
                                            'DRIVER_EVENT_ACQUIRE_STATUS',
                                            'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                            'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE'],
        ProtocolState.SCHEDULED_SAMPLE:   ['PROTOCOL_EVENT_TAKE_SAMPLE',
                                           'PROTOCOL_EVENT_SUCCESS',
                                           'PROTOCOL_EVENT_TIMEOUT',
                                           'DRIVER_EVENT_ACQUIRE_STATUS',
                                           'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                           'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE'],
        ProtocolState.SCHEDULED_BLANK_SAMPLE: ['PROTOCOL_EVENT_TAKE_SAMPLE',
                                               'PROTOCOL_EVENT_SUCCESS',
                                               'PROTOCOL_EVENT_TIMEOUT',
                                               'DRIVER_EVENT_ACQUIRE_STATUS',
                                               'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                               'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE']
    }

    def test_base_driver_enums(self):
        """
        Verify that all the SAMI Instrument driver enumerations have no
        duplicate values that might cause confusion. Also do a little
        extra validation for the Capabilites

        Extra enumeration tests are done in a specific subclass
        """

        # Test Enums defined in the base SAMI driver
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())

        # Test capabilites for duplicates, then verify that capabilities
        # is a subset of proto events

        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class Pco2DriverIntegrationTest(SamiIntegrationTest, Pco2DriverTestMixinSub):
    pass

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class Pco2DriverQualificationTest(SamiQualificationTest, Pco2DriverTestMixinSub):
    pass
