"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

@todo Figure out clock sync off by one issue
@todo figure out the pattern for applying startup config
@todo what to do with startup parameters that don't have a startup value

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest
from gevent import monkey; monkey.patch_all()
import time
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.core.time import get_timestamp_delayed
from nose.plugins.attrib import attr
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.instrument_driver import DriverEvent
from mi.instrument.seabird.test.test_driver import SeaBirdUnitTest
from mi.instrument.seabird.test.test_driver import SeaBirdIntegrationTest
from mi.instrument.seabird.test.test_driver import SeaBirdQualificationTest

from mi.instrument.seabird.sbe26plus.test.sample_data import *

from mi.instrument.seabird.sbe26plus.driver import ScheduledJob
from mi.instrument.seabird.sbe26plus.driver import DataParticleType
from mi.instrument.seabird.sbe26plus.driver import InstrumentDriver
from mi.instrument.seabird.sbe26plus.driver import ProtocolState
from mi.instrument.seabird.sbe26plus.driver import Parameter
from mi.instrument.seabird.sbe26plus.driver import ProtocolEvent
from mi.instrument.seabird.sbe26plus.driver import Capability
from mi.instrument.seabird.sbe26plus.driver import Prompt
from mi.instrument.seabird.sbe26plus.driver import Protocol
from mi.instrument.seabird.sbe26plus.driver import InstrumentCmds
from mi.instrument.seabird.sbe26plus.driver import NEWLINE
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTideSampleDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusWaveBurstDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusStatisticsDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceCalibrationDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceStatusDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTideSampleDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusWaveBurstDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusStatisticsDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceCalibrationDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceStatusDataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import InstrumentCommandException
from pyon.agent.agent import ResourceAgentEvent

# Globals
raw_stream_received = False
parsed_stream_received = False

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

class SeaBird26PlusMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.EXTERNAL_TEMPERATURE_SENSOR: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.CONDUCTIVITY: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.USER_INFO : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        Parameter.TXREALTIME: {TYPE: bool, READONLY: False, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.TXWAVEBURST: {TYPE: bool, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},

