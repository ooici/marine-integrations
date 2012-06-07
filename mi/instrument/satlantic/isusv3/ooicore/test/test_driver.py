#!/usr/bin/env python

"""
@package mi.instrument.satlantic.isusv3.ooicore.test.test_driver
@file /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/satlantic/isusv3/ooicore/driver.py
@author Steve Foley
@brief Test cases for ooicore driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a UNIT
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a INT
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a QUAL
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

#from mock import Mock, call, DEFAULT

#from nose.plugins.attrib import attr

from ion.idk.metadata import Metadata
from ion.idk.comm_config import CommConfig
from ion.idk.unit_test import InstrumentDriverTestCase
from ion.idk.test.driver_qualification import DriverQualificationTestCase
from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentProtocol

#from mi.instrument.satlantic.isusv3.ooicore.driver import State
#from mi.instrument.satlantic.isusv3.ooicore.driver import Event
#from mi.instrument.satlantic.isusv3.ooicore.driver import Error
#from mi.instrument.satlantic.isusv3.ooicore.driver import Status
#from mi.instrument.satlantic.isusv3.ooicore.driver import Prompt
#from mi.instrument.satlantic.isusv3.ooicore.driver import Channel
#from mi.instrument.satlantic.isusv3.ooicore.driver import Command
#from mi.instrument.satlantic.isusv3.ooicore.driver import Parameter
#from mi.instrument.satlantic.isusv3.ooicore.driver import Capability
#from mi.instrument.satlantic.isusv3.ooicore.driver import MetadataParameter
#from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentProtocol
#from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentDriver


# Import pyon first for monkey patching.
from pyon.public import log

# Standard imports.
import os
import signal
import time
import unittest
from datetime import datetime

# 3rd party imports.
from gevent import spawn
from gevent.event import AsyncResult
import gevent
from nose.plugins.attrib import attr
from mock import patch
import uuid

# ION imports.
from interface.objects import StreamQuery
from interface.services.dm.itransform_management_service import TransformManagementServiceClient
from interface.services.cei.iprocess_dispatcher_service import ProcessDispatcherServiceClient
from interface.services.icontainer_agent import ContainerAgentClient
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from pyon.public import StreamSubscriberRegistrar
from prototype.sci_data.stream_defs import ctd_stream_definition
from pyon.agent.agent import ResourceAgentClient
from interface.objects import AgentCommand
from pyon.util.int_test import IonIntegrationTestCase
from pyon.util.context import LocalContextMixin
from pyon.public import CFG
from pyon.event.event import EventSubscriber, EventPublisher

from pyon.core.exception import InstParameterError


# MI imports.
from ion.agents.port.logger_process import EthernetDeviceLogger
from ion.agents.instrument.instrument_agent import InstrumentAgentState
# next line should match the above line mostly
from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreParameter

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
class Testooicore_UNIT(InstrumentDriverTestCase):
    """Unit Test Container"""
    
    def setUp(self):
        """
        @brief initalize mock objects for the protocol object.
        """
        #self.callback = Mock(name='callback')
        #self.logger = Mock(name='logger')
        #self.logger_client = Mock(name='logger_client')
        #self.protocol = ooicoreInstrumentProtocol()
    
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
#     and common for all drivers (minmum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testooicore_INT(InstrumentDriverTestCase):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.satlantic.isusv3.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'ooicoreInstrumentDriver'    
    
    def setUp(self):
        """
        """
        self.protocol = ooicoreInstrumentProtocol()
        #Configure the protocol here...send a CONFIGURE event?
        #self.protocol.configure(self.comm_config)
        
    def test_process(self):
        """
        @brief Test for correct launch of driver process and communications, including
        asynchronous driver events.
        """
        #driver_process, driver_client = self.init_driver_process_client();
        
        # Add test to verify process exists.

        # Send a test message to the process interface, confirm result.
        #msg = 'I am a ZMQ message going to the process.'
        #reply = driver_client.cmd_dvr('process_echo', msg)
        #self.assertEqual(reply,'process_echo: '+msg)

        # Send a test message to the driver interface, confirm result.
        #msg = 'I am a ZMQ message going to the driver.'
        #reply = driver_client.cmd_dvr('driver_echo', msg)
        #self.assertEqual(reply, 'driver_echo: '+msg)
        
        # Test the event thread publishes and client side picks up events.
        #events = [
        #    'I am important event #1!',
        #    'And I am important event #2!'
        #    ]
        #reply = driver_client.cmd_dvr('test_events', events=events)
        #time.sleep(2)
        
        # Confirm the events received are as expected.
        #self.assertEqual(self.events, events)

    ###
    #    Add driver specific integration tests
    ###

###############################################################################
#                            HARDWARE TESTS                                   #
# Device specific hardware tests are for testing against actual device        #
# hardware when available                                                     #
###############################################################################

"""
Remaining tests:

