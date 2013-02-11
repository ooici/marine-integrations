"""
@package mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.test.test_driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_150khz/cgsn/driver.py
@author Lytle Johnson
@brief Test cases for cgsn driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Lytle Johnson'
__license__ = 'Apache 2.0'

import unittest
import re

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.common import BaseEnum
from nose.plugins.attrib import attr
from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Protocol
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_EnsembleDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_EnsembleDataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_CalibrationDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_CalibrationDataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PS0DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PS0DataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PS3DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PS3DataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_FDDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_FDDataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PT200DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_PT200DataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import NEWLINE
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import adcpt_cache_dict

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from pyon.core.exception import Conflict
from interface.objects import AgentCommand
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from random import randint

# Globals
raw_stream_received = False
parsed_stream_received = False

SAMPLE_RAW_DATA = "7F7FF002000612004D008E008001FA01740200003228C941000D041E2D002003600101400900D0070\
114001F000000007D3DD104610301053200620028000006FED0FC090100FF00A148000014800001000C0C0D0D323862000000\
FF050800E014C5EE93EE2300040A000000000000454A4F4B4A4E829F80810088BDB09DFFFFFF9208000000140C0C0D0D323862\
000120FF570089000FFF0080008000800080008000800080008000800080008000800080008000800080008000800080008000\
800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
00800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800\
0800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
008000800080008000800080008000800080008000800080008000800080008000800080008000025D585068650D0D2C0C0D0\
C0E0C0E0C0D0C0E0D0C0C0E0E0B0D0E0D0D0D0C0C0C0C0E0F0E0C0D0F0C0D0E0F0D0C0C0D0D0D00000E0D00000D0B00000D0\
C00000C0C00000C0B00000E0C00000D0C00000D0C00000D0C00000C0C00000D0C00000C00000000000000000000000000000\
000000000000000000000035A52675150434B454341484142414841424148414241484142414841424148414241484142414\
8414241484142414741424148414241474142414841434148414241484142414841424148414241484142414841424148414\
24148414241484142414741424148414241484142414741424148414241484100040400005F00006400000064000000640000\
006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
00006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
FA604091"

break_success_str = NEWLINE + "[BREAK Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"

break_alarm_str = NEWLINE + "[ALARM Wakeup A]" + NEWLINE +\
"WorkHorse Broadband ADCP Version 50.40" + NEWLINE +\
"Teledyne RD Instruments (c) 1996-2010" + NEWLINE +\
"All Rights Reserved." + NEWLINE +\
">"

CALIBRATION_RAW_DATA = \
"ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE +\
"               Calibration date and time: 9/22/2012  11:53:32" + NEWLINE +\
"                             S inverse" + NEWLINE +\
"          ?                                                  " + NEWLINE +\
"     Bx   ?   4.1275e-01  4.2168e-01 -2.0631e-02 -2.8440e-05 ?" + NEWLINE +\
"     By   ?  -4.9163e-03  4.7625e-06 -2.7393e-03 -5.6853e-01 ?" + NEWLINE +\
"     Bz   ?   2.1975e-01 -2.0662e-01 -3.0120e-01  2.7459e-03 ?" + NEWLINE +\
"     Err  ?   4.8227e-01 -4.4007e-01  6.5367e-01 -7.3235e-03 ?" + NEWLINE +\
"          ?                                                  ?" + NEWLINE +\
"                             Coil Offset" + NEWLINE +\
"                         ?                " + NEWLINE +\
"                         ?   3.3914e+04   ?" + NEWLINE +\
"                         ?   3.3331e+04   ?" + NEWLINE +\
"                         ?   3.4030e+04   ?" + NEWLINE +\
"                         ?   3.4328e+04   ?" + NEWLINE +\
"                         ?                ?" + NEWLINE +\
"                             Electrical Null" + NEWLINE +\
"                              ?       " + NEWLINE +\
"                              ? 33989 ?" + NEWLINE +\
"                              ?       ?" + NEWLINE +\
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE +\
"                Calibration date and time: 9/22/2012  11:50:48" + NEWLINE +\
"              Average Temperature During Calibration was   25.7 ?C" + NEWLINE + NEWLINE +\
"                   Up                              Down" + NEWLINE + NEWLINE +\
"        ?                           ?" + NEWLINE +\
" Roll   ?  -1.7305e-07  -2.9588e-05 ?     ?   3.0294e-07   3.1274e-05 ?" + NEWLINE +\
" Pitch  ?  -2.9052e-05  -5.6057e-07 ?     ?  -3.1059e-05  -5.2326e-07 ?" + NEWLINE +\
"        ?                           ?     ?                           ?" + NEWLINE + NEWLINE +\
"        ?                           ?     ?                           ?" + NEWLINE +\
" Offset ?   3.2805e+04   3.2384e+04 ?     ?   3.3287e+04   3.1595e+04 ?" + NEWLINE +\
"        ?                           ?     ?                           ?" + NEWLINE + NEWLINE +\
"                             ?        " + NEWLINE +\
"                      Null   ? 33272 ?" + NEWLINE +\
"                             ?       ?" + NEWLINE +\
">"

PS0_RAW_DATA = \
"Instrument S/N:  18593" + NEWLINE +\
"       Frequency:  153600 HZ" + NEWLINE +\
"   Configuration:  4 BEAM, JANUS" + NEWLINE +\
"     Match Layer:  10" + NEWLINE +\
"      Beam Angle:  20 DEGREES" + NEWLINE +\
"    Beam Pattern:  CONVEX" + NEWLINE +\
"     Orientation:  UP  " + NEWLINE +\
"       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
"Pressure Sens Coefficients:" + NEWLINE +\
"              c3 = +1.629386E-10" + NEWLINE +\
"              c2 = -1.886023E-06" + NEWLINE +\
"              c1 = +1.364779E+00" + NEWLINE +\
"          Offset = -2.457906E+01" + NEWLINE + NEWLINE +\
"Temp Sens Offset:  -0.17 degrees C" + NEWLINE + NEWLINE +\
"    CPU Firmware:  50.40 [0]" + NEWLINE +\
"   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
"    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
"    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
"    PWRTIMG  Ver:  85d3, Type:   6" + NEWLINE + NEWLINE +\
"Board Serial Number Data:" + NEWLINE +\
"   98  00 00 06 FF 13 A0  09 HPI727-3007-00A" + NEWLINE +\
"   28  00 00 06 FE D0 FC  09 CPU727-2011-00E" + NEWLINE +\
"   0C  00 00 06 FF 13 BA  09 HPA727-3009-02B" + NEWLINE +\
"   E7  00 00 06 B2 C6 7D  09 REC727-1004-05A" + NEWLINE +\
"   70  00 00 06 F5 AF 73  09 DSP727-2001-05H" + NEWLINE +\
"   F0  00 00 06 F5 B2 EB  09 TUN727-1005-05A" + NEWLINE +\
">"

PS3_RAW_DATA = \
"Beam Width:   3.7 degrees" + NEWLINE + NEWLINE +\
"Beam     Elevation     Azimuth" + NEWLINE +\
"  1         -69.81      269.92" + NEWLINE +\
"  2         -70.00       89.92" + NEWLINE +\
"  3         -69.82        0.07" + NEWLINE +\
"  4         -69.89      180.08" + NEWLINE + NEWLINE +\
"Beam Directional Matrix (Down):" + NEWLINE +\
"  0.3453    0.0005    0.9385    0.2421  " + NEWLINE +\
" -0.3421   -0.0005    0.9397    0.2444  " + NEWLINE +\
" -0.0005   -0.3451    0.9386   -0.2429  " + NEWLINE +\
"  0.0005    0.3438    0.9390   -0.2438  " + NEWLINE + NEWLINE +\
"  Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
"  1.4587   -1.4508   -0.0010   -0.0051       23899  -23770     -16     -83  " + NEWLINE +\
" -0.0008    0.0033   -1.4532    1.4500         -13      54  -23809   23757  " + NEWLINE +\
"  0.2650    0.2676    0.2657    0.2667        4342    4384    4353    4370  " + NEWLINE +\
"  1.0225    1.0323   -1.0257   -1.0297       16752   16913  -16805  -16871  " + NEWLINE +\
"Beam Angle Corrections Are Loaded." + NEWLINE + ">"

FD_RAW_DATA = \
"Total Unique Faults   =     2" + NEWLINE +\
"Overflow Count        =     0" + NEWLINE +\
"Time of first fault:    12/11/29,19:40:37.32" + NEWLINE +\
"Time of last fault:     12/12/12,20:31:37.14" + NEWLINE + NEWLINE +\
"Fault Log:" + NEWLINE +\
"Entry #  0 Code=0a08h  Count=    2  Delta=112625967 Time=12/12/12,20:31:36.99" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis X over range." + NEWLINE +\
"Entry #  1 Code=0a09h  Count=    2  Delta=112625966 Time=12/12/12,20:31:37.14" + NEWLINE +\
" Parameter = 00000000h" + NEWLINE +\
"  Tilt axis Y over range." + NEWLINE +\
"End of fault log." + NEWLINE + NEWLINE +\
"Fault Log Dump:  addr=007EADC8" + NEWLINE +\
"a5 01 00 02 00 00 00 00 20 13 28 25 0b 1d 0c 06" + NEWLINE +\
"0e 14 1f 25 0c 0c 0c 05 01 f2 0a 08 00 00 00 02" + NEWLINE +\
"63 14 1f 24 0c 0c 0c 05 06 b6 89 2f 00 00 00 00" + NEWLINE +\
"02 6c 0a 09 00 00 00 02 0e 14 1f 25 0c 0c 0c 05" + NEWLINE +\
"06 b6 89 2e 00 00 00 00 02 18 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
"00 00 00 00 00 00 00 00 00 01 " + NEWLINE + NEWLINE +\
">"

PT200_RAW_DATA = \
"Ambient  Temperature =    24.27 Degrees C" + NEWLINE +\
"  Attitude Temperature =    26.70 Degrees C" + NEWLINE +\
"  Internal Moisture    = 8C1Eh" + NEWLINE + NEWLINE +\
"Correlation Magnitude: Narrow Bandwidth" + NEWLINE + NEWLINE +\
"               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
"                 0  255  255  255  255" + NEWLINE +\
"                 1  140  160  177  149" + NEWLINE +\
"                 2   41   62   94   50" + NEWLINE +\
"                 3   20   15   43    5" + NEWLINE +\
"                 4   12    3   19    4" + NEWLINE +\
"                 5    2    3    8    2" + NEWLINE +\
"                 6    3    1    3    3" + NEWLINE +\
"                 7    5    2    1    3" + NEWLINE + NEWLINE +\
"  High Gain RSSI:    66   65   72   65" + NEWLINE +\
"   Low Gain RSSI:    11    8   12    9" + NEWLINE + NEWLINE +\
"  SIN Duty Cycle:    48   49   48   49" + NEWLINE +\
"  COS Duty Cycle:    47   48   50   48" + NEWLINE + NEWLINE +\
"Receive Test Results = $00000000 ... PASS" + NEWLINE + NEWLINE +\
"IXMT    =      0.8 Amps rms  [Data=46h]" + NEWLINE +\
"VXMT    =     43.2 Volts rms [Data=49h]" + NEWLINE +\
"   Z    =     53.9 Ohms" + NEWLINE +\
"Transmit Test Results = $0 ... PASS" + NEWLINE + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"    0    0    0    0" + NEWLINE +\
"   12   12   12   12" + NEWLINE +\
"  255  255  255  255" + NEWLINE +\
"Electronics Test Results = $00000000" + NEWLINE +\
"Receive Bandwidth:" + NEWLINE +\
"    Sample      bw    bw    bw    bw    bw" + NEWLINE +\
"      rate  expect   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"        38      12    14    12    10    14 Khz" + NEWLINE +\
"   results          PASS  PASS  PASS  PASS" + NEWLINE +\
"RSSI Time Constant:" + NEWLINE + NEWLINE +\
"RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
"  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
"  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
"     1     5     7     5     7" + NEWLINE +\
"     2    10    13    10    12" + NEWLINE +\
"     3    15    18    15    17" + NEWLINE +\
"     4    18    22    18    22" + NEWLINE +\
"     5    21    26    22    25" + NEWLINE +\
"     6    24    29    25    28" + NEWLINE +\
"     7    26    31    27    30" + NEWLINE +\
"     8    28    32    29    32" + NEWLINE +\
"     9    29    34    30    34" + NEWLINE +\
"    10    31    35    32    35" + NEWLINE +\
"   nom    38    42    40    42" + NEWLINE +\
"result    PASS  PASS  PASS  PASS" + NEWLINE +\
">"

powering_down_str = NEWLINE +\
"Powering Down"

self_deploy_str = NEWLINE +\
"System will self-deploy in 1 minute unless valid command entered!"
 
###
#   Driver parameters for tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver ',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_name = 'teledyne_workhorse_monitor_150khz_cgsn',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {}
)

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT



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
#                           DATA PARTICLE TEST MIXIN                          #
#     Defines a set of assert methods used for data particle verification     #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.
###############################################################################
class ADCPTMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.TRANSMIT_POWER : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 255},
        Parameter.SPEED_OF_SOUND : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1500},
        Parameter.SALINITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35},
        Parameter.TIME_PER_BURST : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00:00'},
        Parameter.ENSEMBLES_PER_BURST : {TYPE:int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.TIME_PER_ENSEMBLE : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:00:00:00'},
        Parameter.TIME_OF_FIRST_PING : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00/00/00, 00:00:00'},
        Parameter.TIME_OF_FIRST_PING_Y2K : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '0000/00/00, 00:00:00'},
        Parameter.TIME_BETWEEN_PINGS : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:20:00'},
        Parameter.REAL_TIME_CLOCK : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00/00/00, 00:00:00'},
        Parameter.REAL_TIME_CLOCK_Y2K : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '0000/00/00, 00:00:00'},
        Parameter.BUFFERED_OUTPUT_PERIOD : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00'},
        Parameter.FALSE_TARGET_THRESHOLD_MAXIMUM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 50},
        Parameter.LOW_CORRELATION_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 2000},
        Parameter.CLIP_DATA_PAST_BOTTOM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        Parameter.RECEIVER_GAIN_SELECT : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.WATER_REFERENCE_LAYER : {TYPE: list, READONLY: False, DA: False, STARTUP: False, DEFAULT: [1,5]},
        Parameter.NUMBER_OF_DEPTH_CELLS : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 30},
        Parameter.PINGS_PER_ENSEMBLE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 45},
        Parameter.DEPTH_CELL_SIZE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 800 },
        Parameter.TRANSMIT_LENGTH : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.PING_WEIGHT : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.AMBIGUITY_VELOCITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 175},

        Parameter.MODE_1_BANDWIDTH_CONTROL : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.BLANK_AFTER_TRANSMIT : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 352},
        Parameter.DATA_OUT : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 111100000},
        Parameter.INSTRUMENT_ID : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.WATER_PROFILING_MODE : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1}
            }

 
    _header_sample_parameters = {
        ADCPT_EnsembleDataParticleKey.NUM_BYTES_IN_ENSEMBLE: {'type': int, 'value': 752 },
        ADCPT_EnsembleDataParticleKey.NUM_DATA_TYPES: {'type': int, 'value': 6 },
        ADCPT_EnsembleDataParticleKey.CPU_FW_VER: {'type': int, 'value': 50 },
        ADCPT_EnsembleDataParticleKey.CPU_FW_REV: {'type': int, 'value': 40 },
        ADCPT_EnsembleDataParticleKey.SYS_CONFIG: {'type': int, 'value': 16841 },
        ADCPT_EnsembleDataParticleKey.LAG_LEN: {'type': int, 'value': 13 },
        ADCPT_EnsembleDataParticleKey.NUM_BEAMS: {'type': int, 'value': 4 },
        ADCPT_EnsembleDataParticleKey.NUM_CELLS: {'type': int, 'value': 30 },
        ADCPT_EnsembleDataParticleKey.PINGS_PER_ENSEMBLE: {'type': int, 'value': 45 },
        ADCPT_EnsembleDataParticleKey.DEPTH_CELL_LEN: {'type': int, 'value': 800},
        ADCPT_EnsembleDataParticleKey.BLANK_AFTER_TX: {'type': int, 'value': 352},
        ADCPT_EnsembleDataParticleKey.PROFILING_MODE: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.LOW_CORR_THRESH: {'type': int, 'value': 64},
        ADCPT_EnsembleDataParticleKey.NUM_CODE_REPS: {'type': int, 'value': 9},
        ADCPT_EnsembleDataParticleKey.PERCENT_GD_MIN: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.ERR_VEL_MAX: {'type': int, 'value': 2000},
        ADCPT_EnsembleDataParticleKey.TIME_BETWEEN_PINGS: {'type': list, 'value': [1,20,0]},
        ADCPT_EnsembleDataParticleKey.COORD_XFRM: {'type': int, 'value': 31},
        ADCPT_EnsembleDataParticleKey.HEAD_ALIGN: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.HEAD_BIAS: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.CALC_SPD_SND_FROM_DATA : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_DEPTH_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_HEADING_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_PITCH_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_ROLL_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_SALINITY_FROM_SENSOR : {TYPE: bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.USE_TEMPERATURE_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.DEPTH_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.HEADING_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PITCH_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.ROLL_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.SALINITY_SENSOR_AVAIL : {TYPE: bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.TEMPERATURE_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.BIN1_DIST: {'type': int, 'value': 1233},
        ADCPT_EnsembleDataParticleKey.XMIT_PULSE_LEN: {'type': int, 'value': 865},
        ADCPT_EnsembleDataParticleKey.WP_REF_LAYER_AVG: {'type': int, 'value': 1281},
        ADCPT_EnsembleDataParticleKey.FALSE_TARGET_THRESH: {'type': int, 'value': 50},
        ADCPT_EnsembleDataParticleKey.XMIT_LAG_DIST: {'type': int, 'value': 98},
        ADCPT_EnsembleDataParticleKey.CPU_SN: {'type': unicode, 'value': '28000006FED0FC09'},
        ADCPT_EnsembleDataParticleKey.SYS_BW: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.SYS_PWR: {'type': int, 'value': 255},
        ADCPT_EnsembleDataParticleKey.INST_SN: {'type': unicode, 'value': 'A1480000'},
        ADCPT_EnsembleDataParticleKey.BEAM_ANGLE: {'type': int, 'value': 20},
###---------now for the var leader data
        ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUMBER: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.RTC_DATE_TIME: {'type': list, 'value': [12,12,13,13,50,56,98]},
        ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUM_MSB: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.TIMESTAMP: {'type': float, 'value': 3564424256.98},
        ADCPT_EnsembleDataParticleKey.BIT_RESULT: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.SPEED_OF_SOUND: {'type': int, 'value': 1535},
        ADCPT_EnsembleDataParticleKey.DEPTH_OF_XDUCER: {'type': int, 'value': 8},
        ADCPT_EnsembleDataParticleKey.HEADING: {'type': int, 'value': 224},
        ADCPT_EnsembleDataParticleKey.PITCH: {'type': int, 'value': 61125},
        ADCPT_EnsembleDataParticleKey.ROLL: {'type': int, 'value': 61075},
        ADCPT_EnsembleDataParticleKey.SALINITY: {'type': int, 'value': 35},
        ADCPT_EnsembleDataParticleKey.TEMPERATURE: {'type': int, 'value': 2564},
        ADCPT_EnsembleDataParticleKey.MIN_PRE_PING_WAIT_TIME: {'type': list, 'value': [0,0,0]},
        ADCPT_EnsembleDataParticleKey.HDG_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.PITCH_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.ROLL_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.XMIT_CURRENT: {'type': int, 'value': 69},
        ADCPT_EnsembleDataParticleKey.XMIT_VOLTAGE: {'type': int, 'value': 74},
        ADCPT_EnsembleDataParticleKey.AMBIENT_TEMP: {'type': int, 'value': 79},
        ADCPT_EnsembleDataParticleKey.PRESSURE_POS: {'type': int, 'value': 75},
        ADCPT_EnsembleDataParticleKey.PRESSURE_NEG: {'type': int, 'value': 74},
        ADCPT_EnsembleDataParticleKey.ATTITUDE_TEMP: {'type': int, 'value': 78},
        ADCPT_EnsembleDataParticleKey.ATTITUDE: {'type': int, 'value': 130},
        ADCPT_EnsembleDataParticleKey.CONTAMINATION_SENSOR: {'type': int, 'value': 159},
        ADCPT_EnsembleDataParticleKey.BUS_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ADDR_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ILLEGAL_INSTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ZERO_DIV: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.EMUL_EXCEP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNASS_EXCEP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.WATCHDOG: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.BATT_SAVE_PWR: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PINGING: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.COLD_WAKEUP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNKNOWN_WAKEUP: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.CLOCK_RD_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNEXP_ALARM: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.CLOCK_JMP_FWD: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.CLOCK_JMP_BKWRD: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.PWR_FAIL: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.SPUR_4_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.SPUR_5_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.SPUR_6_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.LEV_7_INTR: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PRESSURE: {'type': int, 'value': 4294967197},
        ADCPT_EnsembleDataParticleKey.PRESSURE_VAR: {'type': int, 'value': 2194},
        ADCPT_EnsembleDataParticleKey.RTCY2K_DATE_TIME: {'type': list, 'value': [20,12,12,13,13,50,56,98]},
###------------Velocity data
        ADCPT_EnsembleDataParticleKey.VELOCITY_DATA: {'type': list, 'value': 
            [[-224, 87, 137, -241],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768]]},
###------------Correlation magnitude data
        ADCPT_EnsembleDataParticleKey.CORR_MAG_DATA: {'type': list, 'value': 
            [[93, 88, 80, 104],[101, 13, 13, 44],[12, 13, 12, 14],[12, 14, 12, 13], [12, 14, 13, 12],
            [12, 14, 14, 11], [13, 14, 13, 13], [13, 12, 12, 12], [12, 14, 15, 14],
            [12, 13, 15, 12], [13, 14, 15, 13], [12, 12, 13, 13], [13, 0, 0, 14], [13, 0, 0, 13], [11, 0, 0, 13],
            [12, 0, 0, 12], [12, 0, 0, 12], [11, 0, 0, 14], [12, 0, 0, 13],[12, 0, 0, 13], [12, 0, 0, 13],
            [12, 0, 0, 12], [12, 0, 0, 13],
            [12, 0, 0, 12], [0 ,0 , 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],[0, 0, 0, 0]]},
###------------Echo intensity data
        ADCPT_EnsembleDataParticleKey.ECHO_INTENSITY_DATA: {'type': list, 'value': 
            [[90, 82, 103, 81], [80, 67, 75, 69], [67, 65, 72, 65],[66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], 
            [67, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 71, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], [66, 65, 72, 65]]},
###------------Percent good data
        ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA: {'type': list, 'value': 
            [[4, 0, 0, 95], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0]]}
        }

    _calibration_data_parameters = {
        ADCPT_CalibrationDataParticleKey.CALIBRATION_DATA: {'type': unicode, 'value': 
            "ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE +\
            "               Calibration date and time: 9/22/2012  11:53:32" + NEWLINE +\
            "                             S inverse" + NEWLINE +\
            "          ?                                                  " + NEWLINE +\
            "     Bx   ?   4.1275e-01  4.2168e-01 -2.0631e-02 -2.8440e-05 ?" + NEWLINE +\
            "     By   ?  -4.9163e-03  4.7625e-06 -2.7393e-03 -5.6853e-01 ?" + NEWLINE +\
            "     Bz   ?   2.1975e-01 -2.0662e-01 -3.0120e-01  2.7459e-03 ?" + NEWLINE +\
            "     Err  ?   4.8227e-01 -4.4007e-01  6.5367e-01 -7.3235e-03 ?" + NEWLINE +\
            "          ?                                                  ?" + NEWLINE +\
            "                             Coil Offset" + NEWLINE +\
            "                         ?                " + NEWLINE +\
            "                         ?   3.3914e+04   ?" + NEWLINE +\
            "                         ?   3.3331e+04   ?" + NEWLINE +\
            "                         ?   3.4030e+04   ?" + NEWLINE +\
            "                         ?   3.4328e+04   ?" + NEWLINE +\
            "                         ?                ?" + NEWLINE +\
            "                             Electrical Null" + NEWLINE +\
            "                              ?       " + NEWLINE +\
            "                              ? 33989 ?" + NEWLINE +\
            "                              ?       ?" + NEWLINE +\
            "                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE +\
            "                Calibration date and time: 9/22/2012  11:50:48" + NEWLINE +\
            "              Average Temperature During Calibration was   25.7 ?C" + NEWLINE + NEWLINE +\
            "                   Up                              Down" + NEWLINE + NEWLINE +\
            "        ?                           ?" + NEWLINE +\
            " Roll   ?  -1.7305e-07  -2.9588e-05 ?     ?   3.0294e-07   3.1274e-05 ?" + NEWLINE +\
            " Pitch  ?  -2.9052e-05  -5.6057e-07 ?     ?  -3.1059e-05  -5.2326e-07 ?" + NEWLINE +\
            "        ?                           ?     ?                           ?" + NEWLINE + NEWLINE +\
            "        ?                           ?     ?                           ?" + NEWLINE +\
            " Offset ?   3.2805e+04   3.2384e+04 ?     ?   3.3287e+04   3.1595e+04 ?" + NEWLINE +\
            "        ?                           ?     ?                           ?" + NEWLINE + NEWLINE +\
            "                             ?        " + NEWLINE +\
            "                      Null   ? 33272 ?" + NEWLINE +\
            "                             ?       ?" + NEWLINE }      
        }


    _ps0_parameters = {
        ADCPT_PS0DataParticleKey.PS0_DATA: {'type': unicode, 'value': 
            "Instrument S/N:  18593" + NEWLINE +\
            "       Frequency:  153600 HZ" + NEWLINE +\
            "   Configuration:  4 BEAM, JANUS" + NEWLINE +\
            "     Match Layer:  10" + NEWLINE +\
            "      Beam Angle:  20 DEGREES" + NEWLINE +\
            "    Beam Pattern:  CONVEX" + NEWLINE +\
            "     Orientation:  UP  " + NEWLINE +\
            "       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
            "Pressure Sens Coefficients:" + NEWLINE +\
            "              c3 = +1.629386E-10" + NEWLINE +\
            "              c2 = -1.886023E-06" + NEWLINE +\
            "              c1 = +1.364779E+00" + NEWLINE +\
            "          Offset = -2.457906E+01" + NEWLINE + NEWLINE +\
            "Temp Sens Offset:  -0.17 degrees C" + NEWLINE + NEWLINE +\
            "    CPU Firmware:  50.40 [0]" + NEWLINE +\
            "   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
            "    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
            "    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
            "    PWRTIMG  Ver:  85d3, Type:   6" + NEWLINE + NEWLINE +\
            "Board Serial Number Data:" + NEWLINE +\
            "   98  00 00 06 FF 13 A0  09 HPI727-3007-00A" + NEWLINE +\
            "   28  00 00 06 FE D0 FC  09 CPU727-2011-00E" + NEWLINE +\
            "   0C  00 00 06 FF 13 BA  09 HPA727-3009-02B" + NEWLINE +\
            "   E7  00 00 06 B2 C6 7D  09 REC727-1004-05A" + NEWLINE +\
            "   70  00 00 06 F5 AF 73  09 DSP727-2001-05H" + NEWLINE +\
            "   F0  00 00 06 F5 B2 EB  09 TUN727-1005-05A" + NEWLINE }
        }

    _ps3_parameters = {
        ADCPT_PS3DataParticleKey.PS3_DATA: {'type': unicode, 'value': 
            "Beam Width:   3.7 degrees" + NEWLINE + NEWLINE +\
            "Beam     Elevation     Azimuth" + NEWLINE +\
            "  1         -69.81      269.92" + NEWLINE +\
            "  2         -70.00       89.92" + NEWLINE +\
            "  3         -69.82        0.07" + NEWLINE +\
            "  4         -69.89      180.08" + NEWLINE + NEWLINE +\
            "Beam Directional Matrix (Down):" + NEWLINE +\
            "  0.3453    0.0005    0.9385    0.2421  " + NEWLINE +\
            " -0.3421   -0.0005    0.9397    0.2444  " + NEWLINE +\
            " -0.0005   -0.3451    0.9386   -0.2429  " + NEWLINE +\
            "  0.0005    0.3438    0.9390   -0.2438  " + NEWLINE + NEWLINE +\
            "  Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
            "  1.4587   -1.4508   -0.0010   -0.0051       23899  -23770     -16     -83  " + NEWLINE +\
            " -0.0008    0.0033   -1.4532    1.4500         -13      54  -23809   23757  " + NEWLINE +\
            "  0.2650    0.2676    0.2657    0.2667        4342    4384    4353    4370  " + NEWLINE +\
            "  1.0225    1.0323   -1.0257   -1.0297       16752   16913  -16805  -16871  " + NEWLINE +\
            "Beam Angle Corrections Are Loaded." + NEWLINE  }
    }       
        
    _fd_parameters = {
        ADCPT_FDDataParticleKey.FD_DATA: {'type': unicode, 'value': 
            "Total Unique Faults   =     2" + NEWLINE +\
            "Overflow Count        =     0" + NEWLINE +\
            "Time of first fault:    12/11/29,19:40:37.32" + NEWLINE +\
            "Time of last fault:     12/12/12,20:31:37.14" + NEWLINE + NEWLINE +\
            "Fault Log:" + NEWLINE +\
            "Entry #  0 Code=0a08h  Count=    2  Delta=112625967 Time=12/12/12,20:31:36.99" + NEWLINE +\
            " Parameter = 00000000h" + NEWLINE +\
            "  Tilt axis X over range." + NEWLINE +\
            "Entry #  1 Code=0a09h  Count=    2  Delta=112625966 Time=12/12/12,20:31:37.14" + NEWLINE +\
            " Parameter = 00000000h" + NEWLINE +\
            "  Tilt axis Y over range." + NEWLINE +\
            "End of fault log." + NEWLINE + NEWLINE +\
            "Fault Log Dump:  addr=007EADC8" + NEWLINE +\
            "a5 01 00 02 00 00 00 00 20 13 28 25 0b 1d 0c 06" + NEWLINE +\
            "0e 14 1f 25 0c 0c 0c 05 01 f2 0a 08 00 00 00 02" + NEWLINE +\
            "63 14 1f 24 0c 0c 0c 05 06 b6 89 2f 00 00 00 00" + NEWLINE +\
            "02 6c 0a 09 00 00 00 02 0e 14 1f 25 0c 0c 0c 05" + NEWLINE +\
            "06 b6 89 2e 00 00 00 00 02 18 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00" + NEWLINE +\
            "00 00 00 00 00 00 00 00 00 01 " + NEWLINE + NEWLINE }
        }

    _pt200_parameters = {
        ADCPT_PT200DataParticleKey.PT200_DATA: {'type': unicode, 'value': 
            "Ambient  Temperature =    24.27 Degrees C" + NEWLINE +\
            "  Attitude Temperature =    26.70 Degrees C" + NEWLINE +\
            "  Internal Moisture    = 8C1Eh" + NEWLINE + NEWLINE +\
            "Correlation Magnitude: Narrow Bandwidth" + NEWLINE + NEWLINE +\
            "               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
            "                 0  255  255  255  255" + NEWLINE +\
            "                 1  140  160  177  149" + NEWLINE +\
            "                 2   41   62   94   50" + NEWLINE +\
            "                 3   20   15   43    5" + NEWLINE +\
            "                 4   12    3   19    4" + NEWLINE +\
            "                 5    2    3    8    2" + NEWLINE +\
            "                 6    3    1    3    3" + NEWLINE +\
            "                 7    5    2    1    3" + NEWLINE + NEWLINE +\
            "  High Gain RSSI:    66   65   72   65" + NEWLINE +\
            "   Low Gain RSSI:    11    8   12    9" + NEWLINE + NEWLINE +\
            "  SIN Duty Cycle:    48   49   48   49" + NEWLINE +\
            "  COS Duty Cycle:    47   48   50   48" + NEWLINE + NEWLINE +\
            "Receive Test Results = $00000000 ... PASS" + NEWLINE + NEWLINE +\
            "IXMT    =      0.8 Amps rms  [Data=46h]" + NEWLINE +\
            "VXMT    =     43.2 Volts rms [Data=49h]" + NEWLINE +\
            "   Z    =     53.9 Ohms" + NEWLINE +\
            "Transmit Test Results = $0 ... PASS" + NEWLINE + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "Electronics Test Results = $00000000" + NEWLINE +\
            "Receive Bandwidth:" + NEWLINE +\
            "    Sample      bw    bw    bw    bw    bw" + NEWLINE +\
            "      rate  expect   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
            "        38      12    14    12    10    14 Khz" + NEWLINE +\
            "   results          PASS  PASS  PASS  PASS" + NEWLINE +\
            "RSSI Time Constant:" + NEWLINE + NEWLINE +\
            "RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
            "  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
            "  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
            "     1     5     7     5     7" + NEWLINE +\
            "     2    10    13    10    12" + NEWLINE +\
            "     3    15    18    15    17" + NEWLINE +\
            "     4    18    22    18    22" + NEWLINE +\
            "     5    21    26    22    25" + NEWLINE +\
            "     6    24    29    25    28" + NEWLINE +\
            "     7    26    31    27    30" + NEWLINE +\
            "     8    28    32    29    32" + NEWLINE +\
            "     9    29    34    30    34" + NEWLINE +\
            "    10    31    35    32    35" + NEWLINE +\
            "   nom    38    42    40    42" + NEWLINE +\
            "result    PASS  PASS  PASS  PASS" + NEWLINE }
        }

# Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ###
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is  correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, ADCPT_EnsembleDataParticle)):
            self.assert_particle_header_sample(data_particle)
        elif (isinstance(data_particle, ADCPT_CalibrationDataParticle)):
            self.assert_particle_calibration_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PS0DataParticle)):
            self.assert_particle_ps0_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PS3DataParticle)):
            self.assert_particle_ps3_data(data_particle)
        elif (isinstance(data_particle, ADCPT_FDDataParticle)):
            self.assert_particle_fd_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PT200DataParticle)):
            self.assert_particle_py200_data(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_header_sample(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ensemble data particle
        @param data_particle: ADCPT_EnsembleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ENSEMBLE_PARSED)
        self.assert_data_particle_parameters(data_particle, self._header_sample_parameters, verify_values)

    def assert_particle_calibration_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt calibration data particle
        @param data_particle: ADCPT_CalibrationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.CALIBRATION_PARSED)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def assert_particle_ps0_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PS0_PARSED)
        self.assert_data_particle_parameters(data_particle, self._ps0_parameters, verify_values)

    def assert_particle_ps3_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ps3 data particle
        @param data_particle: ADCPT_PS3DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PS3_PARSED)
        self.assert_data_particle_parameters(data_particle, self._ps3_parameters, verify_values)

    def assert_particle_fd_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.FD_PARSED)
        self.assert_data_particle_parameters(data_particle, self._fd_parameters, verify_values)

    def assert_particle_pt200_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt pt200 data particle
        @param data_particle: ADCPT_PT200DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PT200_PARSED)
        self.assert_data_particle_parameters(data_particle, self._pt200_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase,ADCPTMixin):
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
        self.assert_enum_has_no_duplicates(InstrumentCmds())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, SAMPLE_RAW_DATA)

        self.assert_chunker_sample(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, CALIBRATION_RAW_DATA)
 
        self.assert_chunker_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, PS3_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS3_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS3_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PS3_RAW_DATA)

        self.assert_chunker_sample(chunker, FD_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, FD_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, FD_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, FD_RAW_DATA)

        self.assert_chunker_sample(chunker, PT200_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PT200_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PT200_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PT200_RAW_DATA)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_RAW_DATA, self.assert_particle_header_sample, True)
        self.assert_particle_published(driver, CALIBRATION_RAW_DATA, self.assert_particle_calibration_data, True)
        self.assert_particle_published(driver, PS0_RAW_DATA, self.assert_particle_ps0_data, True)
        self.assert_particle_published(driver, PS3_RAW_DATA, self.assert_particle_ps3_data, True)
        self.assert_particle_published(driver, FD_RAW_DATA, self.assert_particle_fd_data, True)
        self.assert_particle_published(driver, PT200_RAW_DATA, self.assert_particle_pt200_data, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))
        my_parameters = sorted(driver.get_resource(Parameter.ALL))
        
        log.debug("Reported Parameters: %s" % reported_parameters)
        log.debug("Expected Parameters: %s" % expected_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)


    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected. All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['BREAK_ALARM', 'BREAK_SUCCESS','DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['POWERING_DOWN',
                                    'START_AUTOSAMPLE',
                                    'SELF_DEPLOY',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'PROTOCOL_EVENT_QUIT_SESSION'],
            ProtocolState.AUTOSAMPLE: ['BREAK_SUCCESS',
                                       'DRIVER_EVENT_GET'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_build_param_dict(self):
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        saved_dict = {}
        result_dict = {}
        #save current values in adcpt_cache_dict
        saved_dict.update(adcpt_cache_dict)
        #load adcpt_cache_dict with new values
        for key in adcpt_cache_dict.keys():
            adcpt_cache_dict[key] = randint(0,100)
        #sync _param_dict to adcpt_cache_dict
        protocol._build_param_dict()
        #check if the same dict results
        for key in adcpt_cache_dict.keys():
            result_dict[key] = protocol._param_dict.get(key)
        log.debug("cached values: %s" % adcpt_cache_dict)
        log.debug("param_dict: %s" % result_dict)

        self.assertEqual(adcpt_cache_dict, result_dict)
        #restore original values in adcpt_cache_dict
        adcpt_cache_dict.update(saved_dict)
        
###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, ADCPTMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_parameters(self):
        """
        Test driver parameters and verify their type. Startup parameters also verify the parameter
        value. This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        """
        set_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        # One second later
        expected_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        print "timestamp: ",expected_time
#        self.assert_set(Parameter.DS_DEVICE_DATE_TIME, set_time, no_get=True)
#        self.assert_get(Parameter.DS_DEVICE_DATE_TIME, expected_time.upper())
        """

        ###
        # Instrument Parameteres
        ###
        self.assert_set(Parameter.SALINITY, 'iontest'.upper())

        ###
        # Set Sample Parameters
        ###
        # Tested in another method

        ###
        # Read only parameters
        ###
        self.assert_set_readonly(Parameter.MODE1_BANDWIDTH_CONTROL)
        self.assert_set_readonly(Parameter.BLANK_AFTER_TRANSMIT)
        self.assert_set_readonly(Parameter.DATA_OUT)
        self.assert_set_readonly(Parameter.INSTRUMENT_ID)
        self.assert_set_readonly(Parameter.WATER_PROFILING_MODE)

