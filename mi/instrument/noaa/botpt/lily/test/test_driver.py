"""
@package mi.instrument.noaa.lily.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/lily/ooicore/driver.py
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
from mi.core.common import BaseEnum
from mi.instrument.noaa.botpt.driver import BotptStatus01ParticleKey, BotptStatus01Particle

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import time

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

from mi.instrument.noaa.botpt.lily.driver import InstrumentDriver, LILYStatus02ParticleKey, LILYStatus02Particle
from mi.instrument.noaa.botpt.lily.driver import DataParticleType
from mi.instrument.noaa.botpt.lily.driver import LILYDataParticleKey
from mi.instrument.noaa.botpt.lily.driver import LILYDataParticle
from mi.instrument.noaa.botpt.lily.driver import InstrumentCommand
from mi.instrument.noaa.botpt.lily.driver import ProtocolState
from mi.instrument.noaa.botpt.lily.driver import ProtocolEvent
from mi.instrument.noaa.botpt.lily.driver import Capability
from mi.instrument.noaa.botpt.lily.driver import Parameter
from mi.instrument.noaa.botpt.lily.driver import Protocol
from mi.instrument.noaa.botpt.lily.driver import NEWLINE
from mi.instrument.noaa.botpt.lily.driver import LILY_COMMAND_STRING
from mi.instrument.noaa.botpt.lily.driver import LILY_DATA_ON
from mi.instrument.noaa.botpt.lily.driver import LILY_DATA_OFF
from mi.instrument.noaa.botpt.lily.driver import LILY_DUMP_01
from mi.instrument.noaa.botpt.lily.driver import LILY_DUMP_02
from mi.instrument.noaa.botpt.lily.driver import LILY_LEVEL_ON
from mi.instrument.noaa.botpt.lily.driver import LILY_LEVEL_OFF
from mi.instrument.noaa.botpt.lily.driver import DEFAULT_MAX_XTILT
from mi.instrument.noaa.botpt.lily.driver import DEFAULT_MAX_YTILT
from mi.instrument.noaa.botpt.lily.driver import DEFAULT_LEVELING_TIMEOUT

from mi.core.exceptions import SampleException, InstrumentDataException
from pyon.agent.agent import ResourceAgentState

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.lily.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_lily_ooicore',
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
VALID_SAMPLE_01 = "LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655" + NEWLINE
VALID_SAMPLE_02 = "LILY,2013/06/24 23:36:04,-235.349,  26.082,194.26, 26.04,11.96,N9655" + NEWLINE

DATA_ON_COMMAND_RESPONSE = "LILY,2013/05/29 00:23:34," + LILY_COMMAND_STRING + LILY_DATA_ON + NEWLINE
DATA_OFF_COMMAND_RESPONSE = "LILY,2013/05/29 00:23:34," + LILY_COMMAND_STRING + LILY_DATA_OFF + NEWLINE
DUMP_01_COMMAND_RESPONSE = "LILY,2013/05/29 00:22:57," + LILY_COMMAND_STRING + LILY_DUMP_01 + NEWLINE
DUMP_02_COMMAND_RESPONSE = "LILY,2013/05/29 00:23:34," + LILY_COMMAND_STRING + LILY_DUMP_02 + NEWLINE
START_LEVELING_COMMAND_RESPONSE = "LILY,2013/05/29 00:23:34," + LILY_COMMAND_STRING + LILY_LEVEL_ON + NEWLINE
STOP_LEVELING_COMMAND_RESPONSE = "LILY,2013/05/29 00:23:34," + LILY_COMMAND_STRING + LILY_LEVEL_OFF + NEWLINE

BOTPT_FIREHOSE_01 = "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
BOTPT_FIREHOSE_01 += "IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
BOTPT_FIREHOSE_01 += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE

BOTPT_FIREHOSE_02 = "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_02 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
BOTPT_FIREHOSE_02 += "LILY,2013/06/24 22:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655" + NEWLINE
BOTPT_FIREHOSE_02 += "IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
BOTPT_FIREHOSE_02 += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_02 += "LILY,2013/06/24 23:36:02,-235.500,  25.930,194.30, 26.04,11.96,N9655" + NEWLINE
BOTPT_FIREHOSE_02 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE

DUMP_01_STATUS = \
    "LILY,2013/06/24 23:35:41,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9655 ID01" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Vbias= 0.0000 0.0000 0.0000 0.0000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Vgain= 0.0000 0.0000 0.0000 0.0000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Vmin:  -2.50  -2.50   2.50   2.50" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Vmax:   2.50   2.50   2.50   2.50" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: N_SAMP= 360 Xzero=  0.00 Yzero=  0.00" + NEWLINE + \
    "LILY,2013/06/24 23:35:41,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-" + NEWLINE

DUMP_02_STATUS = \
    "LILY,2013/06/24 23:36:05,*01: TBias: 5.00" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: ADCDelay:  310" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: PCA Model: 84833-14" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Firmware Version: 2.1 Rev D" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Calibrated in uRadian, Current Output Mode: uRadian" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Using RS232" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Real Time Clock: Installed" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Use RTC for Timing: Yes" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: External Flash: 2162688 Bytes Installed" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Flash Status (in Samples) (Used/Total): (-1/55424)" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Low Power Logger Data Rate: -1 Seconds per Sample" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Calibration method: Dynamic " + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Positive Limit=330.00   Negative Limit=-330.00 " + NEWLINE + \
    "IRIS,2013/06/24 23:36:05, -0.0680, -0.3284,28.07,N3616" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Calibration Points:023  X: Enabled  Y: Enabled" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Uniaxial (x2) Sensor Type (1)" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: ADC: 16-bit(external)" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Compass: Installed   Magnetic Declination: 0.000000" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Compass: Xoffset:   12, Yoffset:  210, Xrange: 1371, Yrange: 1307" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Motor I_limit: 90.0mA" + NEWLINE + \
    "LILY,2013/06/24 23:36:05,*01: Current Time: 01/11/00 02:12:32" + NEWLINE + \
    "LILY,2013/06/24 23:36:06,*01: Supply Voltage: 11.96 Volts" + NEWLINE + \
    "LILY,2013/06/24 23:36:06,*01: Memory Save Mode: Off" + NEWLINE + \
    "LILY,2013/06/24 23:36:06,*01: Outputting Data: Yes" + NEWLINE + \
    "LILY,2013/06/24 23:36:06,*01: Auto Power-Off Recovery Mode: Off" + NEWLINE + \
    "LILY,2013/06/24 23:36:06,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No" + NEWLINE

LEVELING_STATUS = \
    "LILY,2013/07/24 20:36:27,*  14.667,  81.642,185.21, 33.67,11.59,N9651" + NEWLINE

LEVELED_STATUS = \
    "LILY,2013/06/28 17:29:21,*  -2.277,  -2.165,190.81, 25.69,,Leveled!11.87,N9651" + NEWLINE

SWITCHING_STATUS = \
    "LILY,2013/06/28 18:04:41,*  -7.390, -14.063,190.91, 25.83,,Switching to Y!11.87,N9651"

X_OUT_OF_RANGE = \
    "LILY,2013/03/22 19:07:28,*-330.000,-330.000,185.45, -6.45,,X Axis out of range, switching to Y!11.37,N9651"

Y_OUT_OF_RANGE = \
    "LILY,2013/03/22 19:07:29,*-330.000,-330.000,184.63, -6.43,,Y Axis out of range!11.34,N9651"

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
class LILYTestMixinSub(DriverTestMixin):
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
        Parameter.AUTO_RELEVEL: {TYPE: bool, READONLY: False, DA: False, STARTUP: False},
    }

    _sample_parameters_01 = {
        LILYDataParticleKey.TIME: {TYPE: float, VALUE: 3581130962.0, REQUIRED: True},
        LILYDataParticleKey.X_TILT: {TYPE: float, VALUE: -235.500, REQUIRED: True},
        LILYDataParticleKey.Y_TILT: {TYPE: float, VALUE: 25.930, REQUIRED: True},
        LILYDataParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 194.30, REQUIRED: True},
        LILYDataParticleKey.TEMP: {TYPE: float, VALUE: 26.04, REQUIRED: True},
        LILYDataParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.96, REQUIRED: True},
        LILYDataParticleKey.SN: {TYPE: unicode, VALUE: 'N9655', REQUIRED: True},
        LILYDataParticleKey.OUT_OF_RANGE: {TYPE: bool, VALUE: False, REQUIRED: True}
    }

    _sample_parameters_02 = {
        LILYDataParticleKey.TIME: {TYPE: float, VALUE: 3581130964.0, REQUIRED: True},
        LILYDataParticleKey.X_TILT: {TYPE: float, VALUE: -235.349, REQUIRED: True},
        LILYDataParticleKey.Y_TILT: {TYPE: float, VALUE: 26.082, REQUIRED: True},
        LILYDataParticleKey.MAG_COMPASS: {TYPE: float, VALUE: 194.26, REQUIRED: True},
        LILYDataParticleKey.TEMP: {TYPE: float, VALUE: 26.04, REQUIRED: True},
        LILYDataParticleKey.SUPPLY_VOLTS: {TYPE: float, VALUE: 11.96, REQUIRED: True},
        LILYDataParticleKey.SN: {TYPE: unicode, VALUE: 'N9655', REQUIRED: True},
        LILYDataParticleKey.OUT_OF_RANGE: {TYPE: bool, VALUE: False, REQUIRED: True}
    }

    _status_01_parameters = {
        BotptStatus01ParticleKey.TIME: {TYPE: float, VALUE: 3581130941.0, REQUIRED: True},
        BotptStatus01ParticleKey.MODEL: {TYPE: unicode, VALUE: u'LILY', REQUIRED: True},
        BotptStatus01ParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: u'V2.1', REQUIRED: True},
        BotptStatus01ParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: u'SN-N9655', REQUIRED: True},
        BotptStatus01ParticleKey.ID_NUMBER: {TYPE: unicode, VALUE: u'ID01', REQUIRED: True},
        BotptStatus01ParticleKey.VBIAS: {TYPE: list, VALUE: [0.0] * 4, REQUIRED: True},
        BotptStatus01ParticleKey.VGAIN: {TYPE: list, VALUE: [0.0] * 4, REQUIRED: True},
        BotptStatus01ParticleKey.VMIN: {TYPE: list, VALUE: [-2.5] * 2 + [2.5] * 2, REQUIRED: True},
        BotptStatus01ParticleKey.VMAX: {TYPE: list, VALUE: [2.5] * 4, REQUIRED: True},
        BotptStatus01ParticleKey.AVALS_0: {TYPE: list, VALUE: [0.0] * 6, REQUIRED: True},
        BotptStatus01ParticleKey.AVALS_1: {TYPE: list, VALUE: [0.0] * 6, REQUIRED: True},
        BotptStatus01ParticleKey.AVALS_2: {TYPE: list, VALUE: [0.0] * 6, REQUIRED: True},
        BotptStatus01ParticleKey.AVALS_3: {TYPE: list, VALUE: [0.0] * 6, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF0_KS: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF0_KZ: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF0_TCAL: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF1_KS: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF1_KZ: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.TCOEF1_TCAL: {TYPE: int, VALUE: 0, REQUIRED: True},
        BotptStatus01ParticleKey.N_SAMP: {TYPE: int, VALUE: 360, REQUIRED: True},
        BotptStatus01ParticleKey.XZERO: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        BotptStatus01ParticleKey.YZERO: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        BotptStatus01ParticleKey.BAUD: {TYPE: int, VALUE: 19200, REQUIRED: True},
    }

    _status_02_parameters = {
        LILYStatus02ParticleKey.TIME: {TYPE: float, VALUE: 3581130965.0, REQUIRED: True},
        LILYStatus02ParticleKey.TBIAS: {TYPE: float, VALUE: 5.0, REQUIRED: True},
        LILYStatus02ParticleKey.ABOVE: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        LILYStatus02ParticleKey.BELOW: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        LILYStatus02ParticleKey.KZVALS: {TYPE: list, VALUE: [0] * 4, REQUIRED: True},
        LILYStatus02ParticleKey.ADC_DELAY: {TYPE: int, VALUE: 310, REQUIRED: True},
        LILYStatus02ParticleKey.PCA_MODEL: {TYPE: unicode, VALUE: u'84833-14', REQUIRED: True},
        LILYStatus02ParticleKey.FIRMWARE_REV: {TYPE: unicode, VALUE: u'2.1 Rev D', REQUIRED: True},
        LILYStatus02ParticleKey.XCHAN_GAIN: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        LILYStatus02ParticleKey.YCHAN_GAIN: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        LILYStatus02ParticleKey.TEMP_GAIN: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        LILYStatus02ParticleKey.CAL_MODE: {TYPE: unicode, VALUE: u'uRadian', REQUIRED: True},
        LILYStatus02ParticleKey.OUTPUT_MODE: {TYPE: unicode, VALUE: u'uRadian', REQUIRED: True},
        LILYStatus02ParticleKey.RS232: {TYPE: unicode, VALUE: u'RS232', REQUIRED: True},
        LILYStatus02ParticleKey.RTC_INSTALLED: {TYPE: unicode, VALUE: u'Installed', REQUIRED: True},
        LILYStatus02ParticleKey.RTC_TIMING: {TYPE: unicode, VALUE: u'Yes', REQUIRED: True},
        LILYStatus02ParticleKey.EXT_FLASH_CAPACITY: {TYPE: int, VALUE: 2162688, REQUIRED: True},
        LILYStatus02ParticleKey.USED_SAMPLES: {TYPE: int, VALUE: -1, REQUIRED: True},
        LILYStatus02ParticleKey.TOTAL_SAMPLES: {TYPE: int, VALUE: 55424, REQUIRED: True},
        LILYStatus02ParticleKey.LOW_POWER_RATE: {TYPE: int, VALUE: -1, REQUIRED: True},
        LILYStatus02ParticleKey.CAL_METHOD: {TYPE: unicode, VALUE: u'Dynamic', REQUIRED: True},
        LILYStatus02ParticleKey.POS_LIMIT: {TYPE: float, VALUE: 330.0, REQUIRED: True},
        LILYStatus02ParticleKey.NEG_LIMIT: {TYPE: float, VALUE: -330.0, REQUIRED: True},
        LILYStatus02ParticleKey.NUM_CAL_POINTS: {TYPE: int, VALUE: 23, REQUIRED: True},
        LILYStatus02ParticleKey.CAL_POINTS_X: {TYPE: unicode, VALUE: u'Enabled', REQUIRED: True},
        LILYStatus02ParticleKey.CAL_POINTS_Y: {TYPE: unicode, VALUE: u'Enabled', REQUIRED: True},
        LILYStatus02ParticleKey.SENSOR_TYPE: {TYPE: unicode, VALUE: u'Uniaxial (x2) Sensor Type (1)', REQUIRED: True},
        LILYStatus02ParticleKey.ADC_TYPE: {TYPE: unicode, VALUE: u'16-bit(external)', REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_INSTALLED: {TYPE: unicode, VALUE: u'Installed', REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_MAG_DECL: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_XOFFSET: {TYPE: int, VALUE: 12, REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_YOFFSET: {TYPE: int, VALUE: 210, REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_XRANGE: {TYPE: int, VALUE: 1371, REQUIRED: True},
        LILYStatus02ParticleKey.COMPASS_YRANGE: {TYPE: int, VALUE: 1307, REQUIRED: True},
        LILYStatus02ParticleKey.PID_IMAX: {TYPE: float, VALUE: 100.0, REQUIRED: True},
        LILYStatus02ParticleKey.PID_IMIN: {TYPE: float, VALUE: -100.0, REQUIRED: True},
        LILYStatus02ParticleKey.PID_IGAIN: {TYPE: float, VALUE: 0.015, REQUIRED: True},
        LILYStatus02ParticleKey.PID_PGAIN: {TYPE: float, VALUE: 2.5, REQUIRED: True},
        LILYStatus02ParticleKey.PID_DGAIN: {TYPE: float, VALUE: 10.0, REQUIRED: True},
        LILYStatus02ParticleKey.MOTOR_ILIMIT: {TYPE: float, VALUE: 90.0, REQUIRED: True},
        LILYStatus02ParticleKey.MOTOR_ILIMIT_UNITS: {TYPE: unicode, VALUE: u'mA', REQUIRED: True},
        LILYStatus02ParticleKey.SUPPLY_VOLTAGE: {TYPE: float, VALUE: 11.96, REQUIRED: True},
        LILYStatus02ParticleKey.MEM_SAVE_MODE: {TYPE: unicode, VALUE: u'Off', REQUIRED: True},
        LILYStatus02ParticleKey.OUTPUTTING_DATA: {TYPE: unicode, VALUE: u'Yes', REQUIRED: True},
        LILYStatus02ParticleKey.RECOVERY_MODE: {TYPE: unicode, VALUE: u'Off', REQUIRED: True},
        LILYStatus02ParticleKey.ADV_MEM_MODE: {TYPE: unicode, VALUE: u'Off', REQUIRED: True},
        LILYStatus02ParticleKey.DEL_W_XYMEMD: {TYPE: unicode, VALUE: u'No', REQUIRED: True},

    }

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

    def assert_particle_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, DataParticleType.LILY_PARSED,
                             LILYDataParticleKey, self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, DataParticleType.LILY_PARSED,
                             LILYDataParticleKey, self._sample_parameters_02, verify_values)

    def assert_particle_status_01(self, status_particle, verify_values=False):
        self.assert_particle(status_particle, DataParticleType.LILY_STATUS_01,
                             BotptStatus01ParticleKey, self._status_01_parameters, verify_values)

    def assert_particle_status_02(self, status_particle, verify_values=False):
        self.assert_particle(status_particle, DataParticleType.LILY_STATUS_02,
                             LILYStatus02ParticleKey, self._status_02_parameters, verify_values)


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
# noinspection PyProtectedMember,PyUnusedLocal
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, LILYTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    @staticmethod
    def my_send(driver):
        def inner(data):
            if data.startswith(InstrumentCommand.DATA_ON):
                my_response = DATA_ON_COMMAND_RESPONSE
            elif data.startswith(InstrumentCommand.DATA_OFF):
                my_response = DATA_OFF_COMMAND_RESPONSE
            elif data.startswith(InstrumentCommand.DUMP_SETTINGS_01):
                my_response = DUMP_01_COMMAND_RESPONSE
            elif data.startswith(InstrumentCommand.DUMP_SETTINGS_02):
                my_response = DUMP_02_COMMAND_RESPONSE
            elif data.startswith(InstrumentCommand.START_LEVELING):
                my_response = START_LEVELING_COMMAND_RESPONSE
            elif data.startswith(InstrumentCommand.STOP_LEVELING):
                my_response = STOP_LEVELING_COMMAND_RESPONSE
            else:
                my_response = None
            if my_response is not None:
                log.debug("my_send: data: %s, my_response: %s", data, my_response)
                driver._protocol._promptbuf += my_response
                return len(my_response)

        return inner

    def _send_port_agent_packet(self, driver, data):
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(self.get_ntp_timestamp())
        port_agent_packet.pack_header()
        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Test driver can change state to COMMAND
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        return driver

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

        # Test capabilities for duplicates, then verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        for sample in [LEVELED_STATUS, VALID_SAMPLE_01, VALID_SAMPLE_02, DUMP_01_STATUS, DUMP_02_STATUS]:
            self.assert_chunker_sample(chunker, sample)
            self.assert_chunker_fragmented_sample(chunker, sample)
            self.assert_chunker_combined_sample(chunker, sample)
            self.assert_chunker_sample_with_noise(chunker, sample)

    def test_get_handler(self):
        driver = self.test_connect()
        for param in Parameter.list():
            result = driver._protocol._handler_get([param])
            result_dict = result[1]
            self.assertNotEqual(result_dict, {})

    def test_set_handler(self):
        driver = self.test_connect()
        driver._protocol._handler_command_set({Parameter.XTILT_TRIGGER: 10})
        driver._protocol._handler_command_set({Parameter.YTILT_TRIGGER: 10})
        driver._protocol._handler_command_set({Parameter.LEVELING_TIMEOUT: 10})
        driver._protocol._handler_command_set({Parameter.LEVELING_FAILED: True})
        driver._protocol._handler_command_set({Parameter.AUTO_RELEVEL: False})

    def test_combined_samples(self):
        chunker = StringChunker(Protocol.sieve_function)

        sample = BOTPT_FIREHOSE_02

        ts = self.get_ntp_timestamp()
        chunker.add_chunk(sample, ts)

        timestamp, result = chunker.get_next_data()
        self.assertTrue(result in sample)
        self.assertEqual(timestamp, ts)

        timestamp, result = chunker.get_next_data()
        self.assertTrue(result in sample)
        self.assertEqual(timestamp, ts)

        timestamp, result = chunker.get_next_data()
        self.assertEqual(result, None)

    def test_leveling_status(self):
        chunker = StringChunker(Protocol.sieve_function)

        sample = LEVELING_STATUS

        ts = self.get_ntp_timestamp()
        chunker.add_chunk(sample, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

    def test_data_build_parsed_values(self):
        """
        Verify that the BOTPT LILY driver build_parsed_values method
        raises SampleException when an invalid sample is encountered
        and that it returns a result when a valid sample is encountered
        """
        driver = self.test_connect()

        items = [
            (INVALID_SAMPLE, LILYDataParticle, False),
            (VALID_SAMPLE_01, LILYDataParticle, True),
            (VALID_SAMPLE_02, LILYDataParticle, True),
            (DUMP_01_STATUS, BotptStatus01Particle, True),
            (DUMP_02_STATUS, LILYStatus02Particle, True),
        ]

        for raw_data, particle_class, is_valid in items:
            sample_exception = False
            result = None
            try:
                test_particle = particle_class(raw_data, False)
                result = test_particle._build_parsed_values()
            except SampleException as e:
                log.debug('SampleException caught: %s.', e)
                sample_exception = True
            finally:
                if is_valid:
                    self.assertFalse(sample_exception)
                    self.assertTrue(isinstance(result, list))
                else:
                    self.assertTrue(sample_exception)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        driver = self.test_connect()

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)
        self.assert_particle_published(driver, DUMP_01_STATUS, self.assert_particle_status_01, True)
        self.assert_particle_published(driver, DUMP_02_STATUS, self.assert_particle_status_02, True)

    def test_firehose(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        Verify that the BOTPT LILY driver publishes a particle correctly when the LILY packet is
        embedded in the stream of other BOTPT sensor output.
        """
        driver = self.test_connect()
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)

    def test_data_on_response(self):
        """
        Verify that the driver correctly parses the DATA_ON response
        """
        driver = self.test_connect()
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DATA_ON_COMMAND_RESPONSE)
        self.assertTrue(driver._protocol._get_response(expected_prompt=LILY_DATA_ON))

    def test_data_on_response_with_data(self):
        """
        Verify that the driver correctly parses the DATA_ON response
        when a data packet is right in front of it
        """
        driver = self.test_connect()
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, VALID_SAMPLE_01)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DATA_ON_COMMAND_RESPONSE)
        self.assertTrue(driver._protocol._get_response(expected_prompt=LILY_DATA_ON))

    def test_status_01(self):
        """
        Verify that the driver correctly parses the DUMP-SETTINGS response
        """
        driver = self.test_connect()
        self._send_port_agent_packet(driver, DUMP_01_STATUS + NEWLINE + DUMP_02_COMMAND_RESPONSE)

    def test_status_02(self):
        """
        Verify that the driver correctly parses the DUMP2 response
        """
        driver = self.test_connect()
        self._send_port_agent_packet(driver, DUMP_02_STATUS + NEWLINE + DUMP_02_COMMAND_RESPONSE)

    def test_data_off_response(self):
        """
        Verify that the driver correctly parses the DATA_OFF response
        """
        driver = self.test_connect()
        log.debug("DATA OFF command response: %s", DATA_OFF_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DATA_OFF_COMMAND_RESPONSE)
        self.assertTrue(driver._protocol._get_response(expected_prompt=LILY_DATA_OFF))

    def test_dump_settings_response(self):
        """
        Verify that the driver correctly parses the DUMP_SETTINGS response
        """
        driver = self.test_connect()
        log.debug("DUMP_SETTINGS_01 command response: %s", DUMP_01_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_01_COMMAND_RESPONSE)
        response = driver._protocol._get_response(expected_prompt=LILY_DUMP_01)
        self.assertTrue(response[1].endswith(LILY_DUMP_01))

        log.debug("DUMP_SETTINGS_02 command response: %s", DUMP_02_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(driver, DUMP_02_COMMAND_RESPONSE)
        response = driver._protocol._get_response(expected_prompt=LILY_DUMP_02)
        self.assertTrue(response[1].endswith(LILY_DUMP_02))

    def test_start_stop_autosample(self):
        driver = self.test_connect()
        driver._connection.send.side_effect = self.my_send(driver)

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_status_handlers(self):
        driver = self.test_connect()
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.ACQUIRE_STATUS)

    def test_leveling_timeout(self):
        # stand up the driver in test mode
        driver = self.test_connect()
        driver._connection.send.side_effect = self.my_send(driver)

        # set the leveling timeout to 1 to speed up timeout
        driver._protocol._param_dict.set_value(Parameter.LEVELING_TIMEOUT, 1)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)

        current_state = driver._protocol.get_current_state()
        self.assertEqual(current_state, ProtocolState.COMMAND_LEVELING)

        # sleep for longer than the length of timeout, assert we have returned to COMMAND
        time.sleep(driver._protocol._param_dict.get(Parameter.LEVELING_TIMEOUT) + 1)
        current_state = driver._protocol.get_current_state()
        self.assertEqual(current_state, ProtocolState.COMMAND)

    def test_leveling_complete(self):
        driver = self.test_connect()
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)
        # assert we have entered a leveling state
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND_LEVELING)
        # feed in a leveling complete status message
        self._send_port_agent_packet(driver, LEVELED_STATUS)
        # Assert we have returned to the command state
        self.assertEquals(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_leveling_failure(self):
        driver = self.test_connect()
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_LEVELING)
        # assert we have entered a leveling state
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND_LEVELING)
        self.assertTrue(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        # feed in a leveling failed status message
        try:
            self._send_port_agent_packet(driver, X_OUT_OF_RANGE + NEWLINE)
            time.sleep(1)
        except InstrumentDataException:
            self.assertFalse(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        try:
            self._send_port_agent_packet(driver, Y_OUT_OF_RANGE + NEWLINE)
            time.sleep(1)
        except InstrumentDataException:
            self.assertFalse(driver._protocol._param_dict.get(Parameter.AUTO_RELEVEL))
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(BaseEnum, NEWLINE, mock_callback)
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
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, LILYTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_connection(self):
        self.assert_initialize_driver()

    def test_get(self):
        self.assert_initialize_driver()
        self.assert_get(Parameter.AUTO_RELEVEL, True)
        self.assert_get(Parameter.XTILT_TRIGGER, DEFAULT_MAX_XTILT)
        self.assert_get(Parameter.YTILT_TRIGGER, DEFAULT_MAX_YTILT)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        self.assert_set(Parameter.AUTO_RELEVEL, False)
        self.assert_set(Parameter.XTILT_TRIGGER, 200)
        self.assert_set(Parameter.YTILT_TRIGGER, 200)
        self.assert_set(Parameter.LEVELING_TIMEOUT, 600)

    def test_autosample_leveling(self):
        """
        @brief Test for autosample state leveling
        """
        # This test should be run PRIOR to test_auto_relevel, as it will
        # increase the likelihood that the sensor will be out of level
        # enough to trigger an auto-relevel.
        self.assert_initialize_driver()

        # Begin autosampling
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        log.debug('START_AUTOSAMPLE returned: %r', response)
        self.assert_state_change(ProtocolState.AUTOSAMPLE, 5)

        #Issue start leveling command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_LEVELING)
        log.debug("START_LEVELING returned: %r", response)
        self.assert_state_change(ProtocolState.AUTOSAMPLE_LEVELING, 5)

        # Issue stop leveling command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_LEVELING)
        log.debug("STOP_LEVELING returned: %r", response)
        self.assert_state_change(ProtocolState.AUTOSAMPLE, 5)

    def test_command_leveling(self):
        """
        @brief Test for command state leveling
        """
        # This test should be run PRIOR to test_auto_relevel, as it will
        # increase the likelihood that the sensor will be out of level
        # enough to trigger an auto-relevel.
        self.assert_initialize_driver()

        #Issue start leveling command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_LEVELING)
        log.debug("START_LEVELING returned: %r", response)
        self.assert_state_change(ProtocolState.COMMAND_LEVELING, 30)

        # Issue stop leveling command
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_LEVELING)
        log.debug("STOP_LEVELING returned: %r", response)
        self.assert_state_change(ProtocolState.COMMAND, 30)

    def test_auto_relevel(self):
        """
        @brief Test for verifying auto relevel
        """
        self.assert_initialize_driver()

        # Begin autosampling
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        log.debug('START_AUTOSAMPLE returned: %r', response)
        self.assert_state_change(ProtocolState.AUTOSAMPLE, 30)

        # set the leveling timeout low, so we're not here for long
        self.assert_set(Parameter.LEVELING_TIMEOUT, 5)

        # Set the XTILT to a low threshold so that the driver will
        # automatically start the re-leveling operation
        # NOTE: This test MAY fail if the instrument completes
        # leveling before the triggers have been reset to 300
        self.assert_set(Parameter.XTILT_TRIGGER, 0)

        # verify we have started leveling
        self.assert_state_change(ProtocolState.AUTOSAMPLE_LEVELING, 30)

        # Now set the XTILT back to normal so that the driver will not
        # automatically start the re-leveling operation
        self.assert_set(Parameter.XTILT_TRIGGER, 300)

        self.assert_state_change(ProtocolState.AUTOSAMPLE, 30)

    def test_data_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        self.assert_async_particle_generation(DataParticleType.LILY_PARSED,
                                              self.assert_particle_sample_01,
                                              particle_count=5,
                                              timeout=10)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.COMMAND, 1)

    def test_dump_status(self):
        """
        @brief Test for acquiring status
        """
        self.assert_initialize_driver()

        # Issue acquire status command

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.LILY_STATUS_01, self.assert_particle_status_01)
        self.assert_async_particle_generation(DataParticleType.LILY_STATUS_02, self.assert_particle_status_02)

    def test_leveling_complete(self):
        """
        @brief Test for leveling
        """
        self.assert_initialize_driver()

        #Issue start leveling command

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_LEVELING)
        log.debug("START_LEVELING returned: %r", response)

        # Leveling should complete or abort after DEFAULT_LEVELING_TIMEOUT seconds
        self.assert_state_change(ProtocolState.COMMAND, DEFAULT_LEVELING_TIMEOUT + 10)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, LILYTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_poll(self):
        """
        No polling for a single sample
        """

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

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
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.START_LEVELING,
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
            ProtocolEvent.SET,
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.START_LEVELING,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()