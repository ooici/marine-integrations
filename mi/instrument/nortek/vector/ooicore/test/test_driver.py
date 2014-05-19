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

from gevent import monkey


monkey.patch_all()
import time
import ntplib

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import ParameterTestConfigKey

from mi.instrument.nortek.test.test_driver import NortekUnitTest, NortekIntTest, NortekQualTest, DriverTestMixinSub

from mi.core.instrument.instrument_driver import DriverConfigKey

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import SampleException

from mi.instrument.nortek.driver import ProtocolState, TIMEOUT, EngineeringParameter, Capability
from mi.instrument.nortek.driver import ProtocolEvent

from mi.instrument.nortek.vector.ooicore.driver import DataParticleType
from mi.instrument.nortek.vector.ooicore.driver import Protocol
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityHeaderDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityHeaderDataParticleKey
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorVelocityDataParticleKey
from mi.instrument.nortek.vector.ooicore.driver import VectorSystemDataParticle
from mi.instrument.nortek.vector.ooicore.driver import VectorSystemDataParticleKey

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.vector.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='nortek_vector_dw_ooicore',
    instrument_agent_name='nortek_vector_dw_ooicore_agent',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={
        DriverConfigKey.PARAMETERS:
            {EngineeringParameter.CLOCK_SYNC_INTERVAL: '00:00:00',
             EngineeringParameter.ACQUIRE_STATUS_INTERVAL: '00:00:00'}}
)


# velocity data particle & sample 
def velocity_sample():
    sample_as_hex = "a51000db00008f10000049f041f72303303132120918d8f7"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
velocity_particle = [{DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT2, DataParticleKey.VALUE: 0},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.COUNT, DataParticleKey.VALUE: 219},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.PRESSURE, DataParticleKey.VALUE: 4239},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT1, DataParticleKey.VALUE: 0},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM1, DataParticleKey.VALUE: 61513},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM2, DataParticleKey.VALUE: 63297},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM3, DataParticleKey.VALUE: 803},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM1, DataParticleKey.VALUE: 48},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM2, DataParticleKey.VALUE: 49},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM3, DataParticleKey.VALUE: 50},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM1, DataParticleKey.VALUE: 18},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM2, DataParticleKey.VALUE: 9},
                     {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM3, DataParticleKey.VALUE: 24}]


# velocity header data particle & sample 
def velocity_header_sample():
    sample_as_hex = "a512150012491711121270032f2f2e0002090d0000000000000000000000000000000000000000005d70"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
velocity_header_particle = [{DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: '17/12/2012 11:12:49'},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NUMBER_OF_RECORDS, DataParticleKey.VALUE: 880},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE1, DataParticleKey.VALUE: 47},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE2, DataParticleKey.VALUE: 47},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE3, DataParticleKey.VALUE: 46},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION1, DataParticleKey.VALUE: 2},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION2, DataParticleKey.VALUE: 9},
                            {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION3, DataParticleKey.VALUE: 13}]


# system data particle & sample 
def system_sample():
    sample_as_hex = "a5110e0003261317121294007c3b83041301cdfe0a08007b0000e4d9"
    return sample_as_hex.decode('hex')

