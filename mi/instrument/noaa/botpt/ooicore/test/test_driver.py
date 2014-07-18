"""
@package mi.instrument.noaa.lily.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/ooicore/test/test_driver.py
@author Pete Cable
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

import time
import ntplib
import mi.instrument.noaa.botpt.ooicore.particles as particles
from mi.core.instrument.port_agent_client import PortAgentPacket
from mock import Mock, call
from nose.plugins.attrib import attr
from mi.core.log import get_logger
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.exceptions import InstrumentDataException, SampleException, InstrumentProtocolException
from mi.instrument.noaa.botpt.ooicore.driver import Prompt, ScheduledJob
from mi.instrument.noaa.botpt.ooicore.driver import Parameter
from mi.instrument.noaa.botpt.ooicore.driver import ProtocolState
from mi.instrument.noaa.botpt.ooicore.driver import ProtocolEvent
from mi.instrument.noaa.botpt.ooicore.driver import InstrumentDriver
from mi.instrument.noaa.botpt.ooicore.driver import Protocol
from mi.instrument.noaa.botpt.ooicore.driver import ParameterConstraint
from mi.instrument.noaa.botpt.ooicore.driver import Capability
from mi.instrument.noaa.botpt.ooicore.driver import InstrumentCommand
from mi.instrument.noaa.botpt.ooicore.driver import NEWLINE
import mi.instrument.noaa.botpt.ooicore.test.test_samples as samples
from pyon.core.exception import BadRequest, ResourceError


__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

log = get_logger()

botpt_startup_config = {
        DriverConfigKey.PARAMETERS: {
            Parameter.AUTO_RELEVEL: True,
            Parameter.LEVELING_TIMEOUT: 600,
            Parameter.XTILT_TRIGGER: 300.0,
            Parameter.YTILT_TRIGGER: 300.0,
            Parameter.HEAT_DURATION: 1,
            Parameter.OUTPUT_RATE: 40,
        }
}

# ##
# Driver parameters for the tests
# ##
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_botpt_ooicore',
    instrument_agent_packet_config=particles.DataParticleType(),
    driver_startup_config=botpt_startup_config
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


class BotptTestMixinSub(DriverTestMixin):
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
        # RW
        Parameter.AUTO_RELEVEL: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, VALUE: True},
        Parameter.XTILT_TRIGGER: {TYPE: float, READONLY: False, DA: False, STARTUP: True, VALUE: 300},
        Parameter.YTILT_TRIGGER: {TYPE: float, READONLY: False, DA: False, STARTUP: True, VALUE: 300},
        Parameter.LEVELING_TIMEOUT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 600},
        Parameter.OUTPUT_RATE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 40},
        Parameter.HEAT_DURATION: {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 1},
        # RO
        Parameter.LILY_LEVELING: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: False},
        Parameter.HEATER_ON: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: False},
        Parameter.LEVELING_FAILED: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: False},
    }

    _samples = [samples.LILY_VALID_SAMPLE_01, samples.LILY_VALID_SAMPLE_02, samples.HEAT_VALID_SAMPLE_01,
                samples.HEAT_VALID_SAMPLE_02, samples.IRIS_VALID_SAMPLE_01, samples.IRIS_VALID_SAMPLE_02,
                samples.NANO_VALID_SAMPLE_01, samples.NANO_VALID_SAMPLE_02, samples.LEVELING_STATUS,
                samples.SWITCHING_STATUS, samples.LEVELED_STATUS, samples.X_OUT_OF_RANGE, samples.Y_OUT_OF_RANGE]

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.START_AUTOSAMPLE: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE: {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.START_LEVELING: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.STOP_LEVELING: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.START_HEATER: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.STOP_HEATER: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                'DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_START_AUTOSAMPLE',
                                'DRIVER_EVENT_START_DIRECT',
                                'PROTOCOL_EVENT_START_LEVELING',
                                'PROTOCOL_EVENT_STOP_LEVELING',
                                'PROTOCOL_EVENT_LEVELING_TIMEOUT',
                                'PROTOCOL_EVENT_HEATER_TIMEOUT',
                                'PROTOCOL_EVENT_START_HEATER',
                                'PROTOCOL_EVENT_STOP_HEATER',
                                'PROTOCOL_EVENT_NANO_TIME_SYNC'],
        ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                   'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                   'DRIVER_EVENT_ACQUIRE_STATUS',
                                   'PROTOCOL_EVENT_START_LEVELING',
                                   'PROTOCOL_EVENT_STOP_LEVELING',
                                   'PROTOCOL_EVENT_LEVELING_TIMEOUT',
                                   'PROTOCOL_EVENT_HEATER_TIMEOUT',
                                   'PROTOCOL_EVENT_START_HEATER',
                                   'PROTOCOL_EVENT_STOP_HEATER',
                                   'PROTOCOL_EVENT_NANO_TIME_SYNC'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT',
                                      'EXECUTE_DIRECT'],
    }

    lily_sample_parameters_01 = {
        particles.LilySampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        particles.LilySampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/06/24 23:36:02', REQUIRED: True},
        particles.LilySampleParticleKey.X_TILT: {TYPE: float, VALUE: -235.500, REQUIRED: True},
        particles.LilySampleParticleKey.Y_TILT: {TYPE: float, VALUE: 25.930, REQUIRED: True},
        particles.LilySampleParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 194.30, REQUIRED: True},
        particles.LilySampleParticleKey.TEMP: {TYPE: float, VALUE: 26.04, REQUIRED: True},
        particles.LilySampleParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.96, REQUIRED: True},
        particles.LilySampleParticleKey.SN: {TYPE: unicode, VALUE: 'N9655', REQUIRED: True},
        particles.LilySampleParticleKey.OUT_OF_RANGE: {TYPE: bool, VALUE: False, REQUIRED: True}
    }

    lily_sample_parameters_02 = {
        particles.LilySampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        particles.LilySampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/06/24 23:36:04', REQUIRED: True},
        particles.LilySampleParticleKey.X_TILT: {TYPE: float, VALUE: -235.349, REQUIRED: True},
        particles.LilySampleParticleKey.Y_TILT: {TYPE: float, VALUE: 26.082, REQUIRED: True},
        particles.LilySampleParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 194.26, REQUIRED: True},
        particles.LilySampleParticleKey.TEMP: {TYPE: float, VALUE: 26.04, REQUIRED: True},
        particles.LilySampleParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.96, REQUIRED: True},
        particles.LilySampleParticleKey.SN: {TYPE: unicode, VALUE: 'N9655', REQUIRED: True},
        particles.LilySampleParticleKey.OUT_OF_RANGE: {TYPE: bool, VALUE: False, REQUIRED: True}
    }

    nano_sample_parameters_01 = {
        particles.NanoSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'NANO', REQUIRED: True},
        particles.NanoSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/08/22 22:48:36.013', REQUIRED: True},
        particles.NanoSampleParticleKey.PRESSURE: {TYPE: float, VALUE: 13.888533, REQUIRED: True},
        particles.NanoSampleParticleKey.TEMP: {TYPE: float, VALUE: 26.147947328, REQUIRED: True},
        particles.NanoSampleParticleKey.PPS_SYNC: {TYPE: unicode, VALUE: u'V', REQUIRED: True},
    }

    nano_sample_parameters_02 = {
        particles.NanoSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'NANO', REQUIRED: True},
        particles.NanoSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/08/22 23:13:36.000', REQUIRED: True},
        particles.NanoSampleParticleKey.PRESSURE: {TYPE: float, VALUE: 13.884067, REQUIRED: True},
        particles.NanoSampleParticleKey.TEMP: {TYPE: float, VALUE: 26.172926006, REQUIRED: True},
        particles.NanoSampleParticleKey.PPS_SYNC: {TYPE: unicode, VALUE: u'P', REQUIRED: True},
    }

    iris_sample_parameters_01 = {
        particles.IrisSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'IRIS', REQUIRED: True},
        particles.IrisSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/05/29 00:25:34', REQUIRED: True},
        particles.IrisSampleParticleKey.X_TILT: {TYPE: float, VALUE: -0.0882, REQUIRED: True},
        particles.IrisSampleParticleKey.Y_TILT: {TYPE: float, VALUE: -0.7524, REQUIRED: True},
        particles.IrisSampleParticleKey.TEMP: {TYPE: float, VALUE: 28.45, REQUIRED: True},
        particles.IrisSampleParticleKey.SN: {TYPE: unicode, VALUE: 'N8642', REQUIRED: True}
    }

    iris_sample_parameters_02 = {
        particles.IrisSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'IRIS', REQUIRED: True},
        particles.IrisSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/05/29 00:25:36', REQUIRED: True},
        particles.IrisSampleParticleKey.X_TILT: {TYPE: float, VALUE: -0.0885, REQUIRED: True},
        particles.IrisSampleParticleKey.Y_TILT: {TYPE: float, VALUE: -0.7517, REQUIRED: True},
        particles.IrisSampleParticleKey.TEMP: {TYPE: float, VALUE: 28.49, REQUIRED: True},
        particles.IrisSampleParticleKey.SN: {TYPE: unicode, VALUE: 'N8642', REQUIRED: True}
    }

    heat_sample_parameters_01 = {
        particles.HeatSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'HEAT', REQUIRED: True},
        particles.HeatSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/04/19 22:54:11', REQUIRED: True},
        particles.HeatSampleParticleKey.X_TILT: {TYPE: int, VALUE: -1, REQUIRED: True},
        particles.HeatSampleParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        particles.HeatSampleParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    heat_sample_parameters_02 = {
        particles.HeatSampleParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'HEAT', REQUIRED: True},
        particles.HeatSampleParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/04/19 22:54:11', REQUIRED: True},
        particles.HeatSampleParticleKey.X_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        particles.HeatSampleParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        particles.HeatSampleParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    botpt_status_parameters_01 = {
        particles.BotptStatusParticleKey.LILY1: {TYPE: unicode, VALUE: samples.LILY_FILTERED_STATUS1, REQUIRED: True},
        particles.BotptStatusParticleKey.LILY2: {TYPE: unicode, VALUE: samples.LILY_FILTERED_STATUS2, REQUIRED: True},
        particles.BotptStatusParticleKey.IRIS1: {TYPE: unicode, VALUE: samples.IRIS_FILTERED_STATUS1, REQUIRED: True},
        particles.BotptStatusParticleKey.IRIS2: {TYPE: unicode, VALUE: samples.IRIS_FILTERED_STATUS2, REQUIRED: True},
        particles.BotptStatusParticleKey.NANO: {TYPE: unicode, VALUE: samples.NANO_FILTERED_STATUS, REQUIRED: True},
        particles.BotptStatusParticleKey.SYST: {TYPE: unicode, VALUE: samples.SYST_FILTERED_STATUS, REQUIRED: True},
    }

    lily_leveling_parameters_01 = {
        particles.LilyLevelingParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        particles.LilyLevelingParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/07/24 20:36:27', REQUIRED: True},
        particles.LilyLevelingParticleKey.X_TILT: {TYPE: float, VALUE: 14.667, REQUIRED: True},
        particles.LilyLevelingParticleKey.Y_TILT: {TYPE: float, VALUE: 81.642, REQUIRED: True},
        particles.LilyLevelingParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 185.21, REQUIRED: True},
        particles.LilyLevelingParticleKey.TEMP: {TYPE: float, VALUE: 33.67, REQUIRED: True},
        particles.LilyLevelingParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.59, REQUIRED: True},
        particles.LilyLevelingParticleKey.SN: {TYPE: unicode, VALUE: u'N9651', REQUIRED: True},
        particles.LilyLevelingParticleKey.STATUS: {TYPE: unicode, VALUE: u'None', REQUIRED: True}
    }

    lily_leveling_parameters_02 = {
        particles.LilyLevelingParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        particles.LilyLevelingParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/06/28 17:29:21', REQUIRED: True},
        particles.LilyLevelingParticleKey.X_TILT: {TYPE: float, VALUE: -2.277, REQUIRED: True},
        particles.LilyLevelingParticleKey.Y_TILT: {TYPE: float, VALUE: -2.165, REQUIRED: True},
        particles.LilyLevelingParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 190.81, REQUIRED: True},
        particles.LilyLevelingParticleKey.TEMP: {TYPE: float, VALUE: 25.69, REQUIRED: True},
        particles.LilyLevelingParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.87, REQUIRED: True},
        particles.LilyLevelingParticleKey.SN: {TYPE: unicode, VALUE: u'N9651', REQUIRED: True},
        particles.LilyLevelingParticleKey.STATUS: {TYPE: unicode, VALUE: u'Leveled', REQUIRED: True}
    }

    lily_leveling_parameters_03 = {
        particles.LilyLevelingParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        particles.LilyLevelingParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/06/28 18:04:41', REQUIRED: True},
        particles.LilyLevelingParticleKey.X_TILT: {TYPE: float, VALUE: -7.390, REQUIRED: True},
        particles.LilyLevelingParticleKey.Y_TILT: {TYPE: float, VALUE: -14.063, REQUIRED: True},
        particles.LilyLevelingParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 190.91, REQUIRED: True},
        particles.LilyLevelingParticleKey.TEMP: {TYPE: float, VALUE: 25.83, REQUIRED: True},
        particles.LilyLevelingParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.87, REQUIRED: True},
        particles.LilyLevelingParticleKey.SN: {TYPE: unicode, VALUE: u'N9651', REQUIRED: True},
        particles.LilyLevelingParticleKey.STATUS: {TYPE: unicode, VALUE: u'Switching to Y', REQUIRED: True}
    }

    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    def assert_particle(self, data_particle, particle_type, particle_keys, sample_data, verify_values=False):
        """
        Verify sample particle
        @param data_particle: data particle
        @param particle_type: particle type
        @param particle_keys: particle data keys
        @param sample_data: sample values to verify against
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_keys(particle_keys, sample_data)
        self.assert_data_particle_header(data_particle, particle_type, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, sample_data, verify_values)

    def assert_particle_lily_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.LILY_SAMPLE,
                             particles.LilySampleParticleKey, self.lily_sample_parameters_01, verify_values)

    def assert_particle_lily_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.LILY_SAMPLE,
                             particles.LilySampleParticleKey, self.lily_sample_parameters_02, verify_values)

    def assert_particle_nano_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.NANO_SAMPLE,
                             particles.NanoSampleParticleKey, self.nano_sample_parameters_01, verify_values)

    def assert_particle_nano_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.NANO_SAMPLE,
                             particles.NanoSampleParticleKey, self.nano_sample_parameters_02, verify_values)

    def assert_particle_iris_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.IRIS_SAMPLE,
                             particles.IrisSampleParticleKey, self.iris_sample_parameters_01, verify_values)

    def assert_particle_iris_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.IRIS_SAMPLE,
                             particles.IrisSampleParticleKey, self.iris_sample_parameters_02, verify_values)

    def assert_particle_heat_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.IRIS_SAMPLE,
                             particles.HeatSampleParticleKey, self.heat_sample_parameters_01, verify_values)

    def assert_particle_heat_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.IRIS_SAMPLE,
                             particles.HeatSampleParticleKey, self.heat_sample_parameters_02, verify_values)

    def assert_particle_botpt_status(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.BOTPT_STATUS,
                             particles.BotptStatusParticleKey, self.botpt_status_parameters_01, verify_values)

    def assert_particle_lily_leveling_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.LILY_LEVELING,
                             particles.LilyLevelingParticleKey, self.lily_leveling_parameters_01, verify_values)

    def assert_particle_lily_leveling_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.LILY_LEVELING,
                             particles.LilyLevelingParticleKey, self.lily_leveling_parameters_02, verify_values)

    def assert_particle_lily_leveling_03(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, particles.DataParticleType.LILY_LEVELING,
                             particles.LilyLevelingParticleKey, self.lily_leveling_parameters_03, verify_values)

    def _create_port_agent_packet(self, data_item):
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data_item)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        return port_agent_packet

    def _send_port_agent_packet(self, driver, data_item):
        driver._protocol.got_data(self._create_port_agent_packet(data_item))

    def send_side_effect(self, driver):
        def inner(data):
            response = self._responses.get(data)
            if response is not None:
                log.debug("my_send: data: %s, my_response: %s", data, response)
                self._send_port_agent_packet(driver, response + samples.NEWLINE)
            else:
                log.debug('No response found for %r', data)

        return inner

    _responses = {
        'NANO,*0100IF\n': samples.NANO_STATUS,  # need this for _update_params
        'LILY,*9900XYC2\n': 'LILY,2013/06/28 18:04:41,*9900XYC2',  # lily on
        'IRIS,*9900XYC2\n': 'IRIS,2013/06/28 18:04:41,*9900XYC2',  # iris on
        'LILY,*9900XY-LEVEL,0\n': 'LILY,2013/06/28 18:04:41,*9900XY-LEVEL,0',  # level off
        'LILY,*9900XYC-OFF\n': 'LILY,2013/06/28 18:04:41,*9900XYC-OFF',  # lily off
        'IRIS,*9900XYC-OFF\n': 'IRIS,2013/06/28 18:04:41,*9900XYC-OFF',  # iris off
        'SYST,1\n': samples.SYST_STATUS,
        'LILY,*9900XY-DUMP-SETTINGS\n': samples.LILY_STATUS1,
        'LILY,*9900XY-DUMP2\n': samples.LILY_STATUS2,
        'IRIS,*9900XY-DUMP-SETTINGS\n': samples.IRIS_STATUS1,
        'IRIS,*9900XY-DUMP2\n': samples.IRIS_STATUS2,
        'LILY,*9900XY-LEVEL,1\n': 'LILY,2013/06/28 18:04:41,*9900XY-LEVEL,1',
        'HEAT,1\n': 'HEAT,2013/06/28 18:04:41,*1',
        'HEAT,0\n': 'HEAT,2013/06/28 18:04:41,*0',
        'NANO,*0100E4\n': samples.NANO_VALID_SAMPLE_01,
        'NANO,TS': samples.NANO_VALID_SAMPLE_01,
    }


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
# noinspection PyProtectedMember,PyUnusedLocal,PyUnresolvedReferences
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, BotptTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Verify we can initialize the driver.  Set up mock events for other tests.
        @param initial_protocol_state: target protocol state for driver
        @return: driver instance
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        driver._protocol.set_init_params(botpt_startup_config)
        driver._connection.send.side_effect = self.send_side_effect(driver)
        driver._protocol._protocol_fsm.on_event_actual = driver._protocol._protocol_fsm.on_event
        driver._protocol._protocol_fsm.on_event = Mock()
        driver._protocol._protocol_fsm.on_event.side_effect = driver._protocol._protocol_fsm.on_event_actual
        driver._protocol._init_params()
        return driver

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        driver = self.test_connect()

        self.assert_particle_published(driver, samples.LILY_VALID_SAMPLE_01, self.assert_particle_lily_sample_01, True)
        self.assert_particle_published(driver, samples.LILY_VALID_SAMPLE_02, self.assert_particle_lily_sample_02, True)
        self.assert_particle_published(driver, samples.NANO_VALID_SAMPLE_01, self.assert_particle_nano_sample_01, True)
        self.assert_particle_published(driver, samples.NANO_VALID_SAMPLE_02, self.assert_particle_nano_sample_02, True)
        self.assert_particle_published(driver, samples.IRIS_VALID_SAMPLE_01, self.assert_particle_iris_sample_01, True)
        self.assert_particle_published(driver, samples.IRIS_VALID_SAMPLE_02, self.assert_particle_iris_sample_02, True)
        self.assert_particle_published(driver, samples.HEAT_VALID_SAMPLE_01, self.assert_particle_heat_sample_01, True)
        self.assert_particle_published(driver, samples.HEAT_VALID_SAMPLE_02, self.assert_particle_heat_sample_02, True)

        # disable leveling-related methods to avoid handling these messages (will raise exception)
        driver._protocol._check_completed_leveling = Mock()
        driver._protocol._check_for_autolevel = Mock()

        self.assert_particle_published(driver, samples.LEVELING_STATUS, self.assert_particle_lily_leveling_01, True)
        self.assert_particle_published(driver, samples.LEVELED_STATUS, self.assert_particle_lily_leveling_02, True)
        self.assert_particle_published(driver, samples.SWITCHING_STATUS, self.assert_particle_lily_leveling_03, True)
        self.assert_particle_published(driver, samples.X_OUT_OF_RANGE, self.assert_particle_lily_leveling_02, False)
        self.assert_particle_published(driver, samples.Y_OUT_OF_RANGE, self.assert_particle_lily_leveling_02, False)

    def test_corrupt_data(self):
        """
        Verify corrupt data generates a SampleException
        """
        driver = self.test_connect()
        for sample, p_type in [
            (samples.LILY_VALID_SAMPLE_01, particles.LilySampleParticle),
            (samples.IRIS_VALID_SAMPLE_01, particles.IrisSampleParticle),
            (samples.NANO_VALID_SAMPLE_01, particles.NanoSampleParticle),
            (samples.HEAT_VALID_SAMPLE_01, particles.HeatSampleParticle),
            (samples.LEVELING_STATUS, particles.LilyLevelingParticle),
            (samples.LILY_STATUS1, particles.LilyStatusParticle1),
            (samples.LILY_STATUS2, particles.LilyStatusParticle2),
            (samples.IRIS_STATUS1, particles.IrisStatusParticle1),
            (samples.IRIS_STATUS2, particles.IrisStatusParticle2),
            (samples.NANO_STATUS, particles.NanoStatusParticle),
            (samples.SYST_STATUS, particles.SystStatusParticle),
        ]:
            sample = sample[:8] + 'GARBAGE123123124' + sample[8:]
            with self.assertRaises(SampleException):
                p_type(sample).generate()

    def test_status_particle(self):
        """
        This particle is not generated via the chunker (because it may contain embedded samples)
        so we will test it by manually generating the particle.
        """
        ts = ntplib.system_to_ntp_time(time.time())
        status = NEWLINE.join([samples.SYST_STATUS, samples.LILY_STATUS1, samples.LILY_STATUS2,
                               samples.IRIS_STATUS1, samples.IRIS_STATUS2, samples.NANO_STATUS])
        self.assert_particle_botpt_status(particles.BotptStatusParticle(status, port_timestamp=ts), verify_values=True)

    def test_combined_samples(self):
        """
        Verify combined samples produce the correct number of chunks
        """
        chunker = StringChunker(Protocol.sieve_function)
        ts = self.get_ntp_timestamp()
        my_samples = [(samples.BOTPT_FIREHOSE_01, 6),
                      (samples.BOTPT_FIREHOSE_02, 7)]

        for data, num_samples in my_samples:
            chunker.add_chunk(data, ts)
            results = []
            while True:
                timestamp, result = chunker.get_next_data()
                if result:
                    results.append(result)
                    self.assertTrue(result in data)
                    self.assertEqual(timestamp, ts)
                else:
                    break

            self.assertEqual(len(results), num_samples)

    def test_chunker(self):
        """
        Test the chunker against all input samples
        """
        chunker = StringChunker(Protocol.sieve_function)
        ts = self.get_ntp_timestamp()

        for sample in self._samples:
            chunker.add_chunk(sample, ts)
            (timestamp, result) = chunker.get_next_data()
            self.assertEqual(result, sample)
            self.assertEqual(timestamp, ts)
            (timestamp, result) = chunker.get_next_data()
            self.assertEqual(result, None)

    def test_start_stop_autosample(self):
        """
        Test starting/stopping autosample, verify state transitions
        """
        driver = self.test_connect()

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_status_handler(self):
        """
        Test the acquire status handler
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.ACQUIRE_STATUS)

    def test_leveling_timeout(self):
        """
        Test that leveling times out, is stopped, and the appropriate flags are set.
        """
        driver = self.test_connect()

        expected = [call(ProtocolEvent.GET, Parameter.ALL),  # startup get ALL
                    call(ProtocolEvent.START_LEVELING),      # start leveling
                    call(ProtocolEvent.GET, Parameter.ALL),  # config change get ALL
                    call(ProtocolEvent.LEVELING_TIMEOUT),  # leveling timed out
                    call(ProtocolEvent.GET, Parameter.ALL)]  # config change get ALL

        try:
            # set the leveling timeout to 1 to speed up timeout
            driver._protocol._param_dict.set_value(Parameter.LEVELING_TIMEOUT, 1)
            driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)
            self.assertEqual(driver._protocol._param_dict.get(Parameter.LILY_LEVELING), True)

            # sleep for longer than the length of timeout
            time.sleep(driver._protocol._param_dict.get(Parameter.LEVELING_TIMEOUT) + 1)

        except InstrumentProtocolException:
            # assert that we raised the expected events
            self.assertEqual(driver._protocol._protocol_fsm.on_event.call_args_list, expected)
            self.assertEqual(driver._protocol._param_dict.get(Parameter.LILY_LEVELING), False)
            self.assertEqual(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL), False)
            self.assertEqual(driver._protocol._param_dict.get(Parameter.LEVELING_FAILED), True)

    def test_leveling_complete(self):
        """
        Test the driver processes a leveling complete particle
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)
        # feed in a leveling complete status message
        self._send_port_agent_packet(driver, samples.LEVELED_STATUS)
        # Assert we have returned to the command state
        self.assertEquals(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        expected = [call(ProtocolEvent.GET, Parameter.ALL),  # startup get ALL
                    call(ProtocolEvent.START_LEVELING),      # start leveling
                    call(ProtocolEvent.GET, Parameter.ALL),  # config change get ALL
                    call(ProtocolEvent.STOP_LEVELING),       # leveling timed out
                    call(ProtocolEvent.GET, Parameter.ALL)]  # config change get ALL

        # assert that we raised the expected events
        self.assertEqual(driver._protocol._protocol_fsm.on_event.call_args_list, expected)

    def test_leveling_failure(self):
        """
        Test the driver processes a leveling failure particle, sets the correct flags.
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)
        # assert we have entered a leveling state
        self.assertTrue(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        # feed in a leveling failed status message
        try:
            self._send_port_agent_packet(driver, samples.X_OUT_OF_RANGE + samples.NEWLINE)
            time.sleep(1)
        except InstrumentDataException:
            self.assertFalse(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        try:
            self._send_port_agent_packet(driver, samples.Y_OUT_OF_RANGE + samples.NEWLINE)
            time.sleep(1)
        except InstrumentDataException:
            self.assertFalse(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        expected = [call(ProtocolEvent.GET, Parameter.ALL),  # startup get ALL
                    call(ProtocolEvent.START_LEVELING),      # start leveling
                    call(ProtocolEvent.GET, Parameter.ALL),  # config change get ALL
                    call(ProtocolEvent.GET, Parameter.ALL),  # config change get ALL
                    call(ProtocolEvent.STOP_LEVELING),       # leveling timed out
                    call(ProtocolEvent.GET, Parameter.ALL)]  # config change get ALL

        # assert that we raised the expected events
        self.assertEqual(driver._protocol._protocol_fsm.on_event.call_args_list, expected)

        # assert the correct flags are set
        self.assertEqual(driver._protocol._param_dict.get(Parameter.LILY_LEVELING), False)
        self.assertEqual(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL), False)
        self.assertEqual(driver._protocol._param_dict.get(Parameter.LEVELING_FAILED), True)

    def test_pps_time_sync(self):
        """
        Test that the time sync event is raised when PPS is regained.
        """
        driver = self.test_connect()
        self._send_port_agent_packet(driver, samples.NANO_VALID_SAMPLE_01)  # PPS lost
        self._send_port_agent_packet(driver, samples.NANO_VALID_SAMPLE_02)  # PPS regained

        expected = [call('DRIVER_EVENT_GET', 'DRIVER_PARAMETER_ALL'),  # startup get ALL
                    call('PROTOCOL_EVENT_NANO_TIME_SYNC')]             # Time sync event when PPS regained

        # assert that we raised the expected events
        self.assertEqual(driver._protocol._protocol_fsm.on_event.call_args_list, expected)

    def test_heat_on(self):
        """
        Test turning the heater on/off
        """
        driver = self.test_connect()
        driver._protocol._handler_start_heater()
        self.assertEqual(driver._protocol._param_dict.get(Parameter.HEATER_ON), True)
        driver._protocol._handler_stop_heater()
        self.assertEqual(driver._protocol._param_dict.get(Parameter.HEATER_ON), False)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion. Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(particles.DataParticleType)
        self.assert_enum_has_no_duplicates(ProtocolState)
        self.assert_enum_has_no_duplicates(ProtocolEvent)
        self.assert_enum_has_no_duplicates(Parameter)
        # self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability)
        self.assert_enum_complete(Capability, ProtocolEvent)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected. All states defined in this dict must
        also be defined in the protocol FSM.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, samples.NEWLINE, mock_callback)
        driver_capabilities = Capability.list()
        test_capabilities = Capability.list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, BotptTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def assert_acquire_status(self):
        """
        Verify all status particles generated
        """
        self.clear_events()
        self.assert_async_particle_generation(particles.DataParticleType.BOTPT_STATUS,
                                              self.assert_particle_botpt_status, timeout=20)

    def assert_time_sync(self):
        """
        Verify all status particles generated
        """
        self.clear_events()
        self.assert_async_particle_generation(particles.DataParticleType.NANO_SAMPLE,
                                              self.assert_particle_nano_sample_01, timeout=20)

    def test_connect(self):
        self.assert_initialize_driver()

    def test_get(self):
        self.assert_initialize_driver()
        for param in self._driver_parameters:
            self.assert_get(param, self._driver_parameters[param][self.VALUE])

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()
        constraints = ParameterConstraint.dict()
        parameters = Parameter.dict()
        startup_config = self.test_config.driver_startup_config['parameters']

        for key in constraints:
            _type, minimum, maximum = constraints[key]
            key = parameters[key]
            if _type in [int, float]:
                # assert we can set in range
                self.assert_set(key, maximum - 1)
                # assert exception when out of range
                self.assert_set_exception(key, maximum + 1)
            elif _type == bool:
                # assert we can toggle a boolean parameter
                if startup_config[key]:
                    self.assert_set(key, False)
                else:
                    self.assert_set(key, True)
            # assert bad types throw an exception
            self.assert_set_exception(key, 'BOGUS')

    def test_set_bogus_parameter(self):
        """
        Verify setting a bad parameter raises an exception
        """
        self.assert_initialize_driver()
        self.assert_set_exception('BOGUS', 'CHEESE')

    def test_startup_parameters(self):
        new_values = {
            Parameter.AUTO_RELEVEL: True,
            Parameter.LEVELING_TIMEOUT: 601,
            Parameter.XTILT_TRIGGER: 301,
            Parameter.YTILT_TRIGGER: 301,
            Parameter.HEAT_DURATION: 2,
            Parameter.OUTPUT_RATE: 1,
        }

        self.assert_initialize_driver()
        self.assert_startup_parameters(self.assert_driver_parameters, new_values,
                                       self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS])

    def test_incomplete_config(self):
        """
        Break our startup config, then verify the driver raises an exception
        """
        # grab the old config
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        old_value = startup_params[Parameter.LEVELING_TIMEOUT]
        failed = False

        try:
            # delete a required parameter
            del (startup_params[Parameter.LEVELING_TIMEOUT])
            # re-init to take our broken config
            self.init_driver_process_client()
            self.assert_initialize_driver()
            failed = True
        except ResourceError as e:
            log.info('Exception thrown, test should pass: %r', e)
        finally:
            startup_params[Parameter.LEVELING_TIMEOUT] = old_value

        if failed:
            self.fail('Failed to throw exception on missing parameter')

    def test_auto_relevel(self):
        """
        Test for verifying auto relevel
        """
        self.assert_initialize_driver()

        # set the leveling timeout low, so we're not here for long
        self.assert_set(Parameter.LEVELING_TIMEOUT, 60, no_get=True)

        # Set the XTILT to a low threshold so that the driver will
        # automatically start the re-leveling operation
        # NOTE: This test MAY fail if the instrument completes
        # leveling before the triggers have been reset to 300
        self.assert_set(Parameter.XTILT_TRIGGER, 0, no_get=True)

        self.assert_driver_command(Capability.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE)
        self.assert_async_particle_generation(particles.DataParticleType.LILY_LEVELING,
                                              self.assert_particle_lily_leveling_01)

        # verify the flag is set
        self.assert_get(Parameter.LILY_LEVELING, True)
        self.assert_driver_command(Capability.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND)

    def test_autosample(self):
        """
        Test for turning data on
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE)
        rate = int(self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS][Parameter.OUTPUT_RATE])

        # autosample for 10 seconds, then count the samples...
        # we can't test "inline" because the nano data rate is too high.
        time.sleep(10)
        self.assert_driver_command(Capability.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        for particle_type, assert_func, count in [
            (particles.DataParticleType.LILY_SAMPLE, self.assert_particle_lily_sample_01, 5),
            (particles.DataParticleType.HEAT_SAMPLE, self.assert_particle_heat_sample_01, 5),
            (particles.DataParticleType.IRIS_SAMPLE, self.assert_particle_iris_sample_01, 5),
            (particles.DataParticleType.NANO_SAMPLE, self.assert_particle_nano_sample_01, 5 * rate)
        ]:
            self.assert_async_particle_generation(particle_type, assert_func, particle_count=count, timeout=1)

    def test_commanded_acquire_status(self):
        """
        Test for acquiring status
        """
        self.assert_initialize_driver()
        # Issue acquire status command
        self.assert_particle_generation(Capability.ACQUIRE_STATUS, particles.DataParticleType.BOTPT_STATUS,
                                        self.assert_particle_botpt_status)

    def test_leveling_complete(self):
        """
        Test for leveling complete
        """
        self.assert_initialize_driver()

        # go to autosample
        self.assert_driver_command(Capability.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=5)

        #Issue start leveling command
        self.assert_driver_command(Capability.START_LEVELING)
        # Verify the flag is set
        self.assert_get(Parameter.LILY_LEVELING, True)

        # Leveling should complete or abort after DEFAULT_LEVELING_TIMEOUT seconds
        timeout = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS][Parameter.LEVELING_TIMEOUT]
        # wait for a sample particle to indicate leveling is complete
        self.clear_events()
        self.assert_async_particle_generation(particles.DataParticleType.LILY_SAMPLE,
                                              self.assert_particle_lily_sample_01,
                                              timeout=timeout+10)

        # Verify the flag is unset
        self.assert_get(Parameter.LILY_LEVELING, False)
        self.assert_driver_command(Capability.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=5)

    def test_scheduled_acquire_status(self):
        """
        Verify we can schedule an acquire status event
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status, delay=20)

    def test_scheduled_time_sync(self):
        """
        Verify we can schedule a time sync event.
        If we sync time in command mode, we will generate at least one NANO sample particle.
        """
        self.assert_scheduled_event(ScheduledJob.NANO_TIME_SYNC, self.assert_time_sync, delay=20)

    def test_heat_on(self):
        """
        Test turning the heater on and off.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_HEATER)
        self.assert_get(Parameter.HEATER_ON, True)
        self.assert_driver_command(Capability.STOP_HEATER)
        self.assert_get(Parameter.HEATER_ON, False)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, BotptTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def assert_cycle(self):
        """
        Assert we can enter autosample, acquire all particles, acquire status,
        stop autosample, acquire heat particle, acquire_status.
        """
        self.assert_start_autosample()
        # verify all particles in autosample
        self.assert_particle_async(particles.DataParticleType.LILY_SAMPLE, self.assert_particle_lily_sample_01)
        self.assert_particle_async(particles.DataParticleType.IRIS_SAMPLE, self.assert_particle_iris_sample_01)
        self.assert_particle_async(particles.DataParticleType.NANO_SAMPLE, self.assert_particle_nano_sample_01)
        self.assert_particle_async(particles.DataParticleType.HEAT_SAMPLE, self.assert_particle_heat_sample_01)

        self.assert_particle_polled(Capability.ACQUIRE_STATUS, self.assert_particle_botpt_status,
                                    particles.DataParticleType.BOTPT_STATUS, timeout=60)

        self.assert_particle_async(particles.DataParticleType.LILY_SAMPLE, self.assert_particle_lily_sample_01)
        self.assert_particle_async(particles.DataParticleType.IRIS_SAMPLE, self.assert_particle_iris_sample_01)
        self.assert_particle_async(particles.DataParticleType.NANO_SAMPLE, self.assert_particle_nano_sample_01)
        self.assert_particle_async(particles.DataParticleType.HEAT_SAMPLE, self.assert_particle_heat_sample_01)

        self.assert_stop_autosample()
        # verify all particles in command
        self.assert_particle_async(particles.DataParticleType.HEAT_SAMPLE, self.assert_particle_heat_sample_01)
        self.assert_particle_polled(Capability.ACQUIRE_STATUS, self.assert_particle_botpt_status,
                                    particles.DataParticleType.BOTPT_STATUS, timeout=60)

    def test_cycle(self):
        """
        Verify we can run through the test cycle 4 times
        """
        self.assert_enter_command_mode()
        for x in xrange(4):
            log.debug('test_cycle -- PASS %d', x + 1)
            self.assert_cycle()

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(InstrumentCommand.LILY_DUMP1 + samples.NEWLINE)
        result = self.tcp_client.expect('-DUMP-SETTINGS')
        self.assertTrue(result, msg='Failed to receive expected response in direct access mode.')
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)

    def test_leveling(self):
        """
        Verify we can stop/start leveling
        """
        self.assert_enter_command_mode()
        self.assert_resource_command(Capability.START_LEVELING)
        self.assert_get_parameter(Parameter.LILY_LEVELING, True)
        self.assert_particle_async(particles.DataParticleType.LILY_LEVELING, self.assert_particle_lily_leveling_01)
        self.assert_resource_command(Capability.STOP_LEVELING)
        self.assert_get_parameter(Parameter.LILY_LEVELING, False)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()
        constraints = ParameterConstraint.dict()
        parameters = Parameter.dict()
        reverse_param = Parameter.reverse_dict()
        startup_config = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]

        for key in self._driver_parameters:
            if self._driver_parameters[key][self.READONLY]:
                self.assert_read_only_parameter(key)
            else:
                name = reverse_param.get(key)
                if name in constraints:
                    _type, minimum, maximum = constraints[name]
                    if _type in [int, float]:
                        # assert we can set in range
                        self.assert_set_parameter(key, maximum - 1)
                        # assert exception when out of range
                        with self.assertRaises(BadRequest):
                            self.assert_set_parameter(key, maximum + 1)
                    elif _type == bool:
                        # assert we can toggle a boolean parameter
                        if startup_config[key]:
                            self.assert_set_parameter(key, False)
                        else:
                            self.assert_set_parameter(key, True)
            # assert bad types throw an exception
            with self.assertRaises(BadRequest):
                self.assert_set_parameter(key, 'BOGUS')

        startup_config = self.test_config.driver_startup_config['parameters']

    def test_get_capabilities(self):
        """
        Verify that the correct capabilities are returned from get_capabilities
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
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.START_LEVELING,
                ProtocolEvent.STOP_LEVELING,
                ProtocolEvent.START_HEATER,
                ProtocolEvent.STOP_HEATER,
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
            ProtocolEvent.GET,
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.START_LEVELING,
            ProtocolEvent.STOP_LEVELING,
            ProtocolEvent.START_HEATER,
            ProtocolEvent.STOP_HEATER,
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

    def test_direct_access_exit_from_autosample(self):
        """
        Overridden.  This driver always discovers to command
        """

    def test_discover(self):
        """
        Overridden.  The driver always discovers to command
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)
