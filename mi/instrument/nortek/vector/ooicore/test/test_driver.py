"""
@package mi.instrument.nortek.vector.ooicore.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore/driver.py
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
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import unittest
import re
import time
import datetime
import base64
import ntplib

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType

from mi.instrument.nortek.test.test_driver import hw_config_particle, hw_config_sample
from mi.instrument.nortek.test.test_driver import head_config_particle, head_config_sample
from mi.instrument.nortek.test.test_driver import user_config_particle, user_config_sample
from mi.instrument.nortek.test.test_driver import user_config1, user_config2
from mi.instrument.nortek.test.test_driver import NortekUnitTest, NortekIntTest, NortekQualTest

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.nortek.driver import NortekHardwareConfigDataParticleKey
from mi.instrument.nortek.driver import NortekHeadConfigDataParticleKey
from mi.instrument.nortek.driver import NortekUserConfigDataParticleKey


from mi.instrument.nortek.driver import InstrumentPrompts
from mi.instrument.nortek.driver import InstrumentCmds
from mi.instrument.nortek.driver import Capability
from mi.instrument.nortek.driver import ProtocolState
from mi.instrument.nortek.driver import ProtocolEvent
from mi.instrument.nortek.driver import Parameter
from mi.instrument.nortek.driver import NortekEngClockDataParticleKey
from mi.instrument.nortek.driver import NortekEngClockDataParticle
from mi.instrument.nortek.driver import NortekEngBatteryDataParticleKey
from mi.instrument.nortek.driver import NortekEngBatteryDataParticle
from mi.instrument.nortek.driver import NortekEngIdDataParticleKey
from mi.instrument.nortek.driver import NortekEngIdDataParticle
from mi.instrument.nortek.vector.ooicore.driver import DataParticleType
from mi.instrument.nortek.vector.ooicore.driver import Protocol
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityHeaderDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityHeaderDataParticleKey
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityDataParticleKey
from mi.instrument.nortek.vector.ooicore.driver import VectorSystemDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorSystemDataParticleKey
from mi.instrument.nortek.vector.ooicore.driver import VectorHardwareConfigDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorHeadConfigDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorUserConfigDataParticle

from interface.objects import AgentCommand
from interface.objects import CapabilityType

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from pyon.agent.agent import ResourceAgentEvent

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.vector.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'nortek_vector_dw_ooicore',
    instrument_agent_name = 'nortek_vector_dw_ooicore_agent',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {
        Parameter.AVG_INTERVAL: 61
        }
)

params_dict = {
    Parameter.TRANSMIT_PULSE_LENGTH : int,
    Parameter.BLANKING_DISTANCE : int,
    Parameter.RECEIVE_LENGTH : int,
    Parameter.TIME_BETWEEN_PINGS : int,
    Parameter.TIME_BETWEEN_BURST_SEQUENCES : int,
    Parameter.NUMBER_PINGS : int,
    Parameter.AVG_INTERVAL : int,
    Parameter.USER_NUMBER_BEAMS : int,
    Parameter.TIMING_CONTROL_REGISTER : int,
    Parameter.POWER_CONTROL_REGISTER : int,
    Parameter.COMPASS_UPDATE_RATE : int,
    Parameter.COORDINATE_SYSTEM : int,
    Parameter.NUMBER_BINS : int,
    Parameter.BIN_LENGTH : int,
    Parameter.MEASUREMENT_INTERVAL : int,
    Parameter.DEPLOYMENT_NAME : str,
    Parameter.WRAP_MODE : int,
    Parameter.CLOCK_DEPLOY : str,
    Parameter.DIAGNOSTIC_INTERVAL : int,
    Parameter.MODE : int,
    Parameter.ADJUSTMENT_SOUND_SPEED : int,
    Parameter.NUMBER_SAMPLES_DIAGNOSTIC : int,
    Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC : int,
    Parameter.NUMBER_PINGS_DIAGNOSTIC : int,
    Parameter.MODE_TEST : int,
    Parameter.ANALOG_INPUT_ADDR : int,
    Parameter.SW_VERSION : int,
    Parameter.VELOCITY_ADJ_TABLE : str,
    Parameter.COMMENTS : str,
    Parameter.WAVE_MEASUREMENT_MODE : int,
    Parameter.DYN_PERCENTAGE_POSITION : int,
    Parameter.WAVE_TRANSMIT_PULSE : int,
    Parameter.WAVE_BLANKING_DISTANCE : int,
    Parameter.WAVE_CELL_SIZE : int,
    Parameter.NUMBER_DIAG_SAMPLES : int,
    Parameter.NUMBER_SAMPLES_PER_BURST : int,
    Parameter.ANALOG_OUTPUT_SCALE : int,
    Parameter.CORRELATION_THRESHOLD : int,
    Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG : int,
    Parameter.QUAL_CONSTANTS : str}

        
# velocity data particle & sample 
def velocity_sample():
    sample_as_hex = "a51000db00008f10000049f041f72303303132120918d8f7"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
velocity_particle = [{DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.ANALOG_INPUT2,
                      DataParticleKey.VALUE: 0}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.COUNT,
                      DataParticleKey.VALUE: 219}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.PRESSURE,
                      DataParticleKey.VALUE: 4239}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.ANALOG_INPUT1,
                      DataParticleKey.VALUE: 0}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.VELOCITY_BEAM1,
                      DataParticleKey.VALUE: 61513}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.VELOCITY_BEAM2,
                      DataParticleKey.VALUE: 63297}, 
                     {DataParticleKey.VALUE_ID:  \
                       VectorVelocityDataParticleKey.VELOCITY_BEAM3,
                      DataParticleKey.VALUE: 803}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.AMPLITUDE_BEAM1,
                      DataParticleKey.VALUE: 48}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.AMPLITUDE_BEAM2,
                      DataParticleKey.VALUE: 49}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.AMPLITUDE_BEAM3,
                      DataParticleKey.VALUE: 50}, 
                     {DataParticleKey.VALUE_ID:  \
                       VectorVelocityDataParticleKey.CORRELATION_BEAM1,
                      DataParticleKey.VALUE: 18}, 
                     {DataParticleKey.VALUE_ID:  \
                       VectorVelocityDataParticleKey.CORRELATION_BEAM2,
                      DataParticleKey.VALUE: 9}, 
                     {DataParticleKey.VALUE_ID: \
                       VectorVelocityDataParticleKey.CORRELATION_BEAM3,
                      DataParticleKey.VALUE: 24}]

# velocity header data particle & sample 
def velocity_header_sample():
    sample_as_hex = "a512150012491711121270032f2f2e0002090d0000000000000000000000000000000000000000005d70"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
velocity_header_particle = [{DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.TIMESTAMP,
                             DataParticleKey.VALUE: '17/12/2012 11:12:49'}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.NUMBER_OF_RECORDS,
                             DataParticleKey.VALUE: 880}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.NOISE1,
                             DataParticleKey.VALUE: 47}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.NOISE2,
                             DataParticleKey.VALUE: 47}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.NOISE3,
                             DataParticleKey.VALUE: 46}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.CORRELATION1,
                             DataParticleKey.VALUE: 2}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.CORRELATION2,
                             DataParticleKey.VALUE: 9}, 
                            {DataParticleKey.VALUE_ID: \
                              VectorVelocityHeaderDataParticleKey.CORRELATION3,
                             DataParticleKey.VALUE: 13}]

# system data particle & sample 
def system_sample():
    sample_as_hex = "a5110e0003261317121294007c3b83041301cdfe0a08007b0000e4d9"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
system_particle = [{DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TIMESTAMP,
                    DataParticleKey.VALUE: '13/12/2012 17:03:26'}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.BATTERY,
                    DataParticleKey.VALUE: 148}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.SOUND_SPEED,
                    DataParticleKey.VALUE: 15228}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.HEADING,
                    DataParticleKey.VALUE: 1155}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.PITCH,
                    DataParticleKey.VALUE: 275}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ROLL,
                    DataParticleKey.VALUE: 65229}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TEMPERATURE,
                    DataParticleKey.VALUE: 2058}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ERROR,
                    DataParticleKey.VALUE: 0}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.STATUS,
                    DataParticleKey.VALUE: 123}, 
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ANALOG_INPUT,
                    DataParticleKey.VALUE: 0}]

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
class UnitFromIDK(NortekUnitTest):
    def setUp(self):
        NortekUnitTest.setUp(self)

    def test_velocity_header_sample_format(self):
        """
        Test to make sure we can get velocity_header sample data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests
        """
        
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772
        text_timestamp = time.strptime('17/12/2012 11:12:49', "%d/%m/%Y %H:%M:%S")
        internal_timestamp = ntplib.system_to_ntp_time(time.mktime(text_timestamp))
 
        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.VELOCITY_HEADER,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.INTERNAL_TIMESTAMP: internal_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: velocity_header_particle
            }
        
        self.compare_parsed_data_particle(VectorVelocityHeaderDataParticle,
                                          velocity_header_sample(),
                                          expected_particle)

    def test_velocity_sample_format(self):
        """
        Test to make sure we can get velocity sample data out in a reasonable
        format. Parsed is all we care about...raw is tested in the base
        DataParticle tests
        """
        
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.VELOCITY,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: velocity_particle
            }
        
        self.compare_parsed_data_particle(VectorVelocityDataParticle,
                                          velocity_sample(),
                                          expected_particle)

    def test_system_sample_format(self):
        """
        Test to make sure we can get velocity sample data out in a reasonable
        format. Parsed is all we care about...raw is tested in the base
        DataParticle tests
        """
        
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772
        text_timestamp = time.strptime('13/12/2012 17:03:26', "%d/%m/%Y %H:%M:%S")
        internal_timestamp = ntplib.system_to_ntp_time(time.mktime(text_timestamp))

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.SYSTEM,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.INTERNAL_TIMESTAMP: internal_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: system_particle
            }
        
        self.compare_parsed_data_particle(VectorSystemDataParticle,
                                          system_sample(),
                                          expected_particle)
        
    def test_chunker(self):
        """
        Tests the chunker
        """
        chunker = StringChunker(Protocol.chunker_sieve_function)

        # test complete data structures
        self.assert_chunker_sample(chunker, velocity_sample())
        self.assert_chunker_sample(chunker, system_sample())
        self.assert_chunker_sample(chunker, velocity_header_sample())

        # test fragmented data structures
        sample = velocity_sample()
        fragments = [sample[0:4], sample[4:10], sample[10:14], sample[14:]]
        self.assert_chunker_fragmented_sample(chunker, fragments, sample)

        sample = system_sample()
        fragments = [sample[0:5], sample[5:11], sample[11:15], sample[15:]]
        self.assert_chunker_fragmented_sample(chunker, fragments, sample)

        sample = velocity_header_sample()
        fragments = [sample[0:3], sample[3:11], sample[11:12], sample[12:]]
        self.assert_chunker_fragmented_sample(chunker, fragments, sample)

        # test combined data structures
        self.assert_chunker_combined_sample(chunker,
                                            velocity_sample(),
                                            system_sample(),
                                            velocity_header_sample())
        self.assert_chunker_combined_sample(chunker,
                                            velocity_header_sample(),
                                            velocity_sample(),
                                            system_sample())
        self.assert_chunker_combined_sample(chunker,
                                            velocity_header_sample(),
                                            head_config_sample(),
                                            system_sample())

        # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, velocity_sample())
        self.assert_chunker_sample_with_noise(chunker, system_sample())
        self.assert_chunker_sample_with_noise(chunker, velocity_header_sample())
        

    def test_corrupt_data_structures(self):
        # garbage is not okay
        particle = VectorVelocityHeaderDataParticle(velocity_header_sample().replace(chr(0), chr(1), 1),
                                                    port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
        particle = VectorSystemDataParticle(system_sample().replace(chr(0), chr(1), 1),
                                            port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
        particle = VectorVelocityDataParticle(velocity_sample().replace(chr(16), chr(17), 1),
                                              port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

 
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(NortekIntTest):
    
    protocol_state = ''
    
    def setUp(self):
        NortekIntTest.setUp(self)
 
    def test_set_init_params(self):
        """
        @brief Test for set_init_params()
        """
        self.put_driver_in_command_mode()

        values_before = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        
        self.driver_client.cmd_dvr('set_init_params',
                                   {DriverParameter.ALL:
                                    base64.b64encode(user_config1())})
        self.driver_client.cmd_dvr("apply_startup_params") 

        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)

        # check to see if startup config got set in instrument
        self.assertEquals(values_after[Parameter.MEASUREMENT_INTERVAL], 500)
        self.assertEquals(values_after[Parameter.NUMBER_SAMPLES_PER_BURST], 20)

        self.driver_client.cmd_dvr('set_resource', values_before)
        values_after = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertEquals(values_after, values_before)
        
        

    def test_startup_configuration(self):
        '''
        Test that the startup configuration is applied correctly
        '''
        self.put_driver_in_command_mode()
        value_before = self.driver_client.cmd_dvr('get_resource',
                                                  [Parameter.AVG_INTERVAL])
        self.driver_client.cmd_dvr('apply_startup_params')
        reply = self.driver_client.cmd_dvr('get_resource',
                                           [Parameter.AVG_INTERVAL])
        self.assertEquals(reply, {Parameter.AVG_INTERVAL: 61})
        reply = self.driver_client.cmd_dvr('set_resource', value_before)
        reply = self.driver_client.cmd_dvr('get_resource',
                                           [Parameter.AVG_INTERVAL])
        self.assertEquals(reply, value_before)

    def test_instrument_set_configuration(self):
        """
        @brief Test for setting instrument configuration
        """
        
        self.put_driver_in_command_mode()
        
        # command the instrument to set the user configuration.
        self.driver_client.cmd_dvr('execute_resource',
                                   ProtocolEvent.SET_CONFIGURATION,
                                   user_configuration=base64.b64encode(user_config2()))
        
        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)
        #print("va=%s" %values_after)
        
        # check to see if config got set in instrument
        self.assertEquals(values_after[Parameter.MEASUREMENT_INTERVAL], 600)
        self.assertEquals(values_after[Parameter.NUMBER_SAMPLES_PER_BURST], 10)

    def test_instrument_set(self):
        """
        @brief Test for setting instrument parameter
        """
        self.put_driver_in_command_mode()

        # Get all device parameters. Confirm all expected keys are retrieved
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDictionariesEqual(reply, params_dict, True)

        # Grab a subset of parameters.
        params = [
            Parameter.WRAP_MODE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        #self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        new_wrap_mode = 1 if orig_params[Parameter.WRAP_MODE]==0 else 0
        log.debug('old=%d, new=%d', orig_params[Parameter.WRAP_MODE], new_wrap_mode)
        new_params = {
            Parameter.WRAP_MODE : new_wrap_mode
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(new_params[Parameter.WRAP_MODE],
                         reply[Parameter.WRAP_MODE])

        # Reset parameter to original value and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(orig_params[Parameter.WRAP_MODE],
                         reply[Parameter.WRAP_MODE])

        # set wrap_mode to 1 to leave instrument with wrap mode enabled
        new_params = {
            Parameter.WRAP_MODE : 1,
            Parameter.NUMBER_SAMPLES_PER_BURST : 10,
            Parameter.MEASUREMENT_INTERVAL : 600
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource',
                                           [Parameter.WRAP_MODE,
                                            Parameter.NUMBER_SAMPLES_PER_BURST,
                                            Parameter.MEASUREMENT_INTERVAL])
        self.assertEqual(new_params, reply)
        

    def test_capabilities(self):
        """
        Test get_resource_capaibilties in command state and autosample state;
        should be different in each.
        """
        
        command_capabilities = ['EXPORTED_INSTRUMENT_CMD_READ_ID', 
                                'EXPORTED_INSTRUMENT_CMD_GET_HW_CONFIGURATION', 
                                'DRIVER_EVENT_SET', 
                                'DRIVER_EVENT_GET', 
                                'EXPORTED_INSTRUMENT_CMD_READ_CLOCK', 
                                'EXPORTED_INSTRUMENT_CMD_GET_HEAD_CONFIGURATION', 
                                'EXPORTED_INSTRUMENT_CMD_GET_USER_CONFIGURATION', 
                                'EXPORTED_INSTRUMENT_CMD_POWER_DOWN', 
                                'EXPORTED_INSTRUMENT_CMD_READ_MODE', 
                                'EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_AT_SPECIFIC_TIME', 
                                'EXPORTED_INSTRUMENT_CMD_READ_BATTERY_VOLTAGE', 
                                'EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_IMMEDIATE',
                                'EXPORTED_INSTRUMENT_CMD_SET_CONFIGURATION', 
                                'DRIVER_EVENT_START_AUTOSAMPLE',
                                'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                'DRIVER_EVENT_CLOCK_SYNC']
        
        autosample_capabilities = ['DRIVER_EVENT_STOP_AUTOSAMPLE']
        
        params_list = params_dict.keys()
        
        self.put_driver_in_command_mode()

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        log.debug("\nec=%s\ndc=%s", sorted(command_capabilities),
                  sorted(driver_capabilities[0]))
        self.assertTrue(sorted(command_capabilities) == sorted(driver_capabilities[0]))
        #log.debug('dc=%s' %sorted(driver_capabilities[1]))
        #log.debug('pl=%s' %sorted(params_list))
        self.assertTrue(sorted(params_list) == sorted(driver_capabilities[1]))

        # Put the driver in autosample
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolState.AUTOSAMPLE)

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        log.debug('test_capabilities: autosample mode capabilities=%s',
                  driver_capabilities)
        self.assertTrue(autosample_capabilities == driver_capabilities[0])
               
    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        self.assert_ion_exception(InstrumentCommandException,
            self.driver_client.cmd_dvr, 'bogus_command')

        # Assert for a known command, invalid state.
        self.assert_ion_exception(InstrumentStateException,
            self.driver_client.cmd_dvr, 'execute_resource',
                                        ProtocolEvent.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'configure')

        # Assert we send a bad config object (not a dict).
        BOGUS_CONFIG = 'not a config dict'            
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'configure', BOGUS_CONFIG)
            
        BOGUS_CONFIG = self.port_agent_comm_config().copy()
        BOGUS_CONFIG.pop('addr')
        # Assert we send a bad config object (missing addr value).
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        BOGUS_CONFIG = self.port_agent_comm_config().copy()
        BOGUS_CONFIG['addr'] = ''
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'configure', BOGUS_CONFIG)
        
        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        self.assert_ion_exception(InstrumentStateException,
            self.driver_client.cmd_dvr, 'execute_resource',
                                       ProtocolEvent.ACQUIRE_SAMPLE)

        self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        self.assert_ion_exception(InstrumentStateException,
            self.driver_client.cmd_dvr, 'execute_resource',
                                        ProtocolEvent.ACQUIRE_SAMPLE)
                
        self.driver_client.cmd_dvr('discover_state')

        try:
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)
        except:
            self.assertEqual(self.protocol_state, ProtocolState.AUTOSAMPLE)
            # Put the driver in command mode
            self.driver_client.cmd_dvr('execute_resource',
                                       ProtocolEvent.STOP_AUTOSAMPLE)
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)

        # Assert for a known command, invalid state.
        self.assert_ion_exception(InstrumentStateException,
            self.driver_client.cmd_dvr, 'execute_resource',
                                        ProtocolEvent.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        self.assert_ion_exception(InstrumentStateException,
            self.driver_client.cmd_dvr, 'connect')
        
        # Assert get fails without a parameter.
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        bogus_params = 'I am a bogus param list.'           
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'get_resource', bogus_params)
            
        # Assert get fails with a bad parameter (not ALL or a list).
        bogus_params = [
                'a bogus parameter name',
                Parameter.ADJUSTMENT_SOUND_SPEED
                ]
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'get_resource', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        bogus_params = {
                'a bogus parameter name' : 'bogus value'
        }
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        bogus_params = {
            Parameter.ADJUSTMENT_SOUND_SPEED : 'bogus value'
        }
        self.assert_ion_exception(InstrumentParameterException,
            self.driver_client.cmd_dvr, 'set_resource', bogus_params)
        
        
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(NortekQualTest):
    def assertSampleDataParticle(self, sample):
        if not self.assertBaseDataParticle(sample): # Check the common types
            values = sample['values']
            value_ids = []
            for value in values:
                value_ids.append(value[DataParticleKey.VALUE_ID])
            if sample[DataParticleKey.STREAM_NAME] == DataParticleType.VELOCITY:
                log.debug('assertSampleDataParticle: VectorVelocityDataParticle detected')
                self.assertEqual(sorted(value_ids),
                                 sorted(VectorVelocityDataParticleKey.list()))
                for value in values:
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
            elif sample[DataParticleKey.STREAM_NAME] == DataParticleType.VELOCITY_HEADER:
                log.debug('assertSampleDataParticle: VectorVelocityHeaderDataParticle detected')
                self.assertEqual(sorted(value_ids),
                                 sorted(VectorVelocityHeaderDataParticleKey.list()))
                for value in values:
                    if value[DataParticleKey.VALUE_ID] == VectorVelocityHeaderDataParticleKey.TIMESTAMP:
                        self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
                    else:
                        self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
            elif sample[DataParticleKey.STREAM_NAME] == DataParticleType.SYSTEM:
                log.debug('assertSampleDataParticle: VectorSystemDataParticleKey detected')
                self.assertEqual(sorted(value_ids),
                                 sorted(VectorSystemDataParticleKey.list()))
                for value in values:
                    if value[DataParticleKey.VALUE_ID] == VectorSystemDataParticleKey.TIMESTAMP:
                        self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
                    else:
                        self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))

    def test_poll(self):
        '''
        poll for a single sample
        '''

        self.assert_sample_polled(self.assertSampleDataParticle,
                                  [DataParticleType.VELOCITY,
                                   DataParticleType.VELOCITY_HEADER,
                                   DataParticleType.SYSTEM],
                                  timeout = 100)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assertSampleDataParticle,
                                  [DataParticleType.VELOCITY,
                                   DataParticleType.VELOCITY_HEADER,
                                   DataParticleType.SYSTEM],
                                  timeout = 100)
