"""
@package mi.instrument.nortek.test.test_driver
@file mi/instrument/nortek/test/test_driver.py
@author Steve Foley
@brief Common test code for Nortek drivers
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import base64
import time
import datetime
import re
import unittest
import json

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger ; log = get_logger()

from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.instrument.protocol_cmd_dict import CommandDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictKey

from mi.instrument.nortek.driver import NortekProtocolParameterDict
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticleKey
from mi.instrument.nortek.driver import NortekHeadConfigDataParticleKey
from mi.instrument.nortek.driver import NortekUserConfigDataParticleKey
from mi.instrument.nortek.driver import NortekEngClockDataParticleKey
from mi.instrument.nortek.driver import NortekEngBatteryDataParticleKey
from mi.instrument.nortek.driver import NortekEngIdDataParticleKey
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticle
from mi.instrument.nortek.driver import NortekHeadConfigDataParticle
from mi.instrument.nortek.driver import NortekUserConfigDataParticle
from mi.instrument.nortek.driver import NortekEngClockDataParticle
from mi.instrument.nortek.driver import NortekEngBatteryDataParticle
from mi.instrument.nortek.driver import NortekEngIdDataParticle
from mi.instrument.nortek.driver import NortekDataParticleType
from mi.instrument.nortek.driver import NortekInstrumentProtocol
from mi.instrument.nortek.driver import ScheduledJob
from mi.instrument.nortek.driver import NortekInstrumentDriver
from mi.core.exceptions import NotImplementedException
from mi.core.time import get_timestamp_delayed

from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentProtocolException

from interface.objects import AgentCommand

from mi.instrument.nortek.driver import InstrumentPrompts, Parameter, ProtocolState, ProtocolEvent, InstrumentCmds, \
    Capability


hw_config_particle = [{DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.SERIAL_NUM, DataParticleKey.VALUE: "VEC 8181      "},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.RECORDER_INSTALLED, DataParticleKey.VALUE: 0},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.COMPASS_INSTALLED, DataParticleKey.VALUE: 0},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.BOARD_FREQUENCY, DataParticleKey.VALUE: 65535},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.PIC_VERSION, DataParticleKey.VALUE: 0},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.HW_REVISION, DataParticleKey.VALUE: 4},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.RECORDER_SIZE, DataParticleKey.VALUE: 144},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.VELOCITY_RANGE, DataParticleKey.VALUE: 0},
                      {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.FW_VERSION, DataParticleKey.VALUE: "3.36"}]


def assert_particle_hw_config(self, data_particle, verify_value=False):
    self.assert_data_particle_keys(NortekHardwareConfigDataParticleKey, self.hw_config_particle)
    self.assert_data_particle_header(data_particle, NortekDataParticleType.HARDWARE_CONFIG)
    self.assert_data_particle_parameters(self.hw_config_particle, verify_value)


def hw_config_sample():
    sample_as_hex = "a505180056454320383138312020202020200400ffff00000400900004000000ffff0000ffffffff0000332e3336b048"
    return sample_as_hex.decode('hex')


def head_config_sample():
    sample_as_hex = "a50470003700701701005645432034393433000000000000000000000\
000992ac3eaabea0e001925dbda7805830589051cbd0d00822becff1dbf05fc222b4200a00f000\
00000ffff0000ffff0000ffff0000000000000000ffff0000010000000100000000000000fffff\
fff00000000ffff0100000000001900a2f65914c9050301d81b5a2a9d9ffefc35325d007b9e4ff\
f92324c00987e0afd48ff0afd547d2b01cffe3602ff7ffafff7fffaff000000000000000000000\
000000000009f14100e100e10275b0000000000000000000000000000000000000000000300065b"
    return sample_as_hex.decode('hex')


head_config_particle = [{DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.PRESSURE_SENSOR, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.MAG_SENSOR, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.TILT_SENSOR, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.TILT_SENSOR_MOUNT, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_FREQ, DataParticleKey.VALUE: 6000},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_TYPE, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_SERIAL, DataParticleKey.VALUE: "VEC 4943"},
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.SYSTEM_DATA,
                         DataParticleKey.VALUE: base64.b64encode(
                                "\x00\x00\x00\x00\x00\x00\x00\x00\x99\x2a\xc3\xea\xab\xea\x0e\x00\x19\x25\xdb\
\xda\x78\x05\x83\x05\x89\x05\x1c\xbd\x0d\x00\x82\x2b\xec\xff\x1d\xbf\x05\xfc\
\x22\x2b\x42\x00\xa0\x0f\x00\x00\x00\x00\xff\xff\x00\x00\xff\xff\x00\x00\xff\
\xff\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\x01\x00\x00\x00\x01\x00\
\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff\x00\x00\x00\x00\xff\xff\x01\x00\x00\
\x00\x00\x00\x19\x00\xa2\xf6\x59\x14\xc9\x05\x03\x01\xd8\x1b\x5a\x2a\x9d\x9f\
\xfe\xfc\x35\x32\x5d\x00\x7b\x9e\x4f\xff\x92\x32\x4c\x00\x98\x7e\x0a\xfd\x48\
\xff\x0a\xfd\x54\x7d\x2b\x01\xcf\xfe\x36\x02\xff\x7f\xfa\xff\xf7\xff\xfa\xff\
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x9f\x14\x10\
\x0e\x10\x0e\x10\x27"),
                         DataParticleKey.BINARY: True}, 
                        {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.NUM_BEAMS, DataParticleKey.VALUE: 3}]


def user_config_sample():
    # Visually break it up a bit (full lines are 30 bytes wide)
    sample_as_hex = \
        "a500 0001 0200 1000 0700 2c00 0002 0100 3c00 0300 8200 0000 cc4e 0000 0000 \
        0200 0100 0100 0700 5802 3439 3433 0000 0100 2642 2812 1209 c0a8 0000 3000 \
        1141 1400 0100 1400 0400 0000 2035 \
        5e01 \
        023d 1e3d 393d 533d 6e3d 883d a23d bb3d d43d ed3d 063e 1e3e 363e 4e3e 653e \
        7d3e 933e aa3e c03e d63e ec3e 023f 173f 2c3f 413f 553f 693f 7d3f 913f a43f \
        b83f ca3f dd3f f03f 0240 1440 2640 3740 4940 5a40 6b40 7c40 8c40 9c40 ac40 \
        bc40 cc40 db40 ea40 f940 0841 1741 2541 3341 4241 4f41 5d41 6a41 7841 8541 \
        9241 9e41 ab41 b741 c341 cf41 db41 e741 f241 fd41 0842 1342 1e42 2842 3342 \
        3d42 4742 5142 5b42 6442 6e42 7742 8042 8942 9142 9a42 a242 aa42 b242 ba42 \
        \
        3333 3035 2d30 3031 3036 5f30 3030 3031 5f32 3830 3932 3031 3200 0000 0000 \
        0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 \
        0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 1e00 \
        5a00 5a00 bc02 3200 0000 0000 0000 0700 0000 0000 0000 0000 0000 0000 0100 \
        0000 0000 2a00 0000 0200 1400 ea01 1400 ea01 0a00 0500 0000 4000 4000 0200 \
        0f00 5a00 0000 0100 c800 0000 0000 0f00 ea01 ea01 0000 0000 0000 0000 0000 \
        \
        0712 0080 0040 0000 0000 0000 8200 0000 0a00 0800 b12b 0000 0000 0200 0600 \
        0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0aff \
        cdff 8b00 e500 ee00 0b00 84ff 3dff a7ff"
    
    return sample_as_hex.translate(None, ' ').decode('hex')

user_config_particle = [{DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TX_LENGTH, DataParticleKey.VALUE: 2},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.BLANK_DIST, DataParticleKey.VALUE: 16},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.RX_LENGTH, DataParticleKey.VALUE: 7},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TIME_BETWEEN_PINGS, DataParticleKey.VALUE: 44},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TIME_BETWEEN_BURSTS, DataParticleKey.VALUE: 512},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_PINGS, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.AVG_INTERVAL, DataParticleKey.VALUE: 60},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_BEAMS, DataParticleKey.VALUE: 3},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.PROFILE_TYPE, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.MODE_TYPE, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_TCM1, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_TCM2, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SYNC_OUT_POSITION, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SAMPLE_ON_SYNC, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.START_ON_SYNC, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_PCR1, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_PCR2, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.COMPASS_UPDATE_RATE, DataParticleKey.VALUE: 2},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.COORDINATE_SYSTEM, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_CELLS, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.CELL_SIZE, DataParticleKey.VALUE: 7},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.MEASUREMENT_INTERVAL, DataParticleKey.VALUE: 600},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DEPLOYMENT_NAME, DataParticleKey.VALUE: "4943"},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WRAP_MODE, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DEPLOY_START_TIME, DataParticleKey.VALUE: [26, 42, 28, 12, 12, 9]},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DIAG_INTERVAL, DataParticleKey.VALUE: 43200},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.USE_SPEC_SOUND_SPEED, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DIAG_MODE_ON, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_OUTPUT_ON, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.OUTPUT_FORMAT, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SCALING, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SERIAL_OUT_ON, DataParticleKey.VALUE: True},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.STAGE_ON, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_POWER_OUTPUT, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SOUND_SPEED_ADJUST, DataParticleKey.VALUE: 16657},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_DIAG_SAMPLES, DataParticleKey.VALUE: 20},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_BEAMS_PER_CELL, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_PINGS_DIAG, DataParticleKey.VALUE: 20},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.USE_DSP_FILTER, DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILTER_DATA_OUTPUT, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_INPUT_ADDR, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SW_VER,DataParticleKey.VALUE: 13600},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.VELOCITY_ADJ_FACTOR, DataParticleKey.VALUE:
                          "Aj0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8XPyw/QT9VP2k/fT+RP6Q/uD/KP90/"
                          "8D8CQBRAJkA3QElAWkBrQHxAjECcQKxAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20"
                          "HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC"},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILE_COMMENTS, DataParticleKey.VALUE: "3305-00106_00001_28092012"},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_DATA_RATE, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_CELL_POS, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DYNAMIC_POS_TYPE, DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.PERCENT_WAVE_CELL_POS, DataParticleKey.VALUE: 32768},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_TX_PULSE, DataParticleKey.VALUE: 16384},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FIX_WAVE_BLANK_DIST, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_CELL_SIZE, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_DIAG_PER_WAVE, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_SAMPLE_PER_BURST, DataParticleKey.VALUE: 10},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_SCALE_FACTOR, DataParticleKey.VALUE: 11185},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.CORRELATION_THRS, DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TX_PULSE_LEN_2ND, DataParticleKey.VALUE: 2},
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILTER_CONSTANTS, DataParticleKey.VALUE: 'Cv/N/4sA5QDuAAsAhP89/w=='}]


def eng_clock_sample():
    sample_as_hex = "0907021110120606"
    return sample_as_hex.decode('hex')


eng_clock_particle = [{DataParticleKey.VALUE_ID: NortekEngClockDataParticleKey.DATE_TIME_ARRAY, DataParticleKey.VALUE: [9, 7, 2, 11, 10, 12]}]


def eng_battery_sample():
    sample_as_hex = "a71f0606"
    return sample_as_hex.decode('hex')

eng_battery_particle = [{DataParticleKey.VALUE_ID: NortekEngBatteryDataParticleKey.BATTERY_VOLTAGE, DataParticleKey.VALUE: 8103}]


def eng_id_sample():
    sample_as_hex = "41514420313231352020202020200606"
    return sample_as_hex.decode('hex')

eng_id_particle = [{DataParticleKey.VALUE_ID: NortekEngIdDataParticleKey.ID, DataParticleKey.VALUE: "AQD 1215      "}]


def user_config1():
    # NumberSamplesPerBurst = 20, MeasurementInterval = 500
    # deployment output from the vector application
    user_config_values = "A5 00 00 01 02 00 10 00 07 00 2C 00 00 02 01 00 \
                          40 00 03 00 82 00 00 00 CC 4E 00 00 00 00 01 00 \
                          00 00 01 00 07 00 F4 01 00 00 00 00 00 00 00 00 \
                          39 28 17 14 12 12 30 2A 00 00 30 00 11 41 01 00 \
                          01 00 14 00 04 00 00 00 00 00 5E 01 02 3D 1E 3D \
                          39 3D 53 3D 6E 3D 88 3D A2 3D BB 3D D4 3D ED 3D \
                          06 3E 1E 3E 36 3E 4E 3E 65 3E 7D 3E 93 3E AA 3E \
                          C0 3E D6 3E EC 3E 02 3F 17 3F 2C 3F 41 3F 55 3F \
                          69 3F 7D 3F 91 3F A4 3F B8 3F CA 3F DD 3F F0 3F \
                          02 40 14 40 26 40 37 40 49 40 5A 40 6B 40 7C 40 \
                          8C 40 9C 40 AC 40 BC 40 CC 40 DB 40 EA 40 F9 40 \
                          08 41 17 41 25 41 33 41 42 41 4F 41 5D 41 6A 41 \
                          78 41 85 41 92 41 9E 41 AB 41 B7 41 C3 41 CF 41 \
                          DB 41 E7 41 F2 41 FD 41 08 42 13 42 1E 42 28 42 \
                          33 42 3D 42 47 42 51 42 5B 42 64 42 6E 42 77 42 \
                          80 42 89 42 91 42 9A 42 A2 42 AA 42 B2 42 BA 42 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 1E 00 5A 00 5A 00 BC 02 \
                          32 00 00 00 00 00 00 00 07 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 01 00 00 00 00 00 2A 00 00 00 \
                          02 00 14 00 EA 01 14 00 EA 01 0A 00 05 00 00 00 \
                          40 00 40 00 02 00 0F 00 5A 00 00 00 01 00 C8 00 \
                          00 00 00 00 0F 00 EA 01 EA 01 00 00 00 00 00 00 \
                          00 00 00 00 07 12 00 80 00 40 00 00 00 00 00 00 \
                          82 00 00 00 14 00 10 00 B1 2B 00 00 00 00 02 00 \
                          14 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 0A FF \
                          CD FF 8B 00 E5 00 EE 00 0B 00 84 FF 3D FF 5A 78"
        
    user_config = ''
    for value in user_config_values.split():
        user_config += chr(int(value, 16))
    return user_config


def user_config2():
    # NumberSamplesPerBurst = 10, MeasurementInterval = 600
    # instrument user configuration from the OSU instrument itself
    user_config_values = [
        0xa5, 0x00, 0x00, 0x01, 0x02, 0x00, 0x10, 0x00, 0x07, 0x00, 0x2c, 0x00, 0x00, 0x02, 0x01, 0x00,
        0x3c, 0x00, 0x03, 0x00, 0x82, 0x00, 0x00, 0x00, 0xcc, 0x4e, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00,
        0x01, 0x00, 0x01, 0x00, 0x07, 0x00, 0x58, 0x02, 0x34, 0x39, 0x34, 0x33, 0x00, 0x00, 0x01, 0x00,
        0x26, 0x42, 0x28, 0x12, 0x12, 0x09, 0xc0, 0xa8, 0x00, 0x00, 0x30, 0x00, 0x11, 0x41, 0x14, 0x00,
        0x01, 0x00, 0x14, 0x00, 0x04, 0x00, 0x00, 0x00, 0x20, 0x35, 0x5e, 0x01, 0x02, 0x3d, 0x1e, 0x3d,
        0x39, 0x3d, 0x53, 0x3d, 0x6e, 0x3d, 0x88, 0x3d, 0xa2, 0x3d, 0xbb, 0x3d, 0xd4, 0x3d, 0xed, 0x3d,
        0x06, 0x3e, 0x1e, 0x3e, 0x36, 0x3e, 0x4e, 0x3e, 0x65, 0x3e, 0x7d, 0x3e, 0x93, 0x3e, 0xaa, 0x3e,
        0xc0, 0x3e, 0xd6, 0x3e, 0xec, 0x3e, 0x02, 0x3f, 0x17, 0x3f, 0x2c, 0x3f, 0x41, 0x3f, 0x55, 0x3f,
        0x69, 0x3f, 0x7d, 0x3f, 0x91, 0x3f, 0xa4, 0x3f, 0xb8, 0x3f, 0xca, 0x3f, 0xdd, 0x3f, 0xf0, 0x3f,
        0x02, 0x40, 0x14, 0x40, 0x26, 0x40, 0x37, 0x40, 0x49, 0x40, 0x5a, 0x40, 0x6b, 0x40, 0x7c, 0x40,
        0x8c, 0x40, 0x9c, 0x40, 0xac, 0x40, 0xbc, 0x40, 0xcc, 0x40, 0xdb, 0x40, 0xea, 0x40, 0xf9, 0x40,
        0x08, 0x41, 0x17, 0x41, 0x25, 0x41, 0x33, 0x41, 0x42, 0x41, 0x4f, 0x41, 0x5d, 0x41, 0x6a, 0x41,
        0x78, 0x41, 0x85, 0x41, 0x92, 0x41, 0x9e, 0x41, 0xab, 0x41, 0xb7, 0x41, 0xc3, 0x41, 0xcf, 0x41,
        0xdb, 0x41, 0xe7, 0x41, 0xf2, 0x41, 0xfd, 0x41, 0x08, 0x42, 0x13, 0x42, 0x1e, 0x42, 0x28, 0x42,
        0x33, 0x42, 0x3d, 0x42, 0x47, 0x42, 0x51, 0x42, 0x5b, 0x42, 0x64, 0x42, 0x6e, 0x42, 0x77, 0x42,
        0x80, 0x42, 0x89, 0x42, 0x91, 0x42, 0x9a, 0x42, 0xa2, 0x42, 0xaa, 0x42, 0xb2, 0x42, 0xba, 0x42,
        0x33, 0x33, 0x30, 0x35, 0x2d, 0x30, 0x30, 0x31, 0x30, 0x36, 0x5f, 0x30, 0x30, 0x30, 0x30, 0x31,
        0x5f, 0x32, 0x38, 0x30, 0x39, 0x32, 0x30, 0x31, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x5a, 0x00, 0x5a, 0x00, 0xbc, 0x02,
        0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2a, 0x00, 0x00, 0x00,
        0x02, 0x00, 0x14, 0x00, 0xea, 0x01, 0x14, 0x00, 0xea, 0x01, 0x0a, 0x00, 0x05, 0x00, 0x00, 0x00,
        0x40, 0x00, 0x40, 0x00, 0x02, 0x00, 0x0f, 0x00, 0x5a, 0x00, 0x00, 0x00, 0x01, 0x00, 0xc8, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x0f, 0x00, 0xea, 0x01, 0xea, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x07, 0x12, 0x00, 0x80, 0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x82, 0x00, 0x00, 0x00, 0x0a, 0x00, 0x08, 0x00, 0xb1, 0x2b, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00,
        0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0xff,
        0xcd, 0xff, 0x8b, 0x00, 0xe5, 0x00, 0xee, 0x00, 0x0b, 0x00, 0x84, 0xff, 0x3d, 0xff, 0xa7, 0xff]
    
    user_config = ''
    for value in user_config_values:
        user_config += chr(value)
    return user_config

PORT_TIMESTAMP = 3558720820.531179
DRIVER_TIMESTAMP = 3555423722.711772


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

class DriverTestMixinSub(DriverTestMixin):
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

    _battery_voltage_parameter = {
        NortekEngBatteryDataParticleKey.BATTERY_VOLTAGE: {TYPE: int, VALUE: 0, REQUIRED: True}
    }

    _clock_data_parameter = {
        NortekEngClockDataParticleKey.DATE_TIME_ARRAY: {TYPE: list, VALUE: [1, 2, 3, 4, 5, 6], REQUIRED: True},
        NortekEngClockDataParticleKey.DATE_TIME_STAMP: {TYPE: int, VALUE: 0, REQUIRED: False}
    }

    _user_config_parameters = {
        NortekUserConfigDataParticleKey.TX_LENGTH: {TYPE: int, VALUE: 2, REQUIRED: True},
        NortekUserConfigDataParticleKey.BLANK_DIST: {TYPE: int, VALUE: 16, REQUIRED: True},
        NortekUserConfigDataParticleKey.RX_LENGTH: {TYPE: int, VALUE: 7, REQUIRED: True},
        NortekUserConfigDataParticleKey.TIME_BETWEEN_PINGS: {TYPE: int, VALUE: 44, REQUIRED: True},
        NortekUserConfigDataParticleKey.TIME_BETWEEN_BURSTS: {TYPE: int, VALUE: 512, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_PINGS: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.AVG_INTERVAL: {TYPE: int, VALUE: 61, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_BEAMS: {TYPE: int, VALUE: 3, REQUIRED: True},
        NortekUserConfigDataParticleKey.PROFILE_TYPE: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.MODE_TYPE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.TCR: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekUserConfigDataParticleKey.PCR: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekUserConfigDataParticleKey.POWER_TCM1: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.POWER_TCM2: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.SYNC_OUT_POSITION: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.SAMPLE_ON_SYNC: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.START_ON_SYNC: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.POWER_PCR1: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.POWER_PCR2: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.COMPASS_UPDATE_RATE: {TYPE: int, VALUE: 2, REQUIRED: True},
        NortekUserConfigDataParticleKey.COORDINATE_SYSTEM: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_CELLS: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.CELL_SIZE: {TYPE: int, VALUE: 7, REQUIRED: True},
        NortekUserConfigDataParticleKey.MEASUREMENT_INTERVAL: {TYPE: int, VALUE: 3600, REQUIRED: True},
        NortekUserConfigDataParticleKey.DEPLOYMENT_NAME: {TYPE: unicode, VALUE: '4943', REQUIRED: True},
        NortekUserConfigDataParticleKey.WRAP_MODE: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.DEPLOY_START_TIME: {TYPE: list, VALUE: [26, 42, 28, 12, 12, 9], REQUIRED: True},
        NortekUserConfigDataParticleKey.DIAG_INTERVAL: {TYPE: int, VALUE: 43200, REQUIRED: True},
        NortekUserConfigDataParticleKey.MODE: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekUserConfigDataParticleKey.USE_SPEC_SOUND_SPEED: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.DIAG_MODE_ON: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.ANALOG_OUTPUT_ON: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.OUTPUT_FORMAT: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.SCALING: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.SERIAL_OUT_ON: {TYPE: bool, VALUE: True, REQUIRED: True},
        NortekUserConfigDataParticleKey.STAGE_ON: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.ANALOG_POWER_OUTPUT: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.SOUND_SPEED_ADJUST: {TYPE: int, VALUE: 16657, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_DIAG_SAMPLES: {TYPE: int, VALUE: 20, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_BEAMS_PER_CELL: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_PINGS_DIAG: {TYPE: int, VALUE: 20, REQUIRED: True},
        NortekUserConfigDataParticleKey.MODE_TEST: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekUserConfigDataParticleKey.USE_DSP_FILTER: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekUserConfigDataParticleKey.FILTER_DATA_OUTPUT: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.ANALOG_INPUT_ADDR: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.SW_VER: {TYPE: int, VALUE: 13600, REQUIRED: True},
        NortekUserConfigDataParticleKey.VELOCITY_ADJ_FACTOR: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekUserConfigDataParticleKey.FILE_COMMENTS: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekUserConfigDataParticleKey.WAVE_MODE: {TYPE: int, VALUE: 1, REQUIRED: False},
        NortekUserConfigDataParticleKey.WAVE_DATA_RATE: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.WAVE_CELL_POS: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.DYNAMIC_POS_TYPE: {TYPE: int, VALUE: 1, REQUIRED: True},
        NortekUserConfigDataParticleKey.PERCENT_WAVE_CELL_POS: {TYPE: int, VALUE: 32768, REQUIRED: True},
        NortekUserConfigDataParticleKey.WAVE_TX_PULSE: {TYPE: int, VALUE: 16384, REQUIRED: True},
        NortekUserConfigDataParticleKey.FIX_WAVE_BLANK_DIST: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.WAVE_CELL_SIZE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_DIAG_PER_WAVE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.NUM_SAMPLE_PER_BURST: {TYPE: int, VALUE: 10, REQUIRED: True},
        NortekUserConfigDataParticleKey.ANALOG_SCALE_FACTOR: {TYPE: int, VALUE: 11185, REQUIRED: True},
        NortekUserConfigDataParticleKey.CORRELATION_THRS: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekUserConfigDataParticleKey.TX_PULSE_LEN_2ND: {TYPE: int, VALUE: 2, REQUIRED: True},
        NortekUserConfigDataParticleKey.FILTER_CONSTANTS: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekUserConfigDataParticleKey.CHECKSUM: {TYPE: int, VALUE: 0, REQUIRED: False}
    }

    _head_config_parameter = {
        NortekHeadConfigDataParticleKey.PRESSURE_SENSOR: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.MAG_SENSOR: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.TILT_SENSOR: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.TILT_SENSOR_MOUNT: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.HEAD_FREQ: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.HEAD_TYPE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHeadConfigDataParticleKey.HEAD_SERIAL: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekHeadConfigDataParticleKey.SYSTEM_DATA: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekHeadConfigDataParticleKey.NUM_BEAMS: {TYPE: int, VALUE: 3, REQUIRED: True},
        NortekHeadConfigDataParticleKey.CONFIG: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekUserConfigDataParticleKey.CHECKSUM: {TYPE: int, VALUE: 0, REQUIRED: False}
    }

    _hardware_config_parameter = {
        NortekHardwareConfigDataParticleKey.SERIAL_NUM: {TYPE: unicode, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.RECORDER_INSTALLED: {TYPE: bool, VALUE: False, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.COMPASS_INSTALLED: {TYPE: bool, VALUE: True, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.BOARD_FREQUENCY: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.PIC_VERSION: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.HW_REVISION: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.RECORDER_SIZE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.VELOCITY_RANGE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NortekHardwareConfigDataParticleKey.FW_VERSION: {TYPE: unicode, VALUE: '', REQUIRED: True},
        NortekHardwareConfigDataParticleKey.STATUS: {TYPE: int, VALUE: 0, REQUIRED: False},
        NortekHardwareConfigDataParticleKey.CONFIG: {TYPE: unicode, VALUE: 0, REQUIRED: False},
        NortekHardwareConfigDataParticleKey.CHECKSUM: {TYPE: int, VALUE: 0, REQUIRED: False}
    }

    def assert_particle_battery(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(NortekEngBatteryDataParticleKey, self._battery_voltage_parameter)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.BATTERY)
        self.assert_data_particle_parameters(data_particle, self._battery_voltage_parameter, verify_values)

    def assert_particle_clock(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(NortekEngClockDataParticleKey, self._clock_data_parameter)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.CLOCK)
        self.assert_data_particle_parameters(data_particle, self._clock_data_parameter, verify_values)

    def assert_particle_hardware(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(NortekHardwareConfigDataParticleKey, self._hardware_config_parameter)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.HARDWARE_CONFIG)
        self.assert_data_particle_parameters(data_particle, self._hardware_config_parameter, verify_values)

    def assert_particle_head(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(NortekHeadConfigDataParticleKey, self._head_config_parameter)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.HEAD_CONFIG)
        self.assert_data_particle_parameters(data_particle, self._head_config_parameter, verify_values)

    def assert_particle_user(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """

        self.assert_data_particle_keys(NortekUserConfigDataParticleKey, self._user_config_parameters)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.USER_CONFIG)
        self.assert_data_particle_parameters(data_particle, self._user_config_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class NortekUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    # def assert_chunker_fragmented_sample(self, chunker, fragments, sample):
    #     '''
    #     Verify the chunker can parse a sample that comes in fragmented
    #     @param chunker: Chunker to use to do the parsing
    #     @param sample: raw sample
    #     '''
    #     timestamps = []
    #     for f in fragments:
    #         ts = self.get_ntp_timestamp()
    #         timestamps.append(ts)
    #         chunker.add_chunk(f, ts)
    #         (timestamp, result) = chunker.get_next_data()
    #         if (result): break
    #
    #     self.assertEqual(result, sample)
    #     self.assertEqual(timestamps[0], timestamp)
    #
    #     (timestamp, result) = chunker.get_next_data()
    #     self.assertEqual(result, None)

    # def assert_chunker_combined_sample(self, chunker, sample1, sample2, sample3):
    #     '''
    #     Verify the chunker can parse samples that comes in combined
    #     @param chunker: Chunker to use to do the parsing
    #     @param sample: raw sample
    #     '''
    #     ts = self.get_ntp_timestamp()
    #     chunker.add_chunk(sample1 + sample2 + sample3, ts)
    #
    #     (timestamp, result) = chunker.get_next_data()
    #     self.assertEqual(result, sample1)
    #     self.assertEqual(ts, timestamp)
    #
    #     (timestamp, result) = chunker.get_next_data()
    #     self.assertEqual(result, sample2)
    #     self.assertEqual(ts, timestamp)
    #
    #     (timestamp, result) = chunker.get_next_data()
    #     self.assertEqual(result, sample3)
    #     self.assertEqual(ts, timestamp)
    #
    #     (timestamp,result) = chunker.get_next_data()
    #     self.assertEqual(result, None)

    def test_date_conversion(self):
        date = "\x09\x07\x02\x11\x10\x12"
        datetime_from_words = NortekProtocolParameterDict.convert_words_to_datetime(date)
        log.debug("Date time conversion from words: %s", datetime_from_words)
        words_from_datetime = NortekProtocolParameterDict.convert_datetime_to_words(datetime_from_words)
        log.debug("Date time conversion back to words: %s", words_from_datetime)
        self.assertEqual(words_from_datetime, date)

    def test_core_chunker(self):
        """
        Tests the chunker
        """
        chunker = StringChunker(NortekInstrumentProtocol.chunker_sieve_function)

        # test complete data structures
        self.assert_chunker_sample(chunker, hw_config_sample())
        self.assert_chunker_sample(chunker, head_config_sample())
        self.assert_chunker_sample(chunker, user_config_sample())

        # test fragmented data structures
        self.assert_chunker_fragmented_sample(chunker, hw_config_sample())
        self.assert_chunker_fragmented_sample(chunker, head_config_sample())
        self.assert_chunker_fragmented_sample(chunker, user_config_sample())

        # test combined data structures
        self.assert_chunker_combined_sample(chunker, hw_config_sample())
        self.assert_chunker_combined_sample(chunker, head_config_sample())
        self.assert_chunker_combined_sample(chunker, user_config_sample())

        # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, hw_config_sample())
        self.assert_chunker_sample_with_noise(chunker, head_config_sample())
        self.assert_chunker_sample_with_noise(chunker, user_config_sample())

    def test_core_corrupt_data_structures(self):
        # garbage should yield a checksum failure
        particle = NortekHardwareConfigDataParticle(hw_config_sample().replace(chr(0), chr(1), 1), port_timestamp=PORT_TIMESTAMP)
        json_str = particle.generate()
        obj = json.loads(json_str)
        self.assertNotEqual(obj[DataParticleKey.QUALITY_FLAG], DataParticleValue.OK)

        particle = NortekHeadConfigDataParticle(head_config_sample().replace(chr(0), chr(1), 1), port_timestamp=PORT_TIMESTAMP)
        json_str = particle.generate()
        obj = json.loads(json_str)
        self.assertNotEqual(obj[DataParticleKey.QUALITY_FLAG], DataParticleValue.OK)

        particle = NortekUserConfigDataParticle(user_config_sample().replace(chr(0), chr(1), 1), port_timestamp=PORT_TIMESTAMP)
        json_str = particle.generate()
        obj = json.loads(json_str)
        self.assertNotEqual(obj[DataParticleKey.QUALITY_FLAG], DataParticleValue.OK)

    def test_hw_config_sample_format(self):
        """
        Test to make sure we can get hardware config sample data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.HARDWARE_CONFIG,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: hw_config_particle}

        self.compare_parsed_data_particle(NortekHardwareConfigDataParticle, hw_config_sample(), expected_particle)

    def test_head_config_sample_format(self):
        """
        Test to make sure we can get hardware config sample data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.HEAD_CONFIG,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: head_config_particle}

        self.compare_parsed_data_particle(NortekHeadConfigDataParticle, head_config_sample(), expected_particle)
        
    def test_user_config_sample_format(self):
        """
        Test to make sure we can get user config sample data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.USER_CONFIG,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: user_config_particle}

        self.compare_parsed_data_particle(NortekUserConfigDataParticle,
                                          user_config_sample(),
                                          expected_particle)
        
    def test_eng_clock_sample_format(self):
        """
        Test to make sure we can get clock sample engineering data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.CLOCK,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: eng_clock_particle}

        self.compare_parsed_data_particle(NortekEngClockDataParticle,
                                          eng_clock_sample(),
                                          expected_particle)

    def test_eng_battery_sample_format(self):
        """
        Test to make sure we can get battery sample engineering data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.BATTERY,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: eng_battery_particle}

        self.compare_parsed_data_particle(NortekEngBatteryDataParticle,
                                          eng_battery_sample(),
                                          expected_particle)

    def test_eng_id_sample_format(self):
        """
        Test to make sure we can get id sample engineering data out in a
        reasonable format. Parsed is all we care about...raw is tested in the
        base DataParticle tests.
        """
        port_timestamp = PORT_TIMESTAMP
        driver_timestamp = DRIVER_TIMESTAMP

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: NortekDataParticleType.ID_STRING,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: eng_id_particle}

        self.compare_parsed_data_particle(NortekEngIdDataParticle,
                                          eng_id_sample(),
                                          expected_particle)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN:      [ProtocolEvent.DISCOVER],

            ProtocolState.COMMAND:      [ProtocolEvent.GET,
                                         ProtocolEvent.SET,
                                         ProtocolEvent.START_DIRECT,
                                         ProtocolEvent.START_AUTOSAMPLE,
                                         ProtocolEvent.CLOCK_SYNC,
                                         ProtocolEvent.ACQUIRE_SAMPLE,
                                         ProtocolEvent.ACQUIRE_STATUS,
                                         ProtocolEvent.SET_CONFIGURATION,
                                         ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                         # ProtocolEvent.RESET
                                        ],

            ProtocolState.AUTOSAMPLE:   [ProtocolEvent.STOP_AUTOSAMPLE,
                                         ProtocolEvent.SCHEDULED_CLOCK_SYNC],

            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT]
        }

        driver = NortekInstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


    def test_instrumment_prompts_for_duplicates(self):
        """
        Verify that the InstrumentPrompts enumeration has no duplicate values
	that might cause confusion
        """
        self.assert_enum_has_no_duplicates(InstrumentPrompts())


    def test_instrument_commands_for_duplicates(self):
        """
        Verify that the InstrumentCmds enumeration has no duplicate values
	that might cause confusion
        """
        self.assert_enum_has_no_duplicates(InstrumentCmds())

    def test_protocol_state_for_duplicates(self):
        """
        Verify that the ProtocolState enumeration has no duplicate values
	that might cause confusion
        """
        self.assert_enum_has_no_duplicates(ProtocolState())

    def test_protocol_event_for_duplicates(self):
        """
        Verify that the ProtocolEvent enumeration has no duplicate values
	that might cause confusion
        """
        self.assert_enum_has_no_duplicates(ProtocolEvent())

    def test_capability_for_duplicates(self):
        """
        Verify that the Capability enumeration has no duplicate values
	that might cause confusion
        """
        self.assert_enum_has_no_duplicates(Capability())

    def test_parameter_for_duplicates(self):
        """
        Verify that the Parameter enumeration has no duplicate values that
	might cause confusion
        """
        self.assert_enum_has_no_duplicates(Parameter())


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class NortekIntTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):

    @unittest.skip('temp disable')
    def test_commands(self):
        """
        Run instrument commands from command mode.
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    @unittest.skip('temp disable')
    def test_command_acquire_status(self):
        """
        Test acquire status command and events.
        """

        """
        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRESTATUS
        3. verify the particle coming in
        """
        self.assert_initialize_driver(ProtocolState.COMMAND) # at some point, current state probably shouldn't matter
        # self.assert_initialize_driver()

        # test acquire status
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, delay=1)
        #BV
        self.assert_async_particle_generation(NortekDataParticleType.BATTERY, self.assert_particle_battery)
        #RC
        self.assert_async_particle_generation(NortekDataParticleType.CLOCK, self.assert_particle_clock)
        #GP
        self.assert_async_particle_generation(NortekDataParticleType.HARDWARE_CONFIG, self.assert_particle_hardware)
        #GH
        self.assert_async_particle_generation(NortekDataParticleType.HEAD_CONFIG, self.assert_particle_head)
        #GC
        self.assert_async_particle_generation(NortekDataParticleType.USER_CONFIG, self.assert_particle_user)

    #@unittest.skip('temp disable')
    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.TRANSMIT_PULSE_LENGTH, 3)

        #test read/write parameter w/direct access only
        self.assert_set(Parameter.BIN_LENGTH, 7)


        # #test setting date/time
        # self.assert_set(Parameter.CLOCK_DEPLOY, get_timestamp_delayed("%m/%d/%y"))
        #
        # #test read only parameter - should not be set, value should not change
        # self.assert_set(Parameter.SW_VERSION, 13700, no_get=True)
        # reply = self.driver_client.cmd_dvr('get_resource', [Parameter.SW_VERSION])
        # return_value = reply.get(Parameter.SW_VERSION)
        # self.assertNotEqual(return_value, 13700)

    @unittest.skip('temp disable')
    def test_direct_access(self):
        """
        Verify we can enter the direct access state
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)



    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def assertParamDictionariesEqual(self, pd1, pd2, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd1.keys()), set(pd2.keys()))
            for (key, type_val) in pd2.iteritems():
                log.debug("pd1 key: %s, value: %s, type: %s", key, pd1[key], type_val)
                self.assertTrue(isinstance(pd1[key], type_val))
        else:
            for (key, val) in pd1.iteritems():
                self.assertTrue(pd2.has_key(key))
                self.assertTrue(isinstance(val, pd2[key]))
    
    def check_state(self, expected_state):
        self.protocol_state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(self.protocol_state, expected_state)
        return

    def put_driver_in_command_mode(self):
        """Wrap the steps and asserts for going into command mode.
           May be used in multiple test cases.
        """
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

        try:
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)
        except:
            self.assertEqual(self.protocol_state, ProtocolState.AUTOSAMPLE)
            # Put the driver in command mode
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)

    @unittest.skip('temp disable')
    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, puts instrument in 'command' state
        """
        self.put_driver_in_command_mode()

    @unittest.skip('temp disable')
    def test_instrument_clock_sync(self):
        """
        @brief Test for syncing clock
        """

        self.put_driver_in_command_mode()

        # command the instrument to read the clock.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)

        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response[1]))

        # command the instrument to sync the clck.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)

        # command the instrument to read the clock.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)

        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response[1]))

        # verify that the dates match
        local_time = time.gmtime(time.mktime(time.localtime()))
        local_time_str = time.strftime("%d/%m/%Y %H:%M:%S", local_time)
        self.assertTrue(local_time_str[:12].upper() in response[1].upper())

        # verify that the times match closely
        instrument_time = time.strptime(response[1], '%d/%m/%Y %H:%M:%S')
        #log.debug("it=%s, lt=%s", instrument_time, local_time)
        it = datetime.datetime(*instrument_time[:6])
        lt = datetime.datetime(*local_time[:6])
        #log.debug("it=%s, lt=%s, lt-it=%s", it, lt, lt-it)
        if lt - it > datetime.timedelta(seconds = 5):
            self.fail("time delta too large after clock sync")

    @unittest.skip('temp disable')
    def test_instrument_read_clock(self):
        """
        @brief Test for reading instrument clock
        """
        self.put_driver_in_command_mode()

        # command the instrument to read the clock.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)

        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response[1]))

    @unittest.skip('temp disable')
    def test_instrument_read_mode(self):
        """
        @brief Test for reading what mode
        """
        self.put_driver_in_command_mode()

        # command the instrument to read the mode.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_MODE)

        log.debug("what mode returned: %s", response)
        self.assertTrue(2, response[1])

    @unittest.skip('temp disable')
    def test_instrument_power_down(self):
        """
        @brief Test for power_down
        """
        self.put_driver_in_command_mode()

        # command the instrument to power down.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.POWER_DOWN)

    @unittest.skip('temp disable')
    def test_instrument_read_battery_voltage(self):
        """
        @brief Test for reading battery voltage
        """
        self.put_driver_in_command_mode()

        # command the instrument to read the battery voltage.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_BATTERY_VOLTAGE)

        log.debug("read battery voltage returned: %s", response)
        self.assertTrue(isinstance(response[1], int))

    @unittest.skip('temp disable')
    def test_instrument_read_id(self):
        """
        @brief Test for reading ID
        """
        self.put_driver_in_command_mode()

        # command the instrument to read the ID.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_ID)

        log.debug("read ID returned: %s", response)
        self.assertTrue(re.search(r'VEC 8181.*', response[1]))


    @unittest.skip('temp disable')
    def test_instrument_read_hw_config(self):
        """
        @brief Test for reading HW config
        """

        hw_config = {NortekHardwareConfigDataParticleKey.STATUS: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
                     NortekHardwareConfigDataParticleKey.RECORDER_SIZE: 144,
                     NortekHardwareConfigDataParticleKey.SERIAL_NUM: 'VEC 8181      ',
                     NortekHardwareConfigDataParticleKey.FW_VERSION: '3.36',
                     NortekHardwareConfigDataParticleKey.BOARD_FREQUENCY: 65535,
                     NortekHardwareConfigDataParticleKey.PIC_VERSION: 0,
                     NortekHardwareConfigDataParticleKey.HW_REVISION: 4,
                     NortekHardwareConfigDataParticleKey.CONFIG: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
                     NortekHardwareConfigDataParticleKey.CHECKSUM: 18608}

        self.put_driver_in_command_mode()

        # command the instrument to read the hw config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HW_CONFIGURATION)

        log.debug("read HW config returned: %s", response)
        self.assertEqual(hw_config, response[1])

    @unittest.skip('temp disable')
    def test_instrument_read_head_config(self):
        """
        @brief Test for reading HEAD config
        """

        head_config = {NortekHeadConfigDataParticleKey.CONFIG: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1],
                       NortekHeadConfigDataParticleKey.HEAD_SERIAL: 'VEC 4943',
                       NortekHeadConfigDataParticleKey.SYSTEM_DATA: 'AAAAAAAAAACZKsPqq+oOABkl29p4BYMFiQUcvQ0Agivs/x2/BfwiK0IAoA8AAAAA//8AAP//AAD//wAAAAAAAAAA//8AAAEAAAABAAAAAAAAAP////8AAAAA//8BAAAAAAAZAKL2WRTJBQMB2BtaKp2f/vw1Ml0Ae55P/5IyTACYfgr9SP8K/VR9KwHP/jYC/3/6//f/+v8AAAAAAAAAAAAAAAAAAAAAnxQQDhAOECc=',
                       NortekHeadConfigDataParticleKey.HEAD_FREQ: 6000,
                       NortekHeadConfigDataParticleKey.NUM_BEAMS: 3,
                       NortekHeadConfigDataParticleKey.HEAD_TYPE: 1,
                       NortekHeadConfigDataParticleKey.CHECKSUM: 23302}

        self.put_driver_in_command_mode()

        # command the instrument to read the head config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HEAD_CONFIGURATION)

        log.debug("read HEAD config returned: %s", response)
        #for (k, v) in response[1].items():
        #    log.debug("Comparing item with key %s and value %s", k, v)
        #    self.assert_(k in head_config)
        #    self.assert_(v == head_config[k])
        self.assertEqual(head_config, response[1])

    @unittest.skip('temp disable')
    def test_instrument_read_user_config(self):
        """
        Read the user config. Doesnt matter so much whats in there, but the
        length is probably the important bit.
        """
        # This may need adjustment if the real device gets a different default config
        user_config = {NortekUserConfigDataParticleKey.DIAG_INTERVAL: 43200,
                       NortekUserConfigDataParticleKey.PERCENT_WAVE_CELL_POS: 32768,
                       NortekUserConfigDataParticleKey.DEPLOYMENT_NAME: '4943',
                       NortekUserConfigDataParticleKey.TCR: [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0],
                       NortekUserConfigDataParticleKey.NUM_BEAMS_PER_CELL: 1,
                       NortekUserConfigDataParticleKey.FILE_COMMENTS: '3305-00106_00001_28092012',
                       NortekUserConfigDataParticleKey.CORRELATION_THRS: 0,
                       NortekUserConfigDataParticleKey.NUM_SAMPLE_PER_BURST: 10,
                       NortekUserConfigDataParticleKey.MODE_TEST: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
                       NortekUserConfigDataParticleKey.NUM_DIAG_SAMPLES: 20,
                       NortekUserConfigDataParticleKey.CELL_SIZE: 7,
                       NortekUserConfigDataParticleKey.NUM_BEAMS: 3,
                       NortekUserConfigDataParticleKey.WRAP_MODE: 1,
                       NortekUserConfigDataParticleKey.PCR: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       NortekUserConfigDataParticleKey.BLANK_DIST: 16,
                       NortekUserConfigDataParticleKey.WAVE_TX_PULSE: 16384,
                       NortekUserConfigDataParticleKey.TIME_BETWEEN_PINGS: 44,
                       NortekUserConfigDataParticleKey.NUM_DIAG_PER_WAVE: 0,
                       NortekUserConfigDataParticleKey.FIX_WAVE_BLANK_DIST: 0,
                       NortekUserConfigDataParticleKey.SOUND_SPEED_ADJUST: 16657,
                       NortekUserConfigDataParticleKey.FILTER_CONSTANTS: 'Cv/N/4sA5QDuAAsAhP89/w==',
                       NortekUserConfigDataParticleKey.SW_VER: 13600,
                       NortekUserConfigDataParticleKey.VELOCITY_ADJ_FACTOR: 'Aj0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQKxAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC',
                       NortekUserConfigDataParticleKey.DEPLOY_START_TIME: [26, 42, 28, 12, 12, 9],
                       NortekUserConfigDataParticleKey.TX_LENGTH: 2,
                       NortekUserConfigDataParticleKey.MEASUREMENT_INTERVAL: 3600,
                       NortekUserConfigDataParticleKey.WAVE_MODE: [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1],
                       NortekUserConfigDataParticleKey.AVG_INTERVAL: 61,
                       NortekUserConfigDataParticleKey.NUM_CELLS: 1,
                       NortekUserConfigDataParticleKey.COORDINATE_SYSTEM: 1,
                       NortekUserConfigDataParticleKey.CHECKSUM: 64970,
                       NortekUserConfigDataParticleKey.NUM_PINGS: 1,
                       NortekUserConfigDataParticleKey.ANALOG_INPUT_ADDR: 0,
                       NortekUserConfigDataParticleKey.MODE: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
                       NortekUserConfigDataParticleKey.TX_PULSE_LEN_2ND: 2,
                       NortekUserConfigDataParticleKey.RX_LENGTH: 7,
                       NortekUserConfigDataParticleKey.WAVE_CELL_SIZE: 0,
                       NortekUserConfigDataParticleKey.COMPASS_UPDATE_RATE: 2,
                       NortekUserConfigDataParticleKey.TIME_BETWEEN_BURSTS: 512,
                       NortekUserConfigDataParticleKey.ANALOG_SCALE_FACTOR: 11185,
                       NortekUserConfigDataParticleKey.NUM_PINGS_DIAG: 20}

        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('apply_startup_params')

        # command the instrument to read the head config.
        response = self.driver_client.cmd_dvr('execute_resource',
                                          ProtocolEvent.GET_USER_CONFIGURATION)

        log.debug("read USER config returned: %s, length: %s",
              response, len(response))
        self.assertEqual(user_config, response[1])


    # RECORDER
    #def test_instrument_start_measurement_immediate(self):
    """
    @brief Test for starting measurement immediate
    """
    """
        self.put_driver_in_command_mode()
        
        # command the instrument to start measurement immediate.
        self.driver_client.cmd_dvr('execute_resource',
				   ProtocolEvent.START_MEASUREMENT_IMMEDIATE)
        gevent.sleep(100)  # wait for measurement to complete               

        # Verify we received at least 1 sample.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_measurement_at_specific_time: # 0f samples = %d',
		  len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 1)
    """
    
    # RECORDER
    #def test_instrument_start_measurement_at_specific_time(self):
    """
    @brief Test for starting measurement immediate
    """
    """
        self.put_driver_in_command_mode()
        
        # command the instrument to start measurement immediate.
        self.driver_client.cmd_dvr('execute_resource',
				   ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME)
        gevent.sleep(100)  # wait for measurement to complete               

        # Verify we received at least 1 sample.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_measurement_at_specific_time: # 0f samples = %d',
		  len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 1)
    """
    
    # def test_instrument_acquire_sample(self):
    #     """
    #     Test acquire sample command and events.
    #     """
    #
    #     self.put_driver_in_command_mode()
    #
    #     # command the instrument to auto-sample mode.
    #     self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
    #
    #     # wait for some samples to be generated
    #     gevent.sleep(120)
    #
    #     # Verify we received at least 4 samples.
    #     sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
    #     log.debug('test_instrument_acquire_sample: # 0f samples = %d', len(sample_events))
    #     #log.debug('samples=%s' %sample_events)
    #     self.assertTrue(len(sample_events) >= 4)
    #
    # def test_instrument_start_stop_autosample(self):
    #     """
    #     @brief Test for putting instrument in 'auto-sample' state
    #     """
    #     self.put_driver_in_command_mode()
    #
    #     # command the instrument to auto-sample mode.
    #     self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
    #
    #     self.check_state(ProtocolState.AUTOSAMPLE)
    #
    #     # re-initialize the driver and re-discover instrument state (should be in autosample)
    #     # Transition driver to disconnected.
    #     self.driver_client.cmd_dvr('disconnect')
    #
    #     # Test the driver is disconnected.
    #     self.check_state(DriverConnectionState.DISCONNECTED)
    #
    #     # Transition driver to unconfigured.
    #     self.driver_client.cmd_dvr('initialize')
    #
    #     # Test the driver is unconfigured.
    #     self.check_state(DriverConnectionState.UNCONFIGURED)
    #
    #     # Configure driver and transition to disconnected.
    #     self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())
    #
    #     # Test that the driver is in state disconnected.
    #     self.check_state(DriverConnectionState.DISCONNECTED)
    #
    #     # Setup the protocol state machine and the connection to port agent.
    #     self.driver_client.cmd_dvr('connect')
    #
    #     # Test that the driver protocol is in state unknown.
    #     self.check_state(ProtocolState.UNKNOWN)
    #
    #     # Discover what state the instrument is in and set the protocol state accordingly.
    #     self.driver_client.cmd_dvr('discover_state')
    #
    #     self.check_state(ProtocolState.AUTOSAMPLE)
    #
    #     # wait for some samples to be generated
    #     gevent.sleep(200)
    #
    #     # Verify we received at least 4 samples.
    #     sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
    #     log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
    #     #log.debug('samples=%s' %sample_events)
    #     self.assertTrue(len(sample_events) >= 4)
    #
    #     # stop autosample and return to command mode
    #     self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
    #
    #     self.check_state(ProtocolState.COMMAND)
    #
    # def test_scheduled_clock_sync_autosample(self):
    #     """
    #     Verify the scheduled clock sync is triggered and functions as expected
    #     """
    #     self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=20,
    #                                 autosample_command=ProtocolEvent.START_AUTOSAMPLE)
    #
    #     self.assert_current_state(ProtocolState.AUTOSAMPLE)

    # def test_scheduled_clock_sync(self):
    #     """
    #     Verify the scheduled clock sync is triggered and functions as expected
    #     """
    #     start_wall_time = time.gmtime()
    #
    #     self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, delay=20)
    #     self.assert_current_state(ProtocolState.COMMAND)
    #
    #     end_wall_time = time.gmtime()
    #     result = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)
    #     end_time = time.strptime(result[1],
    #                              "%d/%m/%Y %H:%M:%S")
    #
    #     log.debug("Start time: %s, end time: %s", start_wall_time, end_wall_time)
    #     self.assert_(end_wall_time > start_wall_time)
    #     # this could be better...tricky to measure two varying variables
    #     self.assertNotEqual(end_time, end_wall_time) # gonna be off by at least a little
    #     #self.assertNotEqual(end_time_offset, start_time_offset)

    # def test_metadata_generation(self):
    #     """
    #     Test that we can generate metadata information for the driver,
    #     commands, and parameters.
    #     """
    #     self.assert_initialize_driver()
    #     self.assert_metadata_generation(instrument_params=Parameter.list(),
    #                                     commands=Capability.list())
    #
    #     # check one to see that the file is loading data from somewhere. This is
    #     # a brittle test, but a key indicator probably worth having should the
    #     # file load system not be working
    #     json_result = self.driver_client.cmd_dvr("get_config_metadata")
    #     result = json.loads(json_result)
    #
    #     params = result[ConfigMetadataKey.PARAMETERS]
    #     self.assertEqual(params[Parameter.TRANSMIT_PULSE_LENGTH][ParameterDictKey.DESCRIPTION],
    #                      "Transmit pulse length")
    #
    #     cmds = result[ConfigMetadataKey.COMMANDS]
    #     self.assertEqual(cmds[Capability.SET_CONFIGURATION][CommandDictKey.DISPLAY_NAME],
    #                      "Set configuration")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class NortekQualTest(InstrumentDriverQualificationTestCase):

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

        log.debug("Resource Commands: %s ", str(res_cmds))
        log.debug("Resource Parameters: %s ", str(res_pars))
        
        log.debug("Expected Resource Commands: %s ",
		  str(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)))
        log.debug("Expected Resource Parameters: %s ",
		  str(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)))

        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)),
			 sorted(res_cmds))
        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)),
			 sorted(res_pars))

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

        Verifies the acquire_sample command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        for stream in sampleQueue:
            # make sure there aren't any old samples in the data queues.
            self.data_subscribers.clear_sample_queue(stream)

        # Poll for a sample
        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        self.instrument_agent_client.execute_resource(cmd, timeout=timeout)
    
        for stream in sampleQueue:
            # Watch the parsed data queue and return once a sample
            # has been read or the default timeout has been reached.
            samples = self.data_subscribers.get_samples(stream, 1, timeout = timeout)
            self.assertGreaterEqual(len(samples), 1)
            log.error("SAMPLE: %s" % samples)
    
            # Verify
            for sample in samples:
                sampleDataAssert(sample)

        self.assert_reset()
        self.doCleanups()

    def assert_sample_autosample(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test observatory autosample function.

        Verifies the autosample command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        for stream in sampleQueue:
            # make sure there aren't any old samples in the data queues.
            self.data_subscribers.clear_sample_queue(stream)

        # Begin streaming.
        self.assert_start_autosample()
    
        for stream in sampleQueue:
            # Watch the parsed data queue and return once a sample
            # has been read or the default timeout has been reached.
            samples = self.data_subscribers.get_samples(stream, 1, timeout = timeout)
            self.assertGreaterEqual(len(samples), 1)
            log.error("SAMPLE: %s" % samples)
    
            # Verify
            for sample in samples:
                sampleDataAssert(sample)

        # Halt streaming.
        self.assert_stop_autosample()

    def assertBaseSampleDataParticle(self, sample):
	"""
	Assert the base class particle types in one place
	@param sample The sample to test
	@retval True if it matched something, False if it didnt
	"""
        log.debug('assertBaseSampleDataParticle: sample=%s', sample)
        self.assertTrue(sample[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample.get(DataParticleKey.DRIVER_TIMESTAMP),
				   float))
        self.assertTrue(sample.get(DataParticleKey.PREFERRED_TIMESTAMP))
        
        values = sample['values']
        value_ids = []
        for value in values:
            value_ids.append(value[DataParticleKey.VALUE_ID])
        if sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.HARDWARE_CONFIG:
            log.debug('assertSampleDataParticle: NortekHardwareConfigDataParticleKey detected')
            self.assertEqual(sorted(value_ids), sorted(NortekHardwareConfigDataParticleKey.list()))
            for value in values:
                if value[DataParticleKey.VALUE_ID] in \
			(NortekHardwareConfigDataParticleKey.SERIAL_NUM,
			 NortekHardwareConfigDataParticleKey.RECORDER_INSTALLED,
			 NortekHardwareConfigDataParticleKey.COMPASS_INSTALLED,
			 NortekHardwareConfigDataParticleKey.FW_VERSION):
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
        
                else:
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
	    return True
        elif sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.HEAD_CONFIG:
            log.debug('assertSampleDataParticle: NortekHeadConfigDataParticleKey detected')
            self.assertEqual(sorted(value_ids), sorted(NortekHeadConfigDataParticleKey.list()))
            for value in values:
                if value[DataParticleKey.VALUE_ID] in \
		       (NortekHeadConfigDataParticleKey.PRESSURE_SENSOR,
			NortekHeadConfigDataParticleKey.MAG_SENSOR,
			NortekHeadConfigDataParticleKey.TILT_SENSOR,
			NortekHeadConfigDataParticleKey.HEAD_TYPE,
			NortekHeadConfigDataParticleKey.HEAD_SERIAL,
			NortekHeadConfigDataParticleKey.SYSTEM_DATA):
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
        
                else:
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
	    return True
        elif sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.USER_CONFIG:
            log.debug('assertSampleDataParticle: NortekUserConfigDataParticleKey detected')
            self.assertEqual(sorted(value_ids), sorted(NortekUserConfigDataParticleKey.list()))
            for value in values:
                if value[DataParticleKey.VALUE_ID] in \
		       (NortekUserConfigDataParticleKey.USE_SPEC_SOUND_SPEED,
			NortekUserConfigDataParticleKey.DIAG_MODE_ON,
			NortekUserConfigDataParticleKey.ANALOG_OUTPUT_ON,
			NortekUserConfigDataParticleKey.OUTPUT_FORMAT,
			NortekUserConfigDataParticleKey.SCALING,
			NortekUserConfigDataParticleKey.SERIAL_OUT_ON,
			NortekUserConfigDataParticleKey.STAGE_ON,
			NortekUserConfigDataParticleKey.ANALOG_POWER_OUTPUT,
			NortekUserConfigDataParticleKey.USE_DSP_FILTER):
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
        
                else:
                    self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
            return True
        elif sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.CLOCK:
            log.debug('assertSampleDataParticle: NortekEngClockDataParticleKey detected')
            self.assertEqual(sorted(value_ids),
			     sorted(NortekEngClockDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
            return True
        elif sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.BATTERY:
            log.debug('assertSampleDataParticle: NortekEngBatteryDataParticleKey detected')
            self.assertEqual(sorted(value_ids),
			     sorted(NortekEngBatteryDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value[DataParticleKey.VALUE], int))
            return True
        elif sample[DataParticleKey.STREAM_NAME] == NortekDataParticleType.ID_STRING:
            log.debug('assertSampleDataParticle: NortekEngIdDataParticleKey detected')
            self.assertEqual(sorted(value_ids),
			     sorted(NortekEngIdDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value[DataParticleKey.VALUE], str))
            return True
        else:
            return False

    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly
	supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        log.debug("test_direct_access_telnet_mode_manually: starting DA mode")
        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                           kwargs={#'session_type': DirectAccessTypes.telnet,
                                   'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly
	supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("K1W%!Q")
        self.tcp_client.expect("VECTOR")

        self.assert_direct_access_stop_telnet()

    def test_get_set_parameters(self):
        '''
        verify that parameters can be get set properly
        '''
        self.assert_enter_command_mode()
        
        value_before_set = self.get_parameter(Parameter.BLANKING_DISTANCE)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 40)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, value_before_set)

        value_before_set = self.get_parameter(Parameter.NUMBER_SAMPLES_PER_BURST)
        self.assert_set_parameter(Parameter.NUMBER_SAMPLES_PER_BURST, 60)
        self.assert_set_parameter(Parameter.NUMBER_SAMPLES_PER_BURST,
				  value_before_set)

        self.assert_reset()
        
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from
	get_capabilities at various driver/agent states.
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
		ProtocolEvent.GET_USER_CONFIGURATION,
                ProtocolEvent.POWER_DOWN,
                ProtocolEvent.READ_BATTERY_VOLTAGE,
                ProtocolEvent.READ_CLOCK, 
                ProtocolEvent.READ_ID,
                ProtocolEvent.READ_MODE,
                # RECORDER
		#ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME,
                #ProtocolEvent.START_MEASUREMENT_IMMEDIATE,
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
                Parameter.NUMBER_SAMPLES_PER_BURST,
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

        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [DriverEvent.STOP_AUTOSAMPLE]

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
        #log.debug("it=%s, lt=%s", instrument_time, local_time)
        it = datetime.datetime(*instrument_time[:6])
        lt = datetime.datetime(*local_time[:6])
        #log.debug("it=%s, lt=%s, lt-it=%s", it, lt, lt-it)
        if lt - it > datetime.timedelta(seconds = 5):
            self.fail("time delta too large after clock sync")      
