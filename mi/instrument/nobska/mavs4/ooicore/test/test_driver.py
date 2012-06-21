#!/usr/bin/env python

"""
@package mi.instrument.nobska.mavs4.mavs4.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4/mavs4/driver.py
@author Bill Bollenbacher
@brief Test cases for mavs4 driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

"""
#from mock import Mock, call, DEFAULT

#from nose.plugins.attrib import attr

from ion.idk.metadata import Metadata
from ion.idk.comm_config import CommConfig
from ion.idk.unit_test import InstrumentDriverTestCase
from ion.idk.test.driver_qualification import DriverQualificationTestCase

#from mi.instrument.nobska.mavs4.mavs4.driver import State
#from mi.instrument.nobska.mavs4.mavs4.driver import Event
#from mi.instrument.nobska.mavs4.mavs4.driver import Error
#from mi.instrument.nobska.mavs4.mavs4.driver import Status
#from mi.instrument.nobska.mavs4.mavs4.driver import Prompt
#from mi.instrument.nobska.mavs4.mavs4.driver import Channel
#from mi.instrument.nobska.mavs4.mavs4.driver import Command
#from mi.instrument.nobska.mavs4.mavs4.driver import Parameter
#from mi.instrument.nobska.mavs4.mavs4.driver import Capability
#from mi.instrument.nobska.mavs4.mavs4.driver import MetadataParameter
#from mi.instrument.nobska.mavs4.mavs4.driver import mavs4InstrumentProtocol
#from mi.instrument.nobska.mavs4.mavs4.driver import mavs4InstrumentDriver


# Standard imports.
#import os
#import signal
import time
import unittest
#from datetime import datetime

# 3rd party imports.
#from gevent import spawn
#from gevent.event import AsyncResult
import gevent
from nose.plugins.attrib import attr
#from mock import patch
#import uuid

# ION imports.
#from interface.objects import StreamQuery
#from interface.services.dm.itransform_management_service import TransformManagementServiceClient
#from interface.services.cei.iprocess_dispatcher_service import ProcessDispatcherServiceClient
#from interface.services.icontainer_agent import ContainerAgentClient
#from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
#from pyon.public import StreamSubscriberRegistrar
from prototype.sci_data.stream_defs import ctd_stream_definition
#from pyon.agent.agent import ResourceAgentClient
#from interface.objects import AgentCommand
#from pyon.util.int_test import IonIntegrationTestCase
#from pyon.util.context import LocalContextMixin
#from pyon.public import CFG
#from pyon.event.event import EventSubscriber, EventPublisher

#from pyon.core.exception import InstParameterError


# MI imports.
#from ion.agents.port.logger_process import EthernetDeviceLogger
#from ion.agents.instrument.instrument_agent import InstrumentAgentState
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentParameters
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.core.log import log

from mi.instrument.nobska.mavs4.ooicore.driver import PACKET_CONFIG
"""

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent
import socket

# Standard lib imports
import time
import unittest

# 3rd party imports
from nose.plugins.attrib import attr

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.seabird.sbe37smb.ooicore.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Driver
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37ProtocolState
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Parameter

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

# MI logger
from mi.core.log import log
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes


## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nobska.mavs4.ooicore.driver',
    driver_class="mavs4InstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
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
class Testmavs4_UNIT(InstrumentDriverTestCase):
    """Unit Test Container"""
    
    def setUp(self):
        """
        @brief initialize mock objects for the protocol object.
        """
        #self.callback = Mock(name='callback')
        #self.logger = Mock(name='logger')
        #self.logger_client = Mock(name='logger_client')
        #self.protocol = mavs4InstrumentProtocol()
    
        #self.protocol.configure(self.comm_config)
        #self.protocol.initialize()
        #self.protocol._logger = self.logger 
        #self.protocol._logger_client = self.logger_client
        #self.protocol._get_response = Mock(return_value=('$', None))
        
        # Quick sanity check to make sure the logger got mocked properly
        #self.assertEquals(self.protocol._logger, self.logger)
        #self.assertEquals(self.protocol._logger_client, self.logger_client)
        
    ###
    #    Add driver specific unit tests
    ###
    
    
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testmavs4_INT(InstrumentDriverIntegrationTestCase):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.nobska.mavs4.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'mavs4InstrumentDriver'    
    
    @unittest.skip("skip while in development")
    def test_driver_process(self):
        pass 
    
    def test_instrumment_wakeup(self):
        """
        @brief Test for instrument wakeup
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        

    ###
    #    Add driver specific integration tests
    ###

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class Testmavs4_QUAL(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  
    pass

###############################################################################
# Auto generated code.  There should rarely be reason to edit anything below. #
###############################################################################

"""
these cause nosetest to run all tests twice!
class IntFromIDK(Testmavs4_INT):
    #This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    #called from the IDK test_driver program
    
    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()

class UnitFromIDK(Testmavs4_UNIT):
    #This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    #called from the IDK test_driver program

    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()

class QualFromIDK(Testmavs4_QUAL):
    #This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    #called from the IDK test_driver program

    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()
"""
