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

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
from gevent.timeout import Timeout
import gevent
import socket
from mock import Mock

# Standard lib imports
import time
import unittest
import ntplib
import datetime
import json

# 3rd party imports
from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import BadRequest

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentDriver
from mi.instrument.nobska.mavs4.ooicore.driver import DataParticleType
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolStates
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolEvent
from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentProtocol
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentParameters
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentCmds
from mi.instrument.nobska.mavs4.ooicore.driver import Capability
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentPrompts
from mi.instrument.nobska.mavs4.ooicore.driver import Mavs4StatusDataParticleKey
from mi.instrument.nobska.mavs4.ooicore.driver import Mavs4SampleDataParticleKey
from mi.instrument.nobska.mavs4.ooicore.driver import Mavs4SampleDataParticle
from mi.instrument.nobska.mavs4.ooicore.driver import DeployMenuParameters
from mi.instrument.nobska.mavs4.ooicore.driver import SystemConfigurationMenuParameters
from mi.instrument.nobska.mavs4.ooicore.driver import VelocityOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import CompassOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import CompassScaleFactorsParameters
from mi.instrument.nobska.mavs4.ooicore.driver import TiltOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import SubMenues
from mi.instrument.nobska.mavs4.ooicore.driver import INSTRUMENT_NEWLINE

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.chunker import StringChunker

from mi.core.tcp_client import TcpClient

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nobska.mavs4.ooicore.driver',
    driver_class="mavs4InstrumentDriver",

    instrument_agent_resource_id = 'nobska_mavs4_ooicore',
    instrument_agent_name = 'nobska_mavs4_ooicore_agent',
    instrument_agent_packet_config = DataParticleType(),
    
    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            InstrumentParameters.VELOCITY_FRAME: '3',
        },
    }
)

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT
    