# these values checkout against the sample above
system_particle = [{DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: '13/12/2012 17:03:26'},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.BATTERY, DataParticleKey.VALUE: 148},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.SOUND_SPEED, DataParticleKey.VALUE: 15228},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.HEADING, DataParticleKey.VALUE: 1155},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.PITCH, DataParticleKey.VALUE: 275},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ROLL, DataParticleKey.VALUE: 65229},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TEMPERATURE, DataParticleKey.VALUE: 2058},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ERROR, DataParticleKey.VALUE: 0},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.STATUS, DataParticleKey.VALUE: 123},
                   {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ANALOG_INPUT, DataParticleKey.VALUE: 0}]


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
class VectorDriverTestMixinSub(DriverTestMixinSub):
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

    _sample_parameters_01 = {
        VectorVelocityDataParticleKey.ANALOG_INPUT2: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.PRESSURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.ANALOG_INPUT1: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.VELOCITY_BEAM1: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.VELOCITY_BEAM2: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.VELOCITY_BEAM3: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.AMPLITUDE_BEAM1: {TYPE: int, VALUE: 1, REQUIRED: True},
        VectorVelocityDataParticleKey.AMPLITUDE_BEAM2: {TYPE: int, VALUE: 1, REQUIRED: True},
        VectorVelocityDataParticleKey.AMPLITUDE_BEAM3: {TYPE: int, VALUE: 1, REQUIRED: True},
        VectorVelocityDataParticleKey.CORRELATION_BEAM1: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.CORRELATION_BEAM2: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityDataParticleKey.CORRELATION_BEAM3: {TYPE: int, VALUE: 0, REQUIRED: True}
    }

    _sample_parameters_02 = {
        VectorVelocityHeaderDataParticleKey.TIMESTAMP: {TYPE: unicode, VALUE: '', REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.NUMBER_OF_RECORDS: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.NOISE1: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.NOISE2: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.NOISE3: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.CORRELATION1: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.CORRELATION2: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorVelocityHeaderDataParticleKey.CORRELATION3: {TYPE: int, VALUE: 0, REQUIRED: True}
    }

    _system_data_parameter = {
        VectorSystemDataParticleKey.TIMESTAMP: {TYPE: unicode, VALUE: '', REQUIRED: True},
        VectorSystemDataParticleKey.BATTERY: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.SOUND_SPEED: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.HEADING: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.PITCH: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.ROLL: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.TEMPERATURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.ERROR: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        VectorSystemDataParticleKey.ANALOG_INPUT: {TYPE: int, VALUE: 0, REQUIRED: True}
    }

    def assert_particle_sample(self, data_particle, verify_values=False):
        """
        Verify vel3d_cd_sample particle
        @param data_particle:  VectorVelocityDataParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(VectorVelocityDataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.VELOCITY)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_velocity(self, data_particle, verify_values=False):
        """
        Verify veld3d_cd_velocity particle
        @param data_particle:  VectorVelocityHeaderDataParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(VectorVelocityHeaderDataParticleKey, self._sample_parameters_02)
        self.assert_data_particle_header(data_particle, DataParticleType.VELOCITY_HEADER)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_02, verify_values)

    def assert_particle_system(self, data_particle, verify_values=False):
        """
        Verify vel3d_cd_system particle
        @param data_particle:  VectorSystemDataParticleKeydata particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(VectorSystemDataParticleKey, self._system_data_parameter)
        self.assert_data_particle_header(data_particle, DataParticleType.SYSTEM)
        self.assert_data_particle_parameters(data_particle, self._system_data_parameter, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(NortekUnitTest):
    def setUp(self):
        NortekUnitTest.setUp(self)

    def test_driver_enums(self):
        """
        Verify driver specific enums have no duplicates
        Base unit test driver will test enums specific for the base class.
        """
        self.assert_enum_has_no_duplicates(DataParticleType())

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
        self.assert_chunker_fragmented_sample(chunker, velocity_sample())
        self.assert_chunker_fragmented_sample(chunker, system_sample())
        self.assert_chunker_fragmented_sample(chunker, velocity_header_sample())

        # test combined data structures
        self.assert_chunker_combined_sample(chunker, velocity_sample())
        self.assert_chunker_combined_sample(chunker, system_sample())
        self.assert_chunker_combined_sample(chunker, velocity_header_sample())

        # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, velocity_sample())
        self.assert_chunker_sample_with_noise(chunker, system_sample())
        self.assert_chunker_sample_with_noise(chunker, velocity_header_sample())

    def test_corrupt_data_structures(self):
        # garbage is not okay
        particle = VectorVelocityHeaderDataParticle(velocity_header_sample().replace(chr(0), chr(1), 1),
                                                    port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

        particle = VectorSystemDataParticle(system_sample().replace(chr(0), chr(1), 1),
                                            port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

        particle = VectorVelocityDataParticle(velocity_sample().replace(chr(16), chr(17), 1),
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
class IntFromIDK(NortekIntTest, VectorDriverTestMixinSub):

    def setUp(self):
        NortekIntTest.setUp(self)

    def test_acquire_sample(self):
        """
        Test acquire sample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRESAMPLE
        3. verify the particle coming in
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        # test acquire sample
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_async_particle_generation(DataParticleType.VELOCITY, self.assert_particle_sample, timeout=TIMEOUT)

    def test_command_autosample(self):
        """
        Test autosample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.VELOCITY_HEADER, self.assert_particle_velocity)
        self.assert_async_particle_generation(DataParticleType.SYSTEM, self.assert_particle_system)
        self.assert_async_particle_generation(DataParticleType.VELOCITY, self.assert_particle_sample, timeout=45)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    # def test_instrument_read_id(self):
    #     """
    #     Test for reading ID, need to be implemented in the child class because each ID is unique to the
    #     instrument.
    #     """
    #     self.assert_initialize_driver()
    #
    #     # command the instrument to read the ID.
    #     response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_ID)
    #
    #     log.debug("read ID returned: %s", response)
    #     self.assertTrue(re.search(r'VEL .*', response[1]))
    #
    #     self.assert_driver_command(ProtocolEvent.READ_ID, regex=ID_DATA_PATTERN)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(NortekQualTest, VectorDriverTestMixinSub):

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports direct access to the
        physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("K1W%!Q")
        self.tcp_client.expect("VECTOR")

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        """
        Verify data particles for a single sample that are specific to Vector
        """
        self.assert_sample_polled(self.assert_particle_velocity, DataParticleType.VELOCITY_HEADER, timeout=10)
        self.assert_sample_polled(self.assert_particle_sample, DataParticleType.VELOCITY, timeout=10)
        self.assert_sample_polled(self.assert_particle_system, DataParticleType.SYSTEM, timeout=60)

    def test_autosample(self):
        """
        Verify data particles for autosampling that are specific to Vector
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(Capability.START_AUTOSAMPLE, self.assert_particle_velocity, DataParticleType.VELOCITY_HEADER)
        self.assert_particle_async(DataParticleType.VELOCITY, self.assert_particle_sample, timeout=10)
        self.assert_particle_async(DataParticleType.SYSTEM, self.assert_particle_system, timeout=10)