        # Set sampling parameters
        Parameter.TIDE_INTERVAL : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TIDE_MEASUREMENT_DURATION : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.WAVE_SAMPLES_PER_BURST : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.USE_START_TIME : {TYPE: bool, READONLY: True, DA: False, STARTUP: False, REQUIRED: False, VALUE: False},
        Parameter.USE_STOP_TIME : {TYPE: bool, READONLY: True, DA: False, STARTUP: False, REQUIRED: False, VALUE: False},
        Parameter.TIDE_SAMPLES_PER_DAY : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.WAVE_BURSTS_PER_DAY : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.MEMORY_ENDURANCE : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TOTAL_RECORDED_WAVE_BURSTS : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.WAVE_BURSTS_SINCE_LAST_START : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.TXWAVESTATS : {TYPE: bool, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : {TYPE: bool, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : {TYPE: int, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.MIN_ALLOWABLE_ATTENUATION : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},
        Parameter.HANNING_WINDOW_CUTOFF : {TYPE: float, READONLY: False, DA: False, STARTUP: False, REQUIRED: False},

        # DS parameters - also includes sampling parameters
        Parameter.DEVICE_VERSION : {TYPE: str, READONLY: True},
        Parameter.SERIAL_NUMBER : {TYPE: str, READONLY: True},
        Parameter.DS_DEVICE_DATE_TIME : {TYPE: str, READONLY: True},
        Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER : {TYPE: float, READONLY: True},
        Parameter.QUARTZ_PRESSURE_SENSOR_RANGE : {TYPE: float, READONLY: True},
        Parameter.IOP_MA : {TYPE: float, READONLY: True},
        Parameter.VMAIN_V : {TYPE: float, READONLY: True},
        Parameter.VLITH_V : {TYPE: float, READONLY: True},
        Parameter.LAST_SAMPLE_P : {TYPE: float, READONLY: True, REQUIRED: False},
        Parameter.LAST_SAMPLE_T : {TYPE: float, READONLY: True, REQUIRED: False},
        Parameter.LAST_SAMPLE_S : {TYPE: float, READONLY: True, REQUIRED: False},
        Parameter.SHOW_PROGRESS_MESSAGES : { TYPE: bool, READONLY: True, REQUIRED: False},
        Parameter.STATUS : { TYPE: str, READONLY: True},
        Parameter.LOGGING : { TYPE: bool, READONLY: True},
    }

    _tide_sample_parameters = {
        SBE26plusTideSampleDataParticleKey.TIMESTAMP: {TYPE: float, VALUE: 3558413454.0, REQUIRED: False },
        SBE26plusTideSampleDataParticleKey.PRESSURE: {TYPE: float, VALUE: -159.7139 },
        SBE26plusTideSampleDataParticleKey.PRESSURE_TEMP: {TYPE: float, VALUE: -8382.61 },
        SBE26plusTideSampleDataParticleKey.TEMPERATURE: {TYPE: float, VALUE: 34.6843 },
    }

    _wave_sample_parameters = {
        SBE26plusWaveBurstDataParticleKey.TIMESTAMP: {TYPE: float, VALUE: 3558413454.0 },
        SBE26plusWaveBurstDataParticleKey.PTFREQ: {TYPE: float, VALUE: 171791.359 },
        SBE26plusWaveBurstDataParticleKey.PTRAW: {TYPE: list }
    }

    _statistics_sample_parameters = {
        SBE26plusStatisticsDataParticleKey.DEPTH: {TYPE: float, VALUE: 0.0 },
        SBE26plusStatisticsDataParticleKey.TEMPERATURE: {TYPE: float, VALUE: 23.840 },
        SBE26plusStatisticsDataParticleKey.SALINITY: {TYPE: float, VALUE: 35.000 },
        SBE26plusStatisticsDataParticleKey.DENSITY: {TYPE: float, VALUE: 1023.690 },
        SBE26plusStatisticsDataParticleKey.N_AGV_BAND: {TYPE: int, VALUE: 5 },
        SBE26plusStatisticsDataParticleKey.TOTAL_VARIANCE: {TYPE: float, VALUE: 1.0896e-05 },
        SBE26plusStatisticsDataParticleKey.TOTAL_ENERGY: {TYPE: float, VALUE: 1.0939e-01 },
        SBE26plusStatisticsDataParticleKey.SIGNIFICANT_PERIOD: {TYPE: float, VALUE: 5.3782e-01 },
        SBE26plusStatisticsDataParticleKey.SIGNIFICANT_WAVE_HEIGHT: {TYPE: float, VALUE: 1.3204e-02 },
        SBE26plusStatisticsDataParticleKey.TSS_WAVE_INTEGRATION_TIME: {TYPE: int, VALUE: 128 },
        SBE26plusStatisticsDataParticleKey.TSS_NUMBER_OF_WAVES: {TYPE: float, VALUE: 0 },
        SBE26plusStatisticsDataParticleKey.TSS_TOTAL_VARIANCE: {TYPE: float, VALUE: 1.1595e-05 },
        SBE26plusStatisticsDataParticleKey.TSS_TOTAL_ENERGY: {TYPE: float, VALUE: 1.1640e-01 },
        SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_HEIGHT: {TYPE: float, VALUE: 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_PERIOD: {TYPE: float, VALUE: 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_MAXIMUM_WAVE_HEIGHT: {TYPE: float, VALUE: 1.0893e-02 },
        SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_HEIGHT: {TYPE: float, VALUE: 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_PERIOD: {TYPE: float, VALUE: 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_H1_10: {TYPE: float, VALUE: 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_H1_100: {TYPE: float, VALUE: 0.0000e+00 }
    }

    _calibration_sample_parameters = {
        SBE26plusDeviceCalibrationDataParticleKey.PCALDATE: {TYPE: list, VALUE: [2, 4, 2013] },
        SBE26plusDeviceCalibrationDataParticleKey.PU0: {TYPE: float, VALUE: 5.100000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PY1: {TYPE: float, VALUE: -3.910859e+03 },
        SBE26plusDeviceCalibrationDataParticleKey.PY2: {TYPE: float, VALUE: -1.070825e+04 },
        SBE26plusDeviceCalibrationDataParticleKey.PY3: {TYPE: float, VALUE:  0.000000e+00  },
        SBE26plusDeviceCalibrationDataParticleKey.PC1: {TYPE: float, VALUE: 6.072786e+02 },
        SBE26plusDeviceCalibrationDataParticleKey.PC2: {TYPE: float, VALUE: 1.000000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PC3: {TYPE: float, VALUE: -1.024374e+03 },
        SBE26plusDeviceCalibrationDataParticleKey.PD1: {TYPE: float, VALUE:  2.928000e-02 },
        SBE26plusDeviceCalibrationDataParticleKey.PD2: {TYPE: float, VALUE: 0.000000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PT1: {TYPE: float, VALUE: 2.783369e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT2: {TYPE: float, VALUE: 6.072020e-01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT3: {TYPE: float, VALUE: 1.821885e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT4: {TYPE: float, VALUE: 2.790597e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.FACTORY_M: {TYPE: float, VALUE: 41943.0 },
        SBE26plusDeviceCalibrationDataParticleKey.FACTORY_B: {TYPE: float, VALUE: 2796.2 },
        SBE26plusDeviceCalibrationDataParticleKey.POFFSET: {TYPE: float, VALUE: -1.374000e-01 },
        SBE26plusDeviceCalibrationDataParticleKey.TCALDATE: {TYPE: list, VALUE: [2, 4, 2013] },
        SBE26plusDeviceCalibrationDataParticleKey.TA0: {TYPE: float, VALUE: 1.200000e-04 },
        SBE26plusDeviceCalibrationDataParticleKey.TA1: {TYPE: float, VALUE: 2.558000e-04 },
        SBE26plusDeviceCalibrationDataParticleKey.TA2: {TYPE: float, VALUE: -2.073449e-06 },
        SBE26plusDeviceCalibrationDataParticleKey.TA3: {TYPE: float, VALUE: 1.640089e-07 },
        SBE26plusDeviceCalibrationDataParticleKey.CCALDATE: {TYPE: list, VALUE: [28, 3, 2012], REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CG: {TYPE: float, VALUE: -1.025348e+01, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CH: {TYPE: float, VALUE: 1.557569e+00, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CI: {TYPE: float, VALUE: -1.737200e-03, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CJ: {TYPE: float, VALUE: 2.268000e-04, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CTCOR: {TYPE: float, VALUE: 3.250000e-06, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CPCOR: {TYPE: float, VALUE: -9.570000e-08, REQUIRED: False },
        SBE26plusDeviceCalibrationDataParticleKey.CSLOPE: {TYPE: float, VALUE: 1.000000e+00, REQUIRED: False }
    }

    _status_sample_parameters = {
        SBE26plusDeviceStatusDataParticleKey.DEVICE_VERSION: {TYPE: unicode, VALUE: u'6.1e' },
        SBE26plusDeviceStatusDataParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: u'1329' },
        SBE26plusDeviceStatusDataParticleKey.DS_DEVICE_DATE_TIME: {TYPE: unicode, VALUE: u'05 Oct 2012  17:19:27' },
        SBE26plusDeviceStatusDataParticleKey.USER_INFO: {TYPE: unicode, VALUE: u'ooi' },
        SBE26plusDeviceStatusDataParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER: {TYPE: float, VALUE: 122094 },
        SBE26plusDeviceStatusDataParticleKey.QUARTZ_PRESSURE_SENSOR_RANGE: {TYPE: float, VALUE: 300 },
        SBE26plusDeviceStatusDataParticleKey.EXTERNAL_TEMPERATURE_SENSOR: {TYPE: bool, VALUE: False },
        SBE26plusDeviceStatusDataParticleKey.CONDUCTIVITY: {TYPE: bool, VALUE: False },
        SBE26plusDeviceStatusDataParticleKey.IOP_MA: {TYPE: float, VALUE: 7.4 },
        SBE26plusDeviceStatusDataParticleKey.VMAIN_V: {TYPE: float, VALUE: 16.2 },
        SBE26plusDeviceStatusDataParticleKey.VLITH_V: {TYPE: float, VALUE: 9.0 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_P: {TYPE: float, VALUE: 14.5361 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_T: {TYPE: float, VALUE: 23.8155 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_S: {TYPE: float, VALUE: 0.0, REQUIRED: False},
        SBE26plusDeviceStatusDataParticleKey.TIDE_INTERVAL: {TYPE: int, VALUE: 3.0 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_MEASUREMENT_DURATION: {TYPE: int, VALUE: 60 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: {TYPE: int, VALUE: 6 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_SAMPLES_PER_BURST: {TYPE: int, VALUE: 512 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_SAMPLES_SCANS_PER_SECOND: {TYPE: float, VALUE: 4.0 },
        SBE26plusDeviceStatusDataParticleKey.USE_START_TIME: {TYPE: bool, VALUE: False },
        SBE26plusDeviceStatusDataParticleKey.USE_STOP_TIME: {TYPE: bool, VALUE: False },
        SBE26plusDeviceStatusDataParticleKey.TIDE_SAMPLES_PER_DAY: {TYPE: float, VALUE: 480.0 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_BURSTS_PER_DAY: {TYPE: float, VALUE: 80.0 },
        SBE26plusDeviceStatusDataParticleKey.MEMORY_ENDURANCE: {TYPE: float, VALUE: 258.0 },
        SBE26plusDeviceStatusDataParticleKey.NOMINAL_ALKALINE_BATTERY_ENDURANCE: {TYPE: float, VALUE: 272.8 },
        SBE26plusDeviceStatusDataParticleKey.TOTAL_RECORDED_TIDE_MEASUREMENTS: {TYPE: float, VALUE: 5982 },
        SBE26plusDeviceStatusDataParticleKey.TOTAL_RECORDED_WAVE_BURSTS: {TYPE: float, VALUE: 4525 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_MEASUREMENTS_SINCE_LAST_START: {TYPE: float, VALUE: 11 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_BURSTS_SINCE_LAST_START: {TYPE: float, VALUE: 1 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_SAMPLES_DURATION: {TYPE: int, VALUE: 128 },
        SBE26plusDeviceStatusDataParticleKey.TXREALTIME: {TYPE: bool, VALUE: True },
        SBE26plusDeviceStatusDataParticleKey.TXWAVEBURST: {TYPE: bool, VALUE: True },
        SBE26plusDeviceStatusDataParticleKey.TXWAVESTATS: {TYPE: bool, VALUE: True },
        SBE26plusDeviceStatusDataParticleKey.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: {TYPE: int, VALUE: 512, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC: {TYPE: bool, VALUE: False, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: {TYPE: float, VALUE: 10.0, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND: {TYPE: int, VALUE: 5, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.MIN_ALLOWABLE_ATTENUATION: {TYPE: float, VALUE: 0.0025, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.MIN_PERIOD_IN_AUTO_SPECTRUM: {TYPE: float, VALUE: 0.0e+00, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.MAX_PERIOD_IN_AUTO_SPECTRUM: {TYPE: float, VALUE: 1.0e+06, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.HANNING_WINDOW_CUTOFF: {TYPE: float, VALUE: 0.10, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.SHOW_PROGRESS_MESSAGES: {TYPE: bool, VALUE: True, REQUIRED: False },
        SBE26plusDeviceStatusDataParticleKey.STATUS: {TYPE: unicode, VALUE: u'stopped by user' },
        SBE26plusDeviceStatusDataParticleKey.LOGGING: {TYPE: bool, VALUE: False },
    }

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
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
        if (isinstance(data_particle, SBE26plusTideSampleDataParticle)):
            self.assert_particle_tide_sample(data_particle)
        elif (isinstance(data_particle, SBE26plusWaveBurstDataParticle)):
            self.assert_particle_wave_burst(data_particle)
        elif (isinstance(data_particle, SBE26plusStatisticsDataParticle)):
            self.assert_particle_statistics(data_particle)
        elif (isinstance(data_particle, SBE26plusDeviceCalibrationDataParticle)):
            self.assert_particle_device_calibration(data_particle)
        elif (isinstance(data_particle, SBE26plusDeviceStatusDataParticle)):
            self.assert_particle_device_status(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_tide_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.TIDE_PARSED)
        self.assert_data_particle_parameters(data_particle, self._tide_sample_parameters, verify_values)


    def assert_particle_wave_burst(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusWaveBurstDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.WAVE_BURST)
        self.assert_data_particle_parameters(data_particle, self._wave_sample_parameters, verify_values)

    def assert_particle_statistics(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusStatisticsDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.STATISTICS)
        self.assert_data_particle_parameters(data_particle, self._statistics_sample_parameters, verify_values)

    def assert_particle_device_calibration(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceCalibrationDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_sample_parameters, verify_values)

    def assert_particle_device_status(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_sample_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
# 1. Pick a single method within the class.                                   #
# 2. Create an instance of the class                                          #
# 3. If the method to be tested tries to call out, over-ride the offending    #
#    method with a mock                                                       #
# 4. Using above, try to cover all paths through the functions                #
# 5. Negative testing if at all possible.                                     #
###############################################################################
@attr('UNIT', group='mi')
class SeaBird26PlusUnitTest(SeaBirdUnitTest, SeaBird26PlusMixin):
    def setUp(self):
        SeaBirdUnitTest.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TIDE_DATA_POLLED)

        self.assert_chunker_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TIDE_DATA)

        self.assert_chunker_sample(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_WAVE_BURST, 1024)
        self.assert_chunker_combined_sample(chunker, SAMPLE_WAVE_BURST)

        self.assert_chunker_sample(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_STATISTICS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_STATISTICS)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_CALIBRATION, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_CALIBRATION)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_STATUS) 
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_STATUS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_STATUS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_STATUS)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_TIDE_DATA, self.assert_particle_tide_sample, True)
        self.assert_particle_published(driver, SAMPLE_TIDE_DATA_POLLED, self.assert_particle_tide_sample, True)
        self.assert_particle_published(driver, SAMPLE_WAVE_BURST, self.assert_particle_wave_burst, True)
        self.assert_particle_published(driver, SAMPLE_STATISTICS, self.assert_particle_statistics, True)
        self.assert_particle_published(driver, SAMPLE_DEVICE_CALIBRATION, self.assert_particle_device_calibration, True)
        self.assert_particle_published(driver, SAMPLE_DEVICE_STATUS, self.assert_particle_device_status, True)


    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))


    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))

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
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_ACQUIRE_CONFIGURATION',
                                    'PROTOCOL_EVENT_QUIT_SESSION',
                                    'PROTOCOL_EVENT_SETSAMPLING'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_SEND_LAST_SAMPLE',
                                       'PROTOCOL_EVENT_ACQUIRE_CONFIGURATION',
                                       'DRIVER_EVENT_ACQUIRE_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
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
class SeaBird26PlusIntegrationTest(SeaBirdIntegrationTest, SeaBird26PlusMixin):
    def setUp(self):
        SeaBirdIntegrationTest.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    # PASSES
    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        # The clock in this instrument is a little odd.  It looks like if you wait until the edge of a second
        # to set it, it immediately ticks after the set, making it off by 1.  For now we will accept this
        # behavior, but we need to check this behavior on all SBE instruments.
        # @todo Revisit clock sync across SBE instruments
        set_time = get_timestamp_delayed("%d %b %Y  %H:%M:%S")
        # One second later
        expected_time = get_timestamp_delayed("%d %b %Y  %H:%M:%S")
        self.assert_set(Parameter.DS_DEVICE_DATE_TIME, set_time, no_get=True)
        self.assert_get(Parameter.DS_DEVICE_DATE_TIME, expected_time.upper())

        ###
        #   Instrument Parameteres
        ###
        self.assert_set(Parameter.USER_INFO, 'iontest'.upper())

        ###
        #   Set Sample Parameters
        ###
        # Tested in test_set_sampling method

        ###
        #   Read only parameters
        ###
        self.assert_set_readonly(Parameter.DEVICE_VERSION)
        self.assert_set_readonly(Parameter.SERIAL_NUMBER)
        self.assert_set_readonly(Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER)
        self.assert_set_readonly(Parameter.QUARTZ_PRESSURE_SENSOR_RANGE)
        self.assert_set_readonly(Parameter.EXTERNAL_TEMPERATURE_SENSOR)
        self.assert_set_readonly(Parameter.CONDUCTIVITY)
        self.assert_set_readonly(Parameter.IOP_MA)
        self.assert_set_readonly(Parameter.VMAIN_V)
        self.assert_set_readonly(Parameter.VLITH_V)
        self.assert_set_readonly(Parameter.LAST_SAMPLE_P)
        self.assert_set_readonly(Parameter.LAST_SAMPLE_T)
        self.assert_set_readonly(Parameter.LAST_SAMPLE_S)
        self.assert_set_readonly(Parameter.TXREALTIME)
        self.assert_set_readonly(Parameter.TXWAVEBURST)
        self.assert_set_readonly(Parameter.SHOW_PROGRESS_MESSAGES)
        self.assert_set_readonly(Parameter.STATUS)
        self.assert_set_readonly(Parameter.LOGGING)
    def test_set_sampling(self):
        """
        @brief Test device setsampling.

        setsampling functionality now handled via set.  Below test converted to use set.
        This tests assumes Conductivity is set to false as described in the IOS, we verify
        this, but don't set it because this is a startup parameter.

        Test setting parameters, including bad parameter tests, for all parameters in the set
        sampling when txwavestats is set to false.

        Parameter set:
        * Tide interval (integer minutes)
            - Range 17 - 720
                *NOTE* TIDE INTERVAL WILL BE RESET TO:
                (Number of wave samples per burst) * (wave sample duration) + 10 sec + calculation time
                if not already larger....

        * Tide measurement duration (seconds)
            - Range: 10 - 1020 sec
        * Measure wave burst after every N tide samples
            - Range 1 - 10,000
        * Number of wave samples per burst
            - Range 4 - 60,000
        * wave sample duration
            - Range [0.25, 0.5, 0.75, 1.0]
        * use start time - Not set, driver hard codes to false
            - Range [y, n]
        * use stop time - Not set, driver hard codes to false
            - Range [y, n]
        * TXWAVESTATS (real-time wave statistics)
            - Set to False for this test
        """
        self.assert_initialize_driver()
        self.assert_get(Parameter.CONDUCTIVITY, False)

        #1: TXWAVESTATS = N, CONDUCTIVITY = N
        self.assert_set_sampling_no_txwavestats()

        #2: TXWAVESTATS = Y, CONDUCTIVITY = N
        self.assert_set_sampling_txwavestats_dont_use_conductivity()  

    def set_baseline_no_txwavestats(self):
        sampling_params = {
            Parameter.CONDUCTIVITY: False,
            Parameter.TIDE_INTERVAL: 18,
            Parameter.TIDE_MEASUREMENT_DURATION: 60,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 6000,
            Parameter.WAVE_SAMPLES_PER_BURST: 4,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND: 4.0,
            Parameter.TXWAVESTATS: False
        }
        # Set all parameters to a known ground state
        self.assert_set_bulk(sampling_params)
        return sampling_params

    def assert_set_sampling_no_txwavestats(self):
        log.debug("setsampling Test 1 - TXWAVESTATS = N.")
        
        # First tests to verify we can set all parameters properly
        sampling_params = self.set_baseline_no_txwavestats()

        # Tide interval parameter.  Check edges, out of range and invalid data
        #    * Tide interval (integer minutes)
        #        - Range 17 - 720
        sampling_params[Parameter.TIDE_INTERVAL] = 17
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 720
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 16
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 721
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 18
        
        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()
        
        # Tide measurement duration.  Check edges, out of range and invalid data
        #    * Tide measurement duration (seconds)
        #        - Range: 10 - 1020 sec
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1020
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 9
        self.assert_set_bulk_exception(sampling_params)
        # apparently NOT and edge case...
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1021
        #self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 60
        
        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()

        # Tide samples between wave bursts.  Check edges, out of range and invalid data
        #   * Measure wave burst after every N tide samples
        #       - Range 1 - 10,000
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 1
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10001
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 6000
        
        # Wave samples per burst.  Check edges, out of range and invalid data
        #   * Number of wave samples per burst
        #       - Range 4 - 60,000 *MUST BE MULTIPLE OF 4*
        # Test a good value
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 1000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43200   # If we set this this high
        sampling_params[Parameter.TIDE_INTERVAL] = 181              # ... we need to set
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10860# ... we need to set
        self.assert_set_bulk(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()

        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 9
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43201
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = -1
        self.assert_set_bulk_exception(sampling_params)

        #    * wave scans per second
        #        - Range [4, 2, 1.33, 1]
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 2.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.33
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.0
        self.assert_set_bulk(sampling_params)

        # test bad values
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 3
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 5
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4
        self.assert_set_bulk_exception(sampling_params)
           
    def set_baseline_txwavestats_dont_use_conductivity(self):
        sampling_params = {
            Parameter.CONDUCTIVITY: False,
            Parameter.TIDE_INTERVAL: 18,
            Parameter.TIDE_MEASUREMENT_DURATION: 60,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 8,
            Parameter.WAVE_SAMPLES_PER_BURST: 512,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND: 4.0,
            Parameter.TXWAVESTATS: True,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC: False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR: 15.0,
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR: 35.0,        
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND: 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION: 1.0000,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM: 0.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM: 1.0,
            Parameter.HANNING_WINDOW_CUTOFF: 1.0
        }
        # Set all parameters to a known ground state
        self.assert_set_bulk(sampling_params)
        return sampling_params
    
    def assert_set_sampling_txwavestats_dont_use_conductivity(self):
        log.debug("setsampling Test 2 - TXWAVESTATS = Y. CONDUCTIVITY = N")
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -274.0 # -1 Kelvin?
        self.assert_set_bulk(sampling_params)    
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -273.0 # 0 Kelvin?
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -100.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -30.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -1.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 0.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 30.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 100.0 # if it gets hotter than this, we are likely all dead...
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 500.0 # 500 C getting warmer
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 32767.0 # 32767 C, it's a dry heat
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = True
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = int(1)
        self.assert_set_bulk_exception(sampling_params)
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 35.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = True
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = int(1)
        self.assert_set_bulk_exception(sampling_params)
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide interval parameter.  Check edges, out of range and invalid data
        #    * Tide interval (integer minutes)
        #        - Range 3 - 720
        sampling_params[Parameter.TIDE_INTERVAL] = 3
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 720
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 2
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 721
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide measurement duration.  Check edges, out of range and invalid data
        #    * Tide measurement duration (seconds)
        #        - Range: 10 - 1020 sec
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10 # <--- was 60, should have been 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1020
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 9
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1021
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide samples between wave bursts.  Check edges, out of range and invalid data
        #   * Measure wave burst after every N tide samples
        #       - Range 1 - 10,000
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 1
        self.assert_set_bulk(sampling_params) # in wakeup.
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10001
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 6000

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Test a good value
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 1000
        self.assert_set_bulk(sampling_params)

        # Wave samples per burst.  Check edges, out of range and invalid data
        #   * Number of wave samples per burst
        #       - Range 4 - 60,000 *MUST BE MULTIPLE OF 4*
        sampling_params[Parameter.TIDE_INTERVAL] = 720              # required for 60000
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 60000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 36000   # If we set this this high
        sampling_params[Parameter.TIDE_INTERVAL] = 720              # ... we need to set <--- was 1001
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10860# ... we need to set
        self.assert_set_bulk(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        # 512 - 60,000 in multiple of 4
        
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 3
        self.assert_set_bulk_exception(sampling_params)     
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4      
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 508      
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 511     
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43201
        self.assert_set_bulk_exception(sampling_params)
        
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 60001
        self.assert_set_bulk_exception(sampling_params)           
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = "bar"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        
        # Wave samples per burst.  Check edges, out of range and invalid data
        #    * wave sample duration=
        #        - Range [0.25, 0.5, 0.75, 1.0]
        
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 2.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.33
        self.assert_set_bulk(sampling_params)                           
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.0
        self.assert_set_bulk(sampling_params)
        
        # test bad values
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 3
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 5
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = False
        self.assert_set_bulk_exception(sampling_params)
       
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = False
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = True
        self.assert_set_bulk(sampling_params)
        
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = 1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = float(1.0)
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = "bar"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = -1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 0
        self.assert_set_bulk(sampling_params)
        
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 100000
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 10.0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = "car"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 0.0025
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = "tar"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = True
        self.assert_set_bulk_exception(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM] = float(0.0001)
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = "far"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # The manual only shows 0.10 as a value (assert float)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 0.0
        self.assert_set_bulk(sampling_params)
        # Rounds to 0.00
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = float(0.0001) 
        self.assert_set_bulk_exception(sampling_params)
        # Rounds to 0.01
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = float(0.006) 
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = "far"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = False
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()

        ####
        # First test in command mode
        ####
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE, regex=r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)')
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'SBE 26plus')
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_CONFIGURATION, regex=r'Pressure coefficients')
        self.assert_driver_command_exception(ProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.QUIT_SESSION)

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_driver_command_exception(ProtocolEvent.START_AUTOSAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.ACQUIRE_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'SBE 26plus')
        self.assert_driver_command(ProtocolEvent.ACQUIRE_CONFIGURATION, regex=r'Pressure coefficients')
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex=r'p = +([\-\d.]+), t = +([\-\d.]+)')
        self.assert_driver_command_exception(ProtocolEvent.QUIT_SESSION, exception_class=InstrumentCommandException)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.TIDE_PARSED, self.assert_particle_tide_sample)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_device_status)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_device_calibration)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        self.assert_initialize_driver()

        params = {
            Parameter.TIDE_INTERVAL: 3,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 2,
            Parameter.TXWAVEBURST: True,
            Parameter.TXWAVESTATS: True
        }
        self.assert_set_bulk(params)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.TIDE_PARSED, self.assert_particle_tide_sample, timeout=120)
        self.assert_async_particle_generation(DataParticleType.WAVE_BURST, self.assert_particle_wave_burst, timeout=300)
        self.assert_async_particle_generation(DataParticleType.STATISTICS, self.assert_particle_statistics, timeout=300)

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run first.
        """
        self.assert_initialize_driver()

        self.assert_get(Parameter.TXWAVESTATS, False)
        self.assert_get(Parameter.TXREALTIME, True)
        self.assert_get(Parameter.TXWAVEBURST, False)

        # Now change them so they are caught and see if they are caught
        # on the second pass.
        self.assert_set(Parameter.TXWAVESTATS, True)
        self.assert_set(Parameter.TXREALTIME, False)
        self.assert_set(Parameter.TXWAVEBURST, True)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_initialize_driver()

        self.assert_get(Parameter.TXWAVESTATS, False)
        self.assert_get(Parameter.TXREALTIME, True)
        self.assert_get(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set(Parameter.TXWAVESTATS, True)
        self.assert_set(Parameter.TXREALTIME, False)
        self.assert_set(Parameter.TXWAVEBURST, True)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class SeaBird26PlusQualificationTest(SeaBirdQualificationTest, SeaBird26PlusMixin):
    def setUp(self):
        SeaBirdQualificationTest.setUp(self)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_enter_command_mode()

        params = {
            Parameter.TIDE_INTERVAL: 3,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 2,
            Parameter.TXWAVEBURST: True,
            Parameter.TXWAVESTATS: True
        }
        self.instrument_agent_client.set_resource(params)

        self.assert_start_autosample()

        self.assert_sample_async(self.assert_particle_tide_sample, DataParticleType.TIDE_PARSED, timeout=120, sample_count=1)
        self.assert_sample_async(self.assert_particle_wave_burst, DataParticleType.WAVE_BURST, timeout=300, sample_count=1)
        self.assert_sample_async(self.assert_particle_statistics, DataParticleType.STATISTICS, timeout=300, sample_count=1)

        # Verify we can generate status and config particles while streaming
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_device_status, DataParticleType.DEVICE_STATUS)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_CONFIGURATION, self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION)

        self.assert_stop_autosample()

    def test_poll(self):
        '''
        Verify that we can poll for a sample.  Take sample for this instrument
        Also poll for other engineering data streams.
        '''
        self.assert_enter_command_mode()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_tide_sample, DataParticleType.TIDE_PARSED)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_device_status, DataParticleType.DEVICE_STATUS, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_CONFIGURATION, self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION, sample_count=1)

    def test_direct_access_telnet_mode(self):
        """
        Test that we can connect to the instrument via direct access.  Also
        verify that direct access parameters are reset on exit.
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.TXREALTIME, True)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("TxTide=N\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.TXREALTIME, True)

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
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            AgentCapabilityType.AGENT_PARAMETER: ['example'],
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.ACQUIRE_SAMPLE,
                DriverEvent.START_AUTOSAMPLE,
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.ACQUIRE_CONFIGURATION,
                ProtocolEvent.SETSAMPLING,
                ProtocolEvent.QUIT_SESSION
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ ResourceAgentEvent.RESET, ResourceAgentEvent.GO_INACTIVE ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.SEND_LAST_SAMPLE,
            ProtocolEvent.ACQUIRE_CONFIGURATION
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

    def assert_clock_sync(self):
        """
        verify that the date is set correctly on the instrument
        """
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_STATUS)

        # Now verify that at least the date matches
        params = [Parameter.DS_DEVICE_DATE_TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        log.debug("TIME: %s && %s" % (lt, check_new_params[Parameter.DS_DEVICE_DATE_TIME]))
        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.DS_DEVICE_DATE_TIME].upper())

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        # wait for a bit so the event can be triggered
        time.sleep(3)

        # Set the clock to something in the past
        self.assert_set_parameter(Parameter.DS_DEVICE_DATE_TIME, "01 Jan 2001 01:01:01", verify=False)

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_clock_sync()

    @unittest.skip('needs base class update')
    def test_scheduled_clock_sync(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_enter_command_mode()
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, self.assert_clock_sync)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.assert_sample_async(self.assert_particle_device_status, DataParticleType.DEVICE_STATUS, timeout=30, sample_count=1)

    @unittest.skip('needs base class update')
    def test_scheduled_device_status(self):
        """
        Verify the device status command can be triggered and run in both command
        and streaming mode.
        """
        self.assert_enter_command_mode()
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status)

    def assert_calibration_coefficients(self):
        """
        Verify a calibration particle was generated
        """
        self.assert_sample_async(self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION, timeout=30, sample_count=1)

    @unittest.skip('needs base class update')
    def test_scheduled_device_configuration(self):
        """
        Verify the device configuration command can be triggered and run in both command
        and streaming mode.
        """
        self.assert_enter_command_mode()
        self.assert_scheduled_event(ScheduledJob.CALIBRATION_COEFFICIENTS, self.assert_calibration_coefficients)

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.TXWAVESTATS, False)
        self.assert_get_parameter(Parameter.TXREALTIME, True)
        self.assert_get_parameter(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.TXWAVESTATS, True)
        self.assetert_set_parameter(Parameter.TXREALTIME, False)
        self.assetert_set_parameter(Parameter.TXWAVEBURST, True)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.TXWAVESTATS, False)
        self.assert_get_parameter(Parameter.TXREALTIME, True)
        self.assert_get_parameter(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.TXWAVESTATS, True)
        self.assetert_set_parameter(Parameter.TXREALTIME, False)
        self.assetert_set_parameter(Parameter.TXWAVEBURST, True)