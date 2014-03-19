"""
@package mi.instrument.noaa.iris.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/iris/ooicore/driver.py
@author David Everett
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import time

import ntplib
from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger

log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.chunker import StringChunker

from mi.instrument.noaa.iris.ooicore.driver import InstrumentDriver
from mi.instrument.noaa.iris.ooicore.driver import DataParticleType
from mi.instrument.noaa.iris.ooicore.driver import IRISDataParticleKey
from mi.instrument.noaa.iris.ooicore.driver import IRISDataParticle
from mi.instrument.noaa.iris.ooicore.driver import IRISCommandResponse
from mi.instrument.noaa.iris.ooicore.driver import IRISStatus01Particle
from mi.instrument.noaa.iris.ooicore.driver import IRISStatus02Particle
from mi.instrument.noaa.iris.ooicore.driver import InstrumentCommand
from mi.instrument.noaa.iris.ooicore.driver import ProtocolState
from mi.instrument.noaa.iris.ooicore.driver import ProtocolEvent
from mi.instrument.noaa.iris.ooicore.driver import Capability
from mi.instrument.noaa.iris.ooicore.driver import Parameter
from mi.instrument.noaa.iris.ooicore.driver import Protocol
from mi.instrument.noaa.iris.ooicore.driver import Prompt
from mi.instrument.noaa.iris.ooicore.driver import NEWLINE
from mi.instrument.noaa.iris.ooicore.driver import IRIS_COMMAND_STRING
from mi.instrument.noaa.iris.ooicore.driver import IRIS_STRING
from mi.instrument.noaa.iris.ooicore.driver import IRIS_DATA_ON
from mi.instrument.noaa.iris.ooicore.driver import IRIS_DATA_OFF
from mi.instrument.noaa.iris.ooicore.driver import IRIS_DUMP_01
from mi.instrument.noaa.iris.ooicore.driver import IRIS_DUMP_02

from mi.core.exceptions import SampleException
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import Conflict

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.iris.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_iris_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
)

GO_ACTIVE_TIMEOUT = 180

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

INVALID_SAMPLE = "This is an invalid sample; it had better cause an exception." + NEWLINE
VALID_SAMPLE_01 = "IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
VALID_SAMPLE_02 = "IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642" + NEWLINE

DATA_ON_COMMAND_RESPONSE = "IRIS,2013/05/29 00:23:34," + IRIS_COMMAND_STRING + IRIS_DATA_ON + NEWLINE
DATA_OFF_COMMAND_RESPONSE = "IRIS,2013/05/29 00:23:34," + IRIS_COMMAND_STRING + IRIS_DATA_OFF + NEWLINE
DUMP_01_COMMAND_RESPONSE = "IRIS,2013/05/29 00:22:57," + IRIS_COMMAND_STRING + IRIS_DUMP_01 + NEWLINE
DUMP_02_COMMAND_RESPONSE = "IRIS,2013/05/29 00:23:34," + IRIS_COMMAND_STRING + IRIS_DUMP_02 + NEWLINE

BOTPT_FIREHOSE_01 = "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
BOTPT_FIREHOSE_01 += "IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
BOTPT_FIREHOSE_01 += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE

SIGNON_STATUS = \
    "IRIS,2013/06/12 18:03:44,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N8642 ID01" + NEWLINE

DUMP_01_STATUS = \
    "IRIS,2013/06/19 21:13:00,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Vbias= 0.0000 0.0000 0.0000 0.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Vgain= 0.0000 0.0000 0.0000 0.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Vmin:  -2.50  -2.50   2.50   2.50" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Vmax:   2.50   2.50   2.50   2.50" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00" + NEWLINE + \
    "IRIS,2013/06/12 18:03:44,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-" + NEWLINE

DUMP_02_STATUS = \
    "IRIS,2013/06/12 23:55:09,*01: TBias: 8.85" + NEWLINE + \
    "IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0" + NEWLINE + \
    "IRIS,2013/06/12 23:55:09,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: ADCDelay:  310" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: PCA Model: 90009-01" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Firmware Version: 5.2 Rev N" + NEWLINE + \
    "LILY,2013/06/12 18:04:01,-330.000,-247.647,290.73, 24.50,11.88,N9656" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Output Mode: Degrees" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Calibration performed in Degrees" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Control: Off" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Using RS232" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Real Time Clock: Not Installed" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Use RTC for Timing: No" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: External Flash Capacity: 0 Bytes(Not Installed)" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Relay Thresholds:" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01:   Xpositive= 1.0000   Xnegative=-1.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01:   Ypositive= 1.0000   Ynegative=-1.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Relay Hysteresis:" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01:   Hysteresis= 0.0000" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Calibration method: Dynamic" + NEWLINE + \
    "IRIS,2013/06/12 18:04:01,*01: Positive Limit=26.25   Negative Limit=-26.25" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: Calibration Points:025  X: Disabled  Y: Disabled" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: Biaxial Sensor Type (0)" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: ADC: 12-bit (internal)" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: DAC Output Scale Factor: 0.10 Volts/Degree" + NEWLINE + \
    "HEAT,2013/06/12 18:04:02,-001,0001,0024" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: Total Sample Storage Capacity: 372" + NEWLINE + \
    "IRIS,2013/06/12 18:04:02,*01: BAE Scale Factor:  2.88388 (arcseconds/bit)" + NEWLINE

DUMP_01_STATUS_RESP = NEWLINE.join([line for line in DUMP_01_STATUS.split(NEWLINE) if line.startswith(IRIS_STRING)])
DUMP_02_STATUS_RESP = NEWLINE.join([line for line in DUMP_02_STATUS.split(NEWLINE) if line.startswith(IRIS_STRING)])


###############################################################################
#                           DRIVER TEST MIXIN                                 #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                            #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class IRISTestMixinSub(DriverTestMixin):
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    _driver_parameters = {
        # Parameters defined in the IOS
    }

    _sample_parameters_01 = {
        IRISDataParticleKey.TIME: {TYPE: float, VALUE: 3578801134.0, REQUIRED: True},
        IRISDataParticleKey.X_TILT: {TYPE: float, VALUE: -0.0882, REQUIRED: True},
        IRISDataParticleKey.Y_TILT: {TYPE: float, VALUE: -0.7524, REQUIRED: True},
        IRISDataParticleKey.TEMP: {TYPE: float, VALUE: 28.45, REQUIRED: True},
        IRISDataParticleKey.SN: {TYPE: unicode, VALUE: 'N8642', REQUIRED: True}
    }

    _sample_parameters_02 = {
        IRISDataParticleKey.TIME: {TYPE: float, VALUE: 3578801136.0, REQUIRED: True},
        IRISDataParticleKey.X_TILT: {TYPE: float, VALUE: -0.0885, REQUIRED: True},
        IRISDataParticleKey.Y_TILT: {TYPE: float, VALUE: -0.7517, REQUIRED: True},
        IRISDataParticleKey.TEMP: {TYPE: float, VALUE: 28.49, REQUIRED: True},
        IRISDataParticleKey.SN: {TYPE: unicode, VALUE: 'N8642', REQUIRED: True}
    }

    def assert_particle_sample_01(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  IRISDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(IRISDataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.IRIS_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  IRISDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(IRISDataParticleKey, self._sample_parameters_02)
        self.assert_data_particle_header(data_particle, DataParticleType.IRIS_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_02, verify_values)

    def assert_particle_sample_firehose(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  IRISDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(IRISDataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.IRIS_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_status(self, status_particle, verify_values=False):
        pass


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
# noinspection PyProtectedMember
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, IRISTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def _send_port_agent_packet(self, driver, data_item, ts):
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data_item)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, VALID_SAMPLE_01)
        self.assert_chunker_sample(chunker, DUMP_01_STATUS)
        self.assert_chunker_sample(chunker, DUMP_02_STATUS)
        self.assert_chunker_sample(chunker, DUMP_01_COMMAND_RESPONSE)
        self.assert_chunker_sample(chunker, DUMP_02_COMMAND_RESPONSE)

    def test_connect(self):
        """
        Verify driver transitions correctly and connects
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

    def test_data_build_parsed_values(self):
        """
        Verify that the BOTPT IRIS driver build_parsed_values method
        raises SampleException when an invalid sample is encountered
        and that it returns a result when a valid sample is encountered
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        sample_exception = False
        try:
            raw_data = INVALID_SAMPLE
            test_particle = IRISDataParticle(raw_data)
            test_particle._build_parsed_values()

        except SampleException as e:
            log.debug('SampleException caught: %s.', e)
            sample_exception = True

        finally:
            self.assertTrue(sample_exception)

        sample_exception = False
        result = None
        try:
            raw_data = VALID_SAMPLE_01
            test_particle = IRISDataParticle(raw_data)
            result = test_particle._build_parsed_values()

        except SampleException as e:
            log.error('SampleException caught: %s.', e)
            sample_exception = True

        finally:
            # Assert that the sampleException was not called.  Also assert that
            # the result is a list.  Not getting into the details of the result
            # here; that's done elsewhere.
            self.assertFalse(sample_exception)
            self.assertTrue(isinstance(result, list))

    def test_check_command_response(self):
        """
        Verify that check_data_on_off_response raises a SampleException given an
        invalid response, and that it returns True given a valid response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        items = [
            (INVALID_SAMPLE, IRIS_DATA_ON, False),
            (DATA_ON_COMMAND_RESPONSE, IRIS_DATA_ON, True),
            (DATA_OFF_COMMAND_RESPONSE, IRIS_DATA_OFF, True),
            (DUMP_01_COMMAND_RESPONSE, IRIS_DUMP_01, True),
            (DUMP_02_COMMAND_RESPONSE, IRIS_DUMP_02, True),
            (DUMP_02_COMMAND_RESPONSE, None, True),
        ]

        for data, expected_response, is_valid in items:
            sample_exception = False
            return_value = False
            try:
                response = IRISCommandResponse(data)
                return_value = response.check_command_response(expected_response)
            except SampleException:
                log.debug('SampleException caught in test_check_command_response')
                sample_exception = True
            finally:
                if is_valid:
                    self.assertFalse(sample_exception)
                    self.assertTrue(return_value)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)

    def test_firehose(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        Verify that the BOTPT IRIS driver publishes a particle correctly when the IRIS packet is
        embedded in the stream of other BOTPT sensor output.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)

    def test_data_on_response(self):
        """
        Verify that the driver correctly parses the DATA_ON response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())
        self._send_port_agent_packet(driver, DATA_ON_COMMAND_RESPONSE, ts)
        self.assertTrue(driver._protocol._get_response(expected_prompt=IRIS_DATA_ON))

    def test_data_on_response_with_data(self):
        """
        Verify that the driver correctly parses the DATA_ON response works
        when a data packet is right in front of it
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())
        # Create a data packet and push to the driver
        log.debug("VALID SAMPLE : %s", VALID_SAMPLE_01)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, VALID_SAMPLE_01, ts)

        log.debug("DATA ON command response: %s", DATA_ON_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DATA_ON_COMMAND_RESPONSE, ts)
        self.assertTrue(driver._protocol._get_response(expected_prompt=IRIS_DATA_ON))

    def test_status_01(self):
        """
        Verify that the driver correctly parses the DUMP-SETTINGS response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DUMP_01_STATUS: %s", DUMP_01_STATUS)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_01_STATUS, ts)

    def test_status_02(self):
        """
        Verify that the driver correctly parses the DUMP2 response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DUMP_02_STATUS: %s", DUMP_02_STATUS)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_02_STATUS, ts)

    def test_data_off_response(self):
        """
        Verify that the driver correctly parses the DATA_OFF response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DATA OFF command response: %s", DATA_OFF_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DATA_OFF_COMMAND_RESPONSE, ts)

        self.assertTrue(driver._protocol._get_response(expected_prompt=IRIS_DATA_OFF))

    def test_dump_settings_response(self):
        """
        Verify that the driver correctly parses the DUMP_SETTINGS response
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DUMP_SETTINGS_01 command response: %s", DUMP_01_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_01_COMMAND_RESPONSE, ts)
        response = driver._protocol._get_response(expected_prompt=IRIS_DUMP_01)
        self.assertTrue(isinstance(response[1], IRISCommandResponse))

        # Clear out the linebuf and promptbuf (do_cmd_resp normally does this)
        driver._protocol._linebuf = ''
        driver._protocol._promptbuf = ''

        log.debug("DUMP_SETTINGS_02 command response: %s", DUMP_02_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_02_COMMAND_RESPONSE, ts)
        response = driver._protocol._get_response(expected_prompt=IRIS_DUMP_02)
        self.assertTrue(isinstance(response[1], IRISCommandResponse))

    def test_start_autosample(self):
        def my_send(data):
            my_response = DATA_ON_COMMAND_RESPONSE
            log.debug("my_send: data: %s, my_response: %s", data, my_response)
            driver._protocol._promptbuf += my_response
            return len(DATA_ON_COMMAND_RESPONSE)

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)
        driver._connection.send.side_effect = my_send

        driver._protocol._handler_command_start_autosample(timeout=0)
        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(DATA_ON_COMMAND_RESPONSE, ts)

    def test_stop_autosample(self):
        def my_send(data):
            my_response = DATA_OFF_COMMAND_RESPONSE
            log.debug("my_send: data: %s, my_response: %s", data, my_response)
            driver._protocol._promptbuf += my_response
            return len(DATA_OFF_COMMAND_RESPONSE)

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.AUTOSAMPLE)
        driver._connection.send.side_effect = my_send

        driver._protocol._handler_autosample_stop_autosample()
        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(DATA_OFF_COMMAND_RESPONSE, ts)

    def test_status_01_handler(self):
        def my_send(data):
            my_response = DUMP_01_STATUS
            log.debug("my_send: data: %s, my_response: %s", data, my_response)
            driver._protocol._promptbuf += my_response
            return len(DUMP_01_STATUS)

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.AUTOSAMPLE)
        driver._connection.send.side_effect = my_send

        result = driver._protocol._handler_command_autosample_dump01(timeout=0)[1][1]
        self.assertTrue(result == DUMP_01_STATUS_RESP)

    def test_status_02_handler(self):
        def my_send(data):
            my_response = DUMP_02_STATUS
            log.debug("my_send: data: %s, my_response: %s", data, my_response)
            driver._protocol._promptbuf += my_response
            return len(DUMP_02_STATUS)

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.AUTOSAMPLE)
        driver._connection.send.side_effect = my_send

        result = driver._protocol._handler_command_autosample_dump02(timeout=0)[1][1]
        self.assertTrue(result == DUMP_02_STATUS_RESP)

    def test_dump_01(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(DUMP_01_STATUS, ts)

        response = driver._protocol._get_response(timeout=0)
        self.assertTrue(isinstance(response[1], IRISStatus01Particle))

    def test_dump_02(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(DUMP_02_STATUS, ts)

        response = driver._protocol._get_response(timeout=0)
        self.assertTrue(isinstance(response[1], IRISStatus02Particle))

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


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_connection(self):
        self.assert_initialize_driver()

    def test_get(self):
        pass

    def test_set(self):
        pass

    def test_data_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()

        # Set continuous data on
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(response[1], IRIS_DATA_ON)

        log.debug("DATA_ON returned: %r", response)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        self.assertEqual(response[1], IRIS_DATA_OFF)

        log.debug("DATA_OFF returned: %r", response)

    def test_dump_01(self):
        """
        @brief Test for acquiring status dump 01
        """
        self.assert_initialize_driver()

        # Issues acquire status command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.DUMP_01)
        log.debug("DUMP_01 returned: %r", response)

    def test_dump_02(self):
        """
        @brief Test for acquiring status dump 02
        """
        self.assert_initialize_driver()

        # Issues acquire status command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.DUMP_02)
        log.debug("DUMP_02 returned: %r", response)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, IRISTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_reset(self):
        """
        Verify the agent can be reset
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_start_autosample()
        self.assert_reset()

    # Overridden because does not apply for this driver
    def test_discover(self):
        pass

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
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.GET,
                ProtocolEvent.SET,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.DUMP_01,
                ProtocolEvent.DUMP_02,
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
            ProtocolEvent.DUMP_01,
            ProtocolEvent.DUMP_02,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

    def test_instrument_agent_common_state_model_lifecycle(self, timeout=GO_ACTIVE_TIMEOUT):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.

                COMMANDS TESTED
                *ResourceAgentEvent.INITIALIZE
                *ResourceAgentEvent.RESET
                *ResourceAgentEvent.GO_ACTIVE
                *ResourceAgentEvent.RUN
                *ResourceAgentEvent.PAUSE
                *ResourceAgentEvent.RESUME
                *ResourceAgentEvent.GO_COMMAND
                *ResourceAgentEvent.GO_INACTIVE
                *ResourceAgentEvent.PING_RESOURCE
                *ResourceAgentEvent.CLEAR

                COMMANDS NOT TESTED
                * ResourceAgentEvent.GO_DIRECT_ACCESS
                * ResourceAgentEvent.GET_RESOURCE_STATE
                * ResourceAgentEvent.GET_RESOURCE
                * ResourceAgentEvent.SET_RESOURCE
                * ResourceAgentEvent.EXECUTE_RESOURCE

                STATES ACHIEVED:
                * ResourceAgentState.UNINITIALIZED
                * ResourceAgentState.INACTIVE
                * ResourceAgentState.IDLE'
                * ResourceAgentState.STOPPED
                * ResourceAgentState.COMMAND

                STATES NOT ACHIEVED:
                * ResourceAgentState.DIRECT_ACCESS
                * ResourceAgentState.STREAMING
                * ResourceAgentState.TEST
                * ResourceAgentState.CALIBRATE
                * ResourceAgentState.BUSY
                -- Not tested because they may not be implemented in the driver
        """
        ####
        # UNINITIALIZED
        ####
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_DIRECT_ACCESS, exception_class=Conflict)

        ####
        # INACTIVE
        ####
        self.assert_agent_command(ResourceAgentEvent.INITIALIZE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)

        ####
        # IDLE
        ####
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.INITIALIZE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.RESUME, exception_class=Conflict)

        # Verify we can go inactive
        self.assert_agent_command(ResourceAgentEvent.GO_INACTIVE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Get back to idle
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Reset
        self.assert_agent_command(ResourceAgentEvent.RESET)
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)