#  these are cut and paste from sbe26plus. Not used but keep for reference.
    """
    def check_state(self, expected_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, expected_state)

    def put_instrument_in_command_mode(self):
        # Test that the driver is in state unconfigured.
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

        # Test that the driver protocol is in state command.
        self.check_state(ProtocolState.COMMAND)


    def test_init_logging(self):
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.INIT_LOGGING)
        self.assertTrue(reply)

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_get(Parameter.LOGGING, True)

    def test_quit_session(self):
        self.assert_initialize_driver()

        # Note quit session just sleeps the device, so its safe to remain in COMMAND mode.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.QUIT_SESSION)

        self.assertEqual(reply, None)

        # Must stay in COMMAND state (but sleeping)
        self.assert_current_state(ProtocolState.COMMAND)
        # now can we return to command state?

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_get(Parameter.LOGGING, False)

    def test_get_resource_capabilities(self):
        # Test the driver is in state unconfigured.
        self.assert_initialize_driver()

        # COMMAND
        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

        # Verify all paramaters are present in res_params

        # DS
        self.assertTrue(Parameter.DEVICE_VERSION in res_params)
        self.assertTrue(Parameter.SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.DS_DEVICE_DATE_TIME in res_params)
        self.assertTrue(Parameter.USER_INFO in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_RANGE in res_params)
        self.assertTrue(Parameter.EXTERNAL_TEMPERATURE_SENSOR in res_params)
        self.assertTrue(Parameter.CONDUCTIVITY in res_params)
        self.assertTrue(Parameter.IOP_MA in res_params)
        self.assertTrue(Parameter.VMAIN_V in res_params)
        self.assertTrue(Parameter.VLITH_V in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_P in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_T in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_S in res_params)

        # DS/SETSAMPLING
        self.assertTrue(Parameter.TIDE_INTERVAL in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENT_DURATION in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_PER_BURST in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_SCANS_PER_SECOND in res_params)
        self.assertTrue(Parameter.USE_START_TIME in res_params)
        #Parameter.START_TIME,
        self.assertTrue(Parameter.USE_STOP_TIME in res_params)
        #Parameter.STOP_TIME,
        self.assertTrue(Parameter.TXWAVESTATS in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_PER_DAY in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_PER_DAY in res_params)
        self.assertTrue(Parameter.MEMORY_ENDURANCE in res_params)
        self.assertTrue(Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_WAVE_BURSTS in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.TXREALTIME in res_params)
        self.assertTrue(Parameter.TXWAVEBURST in res_params)
        self.assertTrue(Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM in res_params)
        self.assertTrue(Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND in res_params)
        self.assertTrue(Parameter.MIN_ALLOWABLE_ATTENUATION in res_params)
        self.assertTrue(Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.HANNING_WINDOW_CUTOFF in res_params)
        self.assertTrue(Parameter.SHOW_PROGRESS_MESSAGES in res_params)
        self.assertTrue(Parameter.STATUS in res_params)
        self.assertTrue(Parameter.LOGGING in res_params)

        reply = self.driver_client.cmd_dvr('execute_resource', Capability.START_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 1)
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

    def test_connect_configure_disconnect(self):
        self.assert_initialize_driver()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.assert_current_state(DriverConnectionState.DISCONNECTED)

    def test_bad_commands(self):
        print ">>>>>>>>>>>>>>>>>>>>>>>>> got to test_bad_commands"
        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Test bad commands in UNCONFIGURED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('conquer_the_world')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("1 - conquer_the_world - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

        # Test the driver is configured for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        self.check_state(DriverConnectionState.DISCONNECTED)

        # Test bad commands in DISCONNECTED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('test_the_waters')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("2 - test_the_waters - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)


        # Test the driver is in unknown state.
        reply = self.driver_client.cmd_dvr('connect')
        self.check_state(ProtocolState.UNKNOWN)

        # Test bad commands in UNKNOWN state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("skip_to_the_loo")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("3 - skip_to_the_loo - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)



        # Test the driver is in command mode.
        reply = self.driver_client.cmd_dvr('discover_state')

        self.check_state(ProtocolState.COMMAND)


        # Test bad commands in COMMAND state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("... --- ..., ... --- ...")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("4 - ... --- ..., ... --- ... - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    def test_poll(self):
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()


        # Poll for a sample and confirm result.
        sample1 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE1 = " + str(sample1[1]))

        # Poll for a sample and confirm result.
        sample2 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE2 = " + str(sample2[1]))

        # Poll for a sample and confirm result.
        sample3 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE3 = " + str(sample3[1]))

        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        TS_REGEX_MATCHER = re.compile(TS_REGEX)

        matches1 = TS_REGEX_MATCHER.match(sample1[1])
        self.assertEqual(3, len(matches1.groups()))

        matches2 = TS_REGEX_MATCHER.match(sample2[1])
        self.assertEqual(3, len(matches2.groups()))

        matches3 = TS_REGEX_MATCHER.match(sample3[1])
        self.assertEqual(3, len(matches3.groups()))




        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]

        self.assertEqual(len(sample_events), 12)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_connect(self):
        log.info("test_connect test started")
        self.put_instrument_in_command_mode()

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_clock_sync(self):
        self.put_instrument_in_command_mode()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)
        self.check_state(ProtocolState.COMMAND)
    """
    

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
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        No polling for a single sample
        '''

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
