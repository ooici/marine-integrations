#!/usr/bin/env python

"""
@package ion.services.mi.instrument.sbe37.test.test_sbe37_driver
@file ion/services/mi/instrument/sbe37/test/test_sbe37_driver.py
@author Edward Hunter
@brief Test cases for InstrumentDriver
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent


from mock import patch
from pyon.core.bootstrap import CFG

from gevent import monkey; monkey.patch_all()
import gevent
import re
import json
import copy

# Standard lib imports
import time
import unittest

# 3rd party imports
from nose.plugins.attrib import attr

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.instrument.seabird.test.test_driver import SeaBirdUnitTest
from mi.instrument.seabird.test.test_driver import SeaBirdIntegrationTest
from mi.instrument.seabird.test.test_driver import SeaBirdQualificationTest


from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.seabird.sbe37smb.ooicore.test.sample_data import *

from mi.instrument.seabird.sbe37smb.ooicore.driver import DataParticleType
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37ProtocolState
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Parameter
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37ProtocolEvent
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Capability
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DataParticle
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DataParticleKey
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DeviceCalibrationParticle
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DeviceCalibrationParticleKey
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DeviceStatusParticle
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DeviceStatusParticleKey
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Driver

from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.instrument_driver import DriverConfigKey

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.instrument.seabird.test.test_driver import SeaBirdUnitTest
from mi.instrument.seabird.test.test_driver import SeaBirdIntegrationTest
from mi.instrument.seabird.test.test_driver import SeaBirdQualificationTest

from mi.core.tcp_client import TcpClient

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.instrument.instrument_driver import DriverProtocolState
from ion.services.dm.utility.granule.record_dictionary import RecordDictionaryTool


from prototype.sci_data.stream_parser import PointSupplementStreamParser
from prototype.sci_data.constructor_apis import PointSupplementConstructor
from prototype.sci_data.stream_defs import ctd_stream_definition
from prototype.sci_data.stream_defs import SBE37_CDM_stream_definition
import numpy
from prototype.sci_data.stream_parser import PointSupplementStreamParser

from pyon.core import exception
from pyon.core.exception import InstParameterError
from pyon.core import exception as iex

from gevent.timeout import Timeout

from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict


from interface.objects import CapabilityType
from interface.objects import AgentCapability

###
#   Driver parameters for the tests
###

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT

# Make tests verbose and provide stdout
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_process
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_config
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_connect
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_get_set
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_poll
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_autosample
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_test
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_errors
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_discover_autosample


## Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe37smb.ooicore.driver',
    driver_class="SBE37Driver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType()
)
#

# Used to validate param config retrieved from driver.
PARAMS = {
    SBE37Parameter.OUTPUTSAL : bool,
    SBE37Parameter.OUTPUTSV : bool,
    SBE37Parameter.NAVG : int,
    SBE37Parameter.SAMPLENUM : int,
    SBE37Parameter.INTERVAL : int,
    SBE37Parameter.STORETIME : bool,
    SBE37Parameter.TXREALTIME : bool,
    SBE37Parameter.SYNCMODE : bool,
    SBE37Parameter.SYNCWAIT : int,
    SBE37Parameter.TCALDATE : tuple,
    SBE37Parameter.TA0 : float,
    SBE37Parameter.TA1 : float,
    SBE37Parameter.TA2 : float,
    SBE37Parameter.TA3 : float,
    SBE37Parameter.CCALDATE : tuple,
    SBE37Parameter.CG : float,
    SBE37Parameter.CH : float,
    SBE37Parameter.CI : float,
    SBE37Parameter.CJ : float,
    SBE37Parameter.WBOTC : float,
    SBE37Parameter.CTCOR : float,
    SBE37Parameter.CPCOR : float,
    SBE37Parameter.PCALDATE : tuple,
    SBE37Parameter.PA0 : float,
    SBE37Parameter.PA1 : float,
    SBE37Parameter.PA2 : float,
    SBE37Parameter.PTCA0 : float,
    SBE37Parameter.PTCA1 : float,
    SBE37Parameter.PTCA2 : float,
    SBE37Parameter.PTCB0 : float,
    SBE37Parameter.PTCB1 : float,
    SBE37Parameter.PTCB2 : float,
    SBE37Parameter.POFFSET : float,
    SBE37Parameter.RCALDATE : tuple,
    SBE37Parameter.RTCA0 : float,
    SBE37Parameter.RTCA1 : float,
    SBE37Parameter.RTCA2 : float
}



class SBEMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # DS parameters
        SBE37Parameter.OUTPUTSAL: {TYPE: bool, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        SBE37Parameter.OUTPUTSV: {TYPE: bool, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        SBE37Parameter.NAVG : {TYPE: int, READONLY: False, DA: True, STARTUP: False, REQUIRED: False},
        SBE37Parameter.SAMPLENUM : {TYPE: int, READONLY: False, DA: False, STARTUP: True, REQUIRED: False, VALUE: False},
        SBE37Parameter.INTERVAL : {TYPE: int, READONLY: False, DA: False, STARTUP: True, REQUIRED: False, VALUE: 1},
        SBE37Parameter.STORETIME : {TYPE: bool, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        SBE37Parameter.TXREALTIME : {TYPE: bool, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        SBE37Parameter.SYNCMODE : {TYPE: bool, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        SBE37Parameter.SYNCWAIT : {TYPE: int, READONLY: False, DA: False, STARTUP: True, REQUIRED: False}, # may need a default , VALUE: 1
        # DC parameters
        SBE37Parameter.TCALDATE : {TYPE: tuple, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.TA0 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.TA1 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.TA2 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.TA3 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CCALDATE : {TYPE: tuple, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CG : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CH : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CI : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CJ : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.WBOTC : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CTCOR : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.CPCOR : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PCALDATE : {TYPE: tuple, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PA0 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PA1 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PA2 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCA0 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCA1 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCA2 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCB0 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCB1 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.PTCB2 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.POFFSET : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.RCALDATE : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.RTCA0 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.RTCA1 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        SBE37Parameter.RTCA2 : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},          
    }

    _sample_parameters = {
        SBE37DataParticleKey.TEMP: {TYPE: float, VALUE: 55.9044, REQUIRED: False },
        SBE37DataParticleKey.CONDUCTIVITY: {TYPE: float, VALUE: 41.40609, REQUIRED: False },
        SBE37DataParticleKey.DEPTH: {TYPE: float, VALUE: 572.170, REQUIRED: False }
    }
    
    _device_calibration_parameters = {
        SBE37DeviceCalibrationParticleKey.TCALDATE:  {TYPE: list, VALUE: [8, 11, 2005], REQUIRED: False }, 
        SBE37DeviceCalibrationParticleKey.TA0: {TYPE: float, VALUE: -2.572242e-04, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.TA1: {TYPE: float, VALUE: 3.138936e-04, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.TA2: {TYPE: float, VALUE: -9.717158e-06, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.TA3:  {TYPE: float, VALUE: 2.138735e-07, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.CCALDATE: {TYPE: list, VALUE: [8, 11, 2005], REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.G: {TYPE: float, VALUE: -9.870930e-01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.H: {TYPE: float, VALUE: 1.417895e-01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.I: {TYPE: float, VALUE: 1.334915e-04, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.J: {TYPE: float, VALUE: 3.339261e-05, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.CPCOR: {TYPE: float, VALUE: 9.570000e-08, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.CTCOR: {TYPE: float, VALUE: 3.250000e-06, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.WBOTC: {TYPE: float, VALUE: 1.202400e-05, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PCALDATE: {TYPE: list, VALUE: [12, 8, 2005], REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PRANGE: {TYPE: float, VALUE: 10847.1964958, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PSN: {TYPE: int, VALUE: 4955, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PA0: {TYPE: float, VALUE: 5.916199e+00, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PA1: {TYPE: float, VALUE: 4.851819e-01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PA2: {TYPE: float, VALUE: 4.596432e-07, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCA0: {TYPE: float, VALUE: 2.762492e+02, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCA1: {TYPE: float, VALUE: 6.603433e-01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCA2: {TYPE: float, VALUE: 5.756490e-03, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCSB0: {TYPE: float, VALUE: 2.461450e+01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCSB1: {TYPE: float, VALUE: -9.000000e-04, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.PTCSB2: {TYPE: float, VALUE: 0.000000e+00, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.POFFSET: {TYPE: float, VALUE: 0.000000e+00, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.RTC: {TYPE: list, VALUE: [8, 11, 2005], REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.RTCA0: {TYPE: float, VALUE: 9.999862e-01, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.RTCA1: {TYPE: float, VALUE: 1.686132e-06, REQUIRED: False },
        SBE37DeviceCalibrationParticleKey.RTCA2: {TYPE: float, VALUE: -3.022745e-08, REQUIRED: False },
    }
    
    _device_status_parameters = {
        SBE37DeviceStatusParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 2165, REQUIRED: False },
        SBE37DeviceStatusParticleKey.DATE_TIME: {TYPE: float, VALUE: 3569109103.0, REQUIRED: False },        
        SBE37DeviceStatusParticleKey.LOGGING: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE37DeviceStatusParticleKey.SAMPLE_INTERVAL: {TYPE: int, VALUE: 20208, REQUIRED: False },
        SBE37DeviceStatusParticleKey.SAMPLE_NUMBER: {TYPE: int, VALUE: 0, REQUIRED: False },
        SBE37DeviceStatusParticleKey.MEMORY_FREE: {TYPE: int, VALUE: 200000, REQUIRED: False },
        SBE37DeviceStatusParticleKey.TX_REALTIME: {TYPE: bool, VALUE: True, REQUIRED: False },
        SBE37DeviceStatusParticleKey.OUTPUT_SALINITY: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE37DeviceStatusParticleKey.OUTPUT_SOUND_VELOCITY: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE37DeviceStatusParticleKey.STORE_TIME: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE37DeviceStatusParticleKey.NUMBER_OF_SAMPLES_TO_AVERAGE: {TYPE: int, VALUE: 0, REQUIRED: False },
        SBE37DeviceStatusParticleKey.REFERENCE_PRESSURE: {TYPE: float, VALUE: 0.0, REQUIRED: False },
        SBE37DeviceStatusParticleKey.SERIAL_SYNC_MODE: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE37DeviceStatusParticleKey.SERIAL_SYNC_WAIT: {TYPE: int, VALUE: 0, REQUIRED: False },
        SBE37DeviceStatusParticleKey.INTERNAL_PUMP: {TYPE: bool, VALUE: True, REQUIRED: False },
        SBE37DeviceStatusParticleKey.TEMPERATURE: {TYPE: float, VALUE: 7.54, REQUIRED: False },
    }
    
    
    

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        '''
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        '''
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    #   Data Particle Parameters Methods
    ###
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, SBE37DataParticle)):
            self.assert_particle_sample(data_particle)
        elif (isinstance(data_particle, SBE37DeviceCalibrationParticle)):
            self.assert_particle_device_calibration(data_particle)
        elif (isinstance(data_particle, SBE37DeviceStatusParticleKey)):
            self.assert_particle_device_status(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_particle_device_calibration(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceCalibrationDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._device_calibration_parameters, verify_values)

    def assert_particle_device_status(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._device_status_parameters, verify_values)



@attr('UNIT', group='mi')
class SBEUnitTestCase(SeaBirdUnitTest, SBEMixin):
    """
    Unit Test Container
    """
    
    def setUp(self):
        SeaBirdUnitTest.setUp(self)
        
    TEST_OVERLAY_CONFIG = [SBE37Parameter.SAMPLENUM, SBE37Parameter.INTERVAL]

    TEST_BASELINE_CONFIG = {
        SBE37Parameter.OUTPUTSAL : True,
        SBE37Parameter.OUTPUTSV : True,
        SBE37Parameter.NAVG : 1,
        SBE37Parameter.SAMPLENUM : 1,
        SBE37Parameter.INTERVAL : 1,
        SBE37Parameter.STORETIME : True,
        SBE37Parameter.TXREALTIME : True,
        SBE37Parameter.SYNCMODE : True,
        SBE37Parameter.SYNCWAIT : 1,
        SBE37Parameter.TCALDATE : (1,1),
        SBE37Parameter.TA0 : 1.0,
        SBE37Parameter.TA1 : 1.0,
        SBE37Parameter.TA2 : 1.0,
        SBE37Parameter.TA3 : 1.0,
        SBE37Parameter.CCALDATE : (1,1),
        SBE37Parameter.CG : 1.0,
        SBE37Parameter.CH : 1.0,
        SBE37Parameter.CI : 1.0,
        SBE37Parameter.CJ : 1.0,
        SBE37Parameter.WBOTC : 1.0,
        SBE37Parameter.CTCOR : 1.0,
        SBE37Parameter.CPCOR : 1.0,
        SBE37Parameter.PCALDATE : (1,1),
        SBE37Parameter.PA0 : 1.0,
        SBE37Parameter.PA1 : 1.0,
        SBE37Parameter.PA2 : 1.0,
        SBE37Parameter.PTCA0 : 1.0,
        SBE37Parameter.PTCA1 : 1.0,
        SBE37Parameter.PTCA2 : 1.0,
        SBE37Parameter.PTCB0 : 1.0,
        SBE37Parameter.PTCB1 : 1.0,
        SBE37Parameter.PTCB2 : 1.0,
        SBE37Parameter.POFFSET : 1.0,
        SBE37Parameter.RCALDATE : (1,1),
        SBE37Parameter.RTCA0 : 1.0,
        SBE37Parameter.RTCA1 : 1.0,
        SBE37Parameter.RTCA2 : 1.0
        }
    
    def test_zero_data(self):
        particle = SBE37DataParticle('#87.9140,5.42747, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        parsed = particle.generate()
        self.assertNotEquals(parsed, None)
        particle = SBE37DataParticle('#00.0000,5.42747, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        self.assertNotEquals(parsed, None)
        particle = SBE37DataParticle('#87.9140,0.00000, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        self.assertNotEquals(parsed, None)
        particle = SBE37DataParticle('#87.9140,5.42747, 000.000,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        self.assertNotEquals(parsed, None)
        
        # garbage is not okay
        particle = SBE37DataParticle('#fo.oooo,5.42747, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
        particle = SBE37DataParticle('#87.9140,f.ooooo, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
        particle = SBE37DataParticle('#87.9140,5.42747, foo.ooo,   37.1829, 1506.961, 02 Jan 2001, 15:34:51',
                                     port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = SBE37Driver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE, self.assert_particle_sample, True)
      
        self.assert_particle_published(driver, SAMPLE_DC, self.assert_particle_device_calibration, True)
        self.assert_particle_published(driver, SAMPLE_DS, self.assert_particle_device_status, True)

      

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class SBEIntTestCase(SeaBirdIntegrationTest, SBEMixin):
    """
    Integration tests for the sbe37 driver. This class tests and shows
    use patterns for the sbe37 driver as a zmq driver process.
    """    
    def setUp(self):
        SeaBirdIntegrationTest.setUp(self)


    def assertSampleDict(self, val):
        """
        Verify the value is an SBE37DataParticle with a few key fields or a
        dict with 'raw' and 'parsed' tags.
        """
        
        if (isinstance(val, SBE37DataParticle)):
            raw_dict = json.loads(val.generate_raw())
            parsed_dict = json.loads(val.generate_parsed())
        else:
            self.assertTrue(val['raw'])
            raw_dict = val['raw']
            self.assertTrue(val['parsed'])
            parsed_dict = val['parsed']
            
        self.assertTrue(raw_dict[DataParticleKey.STREAM_NAME],
                        DataParticleValue.RAW)
        self.assertTrue(raw_dict[DataParticleKey.PKT_FORMAT_ID],
                        DataParticleValue.JSON_DATA)
        self.assertTrue(raw_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(raw_dict[DataParticleKey.VALUES],
                        list))
        
        self.assertTrue(parsed_dict[DataParticleKey.STREAM_NAME],
                        DataParticleType.PARSED)
        self.assertTrue(parsed_dict[DataParticleKey.PKT_FORMAT_ID],
                        DataParticleValue.JSON_DATA)
        self.assertTrue(parsed_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(parsed_dict[DataParticleKey.VALUES],
                        list))
        
    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            for (key, type_val) in PARAMS.iteritems():
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
                self.assertTrue(isinstance(val, PARAMS[key]))
    
    def assertParamVals(self, params, correct_params):
        """
        Verify parameters take the correct values.
        """
        self.assertEqual(set(params.keys()), set(correct_params.keys()))
        for (key, val) in params.iteritems():
            correct_val = correct_params[key]
            if isinstance(val, float):
                # Verify to 5% of the larger value.
                max_val = max(abs(val), abs(correct_val))
                self.assertAlmostEqual(val, correct_val, delta=max_val*.01)

            else:
                # int, bool, str, or tuple of same
                self.assertEqual(val, correct_val)

    def test_configuration(self):
        """
        Test to configure the driver process for device comms and transition
        to disconnected state.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver returned state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        log.info("test_connect test started")

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
    def test_startup_configure(self):
        """
        Test to see if the configuration is set properly upon startup.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        startup_config = {DriverConfigKey.PARAMETERS:{SBE37Parameter.SAMPLENUM:13}}
        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect', startup_config)

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)
        
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        
        result = self.driver_client.cmd_dvr('get_resource',
                                            [SBE37Parameter.SAMPLENUM])
        self.assertNotEquals(result[SBE37Parameter.SAMPLENUM], 13)
        result = self.driver_client.cmd_dvr('apply_startup_params')
        result = self.driver_client.cmd_dvr('get_resource',
                                            [SBE37Parameter.SAMPLENUM])
        self.assertEquals(result[SBE37Parameter.SAMPLENUM], 13)
        
    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
        self.assertParamDict(reply, True)

        # Remember original configuration.
        orig_config = reply
        
        # Grab a subset of parameters.
        params = [
            SBE37Parameter.TA0,
            SBE37Parameter.INTERVAL,
            SBE37Parameter.STORETIME,
            SBE37Parameter.TCALDATE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        old_date = orig_params[SBE37Parameter.TCALDATE]
        new_params = {
            SBE37Parameter.TA0 : orig_params[SBE37Parameter.TA0] * 1.2,
            SBE37Parameter.INTERVAL : orig_params[SBE37Parameter.INTERVAL] + 1,
            SBE37Parameter.STORETIME : not orig_params[SBE37Parameter.STORETIME],
            SBE37Parameter.TCALDATE : (old_date[0], old_date[1], old_date[2] + 1)
        }

        # Set parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamVals(reply, new_params)
        
        # Restore original parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamVals(reply, orig_params)

        # Retrieve the configuration and ensure it matches the original.
        # Remove samplenum as it is switched by autosample and storetime.
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
        reply.pop('SAMPLENUM')
        orig_config.pop('SAMPLENUM')
        self.assertParamVals(reply, orig_config)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is disconnected.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)        
    
    def test_autosample(self):
        """
        Test autosample mode.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)
        
        # Wait for a few samples to roll in.
        gevent.sleep(30)
        
        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        self.assertTrue(len(sample_events) >= 2)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    @unittest.skip('Not supported by simulator and very long (> 5 min).')
    def test_test(self):
        """
        Test the hardware testing mode.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        start_time = time.time()
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.TEST)

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.TEST)
        
        while state != SBE37ProtocolState.COMMAND:
            gevent.sleep(5)
            elapsed = time.time() - start_time
            log.info('Device testing %f seconds elapsed.' % elapsed)
            state = self.driver_client.cmd_dvr('get_resource_state')

        # Verify we received the test result and it passed.
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.TEST_RESULT]
        self.assertTrue(len(test_results) == 1)
        self.assertEqual(test_results[0]['value']['success'], 'Passed')

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        with self.assertRaises(InstrumentCommandException):
            reply = self.driver_client.cmd_dvr('bogus_command')

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        with self.assertRaises(InstrumentParameterException):
            reply = self.driver_client.cmd_dvr('configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = 'not a config dict'            
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG.pop('addr')
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG['addr'] = ''
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
        
        # Configure for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
        self.assert_particle_sample(reply[1])

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('connect')

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
        self.assertParamDict(reply, True)
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            reply = self.driver_client.cmd_dvr('get_resource')
            
        # Assert get fails without a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            reply = self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails without a bad parameter (not ALL or a list).
        #with self.assertRaises(InvalidParameterValueError):
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                SBE37Parameter.INTERVAL,
                SBE37Parameter.STORETIME,
                SBE37Parameter.TCALDATE
                ]
            reply = self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                SBE37Parameter.INTERVAL : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set_resource', bogus_params)
        
        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
    
    @unittest.skip('Not supported by simulator.')
    def test_discover_autosample(self):
        """
        Test the device can discover autosample mode.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)
    
        # Let a sample or two come in.
        gevent.sleep(30)
    
        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Wait briefly before we restart the comms.
        gevent.sleep(10)
    
        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        count = 0
        while True:
            try:        
                reply = self.driver_client.cmd_dvr('discover_state')

            except InstrumentTimeoutException:
                count += 1
                if count >=5:
                    self.fail('Could not discover device state.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)

        # Let a sample or two come in.
        # This device takes awhile to begin transmitting again after you
        # prompt it in autosample mode.
        gevent.sleep(30)

        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    def test_startup_config(self):
        """
        Verify that the configuration of the instrument gets set upon launch
        """
        # Startup params are SAMPLENUM, INTERVAL, SYNCWAIT
        # INTERVAL has a default value of 1
        startup_config = {DriverConfigKey.PARAMETERS:{SBE37Parameter.SAMPLENUM:2,
                                                      SBE37Parameter.NAVG:2}}

        # SBE37 doesnt have a startup routine, so we wont test default params
        # as part of the configure routine, mainly testing some InstrumentDriver
        # base logic
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())
        reply = self.driver_client.cmd_dvr('connect')
        reply = self.driver_client.cmd_dvr('discover_state')

        self.driver_client.cmd_dvr("set_init_params", startup_config)
        self.driver_client.cmd_dvr("set_resource", {SBE37Parameter.SYNCWAIT:3})     
        self.driver_client.cmd_dvr("apply_startup_params") # result now matches instrument
        result = self.driver_client.cmd_dvr("get_resource", DriverParameter.ALL)
        self.assertEquals(result[SBE37Parameter.SAMPLENUM], 2) # init param
        self.assertEquals(result[SBE37Parameter.INTERVAL], 1) # default param
        self.assertEquals(result[SBE37Parameter.SYNCWAIT], 3) # manual param
    
        # all setup now, driver stuff could happen here in the real world
        # get to command mode?
        
        # manual changes
        self.driver_client.cmd_dvr("set_resource", {SBE37Parameter.NAVG:10}) 
        self.driver_client.cmd_dvr("set_resource", {SBE37Parameter.SAMPLENUM:10})
        self.driver_client.cmd_dvr("set_resource", {SBE37Parameter.INTERVAL:10}) 
        self.driver_client.cmd_dvr("set_resource", {SBE37Parameter.SYNCWAIT:10})
        result = self.driver_client.cmd_dvr("get_resource", DriverParameter.ALL)
        self.assertEquals(result[SBE37Parameter.NAVG], 10) # not a startup param
        self.assertEquals(result[SBE37Parameter.SAMPLENUM], 10) # init param
        self.assertEquals(result[SBE37Parameter.INTERVAL], 10) # default param
        self.assertEquals(result[SBE37Parameter.SYNCWAIT], 10) # manual param

        # confirm re-apply
        self.driver_client.cmd_dvr("apply_startup_params")
        result = self.driver_client.cmd_dvr("get_resource", DriverParameter.ALL)
        self.assertEquals(result[SBE37Parameter.SAMPLENUM], 2) # init param
        self.assertEquals(result[SBE37Parameter.INTERVAL], 1) # default param
        self.assertEquals(result[SBE37Parameter.SYNCWAIT], 10) # manual param
        
        
        
        
        
    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(SBE37ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.PARSED, self.assert_particle_sample)
        self.assert_particle_generation(SBE37ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_device_status)
        self.assert_particle_generation(SBE37ProtocolEvent.ACQUIRE_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_device_calibration)





