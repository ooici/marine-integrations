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
__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import time
import unittest

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.log import get_logger


log = get_logger()

from mi.idk.unit_test import \
    InstrumentDriverTestCase, ParameterTestConfigKey, AgentCapabilityType, InstrumentDriverUnitTestCase, \
    InstrumentDriverIntegrationTestCase, InstrumentDriverQualificationTestCase, DriverTestMixin

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.instrument_driver import DriverProtocolState, ResourceAgentState, DriverConfigKey
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import SampleException, InstrumentCommandException

from mi.instrument.uw.hpies.ooicore.driver import \
    InstrumentDriver, HEFDataParticle, ParameterConstraints, HEFMotorCurrentParticleKey, HEFDataParticleKey, \
    CalStatusParticleKey, HEFStatusParticleKey, IESDataParticleKey, DataHeaderParticleKey, hef_command
from mi.instrument.uw.hpies.ooicore.driver import \
    DataParticleType, Command, ProtocolState, ProtocolEvent, Capability, Parameter, Protocol, Prompt, \
    NEWLINE

# ##
# Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.uw.hpies.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='VXVOO1',
    instrument_agent_name='uw_hpies_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={DriverConfigKey.PARAMETERS: {
        Parameter.DEBUG_LEVEL: 0,
        Parameter.WSRUN_PINCH: 120,
        Parameter.NFC_CALIBRATE: 60,
        Parameter.CAL_HOLD: 19.97,
        Parameter.NHC_COMPASS: 122,
        Parameter.COMPASS_SAMPLES: 1,
        Parameter.COMPASS_DELAY: 10,
        Parameter.MOTOR_SAMPLES: 10,
        Parameter.EF_SAMPLES: 10,
        Parameter.CAL_SAMPLES: 10,
        Parameter.CONSOLE_TIMEOUT: 300,
        Parameter.WSRUN_DELAY: 0,
        Parameter.MOTOR_DIR_NHOLD: 0,
        Parameter.MOTOR_DIR_INIT: 'f',
        Parameter.POWER_COMPASS_W_MOTOR: False,
        Parameter.KEEP_AWAKE_W_MOTOR: True,
        Parameter.MOTOR_TIMEOUTS_1A: 200,
        Parameter.MOTOR_TIMEOUTS_1B: 200,
        Parameter.MOTOR_TIMEOUTS_2A: 200,
        Parameter.MOTOR_TIMEOUTS_2B: 200,
        Parameter.RSN_CONFIG: True,
        Parameter.INVERT_LED_DRIVERS: False,
        Parameter.M1A_LED: 1,
        Parameter.M2A_LED: 3,
    }
    }
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
    # __metaclass__ = get_logging_metaclass(log_level='info')

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

    # Sample raw data particles
    SAMPLE_HEF_HEADER = "#3__HE05 E a 0 985 2 3546330153 3113 3 3 3 1398896784*1bbc"
    SAMPLE_HEF = '#3__DE 1159 396997 397259 397512 397260 396951 397701*d595'
    SAMPLE_MOTOR_HEADER = '#3__HE05 f a 0 382 0 3546329882 17917 3 3 3 1398896422*d6fe'
    SAMPLE_MOTOR = '#3__DM 11 24425*396b'
    SAMPLE_CAL_HEADER = '#3__HE05 E a 0 983 130 3546345513 13126 3 3 3 1398912144*f7aa'
    SAMPLE_CAL = '#3__DC 2 192655 192637 135611 80036 192554 192644*5c28'
    SAMPLE_HPIES_STATUS = \
        '#3__s1 -748633661 31 23 0 C:\\DATA\\12345.000 OK*3e90' + NEWLINE + \
        '#3__s2 10 0 0 984001 0 0 0*ac87' + NEWLINE + \
        '#3__s3 0 0 0 0 0 0 1*35b7'
    SAMPLE_IES = '#5_AUX,1398880200,04,999999,999999,999999,999999,0010848,021697,022030,' + \
                 '04000005.252,1B05,1398966715*c69e'
    # SAMPLE_HEADING = "#3_hdg=  65.48 pitch=  -3.23 roll=  -2.68 temp=  30.20\r\n*1049"
    # SAMPLE_SM = "#3__SM 0 172 7*c5b2"
    # SAMPLE_Sm = "#3__Sm 0 32*df9f"
    SAMPLE_IES_STATUS = \
        '#5_T:388559 999999 999999 999999 999999 999999 999999 999999 999999 ' + \
        '999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 ' + \
        r'999999 999999 999999 999999 999999 999999 \r\n*cb7a' + NEWLINE + \
        '#5_P:388559 10932 23370  10935 23397  10934 23422  10934 23446  10933 ' + \
        r'23472  10932 23492  \r\n*9c3e' + NEWLINE + \
        '#5_F:388559 33228500 172170704  33228496 172170928  33228492 172171120  ' + \
        r'33228488 172171312  33228484 172171504  33228480 172171664  \r\n*e505' + NEWLINE + \
        r'#5_E:388559 2.29 0.01 0.00 14.00 6.93 5.05 23.83 0.0000 10935 1623 33228.480 172171.656 0.109 \r\n*1605'
    SAMPLE_TIMESTAMP = \
        '#2_TOD,1398883295,1398883288*0059'

    valid_samples = [
        SAMPLE_HEF_HEADER,
        SAMPLE_HEF,
        SAMPLE_MOTOR_HEADER,
        SAMPLE_MOTOR,
        SAMPLE_CAL_HEADER,
        SAMPLE_CAL,
        SAMPLE_HPIES_STATUS,
        SAMPLE_IES,
        SAMPLE_IES_STATUS,
        SAMPLE_TIMESTAMP
    ]

    # Sample raw data particles - invalid
    SAMPLE_HEF_INVALID = SAMPLE_HEF.replace('DE', 'DQ')
    SAMPLE_HEF_MISSING_CHECKSUM = SAMPLE_HEF[:-4]
    SAMPLE_HEF_WRONG_CHECKSUM = '{0}dead'.format(SAMPLE_HEF_MISSING_CHECKSUM)

    _driver_capabilities = {
        Capability.START_AUTOSAMPLE: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE: {STATES: [ProtocolState.AUTOSAMPLE]}
    }

    _driver_parameters = {
        # HEF parameters
        Parameter.SERIAL:
            {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: '', REQUIRED: False},
        Parameter.DEBUG_LEVEL:
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 0, REQUIRED: False},
        Parameter.WSRUN_PINCH:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 120, REQUIRED: False},
        Parameter.NFC_CALIBRATE:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 60, REQUIRED: False},
        Parameter.CAL_HOLD:
            {TYPE: float, READONLY: True, DA: True, STARTUP: True, VALUE: 19.97, REQUIRED: False},
        Parameter.CAL_SKIP:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 19.97, REQUIRED: False},
        Parameter.NHC_COMPASS:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 122, REQUIRED: False},
        Parameter.COMPASS_SAMPLES:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 1, REQUIRED: False},
        Parameter.COMPASS_DELAY:
            {TYPE: int, READONLY: False, DA: True, STARTUP: True, VALUE: 10, REQUIRED: False},
        Parameter.INITIAL_COMPASS:
            {TYPE: int, READONLY: True, DA: False, STARTUP: False, VALUE: 10, REQUIRED: False},
        Parameter.INITIAL_COMPASS_DELAY:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.5, REQUIRED: False},
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
            {TYPE: int, READONLY: True, DA: True, STARTUP: True, VALUE: 3, REQUIRED: False},
        # IES parameters
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
        Parameter.TEMP_OFFSET:
            {TYPE: float, READONLY: True, DA: False, STARTUP: False, VALUE: 0.0, REQUIRED: False},
        Parameter.PRES_OFFSET:
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

    _hef_sample = {
        HEFDataParticleKey.DATA_VALID: {TYPE: bool, VALUE: True, REQUIRED: True},
        HEFDataParticleKey.INDEX: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_1: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_2: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_3: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_4: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_5: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFDataParticleKey.CHANNEL_6: {TYPE: int, VALUE: 0, REQUIRED: True},
    }

    def assert_hef_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(HEFDataParticleKey, self._hef_sample)
        self.assert_data_particle_header(particle, DataParticleType.HORIZONTAL_FIELD)
        self.assert_data_particle_parameters(particle, self._hef_sample, verify_values)

    _header_sample = {
        DataHeaderParticleKey.DATA_VALID: {TYPE: bool, VALUE: True, REQUIRED: True},
        DataHeaderParticleKey.VERSION: {TYPE: int, VALUE: 0, REQUIRED: True},
        DataHeaderParticleKey.TYPE: {TYPE: unicode, VALUE: 'f', REQUIRED: True},
        DataHeaderParticleKey.DESTINATION: {TYPE: unicode, VALUE: 'a', REQUIRED: True},
        DataHeaderParticleKey.INDEX_START: {TYPE: int, VALUE: 0, REQUIRED: True},
        DataHeaderParticleKey.INDEX_STOP: {TYPE: int, VALUE: 382, REQUIRED: True},
        DataHeaderParticleKey.HCNO: {TYPE: int, VALUE: 0, REQUIRED: True},
        DataHeaderParticleKey.TIME: {TYPE: int, VALUE: 3546329882, REQUIRED: True},
        DataHeaderParticleKey.TICKS: {TYPE: int, VALUE: 17917, REQUIRED: True},
        DataHeaderParticleKey.MOTOR_SAMPLES: {TYPE: int, VALUE: 3, REQUIRED: True},
        DataHeaderParticleKey.EF_SAMPLES: {TYPE: int, VALUE: 3, REQUIRED: True},
        DataHeaderParticleKey.CAL_SAMPLES: {TYPE: int, VALUE: 3, REQUIRED: True},
        DataHeaderParticleKey.STM_TIME: {TYPE: int, VALUE: 1398899184, REQUIRED: True},
    }

    def assert_data_header_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(DataHeaderParticleKey, self._header_sample)
        self.assert_data_particle_header(particle, DataParticleType.HPIES_DATA_HEADER)
        self.assert_data_particle_parameters(particle, self._header_sample, verify_values)

    _motor_current_sample = {
        HEFMotorCurrentParticleKey.DATA_VALID: {TYPE: bool, VALUE: True, REQUIRED: True},
        HEFMotorCurrentParticleKey.INDEX: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFMotorCurrentParticleKey.CURRENT: {TYPE: int, VALUE: 0, REQUIRED: True},
    }

    def assert_motor_current_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(HEFMotorCurrentParticleKey, self._motor_current_sample)
        self.assert_data_particle_header(particle, DataParticleType.MOTOR_CURRENT)
        self.assert_data_particle_parameters(particle, self._motor_current_sample, verify_values)

    _calibration_sample = {
        CalStatusParticleKey.DATA_VALID: {TYPE: bool, VALUE: False, REQUIRED: True},
        CalStatusParticleKey.INDEX: {TYPE: int, VALUE: 0, REQUIRED: True},
        CalStatusParticleKey.E1C: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        CalStatusParticleKey.E1A: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        CalStatusParticleKey.E1B: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        CalStatusParticleKey.E2C: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        CalStatusParticleKey.E2A: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        CalStatusParticleKey.E2B: {TYPE: float, VALUE: 0.0, REQUIRED: True},
    }

    def assert_cal_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(CalStatusParticleKey, self._calibration_sample)
        self.assert_data_particle_header(particle, DataParticleType.CALIBRATION_STATUS)
        self.assert_data_particle_parameters(particle, self._calibration_sample, verify_values)

    _status_sample = {
        HEFStatusParticleKey.DATA_VALID: {TYPE: bool, VALUE: False, REQUIRED: True},
        HEFStatusParticleKey.UNIX_TIME: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.HCNO: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEFStatusParticleKey.HCNO_LAST_CAL: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEFStatusParticleKey.HCNO_LAST_COMP: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEFStatusParticleKey.OFILE: {TYPE: unicode, VALUE: 'C:\\filename.0', REQUIRED: True},
        HEFStatusParticleKey.IFOK: {TYPE: unicode, VALUE: 'OK', REQUIRED: True},
        HEFStatusParticleKey.N_COMPASS_WRITES: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEFStatusParticleKey.N_COMPASS_FAIL_WRITES: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.MOTOR_POWER_UPS: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.N_SERVICE_LOOPS: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEFStatusParticleKey.SERIAL_PORT_ERRORS: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.COMPASS_PORT_ERRORS: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.COMPASS_PORT_CLOSED_COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.IRQ2_COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.SPURIOUS_COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.SPSR_BITS56_COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.PIT_ZERO_COUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.ADC_BUFFER_OVERFLOWS: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.MAX7317_QUEUE_OVERFLOWS: {TYPE: int, VALUE: 0, REQUIRED: True},
        HEFStatusParticleKey.PINCH_TIMING_ERRORS: {TYPE: int, VALUE: 0, REQUIRED: True},
    }

    def assert_status_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(HEFStatusParticleKey, self._status_sample)
        self.assert_data_particle_header(particle, DataParticleType.HPIES_STATUS)
        self.assert_data_particle_parameters(particle, self._status_sample, verify_values)

    _echo_sample = {
        IESDataParticleKey.DATA_VALID: {TYPE: bool, VALUE: True, REQUIRED: True},
        IESDataParticleKey.IES_TIMESTAMP: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.TRAVEL_TIMES: {TYPE: int, VALUE: 4, REQUIRED: True},
        IESDataParticleKey.TRAVEL_TIME_1: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.TRAVEL_TIME_2: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.TRAVEL_TIME_3: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.TRAVEL_TIME_4: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.PRESSURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.TEMPERATURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.BLILEY_TEMPERATURE: {TYPE: int, VALUE: 0, REQUIRED: True},
        IESDataParticleKey.BLILEY_FREQUENCY: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        IESDataParticleKey.STM_TIMESTAMP: {TYPE: int, VALUE: 0, REQUIRED: True},
    }

    def assert_echo_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(IESDataParticleKey, self._echo_sample)
        self.assert_data_particle_header(particle, DataParticleType.ECHO_SOUNDING)
        self.assert_data_particle_parameters(particle, self._echo_sample, verify_values)


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

    def test_driver_schema(self):
        """
        Get the driver schema and verify it is configured properly.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
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

        for sample in self.valid_samples:
            self.assert_chunker_sample(chunker, sample)
            self.assert_chunker_sample_with_noise(chunker, sample)
            self.assert_chunker_fragmented_sample(chunker, sample)
            self.assert_chunker_combined_sample(chunker, sample)

    def test_corrupt_data_sample(self):
        for sample in [self.SAMPLE_HEF_INVALID, self.SAMPLE_HEF_MISSING_CHECKSUM]:
            with self.assertRaises(SampleException):
                HEFDataParticle(sample).generate()

    def test_wrong_checksum(self):
        good_particle = HEFDataParticle(self.SAMPLE_HEF)
        bad_particle = HEFDataParticle(self.SAMPLE_HEF_WRONG_CHECKSUM)
        good_particle.generate_dict()
        bad_particle.generate_dict()

        if good_particle.contents[DataParticleKey.QUALITY_FLAG] is DataParticleValue.CHECKSUM_FAILED:
            self.fail('HEF data particle validity flag set incorrectly - should be set to true')
        if bad_particle.contents[DataParticleKey.QUALITY_FLAG] is not DataParticleValue.CHECKSUM_FAILED:
            self.fail('HEF data particle validity flag set incorrectly - should be set to false')

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
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, UtilMixin):
    def assert_async_particle_not_generated(self, particle_list, timeout=10):
        end_time = time.time() + timeout

        while end_time > time.time():
            for particle_type in particle_list:
                if len(self.get_sample_events(particle_type)) > 0:
                    self.fail(
                        "assert_async_particle_not_generated: a particle of type %s was published" % particle_type)
            time.sleep(1.0)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        # put driver into autosample mode
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        self.assert_async_particle_generation(
            DataParticleType.HPIES_DATA_HEADER, self.assert_data_header_particle, timeout=20)
        self.assert_async_particle_generation(
            DataParticleType.MOTOR_CURRENT, self.assert_motor_current_particle, timeout=5)
        self.assert_async_particle_generation(
            DataParticleType.HPIES_STATUS, self.assert_status_particle, timeout=120)
        self.assert_async_particle_generation(
            DataParticleType.HORIZONTAL_FIELD, self.assert_hef_particle, timeout=140)

        self.assert_async_particle_generation(
            DataParticleType.ECHO_SOUNDING, self.assert_echo_particle, timeout=600)

        # take driver out of autosample mode
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        # test that sample particle is not generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for no instrument data")
        self.clear_events()
        particle_list = (
            DataParticleType.CALIBRATION_STATUS,
            DataParticleType.ECHO_SOUNDING,
            DataParticleType.HORIZONTAL_FIELD,
            DataParticleType.HPIES_DATA_HEADER,
            DataParticleType.HPIES_STATUS,
            DataParticleType.TIMESTAMP,
            DataParticleType.MOTOR_CURRENT,
        )
        self.assert_async_particle_not_generated(particle_list, timeout=120)

        # put driver back in autosample mode
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(
            DataParticleType.HPIES_DATA_HEADER, self.assert_data_header_particle, timeout=60)

    @unittest.skip('run just before XX:X0 UTC')
    def test_autosample_echo_particle_generation(self):
        """
        Test echo sounding particle generation - occurs once every 10 minutes, on the 10th minute
        """
        # TODO - set clock to just before 10 minute interval so calibration will occur quickly
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        self.assert_async_particle_generation(
            DataParticleType.ECHO_SOUNDING, self.assert_echo_particle, timeout=600)
        self.assert_async_particle_generation(
            DataParticleType.HPIES_STATUS, self.assert_data_particle_sample, timeout=30)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    @unittest.skip('run just before 23:52 UTC')
    def test_autosample_cal_status_particle_generation(self):
        """
        Test calibration status particle generation - occurs daily at 23:52
        """
        # TODO - set clock to just before 23:52 so cal status particle will be generated quickly
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        self.assert_async_particle_not_generated(DataParticleType.CALIBRATION_STATUS, timeout=60)
        self.assert_async_particle_not_generated(DataParticleType.HPIES_STATUS, timeout=5)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver()

        for key in self._driver_parameters:
            if self._driver_parameters[key][self.READONLY]:
                self.assert_set_exception(key)

    def test_out_of_range(self):
        self.assert_initialize_driver()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.dict()
        for key in constraints:
            _, minimum, maximum = constraints[key]
            self.assert_set_exception(parameters[key], minimum - 1)
            self.assert_set_exception(parameters[key], maximum + 1)
            self.assert_set_exception(parameters[key], 'expects int, not string!!')

    def test_invalid_parameter(self):
        self.assert_initialize_driver()
        self.assert_set_exception('BOGUS', 'bogus parameter can not be set')

    def test_invalid_command(self):
        self.assert_initialize_driver()
        self.assert_driver_command_exception('BOGUS_COMMAND', exception_class=InstrumentCommandException)

        # check improper command - stop autosample from command (can only stop from autosample)
        self.assert_driver_command_exception(ProtocolEvent.STOP_AUTOSAMPLE, exception_class=InstrumentCommandException)

    def test_incomplete_config(self):
        # TODO - only required it is determined that some startup parameters are required
        # startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        # old_value = startup_params[Parameter.CAL_SAMPLES]  # place a required parameter here
        # try:
        #     del (startup_params[Parameter.CAL_SAMPLES])
        #     self.init_driver_process_client()
        #     self.assert_initialize_driver()
        #     self.assert_driver_command(Capability.START_AUTOSAMPLE)
        #     self.assertTrue(False, msg='Failed to raise exception on missing parameter')
        # except Exception as e:
        #     self.assertTrue(self._driver_exception_match(e, InstrumentProtocolException))
        # finally:
        #     startup_params[Parameter.CAL_SAMPLES] = old_value
        pass


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_discover(self):
        """
        Overrides base class - instrument only goes into command mode, not autosample.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

        # Now put the instrument in streaming and reset the driver again.
        self.assert_start_autosample()
        self.assert_reset()

        # When the driver reconnects it should be in command (we force a mission stop during discover)
        self.assert_discover(ResourceAgentState.COMMAND)
        self.assert_reset()

    def test_direct_access_telnet_closed(self):
        """
        Test that we can properly handle the situation when a direct access
        session is launched, the telnet is closed, then direct access is stopped.
        Overridden so to allow for degraded internet connection speed.
        """
        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, DriverProtocolState.COMMAND, 100)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical
        instrument. (telnet mode)
        """
        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        # set direct access parameters (these should be reset upon return from direct access)
        direct_access_parameters = {
            Parameter.DEBUG_LEVEL: 1,
            Parameter.WSRUN_PINCH: 60,
            Parameter.NFC_CALIBRATE: 30,
            Parameter.CAL_HOLD: 39.94,
            Parameter.NHC_COMPASS: 122,
            Parameter.COMPASS_SAMPLES: 2,
            Parameter.COMPASS_DELAY: 20,
            Parameter.MOTOR_SAMPLES: 20,
            Parameter.EF_SAMPLES: 20,
            Parameter.CAL_SAMPLES: 20,
            Parameter.CONSOLE_TIMEOUT: 400,
            Parameter.WSRUN_DELAY: 1,
            Parameter.MOTOR_DIR_NHOLD: 1,
            Parameter.MOTOR_DIR_INIT: 'r',
            # Parameter.POWER_COMPASS_W_MOTOR: 1,
            Parameter.KEEP_AWAKE_W_MOTOR: 1,
            Parameter.MOTOR_TIMEOUTS_1A: 30,
            Parameter.MOTOR_TIMEOUTS_1B: 30,
            Parameter.MOTOR_TIMEOUTS_2A: 30,
            Parameter.MOTOR_TIMEOUTS_2B: 30,
            Parameter.RSN_CONFIG: 0,
            Parameter.INVERT_LED_DRIVERS: 1,
            Parameter.M1A_LED: 3,
            Parameter.M2A_LED: 1,
        }

        for key in direct_access_parameters.keys():
            # command = '#3_%s %s' % (key, direct_access_parameters[key])
            command = hef_command(key, direct_access_parameters[key])
            log.debug('djm - command: %s', command)
            self.tcp_client.send_data(command)
            self.tcp_client.expect_regex(' = ')
            log.debug('djm - key: %s', key)
            log.debug('djm - value: %s', self._driver_parameters[key][self.VALUE])

        # without saving the parameters, the values will be reset on reboot (which is part of wakeup)
        self.tcp_client.send_data('#3_params save')  # read-write, direct access
        self.tcp_client.expect_regex('params save')

        self.assert_direct_access_stop_telnet()
        self.assert_enter_command_mode()

        # verify that all direct access parameters are restored
        for key in self._driver_parameters.keys():
            # verify access of parameters - default values
            if self._driver_parameters[key][self.DA]:
                log.debug('checking direct access parameter: %s', key)
                self.assert_get_parameter(key, self._driver_parameters[key][self.VALUE])

    def test_direct_access_telnet_timeout(self):
        """
        Verify that direct access times out as expected and the agent transitions back to command mode.
        """
        self.assert_enter_command_mode()

        #self.assert_direct_access_start_telnet(timeout=30)
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=30)
        self.assertTrue(self.tcp_client)

        #self.assert_state_change(ResourceAgentState.IDLE, ProtocolState.COMMAND, 180)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 180)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

        # verify we can set read/write parameters
        constraints = ParameterConstraints.dict()
        parameters = Parameter.dict()
        for key in constraints:
            if self._driver_parameters[parameters[key]][self.READONLY]:
                continue
            _, _, maximum = constraints[key]
            self.assert_set_parameter(parameters[key], maximum)

    def test_startup_parameters(self):
        """
        Verify that all startup parameters are set to expected defaults on startup.
        """
        self.assert_enter_command_mode()

        for key in self._driver_parameters.keys():
            if self._driver_parameters[key][self.STARTUP]:
                self.assert_get_parameter(key, self._driver_parameters[key][self.VALUE])

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.GET,
                ProtocolEvent.SET,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            ProtocolEvent.STOP_AUTOSAMPLE,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)
