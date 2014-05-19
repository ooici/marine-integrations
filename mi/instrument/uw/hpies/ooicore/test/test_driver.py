"""
@package mi.instrument.uw.hpies.ooicore.test.test_driver
@file marine-integrations/mi/instrument/uw/hpies/ooicore/driver.py
@author Dan Mergens
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import RawDataParticle
from mi.core.instrument.instrument_driver import DriverProtocolState

__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

# import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger

log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin

# from interface.objects import AgentCommand
#
# from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
# from mi.core.instrument.instrument_driver import DriverAsyncEvent
# from mi.core.instrument.instrument_driver import DriverConnectionState
# from mi.core.instrument.instrument_driver import DriverProtocolState
#
# from ion.agents.instrument.instrument_agent import InstrumentAgentState
# from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.uw.hpies.ooicore.driver import InstrumentDriver, HEFDataParticle
from mi.instrument.uw.hpies.ooicore.driver import DataParticleType
from mi.instrument.uw.hpies.ooicore.driver import Command
from mi.instrument.uw.hpies.ooicore.driver import ProtocolState
from mi.instrument.uw.hpies.ooicore.driver import ProtocolEvent
from mi.instrument.uw.hpies.ooicore.driver import Capability
from mi.instrument.uw.hpies.ooicore.driver import Parameter
from mi.instrument.uw.hpies.ooicore.driver import Protocol
from mi.instrument.uw.hpies.ooicore.driver import Prompt
from mi.instrument.uw.hpies.ooicore.driver import NEWLINE

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.uw.hpies.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='VXVOO1',
    instrument_agent_name='uw_hpies_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
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

###
#   Driver constant definitions
###

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python, mixin classes provide capabilities which must be extended by    #
#  inherited classes, often using multiple inheritance.                       #
#                                                                             #
#  This class defines a configuration structure for testing and common assert #
#  methods for validating data particles.									  #
###############################################################################
class UtilMixin(DriverTestMixin):
    """
    Mixin class used for storing data particle constants and common data assertion methods.
    """
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    # SAMPLE_HEADER = "20140430T222632 #3__HE04 E a 0 985 2 3546330153 3113 3 3 3 1398896784*1bbb"
    SAMPLE_HEF = "20140501T173921 #3__DE 797 79380 192799 192803 192930*56a8"
    SAMPLE_MOTOR = "20140501T173728 #3__DM 11 24425*396b"
    SAMPLE_CAL = "20140430T230632 #3__DC 2 192655 192637 135611 80036 192554 192644*5c28"
    SAMPLE_IES = "20140501T175203 #5_AUX,1398880200,04,999999,999999,999999,999999,0010848,021697,022030,04000005.252,1B05,1398966715*c69e"
    # SAMPLE_HEADING = "20140430T195148 #3_hdg=  65.48 pitch=  -3.23 roll=  -2.68 temp=  30.20\r\n*1049"
    # SAMPLE_TIME = "20140430T195224 #2_TOD,1398887544,1398887537*01f5"
    # SAMPLE_SM = "20140430T222451 #3__SM 0 172 7*c5b2"
    # SAMPLE_Sm = "20140430T222451 #3__Sm 0 32*df9f"
    SAMPLE_HEF_INVALID = SAMPLE_HEF.replace('DE', 'DQ')
    SAMPLE_HEF_MISSING_CHECKSUM = SAMPLE_HEF[:-4]
    SAMPLE_HEF_WRONG_CHECKSUM = "{0}dead".format(SAMPLE_HEF_MISSING_CHECKSUM)

    _driver_capabilities = {

    }

    _driver_parameters = {
        # HEF parameters
        Parameter.SERIAL:
            {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: '', REQUIRED: False},
        Parameter.DEBUG_LEVEL:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 0, REQUIRED: False},
        Parameter.WSRUN_PINCH:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 120, REQUIRED: False},
        Parameter.NFC_CALIBRATE:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 60, REQUIRED: False},
        Parameter.CAL_HOLD:
            {TYPE: float, READONLY: True, DA: True, STARTUP: True, VALUE: 20, REQUIRED: False},
        Parameter.CAL_SKIP:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 10, REQUIRED: False},
        Parameter.NHC_COMPASS:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 122, REQUIRED: False},
        Parameter.COMPASS_SAMPLES:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 1, REQUIRED: False},
        Parameter.COMPASS_DELAY:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.INITIAL_COMPASS:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.INITIAL_COMPASS_DELAY:  # float or int??
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 1, REQUIRED: False},
        Parameter.MOTOR_SAMPLES:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.EF_SAMPLES:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.CAL_SAMPLES:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.CONSOLE_TIMEOUT:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 300, REQUIRED: False},
        Parameter.WSRUN_DELAY:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 0, REQUIRED: False},
        Parameter.MOTOR_DIR_NHOLD:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 0, REQUIRED: False},
        Parameter.MOTOR_DIR_INIT:
            {TYPE: str, READONLY: True, DA: True, STARTUP: True, VALUE: 'f', REQUIRED: False},
        Parameter.POWER_COMPASS_W_MOTOR:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: False, REQUIRED: False},
        Parameter.KEEP_AWAKE_W_MOTOR:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: True, REQUIRED: False},
        Parameter.MOTOR_TIMEOUTS_1A:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 200, REQUIRED: False},
        Parameter.MOTOR_TIMEOUTS_1B:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 200, REQUIRED: False},
        Parameter.MOTOR_TIMEOUTS_2A:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 200, REQUIRED: False},
        Parameter.MOTOR_TIMEOUTS_2B:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 200, REQUIRED: False},
        Parameter.RSN_CONFIG:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: True, REQUIRED: False},
        Parameter.INVERT_LED_DRIVERS:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: False, REQUIRED: False},
        Parameter.M1A_LED:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 1, REQUIRED: False},
        Parameter.M2A_LED:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 1, REQUIRED: False},
        # IES parameters
        Parameter.IES_TIME:
            {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: '', REQUIRED: False},
        Parameter.ECHO_SAMPLES:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 4, REQUIRED: False},
        Parameter.WATER_DEPTH:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 3000, REQUIRED: False},
        Parameter.ACOUSTIC_LOCKOUT:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 3.6, REQUIRED: False},
        Parameter.ACOUSTIC_OUTPUT:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 186, REQUIRED: False},
        Parameter.RELEASE_TIME:
            {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: 'Thu Dec 25 12:00:00 2014', REQUIRED: False},
        Parameter.COLLECT_TELEMETRY:
            {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: True, REQUIRED: False},
        Parameter.MISSION_STATEMENT:
            {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: 'No mission statement has been entered',
             REQUIRED: False},
        Parameter.PT_SAMPLES:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 1, REQUIRED: False},
        Parameter.TEMP_COEFF_U0:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 5.814289, REQUIRED: False},
        Parameter.TEMP_COEFF_Y1:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -3978.811, REQUIRED: False},
        Parameter.TEMP_COEFF_Y2:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -10771.79, REQUIRED: False},
        Parameter.TEMP_COEFF_Y3:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.0, REQUIRED: False},
        Parameter.PRES_COEFF_C1:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -30521.42, REQUIRED: False},
        Parameter.PRES_COEFF_C2:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -2027.363, REQUIRED: False},
        Parameter.PRES_COEFF_C3:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 95228.34, REQUIRED: False},
        Parameter.PRES_COEFF_D1:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.039810, REQUIRED: False},
        Parameter.PRES_COEFF_D2:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.0, REQUIRED: False},
        Parameter.PRES_COEFF_T1:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 30.10050, REQUIRED: False},
        Parameter.PRES_COEFF_T2:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.096742, REQUIRED: False},
        Parameter.PRES_COEFF_T3:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 56.45416, REQUIRED: False},
        Parameter.PRES_COEFF_T4:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 151.539900, REQUIRED: False},
        Parameter.PRES_COEFF_T5:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.0, REQUIRED: False},
        Parameter.BLILEY_0:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -0.575100, REQUIRED: False},
        Parameter.BLILEY_1:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -0.5282501, REQUIRED: False},
        Parameter.BLILEY_2:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: -0.013084390, REQUIRED: False},
        Parameter.BLILEY_3:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.00004622697, REQUIRED: False},
    }

    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is known to this driver and is correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
            self.assert_particle_raw(data_particle)
        else:
            log.error("Unknown particle detected: %s" % data_particle)
            self.assertFalse(True)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(Command())

        # Test capabilities for duplicates, then verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.SAMPLE_HEF)
        self.assert_chunker_sample(chunker, self.SAMPLE_CAL)
        self.assert_chunker_sample(chunker, self.SAMPLE_IES)
        self.assert_chunker_sample(chunker, self.SAMPLE_MOTOR)
        self.assert_chunker_sample_with_noise(chunker, self.SAMPLE_HEF)
        self.assert_chunker_fragmented_sample(chunker, self.SAMPLE_HEF)
        self.assert_chunker_combined_sample(chunker, self.SAMPLE_HEF)

    def test_corrupt_data_sample(self):
        for particle in (HEFDataParticle(self.SAMPLE_HEF_INVALID),
                         HEFDataParticle(self.SAMPLE_HEF_MISSING_CHECKSUM),
                         HEFDataParticle(self.SAMPLE_HEF_WRONG_CHECKSUM)):
            with self.assertRaises(SampleException):
                particle.generate()

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: [ProtocolEvent.DISCOVER],
            ProtocolState.COMMAND: [ProtocolEvent.GET,
                                    ProtocolEvent.SET,
                                    ProtocolEvent.START_AUTOSAMPLE,
                                    ProtocolEvent.START_DIRECT,
            ],
            ProtocolState.AUTOSAMPLE: [ProtocolEvent.STOP_AUTOSAMPLE,
            ],
            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT,
            ],
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        # put driver into autosample mode
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        self.assert_async_particle_generation(DataParticleType.MOTOR_CURRENT, self.assert_data_particle_sample,
                                              timeout=20)
        self.assert_async_particle_generation(DataParticleType.HPIES_STATUS, self.assert_data_particle_sample,
                                              timeout=30)
        self.assert_async_particle_generation(DataParticleType.ECHO_SOUNDING, self.assert_data_particle_sample,
                                              timeout=100)
        self.assert_async_particle_generation(DataParticleType.HORIZONTAL_FIELD, self.assert_data_particle_sample,
                                              timeout=110)
        # it can take 46 minutes for the first calibration status to occur - need to test in qual
        # self.assert_async_particle_generation(DataParticleType.CALIBRATION_STATUS, self.assert_data_particle_sample,
        #                                       timeout=30)
        # self.assert_async_particle_generation(DataParticleType.HPIES_STATUS, self.assert_data_particle_sample,
        #                                       timeout=30)

        # take driver out of autosample mode
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        # test that sample particle is not generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for no instrument data")
        self.clear_events()
        self.assert_async_particle_not_generated(DataParticleType.MOTOR_CURRENT, timeout=60)
        self.assert_async_particle_not_generated(DataParticleType.HPIES_STATUS, timeout=60)
        self.assert_async_particle_not_generated(DataParticleType.ECHO_SOUNDING, timeout=60)
        self.assert_async_particle_not_generated(DataParticleType.HORIZONTAL_FIELD, timeout=60)

        # put driver back in autosample mode
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.MOTOR_CURRENT, self.assert_data_particle_sample,
                                              timeout=20)

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver()

        # verify we cannot set readonly parameters
        read_only_params = [
            Parameter.SERIAL,
            Parameter.DEBUG_LEVEL,
            Parameter.CAL_HOLD,
            Parameter.CAL_SKIP,
            Parameter.INITIAL_COMPASS,
            Parameter.INITIAL_COMPASS_DELAY,
            Parameter.CONSOLE_TIMEOUT,
            Parameter.WSRUN_DELAY,
            Parameter.MOTOR_DIR_NHOLD,
            Parameter.MOTOR_DIR_INIT,
            Parameter.POWER_COMPASS_W_MOTOR,
            Parameter.KEEP_AWAKE_W_MOTOR,
            Parameter.RSN_CONFIG,
            Parameter.INVERT_LED_DRIVERS,
            Parameter.M1A_LED,
            Parameter.M2A_LED,
            Parameter.IES_TIME,
            Parameter.ECHO_SAMPLES,
            Parameter.WATER_DEPTH,
            Parameter.ACOUSTIC_LOCKOUT,
            Parameter.ACOUSTIC_OUTPUT,
            Parameter.RELEASE_TIME,
            Parameter.COLLECT_TELEMETRY,
            Parameter.MISSION_STATEMENT,
            Parameter.PT_SAMPLES,
            Parameter.TEMP_COEFF_U0,
            Parameter.TEMP_COEFF_Y1,
            Parameter.TEMP_COEFF_Y2,
            Parameter.TEMP_COEFF_Y3,
            Parameter.PRES_COEFF_C1,
            Parameter.PRES_COEFF_C2,
            Parameter.PRES_COEFF_C3,
            Parameter.PRES_COEFF_D1,
            Parameter.PRES_COEFF_D2,
            Parameter.PRES_COEFF_T1,
            Parameter.PRES_COEFF_T2,
            Parameter.PRES_COEFF_T3,
            Parameter.PRES_COEFF_T4,
            Parameter.PRES_COEFF_T5,
            Parameter.BLILEY_0,
            Parameter.BLILEY_1,
            Parameter.BLILEY_2,
            Parameter.BLILEY_3
        ]
        for param in read_only_params:
            self.assert_set_exception(param)

            # verify out-of-range exception on set - TODO - ranges have not yet been defined in IOS
            # self.assert_set_exception(Parameter.WSRUN_PINCH, -1)
            # self.assert_set_exception(Parameter.NFC_CALIBRATE, -1)
            # self.assert_set_exception(Parameter.NHC_COMPASS, -1)
            # self.assert_set_exception(Parameter.COMPASS_SAMPLES, -1)
            # self.assert_set_exception(Parameter.COMPASS_DELAY, -1)
            # self.assert_set_exception(Parameter.MOTOR_SAMPLES, -1)
            # self.assert_set_exception(Parameter.EF_SAMPLES, -1)
            # self.assert_set_exception(Parameter.CAL_SAMPLES, -1)
            # self.assert_set_exception(Parameter.MOTOR_TIMEOUTS_1A, -1)
            # self.assert_set_exception(Parameter.MOTOR_TIMEOUTS_1B, -1)
            # self.assert_set_exception(Parameter.MOTOR_TIMEOUTS_2A, -1)
            # self.assert_set_exception(Parameter.MOTOR_TIMEOUTS_2B, -1)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical
        instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()

    def test_autosample(self):
        """
        start and stop autosample and verify data particle
        """

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