#self._dvr_proc = self.driver_process
#self._pagent = self.port_agent
#self._dvr_client = self.driver_client
#self._events = self.events
#COMMS_CONFIG = self.port_agent_comm_config()
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SBEQualificationTestCase(SeaBirdQualificationTest, SBEMixin):
    """Qualification Test Container"""

    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.
    
    def setUp(self):
        SeaBirdQualificationTest.setUp(self)

    @unittest.skip("da currently broken for this instrument")
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (telnet mode)
        """
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        s = TcpClient(retval.result['ip_address'], retval.result['port'])
        s.telnet_handshake()
        
        s.send_data("ts\r\n", "1")
        log.debug("SENT THE TS COMMAND")

        pattern = re.compile("^([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9a-z]+),([ 0-9:]+)")

        matches = 0
        n = 0
        while n < 100:
            n = n + 1
            gevent.sleep(1)
            data = s.get_data()
            log.debug("READ ==>" + str(repr(data)))
            m = pattern.search(data)
            if m != None:
                matches = m.lastindex
                if matches == 7:
                    break

        self.assertTrue(matches == 7) # need to have found 7 conformant fields.

    @unittest.skip("Do not include until a good method is devised")
    def test_direct_access_virtual_serial_port_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (virtual serial port mode)

        Status: Sample code for this test has yet to be written.
                WCB will implement next iteration

        UPDATE: Do not include for now. May include later as a
                good method is devised

        TODO:
        """
        pass

    def test_sbe37_parameter_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(SBE37Parameter.ALL, DriverParameter.ALL)

        self.assertTrue(self.check_for_reused_values(DriverParameter))
        self.assertTrue(self.check_for_reused_values(SBE37Parameter))


    def test_protocol_event_enum(self):
        """
        @brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(SBE37ProtocolEvent.ENTER, DriverEvent.ENTER)
        self.assertEqual(SBE37ProtocolEvent.EXIT, DriverEvent.EXIT)
        self.assertEqual(SBE37ProtocolEvent.GET, DriverEvent.GET)
        self.assertEqual(SBE37ProtocolEvent.SET, DriverEvent.SET)
        self.assertEqual(SBE37ProtocolEvent.DISCOVER, DriverEvent.DISCOVER)
        self.assertEqual(SBE37ProtocolEvent.ACQUIRE_SAMPLE, DriverEvent.ACQUIRE_SAMPLE)
        self.assertEqual(SBE37ProtocolEvent.START_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolEvent.STOP_AUTOSAMPLE, DriverEvent.STOP_AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolEvent.TEST, DriverEvent.TEST)
        self.assertEqual(SBE37ProtocolEvent.RUN_TEST, DriverEvent.RUN_TEST)
        self.assertEqual(SBE37ProtocolEvent.CALIBRATE, DriverEvent.CALIBRATE)
        self.assertEqual(SBE37ProtocolEvent.EXECUTE_DIRECT, DriverEvent.EXECUTE_DIRECT)
        self.assertEqual(SBE37ProtocolEvent.START_DIRECT, DriverEvent.START_DIRECT)
        self.assertEqual(SBE37ProtocolEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

        self.assertTrue(self.check_for_reused_values(DriverEvent))
        self.assertTrue(self.check_for_reused_values(SBE37ProtocolEvent))


    def test_protocol_state_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.

        """

        self.assertEqual(SBE37ProtocolState.UNKNOWN, DriverProtocolState.UNKNOWN)
        self.assertEqual(SBE37ProtocolState.COMMAND, DriverProtocolState.COMMAND)
        self.assertEqual(SBE37ProtocolState.AUTOSAMPLE, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolState.TEST, DriverProtocolState.TEST)
        self.assertEqual(SBE37ProtocolState.CALIBRATE, DriverProtocolState.CALIBRATE)
        self.assertEqual(SBE37ProtocolState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS)


        #SBE37ProtocolState.UNKNOWN = SBE37ProtocolState.COMMAND
        #SBE37ProtocolState.UNKNOWN2 = SBE37ProtocolState.UNKNOWN

        self.assertTrue(self.check_for_reused_values(DriverProtocolState))
        self.assertTrue(self.check_for_reused_values(SBE37ProtocolState))


    @unittest.skip("Underlying method not yet implemented")
    def test_driver_memory_leaks(self):
        """
        @brief long running test that runs over a half hour, and looks for memory leaks.
               stub this out for now
        TODO: write test if time permits after all other tests are done.
        """
        pass

    @unittest.skip("SKIP for now.  This will come in around the time we split IA into 2 parts wet side dry side")
    def test_instrument_agent_data_decimation(self):
        """
        @brief This test verifies that the instrument driver,
               if required, can properly decimate sampling data.
                decimate here means send every 5th sample.

        """
        pass


    def assertParsedGranules(self):
        
        for granule in self.data_subscribers.parsed_samples_received:
            rdt = RecordDictionaryTool.load_from_granule(granule)
            
            self.assert_('conductivity' in rdt)
            self.assert_(rdt['conductivity'] is not None)
            self.assertTrue(isinstance(rdt['conductivity'], numpy.ndarray))                      

            self.assert_('depth' in rdt)
            self.assert_(rdt['depth'] is not None)
            self.assertTrue(isinstance(rdt['depth'], numpy.ndarray))

            self.assert_('temp' in rdt)
            self.assert_(rdt['temp'] is not None)
            self.assertTrue(isinstance(rdt['temp'], numpy.ndarray))
        
    def assertSampleDataParticle(self, val):
        """
        Verify the value for a sbe37 sample data particle

        {
          'quality_flag': 'ok',
          'preferred_timestamp': 'driver_timestamp',
          'stream_name': 'parsed',
          'pkt_format_id': 'JSON_Data',
          'pkt_version': 1,
          'driver_timestamp': 3559843883.8029947,
          'values': [
            {
              'value_id': 'temp',
              'value': 67.4448
            },
            {
              'value_id': 'conductivity',
              'value': 44.69101
            },
            {
              'value_id': 'pressure',
              'value': 865.096
            }
          ],
        }
        """

        if (isinstance(val, SBE37DataParticle)):
            sample_dict = json.loads(val.generate_parsed())
        else:
            sample_dict = val

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleType.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            self.assertTrue(x['value_id'] in ['temp', 'conductivity', 'pressure'])
            self.assertTrue(isinstance(x['value'], float))


    def test_capabilities(self):
        """
        Test the ability to retrieve agent and resource parameter and command
        capabilities in various system states.
        """

        agt_cmds_all = [
            ResourceAgentEvent.INITIALIZE,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_ACTIVE,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.RUN,
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.PAUSE,
            ResourceAgentEvent.RESUME,
            ResourceAgentEvent.GO_COMMAND,
            ResourceAgentEvent.GO_DIRECT_ACCESS
        ]

        agt_pars_all = ['example']

        res_cmds_all =[
            SBE37ProtocolEvent.TEST,
            SBE37ProtocolEvent.ACQUIRE_SAMPLE,
            SBE37ProtocolEvent.START_AUTOSAMPLE,
            SBE37ProtocolEvent.STOP_AUTOSAMPLE
        ]

        res_pars_all = PARAMS.keys()


        def sort_caps(caps_list):
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_pars = []

            if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
                agt_cmds = [x.name for x in retval if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in retval if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in retval if x.cap_type==CapabilityType.RES_CMD]
                res_pars = [x.name for x in retval if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps_list)>0 and isinstance(caps_list[0], dict):
                agt_cmds = [x['name'] for x in retval if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in retval if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in retval if x['cap_type']==CapabilityType.RES_CMD]
                res_pars = [x['name'] for x in retval if x['cap_type']==CapabilityType.RES_PAR]

            return agt_cmds, agt_pars, res_cmds, res_pars


        ##################################################################
        # UNINITIALIZED
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_uninitialized = [
            ResourceAgentEvent.INITIALIZE
        ]
        self.assertItemsEqual(agt_cmds, agt_cmds_uninitialized)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # INACTIVE
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_inactive = [
            ResourceAgentEvent.GO_ACTIVE,
            ResourceAgentEvent.RESET
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_inactive)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # IDLE
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_idle = [
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.RUN
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_idle)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states as read from IDLE.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # COMMAND
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_command = [
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_DIRECT_ACCESS,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.PAUSE
        ]

        res_cmds_command = [
            SBE37ProtocolEvent.TEST,
            SBE37ProtocolEvent.ACQUIRE_SAMPLE,
            SBE37ProtocolEvent.START_AUTOSAMPLE
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_command)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_command)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state COMMAND.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        cmd = AgentCommand(command=SBE37ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        ##################################################################
        # STREAMING
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state STREAMING
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)


        agt_cmds_streaming = [
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_INACTIVE
        ]

        res_cmds_streaming = [
            SBE37ProtocolEvent.STOP_AUTOSAMPLE
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_streaming)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_streaming)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state STREAMING.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        gevent.sleep(5)

        cmd = AgentCommand(command=SBE37ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        ##################################################################
        # COMMAND
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_command)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_command)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state STREAMING.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # UNINITIALIZED
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_uninitialized)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

    def test_autosample(self):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


        # Make sure the sampling rate and transmission are sane.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5,
            SBE37Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_resource(params)

        self.data_subscribers.clear_sample_queue('parsed')

        # Begin streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Assert we got 3 samples.
        samples = self.data_subscribers.get_samples('parsed', 3)
        self.assertGreaterEqual(len(samples), 3)

        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())

        # Halt streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        self.doCleanups()

    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            for (key, type_val) in PARAMS.iteritems():
                if type_val == list or type_val == tuple:
                    self.assertTrue(isinstance(pd[key], (list, tuple)))
                else:
                    self.assertTrue(isinstance(pd[key], type_val))

        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
                self.assertTrue(isinstance(val, PARAMS[key]))

    def assertParamVals(self, params, correct_params):
        """
        Verify parameters take the correct values.
        """
        self.assertEqual(set(params.keys()), set(correct_params.keys()))
        for (key, val) in params.iteritems():
            correct_val = correct_params[key]
            if isinstance(val, float):
                # Verify to 5% of the larger value.
                max_val = max(abs(val), abs(correct_val))
                self.assertAlmostEqual(val, correct_val, delta=max_val*.01)

            elif isinstance(val, (list, tuple)):
                # list of tuple.
                self.assertEqual(list(val), list(correct_val))

            else:
                # int, bool, str.
                self.assertEqual(val, correct_val)

    @unittest.skip("PROBLEM WITH command=ResourceAgentEvent.GO_ACTIVE")
    def test_get_set(self):
        """
        Test instrument driver get and set interface.
        """
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()

        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Retrieve all resource parameters.
        reply = self.instrument_agent_client.get_resource(SBE37Parameter.ALL)
        self.assertParamDict(reply, True)
        orig_config = reply

        # Retrieve a subset of resource parameters.
        params = [
            SBE37Parameter.OUTPUTSV,
            SBE37Parameter.NAVG,
            SBE37Parameter.TA0
        ]
        reply = self.instrument_agent_client.get_resource(params)
        self.assertParamDict(reply)
        orig_params = reply

        # Set a subset of resource parameters.
        new_params = {
            SBE37Parameter.OUTPUTSV : not orig_params[SBE37Parameter.OUTPUTSV],
            SBE37Parameter.NAVG : orig_params[SBE37Parameter.NAVG] + 1,
            SBE37Parameter.TA0 : orig_params[SBE37Parameter.TA0] * 2
        }
        self.instrument_agent_client.set_resource(new_params)
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertParamVals(check_new_params, new_params)

        # Reset the parameters back to their original values.
        self.instrument_agent_client.set_resource(orig_params)
        reply = self.instrument_agent_client.get_resource(SBE37Parameter.ALL)
        reply.pop(SBE37Parameter.SAMPLENUM)
        orig_config.pop(SBE37Parameter.SAMPLENUM)
        self.assertParamVals(reply, orig_config)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    @unittest.skip("PROBLEM WITH command=ResourceAgentEvent.GO_ACTIVE")
    def oldtest_poll(self):
        """
        Test observatory polling function.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        ###
        # Poll for a few samples
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        self.data_subscribers.clear_sample_queue(DataParticleType.PARSED)
        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        # Watch the parsed data queue and return once three samples
        # have been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(DataParticleType.PARSED, 3)
        self.assertGreaterEqual(len(samples), 3)

        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        self.doCleanups()

    def test_poll(self):
        '''
        Verify that we can poll for a sample.  Take sample for this instrument
        Also poll for other engineering data streams.
        '''
        self.assert_enter_command_mode()


        self.assert_particle_polled(SBE37ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sample, DataParticleType.PARSED)
        self.assert_particle_polled(SBE37ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_device_status, DataParticleType.DEVICE_STATUS)
        self.assert_particle_polled(SBE37ProtocolEvent.ACQUIRE_CONFIGURATION, self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION)


    def test_instrument_driver_vs_invalid_commands(self):
        """
        @Author Edward Hunter
        @brief This test should send mal-formed, misspelled,
               missing parameter, or out of bounds parameters
               at the instrument driver in an attempt to
               confuse it.

               See: test_instrument_driver_to_physical_instrument_interoperability
               That test will provide the how-to of connecting.
               Once connected, send messed up commands.

               * negative testing


               Test illegal behavior and replies.
        """


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)



        # Try to execute agent command with bogus command.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command='BOGUS_COMMAND')
            retval = self.instrument_agent_client.execute_agent(cmd)


        # Can't go active in unitialized state.
        # Status 660 is state error.
        with self.assertRaises(Conflict):
            cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
            retval = self.instrument_agent_client.execute_agent(cmd)


        # Try to execute the resource, wrong state.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
            retval = self.instrument_agent_client.execute_agent(cmd)


        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)


        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)


        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # OK, I can do this now.
        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertTrue(reply.result)

        # 404 unknown agent command.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command='kiss_edward')
            reply = self.instrument_agent_client.execute_agent(cmd)


        '''
        @todo this needs to be re-enabled eventually
        # 670 unknown driver command.
        cmd = AgentCommand(command='acquire_sample_please')
        retval = self.instrument_agent_client.execute(cmd)
        log.debug("retval = " + str(retval))

        # the return value will likely be changed in the future to return
        # to being 670... for now, lets make it work.
        #self.assertEqual(retval.status, 670)
        self.assertEqual(retval.status, -1)

        try:
            reply = self.instrument_agent_client.get_param('1234')
        except Exception as e:
            log.debug("InstrumentParameterException ERROR = " + str(e))

        #with self.assertRaises(XXXXXXXXXXXXXXXXXXXXXXXX):
        #    reply = self.instrument_agent_client.get_param('1234')

        # 630 Parameter error.
        #with self.assertRaises(InstParameterError):
        #    reply = self.instrument_agent_client.get_param('bogus bogus')

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)
        '''
        pass

    def test_direct_access_config(self):
        """
        Verify that the configurations work when we go into direct access mode
        and jack with settings
        """
        # NAVG is direct access
        # INTERVAL has a default value of 1

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        self.instrument_agent_client.execute_agent(cmd)
        
        self.instrument_agent_client.set_resource({SBE37Parameter.NAVG:2})
        self.instrument_agent_client.set_resource({SBE37Parameter.SAMPLENUM:2})
        self.instrument_agent_client.set_resource({SBE37Parameter.INTERVAL:2})     

        params = [
            SBE37Parameter.SAMPLENUM,
            SBE37Parameter.NAVG,
            SBE37Parameter.INTERVAL
        ]
        reply = self.instrument_agent_client.get_resource(params)
        self.assertParamDict(reply)
        orig_params = reply
        self.assertEquals(reply[SBE37Parameter.NAVG], 2) # da param
        self.assertEquals(reply[SBE37Parameter.SAMPLENUM], 2) # non-da param
        self.assertEquals(reply[SBE37Parameter.INTERVAL], 2) # non-da param, w/default
        
        # go into direct access mode
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("INTERVAL=20\r\n")
        self.tcp_client.send_data("NAVG=20\r\n")
        self.tcp_client.send_data("SAMPLENUM=20\r\n")
        self.assert_direct_access_stop_telnet()

        reply = self.instrument_agent_client.get_resource(params)
        self.assertParamDict(reply)
        orig_params = reply
        self.assertEquals(reply[SBE37Parameter.NAVG], 2) # da param
        self.assertEquals(reply[SBE37Parameter.SAMPLENUM], 20) # non-da param
        self.assertEquals(reply[SBE37Parameter.INTERVAL], 20) # non-da param, w/default