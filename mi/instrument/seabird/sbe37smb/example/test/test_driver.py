#!/usr/bin/env python

"""
@package mi.instrument.seabird.sbe37smb.example.test.test_driver
@file /Users/wfrench/Workspace/code/marine-integrations/mi/instrument/seabird/sbe37smb/example/driver.py
@author Bill French
@brief Test cases for example driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a UNIT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a INT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a QUAL
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from ion.idk.metadata import Metadata
from ion.idk.comm_config import CommConfig

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from ion.agents.instrument.instrument_agent import InstrumentAgentState

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.instrument.seabird.sbe37smb.example.driver import PACKET_CONFIG

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe37smb.example.driver',
    driver_class="exampleInstrumentDriver",
    
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)

@attr('UNIT', group='mi')
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_foo(self):
        pass

@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access(self):
        """
        Test agent direct_access command. This causes creation of
        driver process and transition to direct access.
        """
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='go_direct_access',
            #kwargs={'session_type':DirectAccessTypes.telnet,
            kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        print("go_direct_access retval=" + str(retval))
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.DIRECT_ACCESS)

        # sleep to let tester run telnet client manually
        print "test sleeping to run telnet client"
        time.sleep(60)

        # Halt DA.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)