* Parameter manipulation
** Get read/write parameter
** Set read/write parameter
** Get read-only parameter
** Set read-only parameter (and fail)
** Get direct-access-only parameter (and fail)
** Set direct-access-only parameter (and fail)
* Get status values
** Lamp odometer
** Disk info
** Build info
** Clock info
* Enter and exit all operating modes
* Menu navigation
* Get next operating mode (can be mocked?)
* File Commands:
** List commands
*** LP (list program file)
*** LC (list coefficient file)
*** LL (list log files)
*** LD (list data files)
** Output Commands
*** OE (output extinction coefficient file)
*** OW (output wavelength coefficient file)
*** OS (output schedule file)
*** OL (output log file)
*** OD (output Data files)
** Upload Commands (direct access only)?
*** US (upload schedule file)
*** UE (upload extinction coefficient file)
*** UP (upload program file)
** Erase Commands
*** EE (erase extinction coefficient file)
*** EL (erase log files)
*** ED (erase data files)
*** EAD (erase all data files)
* Commands
** Reboot
** Submit schedule?
** Submit calibration?
** Get calibrations?

"""

@attr('HARDWARE', group='mi')
class Testooicore_HW(InstrumentDriverTestCase):
    """Hardware Test Container"""
    
    def setUp(self):
        driver_module = 'mi.instrument.satlantic.isusv3.ooicore.driver'
        driver_class = 'OoiCoreInstrumentProtocol'
        # @todo Make this configurable
        
        # test_device_addr = "67.58.40.195"
        # test_device_port = 2001
        test_device_addr = self.comm_config.device_addr
        test_device_port = self.comm_config.device_port
        delim = ['<<', '>>']
        
        # Zmq parameters used by driver process and client.
        self.config_params = {'addr': 'localhost'}                
        self._support = DriverIntegrationTestSupport(driver_module,
                                                     driver_class,
                                                     test_device_addr,
                                                     test_device_port,
                                                     delim)
        # Clear the driver event list
        self._events = []
        self._pagent = None
        self._dvr_proc = None

        mi_logger.info("Starting port agent")
        self.config_params['port'] = self._support.start_pagent()
        self.addCleanup(self._support.stop_pagent)
        
        mi_logger.info("Starting Satlantic ISUSv3 driver")
        self._dvr_client = self._support.start_driver()
        self.addCleanup(self._support.stop_driver)
        
        self._dvr_client = self._support._dvr_client
        
        # we never get to the protocol if we never connect!
        self._connect()

    def _clean_up(self):
        # set back to command mode
        if self._dvr_client:
            try:
                reply = self._dvr_client.cmd_dvr('execute_break')
            except InstrumentStateError:
                # no biggie if we are already in cmd mode
                pass
            # clean up our parameters?
            #reply = self._dvr_client.cmd_dvr('set',
            #                                 {Parameter.MAXRATE:1},
            #                                  timeout=20)
            self._disconnect()
        
        self._support.stop_driver()

    def tearDown(self):
        super(Testooicore_HW, self).tearDown()
        self._clean_up()

    def _initialize(self):
        reply = self._dvr_client.cmd_dvr('execute_init_device')
        time.sleep(1)

    def _connect(self):
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.UNCONFIGURED, reply)
        configs = self.config_params
        reply = self._dvr_client.cmd_dvr('configure', configs)
        self.assertEqual(reply, None)
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        reply = self._dvr_client.cmd_dvr('connect')
        self.assertEqual(reply, None)
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverProtocolState.UNKNOWN, reply)

        self._initialize()
        
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)

        time.sleep(1)

    def _disconnect(self):
        reply = self._dvr_client.cmd_dvr('disconnect')
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        time.sleep(1)

    def test_connect_disconnect(self):
        """ Just a place holder for running just the basic setUp, teardown
        routines that handle connecting and disconnecting """
        pass
    
    def test_get_RW_param(self):
        """ Test getting a read-write parameter """
        reply = self._dvr_client.cmd_dvr('get', [Parameter.INITIAL_DELAY,
                                                 Parameter.STATUS_MESSSAGES])

    def test_get_RO_param(self):
        """ Test getting a read-only parameter """
        self._assert(False)

    def test_get_DA_param(self):
        """ Test getting a direct access parameter """
        self._assert(False)
        
    def test_range_params(self):
        """ Some parameters like the nitrate DAC range have min and max values
        set via one menu path (min first, max next). Make sure they can be
        set. This will involve checking some logic that a min or a max value
        can be set and returned to a prompt properly.
        """
        self._assert(False)
        
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class Testooicore_QUAL(DriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  
    pass

###############################################################################
# Auto generated code.  There should rarely be reason to edit anything below. #
###############################################################################

class IntFromIDK(Testooicore_INT):
    """
    This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    called from the IDK test_driver program
    """
    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()

class UnitFromIDK(Testooicore_UNIT):
    """
    This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    called from the IDK test_driver program
    """
    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()

class QualFromIDK(Testooicore_QUAL):
    """
    This class overloads the default test class so that comm configurations can be overloaded.  This is the test class
    called from the IDK test_driver program
    """
    @classmethod
    def init_comm(cls):
        cls.comm_config = CommConfig.get_config_from_file(Metadata()).dict()

