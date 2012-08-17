"""
@package mi.instrument.nortek.aquadopp.ooicore.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore/driver.py
@author Bill Bollenbacher
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import gevent
import unittest

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.instrument.nortek.aquadopp.ooicore.driver import ProtocolState

from interface.objects import AgentCommand
from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.aquadopp.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'OQYBVZ',
    instrument_agent_name = 'nortek_aquadopp_ooicore',
    instrument_agent_packet_config = {},
    instrument_agent_stream_definition = {}
)

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
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    ###
    #    Add instrument specific unit tests
    ###


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
    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' or 'auto-sample' state
        """
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode or auto-sample mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertTrue((state == ProtocolState.COMMAND) or (state == ProtocolState.AUTOSAMPLE))
                
               
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

    #@unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_down; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_up; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent initialize; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent go_active; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent run; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={#'session_type': DirectAccessTypes.telnet,
                                   'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run




