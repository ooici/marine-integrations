"""
@package mi.instrument.nortek.aquadopp.ooicore.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore/driver.py
@author Ronald Ronquillo
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

__author__ = 'Ronald Ronquillo'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import unittest
import re
import time
import datetime
import base64

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import ParameterTestConfigKey

from mi.core.instrument.instrument_driver import DriverConnectionState, ResourceAgentEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
# from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.nortek.aquadopp.ooicore.driver import DataParticleType
from mi.instrument.nortek.aquadopp.ooicore.driver import Protocol
from mi.instrument.nortek.aquadopp.ooicore.driver import InstrumentPrompts
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticleKey

from interface.objects import AgentCommand
from interface.objects import CapabilityType

from mi.instrument.nortek.test.test_driver import NortekUnitTest, NortekIntTest, NortekQualTest, DriverTestMixinSub
from mi.instrument.nortek.driver import Parameter, ProtocolState, ProtocolEvent

# from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from pyon.agent.agent import ResourceAgentEvent

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.aquadopp.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='nortek_aquadopp_dw_ooicore',
    instrument_agent_name='nortek_aquadopp_dw_ooicore_agent',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={Parameter.TRANSMIT_PULSE_LENGTH: 0x2})


# velocity data particle & sample
def velocity_sample():
    sample_as_hex = "a5011500101926221211000000009300f83b810628017f01002d0000e3094c0122ff9afe1e1416006093"
    return sample_as_hex.decode('hex')

velocity_particle = [{'value_id': 'timestamp', 'value': '26/11/2012 22:10:19'},
                     {'value_id': 'error', 'value': 0},
                     {'value_id': 'analog1', 'value': 0}, 
                     {'value_id': 'battery_voltage', 'value': 147}, 
                     {'value_id': 'sound_speed_analog2', 'value': 15352}, 
                     {'value_id': 'heading', 'value': 1665}, 
                     {'value_id': 'pitch', 'value': 296}, 
                     {'value_id': 'roll', 'value': 383}, 
                     {'value_id': 'status', 'value': 45}, 
                     {'value_id': 'pressure', 'value': 0}, 
                     {'value_id': 'temperature', 'value': 2531}, 
                     {'value_id': 'velocity_beam1', 'value': 332}, 
                     {'value_id': 'velocity_beam2', 'value': 65314}, 
                     {'value_id': 'velocity_beam3', 'value': 65178}, 
                     {'value_id': 'amplitude_beam1', 'value': 30}, 
                     {'value_id': 'amplitude_beam2', 'value': 20}, 
                     {'value_id': 'amplitude_beam3', 'value': 22}]


# diagnostic header data particle & sample
def diagnostic_header_sample():
    sample_as_hex = "a5061200140001000000000011192622121100000000000000000000000000000000a108"
    return sample_as_hex.decode('hex')

diagnostic_header_particle = [{'value_id': 'records', 'value': 20},
                              {'value_id': 'cell', 'value': 1},
                              {'value_id': 'noise1', 'value': 0},
                              {'value_id': 'noise2', 'value': 0},
                              {'value_id': 'noise3', 'value': 0},
                              {'value_id': 'noise4', 'value': 0},
                              {'value_id': 'processing_magnitude_beam1', 'value': 6417}, 
                              {'value_id': 'processing_magnitude_beam2', 'value': 8742}, 
                              {'value_id': 'processing_magnitude_beam3', 'value': 4370}, 
                              {'value_id': 'processing_magnitude_beam4', 'value': 0}, 
                              {'value_id': 'distance1', 'value': 0},
                              {'value_id': 'distance2', 'value': 0},
                              {'value_id': 'distance3', 'value': 0},
                              {'value_id': 'distance4', 'value': 0}]


# diagnostic data particle & sample
def diagnostic_sample():
    sample_as_hex = "a5801500112026221211000000009300f83ba0065c0189fe002c0000e40904ffd8ffbdfa18131500490f"
    return sample_as_hex.decode('hex')

diagnostic_particle = [{'value_id': 'timestamp', 'value': '26/11/2012 22:11:20'},
                       {'value_id': 'error', 'value': 0}, 
                       {'value_id': 'analog1', 'value': 0}, 
                       {'value_id': 'battery_voltage', 'value': 147}, 
                       {'value_id': 'sound_speed_analog2', 'value': 15352}, 
                       {'value_id': 'heading', 'value': 1696}, 
                       {'value_id': 'pitch', 'value': 348}, 
                       {'value_id': 'roll', 'value': 65161}, 
                       {'value_id': 'status', 'value': 44}, 
                       {'value_id': 'pressure', 'value': 0}, 
                       {'value_id': 'temperature', 'value': 2532}, 
                       {'value_id': 'velocity_beam1', 'value': 65284}, 
                       {'value_id': 'velocity_beam2', 'value': 65496}, 
                       {'value_id': 'velocity_beam3', 'value': 64189}, 
                       {'value_id': 'amplitude_beam1', 'value': 24},                        
                       {'value_id': 'amplitude_beam2', 'value': 19}, 
                       {'value_id': 'amplitude_beam3', 'value': 21}]


###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python, mixin classes are classes designed such that they wouldn't be   #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################
class AquadoppDriverTestMixinSub(DriverTestMixinSub):
    """
    Mixin class used for storing data particle constance and common data assertion methods.
    """

    #Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    #this particle can be used for both the velocity particle and the diagnostic particle
    _sample_velocity_diagnostic = {
        AquadoppDwVelocityDataParticleKey.TIMESTAMP: {TYPE: unicode, VALUE: '', REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.ERROR: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.ANALOG1: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.BATTERY_VOLTAGE: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.SOUND_SPEED_ANALOG2: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.HEADING: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.PITCH: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.ROLL: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.PRESSURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.TEMPERATURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM1: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM2: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM3: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM1: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM2: {TYPE: int, VALUE: 0, REQUIRED: True},
        AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM3: {TYPE: int, VALUE: 0, REQUIRED: True}
    }

    def assert_particle_velocity(self, data_particle, verify_values=False):
        """
        Verify velpt_velocity_data
        @param data_particle:  AquadoppDwVelocityDataParticleKey data particle
        @param verify_values:
        """

        self.assert_data_particle_keys(AquadoppDwVelocityDataParticleKey, self._sample_velocity_diagnostic)
        self.assert_data_particle_header(data_particle, DataParticleType.VELOCITY)
        self.assert_data_particle_parameters(data_particle, self._sample_velocity_diagnostic, verify_values)


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
class DriverUnitTest(NortekUnitTest):
    def setUp(self):
        NortekUnitTest.setUp(self)

    def assert_chunker_fragmented_sample(self, chunker, fragments, sample):
        '''
        Verify the chunker can parse a sample that comes in fragmented
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        timestamps = []
        for f in fragments:
            ts = self.get_ntp_timestamp()
            timestamps.append(ts)
            chunker.add_chunk(f, ts)
            (timestamp, result) = chunker.get_next_data()
            if (result): break

        self.assertEqual(result, sample)
        self.assertEqual(timestamps[0], timestamp)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_combined_sample(self, chunker, sample1, sample2, sample3):
        '''
        Verify the chunker can parse samples that comes in combined
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        ts = self.get_ntp_timestamp()
        chunker.add_chunk(sample1 + sample2 + sample3, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample1)
        self.assertEqual(ts, timestamp)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample2)
        self.assertEqual(ts, timestamp)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample3)
        self.assertEqual(ts, timestamp)

        (timestamp,result) = chunker.get_next_data()
        self.assertEqual(result, None)
        
    def test_instrumment_prompts_for_duplicates(self):
        """
        Verify that the InstrumentPrompts enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(InstrumentPrompts())


    def test_instrument_commands_for_duplicates(self):
        """
        Verify that the InstrumentCmds enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(InstrumentCmds())

    def test_protocol_state_for_duplicates(self):
        """
        Verify that the ProtocolState enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(ProtocolState())

    def test_protocol_event_for_duplicates(self):
        """
        Verify that the ProtocolEvent enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(ProtocolEvent())

    def test_capability_for_duplicates(self):
        """
        Verify that the Capability enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(Capability())

    def test_parameter_for_duplicates(self):
        """
        Verify that the Parameter enumeration has no duplicate values that might cause confusion
        """
        self.assert_enum_has_no_duplicates(Parameter())

    def test_driver_enums(self):
        """
        Verify driver specific enums have no duplicates
        Base unit test driver will test enums specific for the base class.
        """
        self.assert_enum_has_no_duplicates(DataParticleType())

    def test_velocity_sample_format(self):
        """
        Verify driver can get velocity sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
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
            DataParticleKey.VALUES: velocity_particle}

        self.compare_parsed_data_particle(AquadoppDwVelocityDataParticle,
                                          velocity_sample(),
                                          expected_particle)

    def test_chunker(self):
        """
        Verify the chunker can parse each sample type
        1. complete data structure
        2. fragmented data structure
        3. combined data structure
        4. data structure with noise
        """
        chunker = StringChunker(Protocol.chunker_sieve_function)

        # test complete data structures
        self.assert_chunker_sample(chunker, velocity_sample())
        self.assert_chunker_sample(chunker, diagnostic_sample())
        self.assert_chunker_sample(chunker, diagnostic_header_sample())

        # test fragmented data structures
        self.assert_chunker_fragmented_sample(chunker, velocity_sample())
        self.assert_chunker_fragmented_sample(chunker, diagnostic_sample())
        self.assert_chunker_fragmented_sample(chunker, diagnostic_header_sample())

        # test combined data structures
        self.assert_chunker_combined_sample(chunker, velocity_sample())
        self.assert_chunker_combined_sample(chunker, diagnostic_sample())
        self.assert_chunker_combined_sample(chunker, diagnostic_header_sample())

        # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, velocity_sample())
        self.assert_chunker_sample_with_noise(chunker, diagnostic_sample())
        self.assert_chunker_sample_with_noise(chunker, diagnostic_header_sample())

    def test_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, an exception is raised
        """

        particle = AquadoppDwVelocityDataParticle(velocity_sample().replace(chr(0), chr(1), 1),
                        port_timestamp=3558720820.531179)
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
class IntFromIDK(NortekIntTest, AquadoppDriverTestMixinSub):
    
    protocol_state = ''
    
    def setUp(self):
        NortekIntTest.setUp(self)

    def test_acquire_sample(self):
        """
        Verify acquire sample command and events.
        1. initialize the instrument to COMMAND state
        2. command the driver to ACQUIRE SAMPLE
        3. verify the particle coming in
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        # test acquire sample
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_async_particle_generation(DataParticleType.VELOCITY, self.assert_particle_velocity)


    # @unittest.skip('temp disable')
    def test_command_autosample(self):
        """
        Verify autosample command and events.
        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE state
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        5. verify the sampling is continuous by gathering several samples
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        # test autosample
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.VELOCITY, self.assert_particle_velocity, timeout=45)

        # # wait for some samples to be generated
        gevent.sleep(10)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type'] == DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_acquire_sample: # 0f samples = %d', len(sample_events))
        log.debug('samples=%s', sample_events)
        self.assertTrue(len(sample_events) >= 4)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)



    # @unittest.skip('temp disable')
    def test_startup_configuration(self):
        """
        Test that the startup configuration is applied correctly
        """
        self.put_driver_in_command_mode()

        value_before = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])

        self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])

        self.assertEquals(reply, {Parameter.TRANSMIT_PULSE_LENGTH: 0x2})

        reply = self.driver_client.cmd_dvr('set_resource', value_before)

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])

        self.assertEquals(reply, value_before)

    # @unittest.skip('temp disable')
    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, puts instrument in 'command' state
        """
        self.put_driver_in_command_mode()

    # @unittest.skip('temp disable')
    def test_instrument_read_clock(self):
        """
        @brief Test for reading instrument clock
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the clock.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)
        
        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response[1]))

    # @unittest.skip('temp disable')
    def test_instrument_read_mode(self):
        """
        @brief Test for reading what mode
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the mode.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_MODE)
        
        log.debug("what mode returned: %s", response)
        self.assertTrue(2, response[1])

    # @unittest.skip('temp disable')      # TODO don't think this is requireed in the OIS & fully supported in code
    def test_instrument_read_id(self):
        """
        @brief Test for reading ID
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the ID.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_ID)
        
        log.debug("read ID returned: %s", response)
        self.assertTrue(re.search(r'AQD 9984.*', response[1]))

    # @unittest.skip('temp disable')
    def test_instrument_read_hw_config(self):
        """
        @brief Test for reading HW config
        """
        
        hw_config = {'Status': 4, 
                     'RecSize': 144, 
                     'SerialNo': 'AQD 9984      ', 
                     'FWversion': '3.37', 
                     'Frequency': 65535, 
                     'PICversion': 0, 
                     'HWrevision': 4, 
                     'Config': 4}
        
        self.put_driver_in_command_mode()
        
        # command the instrument to read the hw config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HW_CONFIGURATION)
        
        log.debug("read HW config returned: %s", response)
        self.assertEqual(hw_config, response[1])

    # @unittest.skip('temp disable')
    def test_instrument_read_head_config(self):
        """
        @brief Test for reading HEAD config
        """
        
        head_config = {'Config': 16447, 
                       'SerialNo': 'A3L 5258\x00\x00\x00\x00', 
                       'System': 'QQBBAEEAAADFCx76HvoAAM/1MQqfDJ8MnwzTs1v8AC64/8aweQHgLsP/uAsAAAAA//8AAAEAAAABAAAAAAAAAAAA//8AAP//AAD//wAAAAAAAP//AQAAAAAA/////wAAAAAJALLvww7JBQMB2BtnKsnLL/yuJ9oAIs20AcQmAP//f2sDov9rA7R97f31/oD+5XsiAC4A9f8AAAAAAAAAAAAAAAAAAAAAVRUQDhAOECc=', 
                       'Frequency': 2000, 
                       'NBeams': 3, 
                       'Type': 0}

        self.put_driver_in_command_mode()
        
        # command the instrument to read the head config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HEAD_CONFIGURATION)
        
        log.debug("read HEAD config returned: %s", response)
        self.assertEqual(head_config, response[1])

    # @unittest.skip('temp disable')
    def test_instrument_acquire_sample(self):
        """
        Test acquire sample command and events.
        """

        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # wait for some samples to be generated
        gevent.sleep(100)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d', len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 4)

    # @unittest.skip('temp disable')
    def test_instrument_start_stop_autosample(self):
        """
        @brief Test for putting instrument in 'auto-sample' state
        """
        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolState.AUTOSAMPLE)
           
        # re-initialize the driver and re-discover instrument state (should be in autosample)
        # Transition driver to disconnected.
        self.driver_client.cmd_dvr('disconnect')

        # Test the driver is disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Transition driver to unconfigured.
        self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(ProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        self.check_state(ProtocolState.AUTOSAMPLE)

        # wait for some samples to be generated
        gevent.sleep(100)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 4)

        # stop autosample and return to command mode
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
                
        self.check_state(ProtocolState.COMMAND)

    # @unittest.skip('temp disable')
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
        
        params_list = [
            Parameter.TRANSMIT_PULSE_LENGTH,
            Parameter.BLANKING_DISTANCE,
            Parameter.RECEIVE_LENGTH,
            Parameter.TIME_BETWEEN_PINGS,
            Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
            Parameter.NUMBER_PINGS,
            Parameter.AVG_INTERVAL,
            Parameter.USER_NUMBER_BEAMS, 
            Parameter.TIMING_CONTROL_REGISTER,
            Parameter.POWER_CONTROL_REGISTER,
            Parameter.COMPASS_UPDATE_RATE,  
            Parameter.COORDINATE_SYSTEM,
            Parameter.NUMBER_BINS,
            Parameter.BIN_LENGTH,
            Parameter.MEASUREMENT_INTERVAL,
            Parameter.DEPLOYMENT_NAME,
            Parameter.WRAP_MODE,
            Parameter.CLOCK_DEPLOY,
            Parameter.DIAGNOSTIC_INTERVAL,
            Parameter.MODE,
            Parameter.ADJUSTMENT_SOUND_SPEED,
            Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
            Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
            Parameter.NUMBER_PINGS_DIAGNOSTIC,
            Parameter.MODE_TEST,
            Parameter.ANALOG_INPUT_ADDR,
            Parameter.SW_VERSION,
            Parameter.VELOCITY_ADJ_TABLE,
            Parameter.COMMENTS,
            Parameter.WAVE_MEASUREMENT_MODE,
            Parameter.DYN_PERCENTAGE_POSITION,
            Parameter.WAVE_TRANSMIT_PULSE,
            Parameter.WAVE_BLANKING_DISTANCE,
            Parameter.WAVE_CELL_SIZE,
            Parameter.NUMBER_DIAG_SAMPLES,
            Parameter.ANALOG_OUTPUT_SCALE,
            Parameter.CORRELATION_THRESHOLD,
            Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
            Parameter.QUAL_CONSTANTS,
            ]
        
        self.put_driver_in_command_mode()

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        log.debug("\nec=%s\ndc=%s" %(sorted(command_capabilities), sorted(driver_capabilities[0])))
        self.assertTrue(sorted(command_capabilities) == sorted(driver_capabilities[0]))
        #log.debug('dc=%s' %sorted(driver_capabilities[1]))
        #log.debug('pl=%s' %sorted(params_list))
        self.assertTrue(sorted(params_list) == sorted(driver_capabilities[1]))

        # Put the driver in autosample
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolState.AUTOSAMPLE)

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        log.debug('test_capabilities: autosample mode capabilities=%s' %driver_capabilities)
        self.assertTrue(autosample_capabilities == driver_capabilities[0])

    @unittest.skip('temp disable')
    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        # with self.assertRaises(InstrumentCommandException):
        #     self.driver_client.cmd_dvr('bogus_command')       # TODO temporary comment out

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = 'not a config dict'            
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG.pop('addr')
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG['addr'] = ''
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
        
        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
                
        self.driver_client.cmd_dvr('discover_state')

        try:
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)
        except:
            self.assertEqual(self.protocol_state, ProtocolState.AUTOSAMPLE)
            # Put the driver in command mode
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('connect')
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.ADJUSTMENT_SOUND_SPEED]
            self.driver_client.cmd_dvr('get_resource', bogus_params)
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name': 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.ADJUSTMENT_SOUND_SPEED: 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(NortekQualTest, AquadoppDriverTestMixinSub):
    def setUp(self):
        NortekQualTest.setUp(self)

    def assert_execute_resource(self, command):
        """
        @brief send an execute_resource command and ensure no exceptions are raised
        """
        
        # send command to the instrument 
        cmd = AgentCommand(command=ResourceAgentEvent.EXECUTE_RESOURCE,
                           args=[command])
        try:            
            return self.instrument_agent_client.execute_agent(cmd)
        except:
            self.fail('assert_execute_resource: execute_resource command failed for %s' %command)

    def assert_resource_capabilities(self, capabilities):

        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @return res_cmds, res_pars
            '''
            res_cmds = []
            res_pars = []

            if(not capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)):
                capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)):
                capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

            res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
            res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            return res_cmds, res_pars

        retval = self.instrument_agent_client.get_capabilities()
        res_cmds, res_pars = sort_capabilities(retval)

        log.debug("Resource Commands: %s " % sorted(res_cmds))
        log.debug("Expected Resource Commands: %s " % sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)))
        
        log.debug("Resource Parameters: %s " % sorted(res_pars))
        log.debug("Expected Resource Parameters: %s " % sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)))

        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)), sorted(res_cmds), "commands don't match")
        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)), sorted(res_pars), "parameters don't match")

    def get_parameter(self, name):
        '''
        get parameter, assumes we are in command mode.
        '''
        getParams = [ name ]

        result = self.instrument_agent_client.get_resource(getParams)

        return result[name]

    def assert_sample_polled(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test observatory polling function.

        Verifies the acquire_status command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        ###
        # Poll for a sample
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        log.debug("Acquire Sample")
        self.data_subscribers.clear_sample_queue(sampleQueue)

        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Watch the parsed data queue and return once a sample
        # has been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sampleQueue, 4, timeout = timeout)
        self.assertGreaterEqual(len(samples), 4)
        log.error("SAMPLE: %s" % samples)

        # Verify
        for sample in samples:
            sampleDataAssert(sample)

        self.assert_reset()
        self.doCleanups()

    def assertSampleDataParticle(self, sample):
        log.debug('assertSampleDataParticle: sample=%s' %sample)
        self.assertTrue(sample[DataParticleKey.STREAM_NAME],
            DataParticleType.PARSED)
        self.assertTrue(sample[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample.get(DataParticleKey.PREFERRED_TIMESTAMP))
        
        values = sample['values']
        value_ids = []
        for value in values:
            value_ids.append(value['value_id'])
        if AquadoppDwVelocityDataParticleKey.TIMESTAMP in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwVelocityDataParticle/AquadoppDwDiagnosticDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwVelocityDataParticleKey.list()))
            for value in values:
                if value['value_id'] == AquadoppDwVelocityDataParticleKey.TIMESTAMP:
                    self.assertTrue(isinstance(value['value'], str))
                else:
                    self.assertTrue(isinstance(value['value'], int))
        elif AquadoppDwDiagnosticHeaderDataParticleKey.RECORDS in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwDiagnosticHeaderDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwDiagnosticHeaderDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value['value'], int))
        else:
            self.fail('Unknown data particle')

    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={#'session_type': DirectAccessTypes.telnet,
                                   'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        gevent.sleep(600)  # wait for manual telnet session to be run


    def test_direct_access_telnet_mode(self):
        """
        Verify the Instrument Driver properly supports direct access to the
        physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("K1W%!Q")
        result = self.tcp_client.expect("AQUADOPP")

        self.assertTrue(result)

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        poll for a single sample
        '''

        self.assert_sample_polled(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_get_set_parameters(self):
        '''
        verify that parameters can be get set properly
        '''
        self.assert_enter_command_mode()
        
        value_before_set = self.get_parameter(Parameter.BLANKING_DISTANCE)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 40)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, value_before_set)

        value_before_set = self.get_parameter(Parameter.AVG_INTERVAL)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, 4)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, value_before_set)

        self.assert_reset()

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.SET, 
                ProtocolEvent.ACQUIRE_SAMPLE, 
                ProtocolEvent.GET, 
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.GET_HEAD_CONFIGURATION,
                ProtocolEvent.GET_HW_CONFIGURATION,
                ProtocolEvent.POWER_DOWN,
                ProtocolEvent.READ_BATTERY_VOLTAGE,
                ProtocolEvent.READ_CLOCK, 
                ProtocolEvent.READ_ID,
                ProtocolEvent.READ_MODE,
                ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME,
                ProtocolEvent.START_MEASUREMENT_IMMEDIATE,
                ProtocolEvent.SET_CONFIGURATION
            ],
            AgentCapabilityType.RESOURCE_PARAMETER: [
                Parameter.TRANSMIT_PULSE_LENGTH,
                Parameter.BLANKING_DISTANCE,
                Parameter.RECEIVE_LENGTH,
                Parameter.TIME_BETWEEN_PINGS,
                Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
                Parameter.NUMBER_PINGS,
                Parameter.AVG_INTERVAL,
                Parameter.USER_NUMBER_BEAMS, 
                Parameter.TIMING_CONTROL_REGISTER,
                Parameter.POWER_CONTROL_REGISTER,
                Parameter.COMPASS_UPDATE_RATE,  
                Parameter.COORDINATE_SYSTEM,
                Parameter.NUMBER_BINS,
                Parameter.BIN_LENGTH,
                Parameter.MEASUREMENT_INTERVAL,
                Parameter.DEPLOYMENT_NAME,
                Parameter.WRAP_MODE,
                Parameter.CLOCK_DEPLOY,
                Parameter.DIAGNOSTIC_INTERVAL,
                Parameter.MODE,
                Parameter.ADJUSTMENT_SOUND_SPEED,
                Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                Parameter.NUMBER_PINGS_DIAGNOSTIC,
                Parameter.MODE_TEST,
                Parameter.ANALOG_INPUT_ADDR,
                Parameter.SW_VERSION,
                Parameter.VELOCITY_ADJ_TABLE,
                Parameter.COMMENTS,
                Parameter.WAVE_MEASUREMENT_MODE,
                Parameter.DYN_PERCENTAGE_POSITION,
                Parameter.WAVE_TRANSMIT_PULSE,
                Parameter.WAVE_BLANKING_DISTANCE,
                Parameter.WAVE_CELL_SIZE,
                Parameter.NUMBER_DIAG_SAMPLES,
                Parameter.ANALOG_OUTPUT_SCALE,
                Parameter.CORRELATION_THRESHOLD,
                Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                Parameter.QUAL_CONSTANTS
            ],
        }

        self.assert_resource_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [DriverEvent.STOP_AUTOSAMPLE]

        self.assert_start_autosample()
        self.assert_resource_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_resource_capabilities(capabilities)

    def test_instrument_set_configuration(self):
        """
        @brief Test for setting instrument configuration
        """
        
        self.assert_enter_command_mode()
        
        # command the instrument to set the user configuration.
        cmd = AgentCommand(command=ResourceAgentEvent.EXECUTE_RESOURCE,
                           args=[ProtocolEvent.SET_CONFIGURATION],
                           kwargs={'user_configuration':base64.b64encode(user_config2())})
        try:
            self.instrument_agent_client.execute_agent(cmd)
            pass
        except:
            self.fail('test of set_configuration command failed')
        
    def test_instrument_clock_sync(self):
        """
        @brief Test for syncing clock
        """
        
        self.assert_enter_command_mode()
        
        # command the instrument to read the clock.
        response = self.assert_execute_resource(ProtocolEvent.READ_CLOCK)
        
        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response.result))

        # command the instrument to sync the clck.
        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # command the instrument to read the clock.
        response = self.assert_execute_resource(ProtocolEvent.READ_CLOCK)
        
        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response.result))
        
        # verify that the dates match 
        local_time = time.gmtime(time.mktime(time.localtime()))
        local_time_str = time.strftime("%d/%m/%Y %H:%M:%S", local_time)
        self.assertTrue(local_time_str[:12].upper() in response.result.upper())
        
        # verify that the times match closely
        instrument_time = time.strptime(response.result, '%d/%m/%Y %H:%M:%S')
        #log.debug("it=%s, lt=%s" %(instrument_time, local_time))
        it = datetime.datetime(*instrument_time[:6])
        lt = datetime.datetime(*local_time[:6])
        #log.debug("it=%s, lt=%s, lt-it=%s" %(it, lt, lt-it))
        if lt - it > datetime.timedelta(seconds = 5):
            self.fail("time delta too large after clock sync")      