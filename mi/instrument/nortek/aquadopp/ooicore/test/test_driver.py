"""
@package mi.instrument.nortek.aquadopp.ooicore.test.test_driver
@author Rachel Manoni
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

__author__ = 'Rachel Manoni, Ronald Ronquillo'
__license__ = 'Apache 2.0'

import time

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey
from mi.instrument.ooici.mi.test_driver.test.test_driver import DriverTestMixinSub

from mi.core.instrument.instrument_driver import DriverConfigKey, ResourceAgentState

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import SampleException

from mi.instrument.nortek.aquadopp.ooicore.driver import NortekDataParticleType
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticleKey

from mi.instrument.nortek.test.test_driver import NortekUnitTest, NortekIntTest, NortekQualTest, user_config2
from mi.instrument.nortek.driver import ProtocolState, ProtocolEvent, TIMEOUT, Parameter, NortekEngIdDataParticleKey, \
    NortekInstrumentProtocol, NEWLINE, EngineeringParameter

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.aquadopp.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='nortek_aquadopp_dw_ooicore',
    instrument_agent_name='nortek_aquadopp_dw_ooicore_agent',
    instrument_agent_packet_config=NortekDataParticleType(),
    driver_startup_config={
        DriverConfigKey.PARAMETERS: {
            Parameter.DEPLOYMENT_NAME: 'test',
            Parameter.VELOCITY_ADJ_TABLE: 'Aj0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8'
                                          'XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQK'
                                          'xAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20'
                                          'HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC',
            Parameter.COMMENTS: 'this is a test',
            Parameter.ANALOG_OUTPUT_SCALE: 6711,
            Parameter.QUAL_CONSTANTS: 'Cv/N/4sA5QDuAAsAhP89/w==',
            #update the following two parameters to allow for faster collecting of samples during testing
            Parameter.AVG_INTERVAL: 1,
            Parameter.MEASUREMENT_INTERVAL: 1}}
)


def eng_id_sample():
    sample_as_hex = "415144"
    return sample_as_hex.decode('hex')

eng_id_particle = [{DataParticleKey.VALUE_ID: NortekEngIdDataParticleKey.ID, DataParticleKey.VALUE: "AQD 8493      "}]


def bad_sample():
    sample = 'thisshouldnotworkd'
    return sample


def velocity_sample():
    sample_as_hex = "a5011500101926221211000000009300f83b810628017f01002d0000e3094c0122ff9afe1e1416006093"
    return sample_as_hex.decode('hex')

velocity_particle = [{'value_id': 'date_time_string', 'value': '26/11/2012 22:10:19'},
                     {'value_id': 'error_code', 'value': 0},
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
        @param data_particle AquadoppDwVelocityDataParticleKey data particle
        @param verify_values bool, should we verify parameter values
        """
        self.assert_data_particle_keys(AquadoppDwVelocityDataParticleKey, self._sample_velocity_diagnostic)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.VELOCITY)
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

    def test_driver_enums(self):
        """
        Verify driver specific enums have no duplicates
        Base unit test driver will test enums specific for the base class.
        """
        self.assert_enum_has_no_duplicates(NortekDataParticleType())

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
            DataParticleKey.STREAM_NAME: NortekDataParticleType.VELOCITY,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: velocity_particle}
        
        self.compare_parsed_data_particle(AquadoppDwVelocityDataParticle, velocity_sample(), expected_particle)

    def test_chunker(self):
        """
        Verify the chunker can parse each sample type
        1. complete data structure
        2. fragmented data structure
        3. combined data structure
        4. data structure with noise
        """
        chunker = StringChunker(NortekInstrumentProtocol.sieve_function)

        self.assert_chunker_sample(chunker, velocity_sample())
        self.assert_chunker_fragmented_sample(chunker, velocity_sample())
        self.assert_chunker_combined_sample(chunker, velocity_sample())
        self.assert_chunker_sample_with_noise(chunker, velocity_sample())

    def test_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, an exception is raised
        """
        particle = AquadoppDwVelocityDataParticle(bad_sample(), port_timestamp=3558720820.531179)

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
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_async_particle_generation(NortekDataParticleType.VELOCITY, self.assert_particle_velocity, timeout=TIMEOUT)

    def test_command_autosample(self):
        """
        Verify autosample command and events.
        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE state
        3. verify the particle coming in and the sampling is continuous (gather several samples)
        4. stop AUTOSAMPLE
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(NortekDataParticleType.VELOCITY, self.assert_particle_velocity,
                                              particle_count=4, timeout=TIMEOUT)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.BLANKING_DISTANCE, 50)
        self.assert_set(Parameter.TIMING_CONTROL_REGISTER, 131)
        self.assert_set(Parameter.COMPASS_UPDATE_RATE, 2)
        self.assert_set(Parameter.COORDINATE_SYSTEM, 1)
        self.assert_set(Parameter.VELOCITY_ADJ_TABLE, 'bu0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8'
                                          'XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQK'
                                          'xAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20'
                                          'HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC',)

        #these need to update simultaneously
        #self.assert_set(Parameter.MEASUREMENT_INTERVAL, 61)
        #self.assert_set(Parameter.AVG_INTERVAL, 61)

        #test read only parameters (includes immutable, when not startup)
        self.assert_set_exception(EngineeringParameter.CLOCK_SYNC_INTERVAL, '12:00:00')
        self.assert_set_exception(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, '12:00:00')
        self.assert_set_exception(Parameter.TRANSMIT_PULSE_LENGTH, 20)
        self.assert_set_exception(Parameter.TIME_BETWEEN_PINGS, 45)
        self.assert_set_exception(Parameter.NUMBER_PINGS, 1)
        self.assert_set_exception(Parameter.RECEIVE_LENGTH, 8)
        self.assert_set_exception(Parameter.TIME_BETWEEN_BURST_SEQUENCES, 1)
        self.assert_set_exception(Parameter.USER_NUMBER_BEAMS, 4)
        self.assert_set_exception(Parameter.POWER_CONTROL_REGISTER, 1)
        self.assert_set_exception(Parameter.A1_1_SPARE, 3)
        self.assert_set_exception(Parameter.B0_1_SPARE, 1)
        self.assert_set_exception(Parameter.B1_1_SPARE, 2)
        self.assert_set_exception(Parameter.NUMBER_BINS, 2)
        self.assert_set_exception(Parameter.BIN_LENGTH, 8)
        self.assert_set_exception(Parameter.ADJUSTMENT_SOUND_SPEED, 16658)
        self.assert_set_exception(Parameter.DEPLOYMENT_NAME, 'test')
        self.assert_set_exception(Parameter.WRAP_MODE, 0)
        self.assert_set_exception(Parameter.CLOCK_DEPLOY, 123)
        self.assert_set_exception(Parameter.DIAGNOSTIC_INTERVAL, 10801)
        self.assert_set_exception(Parameter.MODE, 49)
        self.assert_set_exception(Parameter.NUMBER_SAMPLES_DIAGNOSTIC, 2)
        self.assert_set_exception(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC, 2)
        self.assert_set_exception(Parameter.NUMBER_PINGS_DIAGNOSTIC, 2)
        self.assert_set_exception(Parameter.MODE_TEST, 5)
        self.assert_set_exception(Parameter.ANALOG_INPUT_ADDR, '123')
        self.assert_set_exception(Parameter.SW_VERSION, 'blah')
        self.assert_set_exception(Parameter.USER_1_SPARE, 23)
        self.assert_set_exception(Parameter.COMMENTS, 'hello there')
        self.assert_set_exception(Parameter.WAVE_MEASUREMENT_MODE, 3)
        self.assert_set_exception(Parameter.DYN_PERCENTAGE_POSITION, 3)
        self.assert_set_exception(Parameter.WAVE_TRANSMIT_PULSE,3 )
        self.assert_set_exception(Parameter.WAVE_BLANKING_DISTANCE, 3)
        self.assert_set_exception(Parameter.WAVE_CELL_SIZE, 3)
        self.assert_set_exception(Parameter.NUMBER_DIAG_SAMPLES, 1)
        self.assert_set_exception(Parameter.A1_2_SPARE, 6)
        self.assert_set_exception(Parameter.B0_2_SPARE, 4)
        self.assert_set_exception(Parameter.NUMBER_SAMPLES_PER_BURST, 4)
        self.assert_set_exception(Parameter.USER_2_SPARE, 1)
        self.assert_set_exception(Parameter.ANALOG_OUTPUT_SCALE, 234)
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, 1234)
        self.assert_set_exception(Parameter.USER_3_SPARE, 1)
        self.assert_set_exception(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG, 1)
        self.assert_set_exception(Parameter.USER_4_SPARE, 1)
        self.assert_set_exception(Parameter.QUAL_CONSTANTS, 'consts')


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(NortekQualTest, AquadoppDriverTestMixinSub):
    def setUp(self):
        NortekQualTest.setUp(self)

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

        log.debug("DA Server Started.  Reading battery voltage")
        self.tcp_client.send_data("BV")
        self.tcp_client.expect("\x06\x06")

        self.tcp_client.send_data("CC" + user_config2())
        self.tcp_client.expect("\x06\x06")

        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)

        #verify the setting got restored.
        self.assert_get_parameter(Parameter.TRANSMIT_PULSE_LENGTH, 125)
        self.assert_get_parameter(Parameter.RECEIVE_LENGTH, 32)
        self.assert_get_parameter(Parameter.TIME_BETWEEN_BURST_SEQUENCES, 512)
        self.assert_get_parameter(Parameter.TIMING_CONTROL_REGISTER, 131)
        self.assert_get_parameter(Parameter.BIN_LENGTH, 7)
        self.assert_get_parameter(Parameter.ADJUSTMENT_SOUND_SPEED, 1525)
        self.assert_get_parameter(Parameter.VELOCITY_ADJ_TABLE, 'Aj0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8'
                                          'XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQK'
                                          'xAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20'
                                          'HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC',)

        self.assert_get_parameter(EngineeringParameter.CLOCK_SYNC_INTERVAL, '00:00:00')
        self.assert_get_parameter(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, '00:00:00')
        self.assert_get_parameter(Parameter.BLANKING_DISTANCE, 49)
        self.assert_get_parameter(Parameter.TIME_BETWEEN_PINGS, 437)
        self.assert_get_parameter(Parameter.NUMBER_PINGS, 1)
        self.assert_get_parameter(Parameter.AVG_INTERVAL, 1)
        self.assert_get_parameter(Parameter.USER_NUMBER_BEAMS, 3)
        self.assert_get_parameter(Parameter.POWER_CONTROL_REGISTER, 0)
        self.assert_get_parameter(Parameter.COMPASS_UPDATE_RATE, 1)
        self.assert_get_parameter(Parameter.COORDINATE_SYSTEM, 2)
        self.assert_get_parameter(Parameter.NUMBER_BINS, 1)
        self.assert_get_parameter(Parameter.MEASUREMENT_INTERVAL, 1)
        self.assert_get_parameter(Parameter.WRAP_MODE, 0)
        self.assert_get_parameter(Parameter.CLOCK_DEPLOY, [0,0,0,0,0,0])
        self.assert_get_parameter(Parameter.DIAGNOSTIC_INTERVAL, 11250)
        self.assert_get_parameter(Parameter.MODE, 48)
        self.assert_get_parameter(Parameter.NUMBER_SAMPLES_DIAGNOSTIC, 20)
        self.assert_get_parameter(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC, 1)
        self.assert_get_parameter(Parameter.NUMBER_PINGS_DIAGNOSTIC, 1)
        self.assert_get_parameter(Parameter.MODE_TEST, 4)
        self.assert_get_parameter(Parameter.WAVE_MEASUREMENT_MODE, 0)
        self.assert_get_parameter(Parameter.DYN_PERCENTAGE_POSITION, 0)
        self.assert_get_parameter(Parameter.WAVE_TRANSMIT_PULSE, 0)
        self.assert_get_parameter(Parameter.WAVE_BLANKING_DISTANCE, 0)
        self.assert_get_parameter(Parameter.WAVE_CELL_SIZE, 0)
        self.assert_get_parameter(Parameter.NUMBER_DIAG_SAMPLES, 0)
        self.assert_get_parameter(Parameter.NUMBER_SAMPLES_PER_BURST, 0)
        self.assert_get_parameter(Parameter.ANALOG_OUTPUT_SCALE, 6711)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 0)
        self.assert_get_parameter(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG, 2)

        # Test direct access inactivity timeout
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        # Test session timeout without activity
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        # Test direct access session timeout with activity
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            time.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 45)

    def test_get_set_parameters(self):
        """
        Verify that parameters can be get/set properly
        """
        self.assert_enter_command_mode()

        #test read/write parameter
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 50)
        self.assert_set_parameter(Parameter.TIMING_CONTROL_REGISTER, 131)
        self.assert_set_parameter(Parameter.COMPASS_UPDATE_RATE, 2)
        self.assert_set_parameter(Parameter.COORDINATE_SYSTEM, 1)
        self.assert_set_parameter(Parameter.VELOCITY_ADJ_TABLE, 'bu0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8'
                                          'XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQK'
                                          'xAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20'
                                          'HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC',)

        #test read only parameters (includes immutable, when not startup)
        self.assert_get_parameter(EngineeringParameter.CLOCK_SYNC_INTERVAL, '00:00:00')
        self.assert_get_parameter(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, '00:00:00')
        self.assert_get_parameter(Parameter.TRANSMIT_PULSE_LENGTH, 125)
        self.assert_get_parameter(Parameter.TIME_BETWEEN_PINGS, 437)
        self.assert_get_parameter(Parameter.NUMBER_PINGS, 1)
        self.assert_get_parameter(Parameter.RECEIVE_LENGTH, 32)
        self.assert_get_parameter(Parameter.TIME_BETWEEN_BURST_SEQUENCES, 512)
        self.assert_get_parameter(Parameter.USER_NUMBER_BEAMS, 3)
        self.assert_get_parameter(Parameter.POWER_CONTROL_REGISTER, 0)
        self.assert_get_parameter(Parameter.NUMBER_BINS, 1)
        self.assert_get_parameter(Parameter.BIN_LENGTH, 7)
        self.assert_get_parameter(Parameter.ADJUSTMENT_SOUND_SPEED, 1525)
        self.assert_get_parameter(Parameter.WRAP_MODE, 0)
        self.assert_get_parameter(Parameter.CLOCK_DEPLOY, [0, 0, 0, 0, 0, 0])
        self.assert_get_parameter(Parameter.DIAGNOSTIC_INTERVAL, 11250)
        self.assert_get_parameter(Parameter.MODE, 48)
        self.assert_get_parameter(Parameter.NUMBER_SAMPLES_DIAGNOSTIC, 20)
        self.assert_get_parameter(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC, 1)
        self.assert_get_parameter(Parameter.ANALOG_INPUT_ADDR, 0)
        self.assert_get_parameter(Parameter.NUMBER_PINGS_DIAGNOSTIC, 1)
        self.assert_get_parameter(Parameter.MODE_TEST, 4)
        self.assert_get_parameter(Parameter.SW_VERSION, 13902)
        self.assert_get_parameter(Parameter.SW_VERSION, 13902)
        self.assert_get_parameter(Parameter.WAVE_MEASUREMENT_MODE, 0)
        self.assert_get_parameter(Parameter.DYN_PERCENTAGE_POSITION, 0)
        self.assert_get_parameter(Parameter.WAVE_TRANSMIT_PULSE, 0)
        self.assert_get_parameter(Parameter.WAVE_BLANKING_DISTANCE, 0)
        self.assert_get_parameter(Parameter.WAVE_CELL_SIZE, 0)
        self.assert_get_parameter(Parameter.NUMBER_DIAG_SAMPLES, 0)
        self.assert_get_parameter(Parameter.NUMBER_SAMPLES_PER_BURST, 0)
        self.assert_get_parameter(Parameter.ANALOG_OUTPUT_SCALE, 6711)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 0)
        self.assert_get_parameter(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG, 2)

        #NOTE: the following cannot be tested because there are no default values
        #    'spare' parameters are not used by the driver, only place holders for the config file sent to set params
        #     other parameter values are dependent on the instrument being tested
        # self.assert_get_parameter(Parameter.A1_1_SPARE, 3)
        # self.assert_get_parameter(Parameter.B0_1_SPARE, 1)
        # self.assert_get_parameter(Parameter.B1_1_SPARE, 2)
        # self.assert_get_parameter(Parameter.DEPLOYMENT_NAME, 'test')
        # self.assert_get_parameter(Parameter.USER_1_SPARE, 23)
        # self.assert_get_parameter(Parameter.COMMENTS, 'hello there')
        # self.assert_get_parameter(Parameter.A1_2_SPARE, 6)
        # self.assert_get_parameter(Parameter.B0_2_SPARE, 4)
        # self.assert_get_parameter(Parameter.USER_2_SPARE, 1)
        # self.assert_get_parameter(Parameter.USER_3_SPARE, 1)
        # self.assert_get_parameter(Parameter.USER_4_SPARE, 1)
        # self.assert_get_parameter(Parameter.QUAL_CONSTANTS, 'consts')

    def test_poll(self):
        """
        Verify the driver can poll the instrument for a single sample
        """
        self.assert_sample_polled(self.assert_particle_velocity, NortekDataParticleType.VELOCITY, timeout=10)

    def test_autosample(self):
        """
        Verify the driver can enter and exit autosample mode, while in autosample the driver will collect multiple
        samples.
        """
        self.assert_sample_autosample(self.assert_particle_velocity, NortekDataParticleType.VELOCITY, timeout=20)