class Mavs4Mixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    
    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        InstrumentParameters.SYS_CLOCK : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.NOTE1 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.NOTE2 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.NOTE3 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.VELOCITY_FRAME : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: '3', VALUE: '3', REQUIRED: False},
        InstrumentParameters.MONITOR : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.LOG_DISPLAY_TIME : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.QUERY_MODE : {TYPE: str, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.FREQUENCY : {TYPE: float, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1.0, REQUIRED: False},
        InstrumentParameters.MEASUREMENTS_PER_SAMPLE : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1, REQUIRED: False},
        InstrumentParameters.SAMPLE_PERIOD : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.SAMPLES_PER_BURST : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.BURST_INTERVAL_DAYS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0, REQUIRED: False},
        InstrumentParameters.BURST_INTERVAL_HOURS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0, REQUIRED: False},
        InstrumentParameters.BURST_INTERVAL_MINUTES : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0, REQUIRED: False},
        InstrumentParameters.BURST_INTERVAL_SECONDS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0, REQUIRED: False},
        InstrumentParameters.SI_CONVERSION : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.WARM_UP_INTERVAL : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'f', REQUIRED: False},
        InstrumentParameters.THREE_AXIS_COMPASS : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'y', REQUIRED: False},
        InstrumentParameters.SOLID_STATE_TILT : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'y', REQUIRED: False},
        InstrumentParameters.THERMISTOR : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'y', REQUIRED: False},
        InstrumentParameters.PRESSURE : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'n', REQUIRED: False},
        InstrumentParameters.AUXILIARY_1 : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'n', REQUIRED: False},
        InstrumentParameters.AUXILIARY_2 : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'n', REQUIRED: False},
        InstrumentParameters.AUXILIARY_3 : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: 'n', REQUIRED: False},
        InstrumentParameters.SENSOR_ORIENTATION : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: '2', REQUIRED: False},
        InstrumentParameters.SERIAL_NUMBER : {TYPE: str, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_A : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_B : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_C : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_D : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_OFFSET_0 : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_OFFSET_1 : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_OFFSET_2 : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_0 : {TYPE: float, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_1 : {TYPE: float, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_2 : {TYPE: float, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.TILT_PITCH_OFFSET : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
        InstrumentParameters.TILT_ROLL_OFFSET : {TYPE: int, READONLY: True, DA: False, STARTUP: False, REQUIRED: False},
    }

    # parameter values to test.
    parameter_values = {
        InstrumentParameters.NOTE1 : 'New note1 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.NOTE2 : 'New note2 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.NOTE3 : 'New note3 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.MONITOR : 'y',
        InstrumentParameters.LOG_DISPLAY_TIME : 'y',
        InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : 'y',
        InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : 'HEX',
        InstrumentParameters.QUERY_MODE : 'n',
        InstrumentParameters.FREQUENCY : 2.0,
        InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 10,
        InstrumentParameters.SAMPLE_PERIOD : 5.0,
        InstrumentParameters.SAMPLES_PER_BURST : 2,
        InstrumentParameters.BURST_INTERVAL_DAYS : 0,
        InstrumentParameters.BURST_INTERVAL_HOURS : 0,
        InstrumentParameters.BURST_INTERVAL_MINUTES : 0,
        InstrumentParameters.BURST_INTERVAL_SECONDS : 0,
        InstrumentParameters.SI_CONVERSION : .00231,
    }
    
    parameter_values_B = {
        InstrumentParameters.NOTE1 : 'New note1 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.NOTE2 : 'New note2 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.NOTE3 : 'New note3 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        InstrumentParameters.MONITOR : 'n',
        InstrumentParameters.LOG_DISPLAY_TIME : 'n',
        InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : 'n',
        InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : 'HEX',
        InstrumentParameters.QUERY_MODE : 'y',
        InstrumentParameters.FREQUENCY : 10.0,
        InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 20,
        InstrumentParameters.SAMPLE_PERIOD : 2.0,
        InstrumentParameters.SAMPLES_PER_BURST : 4,
        InstrumentParameters.BURST_INTERVAL_DAYS : 1,
        InstrumentParameters.BURST_INTERVAL_HOURS : 1,
        InstrumentParameters.BURST_INTERVAL_MINUTES : 1,
        InstrumentParameters.BURST_INTERVAL_SECONDS : 1,
        InstrumentParameters.SI_CONVERSION : .00123,
    }
    
        
    _status_parameters = {
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_A: {TYPE: int, VALUE: 1 },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_B: {TYPE: int, VALUE: 2 },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_C: {TYPE: int, VALUE: 3 },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_D: {TYPE: int, VALUE: 4 },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_0: {TYPE: int, VALUE: 5 },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_1: {TYPE: int, VALUE: 6 },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_2: {TYPE: int, VALUE: 7 },
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_0: {TYPE: float, VALUE: 8.0 },
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_1: {TYPE: float, VALUE: 9.0},
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_2: {TYPE: float, VALUE: 10.0},
        Mavs4StatusDataParticleKey.TILT_PITCH_OFFSET: {TYPE: int, VALUE: 11 },
        Mavs4StatusDataParticleKey.TILT_ROLL_OFFSET: {TYPE: int, VALUE: 12 },
        Mavs4StatusDataParticleKey.SAMPLE_PERIOD: {TYPE: float, VALUE: 13.0 },
        Mavs4StatusDataParticleKey.SAMPLES_PER_BURST: {TYPE: int, VALUE: 14 },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_DAYS: {TYPE: int, VALUE: 15 },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_HOURS: {TYPE: int, VALUE: 16},
        Mavs4StatusDataParticleKey.BURST_INTERVAL_MINUTES: {TYPE: int, VALUE: 17 },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_SECONDS: {TYPE: int, VALUE: 18 },
        Mavs4StatusDataParticleKey.SI_CONVERSION: {TYPE: float, VALUE: 19.0 },
    }
        
    _sample_parameters = {
        Mavs4SampleDataParticleKey.TIMESTAMP: {TYPE: float, VALUE: 3565047050.0},
        Mavs4SampleDataParticleKey.FRACTIONAL_SECOND: {TYPE: int, VALUE: 40},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_A: {TYPE: int, VALUE: 64965},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_B: {TYPE: int, VALUE: 65392},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_C: {TYPE: int, VALUE: 65307},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_D: {TYPE: int, VALUE: 65420},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_EAST: {TYPE: float, VALUE: 1.2},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_NORTH: {TYPE: float, VALUE: 3.4},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_WEST: {TYPE: float, VALUE: 5.6},
        Mavs4SampleDataParticleKey.TEMPERATURE: {TYPE: float, VALUE: 22.21},
        Mavs4SampleDataParticleKey.COMPASS_MX: {TYPE: float, VALUE: 0.96},
        Mavs4SampleDataParticleKey.COMPASS_MY: {TYPE: float, VALUE: 0.28},
        Mavs4SampleDataParticleKey.PITCH: {TYPE: float, VALUE: 3.0},
        Mavs4SampleDataParticleKey.ROLL: {TYPE: float, VALUE: -5.1},
    }

    SAMPLE = "12 20 2012 18 50 50.40 FDC5 FF70 FF1B FF8C 1.2 3.4 5.6 22.21 0.96 0.28 3.0 -5.1\n"
    
    def assert_clock_set(self, sent_time, rcvd_time):
        # verify that the dates match
        print("sts=%s, rts=%s" %(sent_time, rcvd_time))
        self.assertTrue(sent_time[:12].upper() in rcvd_time.upper())
           
        sent_timestamp = time.strptime(sent_time, "%m/%d/%Y %H:%M:%S")
        ntp_sent_timestamp = ntplib.system_to_ntp_time(time.mktime(sent_timestamp))
        rcvd_timestamp = time.strptime(rcvd_time, "%m/%d/%Y %H:%M:%S")
        ntp_rcvd_timestamp = ntplib.system_to_ntp_time(time.mktime(rcvd_timestamp))
        # verify that the times match closely
        print("sts=%d, rts=%d" %(ntp_sent_timestamp, ntp_rcvd_timestamp))
        if ntp_rcvd_timestamp - ntp_sent_timestamp > 45:
            self.fail("time delta too large after clock sync")        
    
    def assert_status_data_particle_header(self, data_particle, stream_name):
        """
        Verify a status data particle header is formatted properly w/o port agent timestamp
        @param data_particle: version 1 data particle
        @param stream_name: version 1 data particle
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("assert_status_data_particle_header: SAMPLEDICT = %s" % sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_particle_status(self, data_particle, verify_values = False):
        '''
        Verify a status data particle
        @param data_particle:  status data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_status_data_particle_header(data_particle, DataParticleType.STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)

    TIME_TO_SET = '03/29/2002 11:11:42'


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
class Testmavs4_UNIT(InstrumentDriverUnitTestCase, Mavs4Mixin):
    """Unit Test Container"""
    
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)
    
    def assert_status_particle_published(self, particle_assert_method, verify_values = False):
        """
        Verify that we can send data through the port agent and the the correct particles
        are generated.

        Create a port agent packet, send it through got_data, then finally grab the data particle
        from the data particle queue and verify it using the passed in assert method.
        @param driver: instrument driver with mock port agent client
        @param sample_data: the byte string we want to send to the driver
        @param particle_assert_method: assert method to validate the data particle.
        @param verify_values: Should we validate values?
        """
        # Find all particles of the correct data particle types (not raw)
        particles = []
        for p in self._data_particle_received:
            particle_dict = json.loads(p)
            stream_type = particle_dict.get('stream_name')
            self.assertIsNotNone(stream_type)
            if(stream_type == DataParticleType.STATUS):
                particles.append(p)

        log.debug("status particles: %s " % particles)
        self.assertEqual(len(particles), 1)

        # Verify the data particle
        particle_assert_method(particles.pop(), verify_values)

    def test_driver_enums(self):
        """
        Verify that all driver enumerations have no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentPrompts())
        self.assert_enum_has_no_duplicates(ProtocolStates())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(InstrumentParameters())
        self.assert_enum_has_no_duplicates(DeployMenuParameters())
        self.assert_enum_has_no_duplicates(SystemConfigurationMenuParameters())
        self.assert_enum_has_no_duplicates(VelocityOffsetParameters())
        self.assert_enum_has_no_duplicates(CompassOffsetParameters())
        self.assert_enum_has_no_duplicates(CompassScaleFactorsParameters())
        self.assert_enum_has_no_duplicates(TiltOffsetParameters())
        self.assert_enum_has_no_duplicates(SubMenues())

        # Test capabilites for duplicates, then verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(mavs4InstrumentProtocol.chunker_sieve_function)

        self.assert_chunker_sample(chunker, self.SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.SAMPLE)
    
    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = Mavs4SampleDataParticle(self.SAMPLE.replace('2012', 'foobar'),
                                           port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    @unittest.skip("skipped pending driver param fix")
    def test_status_particle(self):
        """
        Verify driver produces the correct status data particle
        """
        driver = mavs4InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolStates.COMMAND)
        
        # mock the _update_params() method which tries to get parameters from an actual instrument
        _update_params_mock = Mock(spec="_update_params")
        driver._protocol._update_params = _update_params_mock

        # load the status parameter values
        pd = driver._protocol._param_dict
        for name in self._status_parameters.keys():
            pd.set(name, self._status_parameters[name][VALUE])
            
        # clear out any old events
        self.clear_data_particle_queue()

        # call the method in the driver that generates and sends the status data particle
        driver._protocol._generate_status_event()
        
        # check that the status data particle was published
        self.assert_status_particle_published(self.assert_particle_status, verify_values=True)
    
    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = mavs4InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)    # defaults to autosample mode, so sample generated

        self.assert_raw_particle_published(driver, True)

        # validate data particle
        self.assert_particle_published(driver, self.SAMPLE, self.assert_particle_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = mavs4InstrumentProtocol(InstrumentPrompts, INSTRUMENT_NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))

    @unittest.skip("skipped pending driver param fix")
    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = mavs4InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolStates.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(InstrumentParameters.ALL))

        log.debug("Reported Parameters: %s" % reported_parameters)
        log.debug("Expected Parameters: %s" % expected_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolStates.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolStates.COMMAND: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                     'DRIVER_EVENT_CLOCK_SYNC',
                                     'DRIVER_EVENT_GET',
                                     'DRIVER_EVENT_SET',
                                     'DRIVER_EVENT_START_AUTOSAMPLE',
                                     'DRIVER_EVENT_START_DIRECT'],
            ProtocolStates.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE'],
            ProtocolStates.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 
                                           'EXECUTE_DIRECT']
        }

        driver = mavs4InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testmavs4_INT(InstrumentDriverIntegrationTestCase, Mavs4Mixin):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.nobska.mavs4.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'mavs4InstrumentDriver'    
    

    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        self.assert_initialize_driver()
                
               
    def test_get_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also
        verify the parameter value. This test confirms that parameters are
        being read/converted properly and that the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        self.assert_parameters(reply, self._driver_parameters, True)


    def test_set(self):
        """
        Test device parameter access.
        """
        self.assert_initialize_driver()

        # construct values dynamically to get time stamp for notes
        new_parameter_values = {}
        for key in self.parameter_values.iterkeys():
            new_parameter_values[key] = self.parameter_values[key]
               
        # Set parameters and verify.
        self.assert_set_bulk(new_parameter_values)
        
        # do it all again with a different value set
        new_parameter_values = {}
        for key in self.parameter_values_B.iterkeys():
            new_parameter_values[key] = self.parameter_values_B[key]
        self.assert_set_bulk(new_parameter_values)
        

    def test_set_clock(self):
        self.assert_initialize_driver()

        new_parameter_values = {}
        new_parameter_values[InstrumentParameters.SYS_CLOCK] = self.TIME_TO_SET
        new_parameter_list = []
        new_parameter_list.append(InstrumentParameters.SYS_CLOCK)
        
        # Set parameters and verify.
        self.driver_client.cmd_dvr('set_resource', new_parameter_values)
        reply = self.driver_client.cmd_dvr('get_resource', new_parameter_list)
        
        rcvd_time = reply[InstrumentParameters.SYS_CLOCK]
        self.assert_clock_set(self.TIME_TO_SET, rcvd_time)

    
    def test_read_only_parameters(self):
        self.assert_initialize_driver()

        self.assert_set_readonly(InstrumentParameters.VELOCITY_OFFSET_PATH_A)
        self.assert_set_readonly(InstrumentParameters.VELOCITY_OFFSET_PATH_B)
        self.assert_set_readonly(InstrumentParameters.VELOCITY_OFFSET_PATH_C)
        self.assert_set_readonly(InstrumentParameters.VELOCITY_OFFSET_PATH_D)
        self.assert_set_readonly(InstrumentParameters.COMPASS_OFFSET_0)
        self.assert_set_readonly(InstrumentParameters.COMPASS_OFFSET_1)
        self.assert_set_readonly(InstrumentParameters.COMPASS_OFFSET_2)
        self.assert_set_readonly(InstrumentParameters.COMPASS_SCALE_FACTORS_0)
        self.assert_set_readonly(InstrumentParameters.COMPASS_SCALE_FACTORS_1)
        self.assert_set_readonly(InstrumentParameters.COMPASS_SCALE_FACTORS_2)
        self.assert_set_readonly(InstrumentParameters.TILT_PITCH_OFFSET)
        self.assert_set_readonly(InstrumentParameters.TILT_ROLL_OFFSET)
        self.assert_set_readonly(InstrumentParameters.VELOCITY_FRAME)
        self.assert_set_readonly(InstrumentParameters.WARM_UP_INTERVAL)
        self.assert_set_readonly(InstrumentParameters.THREE_AXIS_COMPASS)
        self.assert_set_readonly(InstrumentParameters.SOLID_STATE_TILT)
        self.assert_set_readonly(InstrumentParameters.THERMISTOR)
        self.assert_set_readonly(InstrumentParameters.PRESSURE)
        self.assert_set_readonly(InstrumentParameters.AUXILIARY_1)
        self.assert_set_readonly(InstrumentParameters.AUXILIARY_2)
        self.assert_set_readonly(InstrumentParameters.AUXILIARY_3)
        self.assert_set_readonly(InstrumentParameters.SENSOR_ORIENTATION)
        self.assert_set_readonly(InstrumentParameters.SERIAL_NUMBER)
    
    def test_instrumment_start_stop_autosample(self):
        """
        @brief Test for start/stop of instrument autosample, puts instrument in 'command' state first
        """
        self.assert_initialize_driver()
                
        # start auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.AUTOSAMPLE)
                
        # stop auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)


    def test_instrument_autosample_samples(self):
        """
        @brief Test for putting instrument in 'auto-sample' state and receiving samples
        """
        self.assert_initialize_driver()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.assert_current_state(ProtocolStates.AUTOSAMPLE)
           
        # wait for some samples to be generated
        log.debug('test_instrument_start_stop_autosample: waiting 5 seconds for samples')
        gevent.sleep(5)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        for sample in sample_events:
            if sample['value'].find(DataParticleType.SAMPLE) != -1:
                log.debug('parsed sample=%s\n' %sample)
                sample_dict = eval(sample['value'])     # turn string into dictionary
                values = sample_dict['values']          # get particle dictionary
                # pull timestamp out of particle
                ntp_timestamp = [item for item in values if item["value_id"] == "timestamp"][0]['value']
                float_timestamp = ntplib.ntp_to_system_time(ntp_timestamp)
                log.debug('dt=%s' %time.ctime(float_timestamp))
        self.assertTrue(len(sample_events) >= 2)

        # stop autosample and return to command mode
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
                
        self.assert_current_state(ProtocolStates.COMMAND)
    

    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.STATUS, self.assert_particle_status, delay=20)
        
    def test_metadata_generation(self):
        """
        Test that we can generate metadata information for the driver,
        commands, and parameters.
        """
        self.assert_initialize_driver()

        json_result = self.driver_client.cmd_dvr("get_config_metadata")
        self.assert_(json_result != None)
        self.assert_(len(json_result) > 100) # just make sure we have something...
        result = json.loads(json_result)
        self.assert_(result != None)
        self.assert_(isinstance(result, dict))
        self.assertFalse(result[ConfigMetadataKey.COMMANDS])

        self.assertTrue(result[ConfigMetadataKey.DRIVER])
        self.assertTrue(result[ConfigMetadataKey.DRIVER][DriverDictKey.VENDOR_SW_COMPATIBLE])

        self.assertTrue(result[ConfigMetadataKey.PARAMETERS])        
        keys = result[ConfigMetadataKey.PARAMETERS].keys()
        keys.append(DriverParameter.ALL)
        keys.sort()
        enum_list = InstrumentParameters.list()
        enum_list.sort()
        self.assertEqual(keys, enum_list)
        
    def test_related_parameters(self):
        """
        Measurement Frequency, Measurement/Sample, and Sample period are all
        tied together. When one changes, the others must follow suit when
        being set as a group.
        """
        self.assert_initialize_driver()
        read_values = [
            InstrumentParameters.FREQUENCY,
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
            InstrumentParameters.SAMPLE_PERIOD
            ]

        # The "normal, everything is good" case
        new_parameter_values = {
            InstrumentParameters.FREQUENCY : 2.0,
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 10,
            InstrumentParameters.SAMPLE_PERIOD : 5.0,
        }
        self.driver_client.cmd_dvr('set_resource', new_parameter_values)
        reply = self.driver_client.cmd_dvr('get_resource', read_values)
        self.assertEqual(reply[InstrumentParameters.MEASUREMENTS_PER_SAMPLE], 10)
        self.assertEqual(reply[InstrumentParameters.FREQUENCY], 2)
        self.assertEqual(reply[InstrumentParameters.SAMPLE_PERIOD], 5.0)
        
        # The single case
        new_parameter_values = {
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 20,
        }
        self.driver_client.cmd_dvr('set_resource', new_parameter_values)
        reply = self.driver_client.cmd_dvr('get_resource', read_values)
        self.assertEqual(reply[InstrumentParameters.MEASUREMENTS_PER_SAMPLE], 20)
        self.assertEqual(reply[InstrumentParameters.FREQUENCY], 2)
        self.assertEqual(reply[InstrumentParameters.SAMPLE_PERIOD], 10.0)

        # Two good values (M/S and Freq are okay)
        new_parameter_values = {
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 1,
            InstrumentParameters.FREQUENCY : 1.0,
        }
        self.driver_client.cmd_dvr('set_resource', new_parameter_values)
        reply = self.driver_client.cmd_dvr('get_resource', read_values)
        self.assertEqual(reply[InstrumentParameters.MEASUREMENTS_PER_SAMPLE], 1)
        self.assertEqual(reply[InstrumentParameters.FREQUENCY], 1.0)
        self.assertEqual(reply[InstrumentParameters.SAMPLE_PERIOD], 1.0)
       
        # One value wrong
        new_parameter_values = {
            InstrumentParameters.FREQUENCY : 10.0,
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 2,
            InstrumentParameters.SAMPLE_PERIOD : 5.0,
        }
        self.assertRaises(BadRequest,
                          self.driver_client.cmd_dvr, 'set_resource',
                                                      new_parameter_values)
        
        # Two values wrong
        new_parameter_values = {
            InstrumentParameters.FREQUENCY : 20.0,
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 10,
            InstrumentParameters.SAMPLE_PERIOD : 5.0,
        }
        self.assertRaises(BadRequest,
                          self.driver_client.cmd_dvr, 'set_resource',
                                                      new_parameter_values)
        
        # Two bad values
        new_parameter_values = {
            InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 10,
            InstrumentParameters.SAMPLE_PERIOD : 5.0,
        }
        self.assertRaises(BadRequest,
                          self.driver_client.cmd_dvr, 'set_resource',
                                                      new_parameter_values)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class Testmavs4_QUAL(InstrumentDriverQualificationTestCase, Mavs4Mixin):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  


    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_down; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_up; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent initialize; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent go_active; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent run; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run


    def test_direct_access_telnet_mode(self):
        """
        Test that we can connect to the instrument via direct access.  Also
        verify that direct access parameters are reset on exit.
        """
        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("\r\n\r\n")
        self.assertTrue(self.tcp_client.expect("Modular Acoustic Velocity Sensor"))

        self.assert_direct_access_stop_telnet()

               
    def test_parameter_enum(self):
        """
        @ brief InstrumentParameters enum test

            1. test that InstrumentParameters matches the expected enums from DriverParameter.
            2. test that multiple distinct parameters do not resolve back to the same string.
        """

        self.assertEqual(InstrumentParameters.ALL, DriverParameter.ALL)

        self.assert_enum_has_no_duplicates(DriverParameter)
        self.assert_enum_has_no_duplicates(InstrumentParameters)

    def test_protocol_state_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.

        """

        self.assertEqual(ProtocolStates.UNKNOWN, DriverProtocolState.UNKNOWN)
        self.assertEqual(ProtocolStates.COMMAND, DriverProtocolState.COMMAND)
        self.assertEqual(ProtocolStates.AUTOSAMPLE, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(ProtocolStates.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS)

        self.assert_enum_has_no_duplicates(DriverProtocolState)
        self.assert_enum_has_no_duplicates(ProtocolStates)

    def test_protocol_event_enum(self):
        """
        @brief ProtocolEvent enum test

            1. test that ProtocolEvent matches the expected enums from DriverProtocolState.
            2. test that multiple distinct events do not resolve back to the same string.
        """

        self.assertEqual(ProtocolEvent.ENTER, DriverEvent.ENTER)
        self.assertEqual(ProtocolEvent.EXIT, DriverEvent.EXIT)
        self.assertEqual(ProtocolEvent.GET, DriverEvent.GET)
        self.assertEqual(ProtocolEvent.SET, DriverEvent.SET)
        self.assertEqual(ProtocolEvent.DISCOVER, DriverEvent.DISCOVER)
        self.assertEqual(ProtocolEvent.START_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.STOP_AUTOSAMPLE, DriverEvent.STOP_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.EXECUTE_DIRECT, DriverEvent.EXECUTE_DIRECT)
        self.assertEqual(ProtocolEvent.START_DIRECT, DriverEvent.START_DIRECT)
        self.assertEqual(ProtocolEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

        self.assert_enum_has_no_duplicates(DriverEvent)
        self.assert_enum_has_no_duplicates(ProtocolEvent)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            AgentCapabilityType.AGENT_PARAMETER: ['example'],
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.CLOCK_SYNC,
                DriverEvent.GET,
                DriverEvent.SET,
                DriverEvent.ACQUIRE_STATUS,
                DriverEvent.START_AUTOSAMPLE,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.RESET, ResourceAgentEvent.GO_INACTIVE ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.STOP_AUTOSAMPLE,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.INITIALIZE]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    def test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_STATUS, timeout=60)

        # Now verify that at least the date matches
        params = [InstrumentParameters.SYS_CLOCK]
        print("doing get resource")
        reply = self.instrument_agent_client.get_resource(params)
        rcvd_time = reply[InstrumentParameters.SYS_CLOCK]
        lt = time.strftime("%m/%d/%Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assert_clock_set(lt, rcvd_time)

    def test_sample_autosample(self):
        self.assert_enter_command_mode()
        self.assert_start_autosample()

        self.assert_sample_async(self.assert_particle_sample, DataParticleType.SAMPLE, timeout=30, sample_count=1)
