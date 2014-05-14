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
import json

from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger; log = get_logger()

from mi.idk.unit_test import InstrumentDriverUnitTestCase, ParameterTestConfigKey, InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import DriverTestMixin

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

from mi.core.instrument.instrument_driver import DriverConnectionState, DriverParameter, DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.instrument.protocol_cmd_dict import CommandDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictKey, ParameterDictType

from mi.instrument.nortek.driver import NortekProtocolParameterDict, TIMEOUT, \
    NortekParameterDictVal, EngineeringParameter, INTERVAL_TIME_REGEX
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
from mi.core.exceptions import NotImplementedException, InstrumentCommandException, InstrumentParameterException

from interface.objects import AgentCommand

from mi.instrument.nortek.driver import InstrumentPrompts, Parameter, ProtocolState, ProtocolEvent, InstrumentCmds, \
    Capability, NEWLINE


InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='3DLE2A',
    instrument_agent_name='nortek_driver',
    instrument_agent_packet_config=NortekDataParticleType(),

    driver_startup_config={
        DriverConfigKey.PARAMETERS:
            {EngineeringParameter.CLOCK_SYNC_INTERVAL: '00:00:10',
             EngineeringParameter.ACQUIRE_STATUS_INTERVAL: '00:00:10'}}
)


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
                        {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SW_VER, DataParticleKey.VALUE: 13600},
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

eng_id_particle = [{DataParticleKey.VALUE_ID: NortekEngIdDataParticleKey.ID, DataParticleKey.VALUE: "4151442031323135202020202020"}]


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

    _id_parameter = {
        NortekEngIdDataParticleKey.ID: {TYPE: str, VALUE: '', REQUIRED:True}
    }

    _driver_parameters = {
        Parameter.TRANSMIT_PULSE_LENGTH: {TYPE: int, VALUE: 2, REQUIRED: True},
        Parameter.BLANKING_DISTANCE: {TYPE: int, VALUE: 16, REQUIRED: True},
        Parameter.RECEIVE_LENGTH: {TYPE: int, VALUE: 7, REQUIRED: True},
        Parameter.TIME_BETWEEN_PINGS: {TYPE: int, VALUE: 44, REQUIRED: True},
        Parameter.TIME_BETWEEN_BURST_SEQUENCES: {TYPE: int, VALUE: 512, REQUIRED: True},
        Parameter.NUMBER_PINGS: {},
        Parameter.AVG_INTERVAL: {},
        Parameter.USER_NUMBER_BEAMS: {},
        Parameter.TIMING_CONTROL_REGISTER: {},
        Parameter.POWER_CONTROL_REGISTER: {},
        Parameter.A1_1_SPARE: {},
        Parameter.B0_1_SPARE: {},
        Parameter.B1_1_SPARE: {},
        Parameter.COMPASS_UPDATE_RATE: {},
        Parameter.COORDINATE_SYSTEM: {},
        Parameter.NUMBER_BINS: {},
        Parameter.BIN_LENGTH: {},
        Parameter.MEASUREMENT_INTERVAL: {},
        Parameter.DEPLOYMENT_NAME: {},
        Parameter.WRAP_MODE: {},
        Parameter.CLOCK_DEPLOY: {},
        Parameter.DIAGNOSTIC_INTERVAL: {},
        Parameter.MODE: {},
        Parameter.ADJUSTMENT_SOUND_SPEED: {},
        Parameter.NUMBER_SAMPLES_DIAGNOSTIC: {},
        Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC: {},
        Parameter.NUMBER_PINGS_DIAGNOSTIC: {},
        Parameter.MODE_TEST: {},
        Parameter.ANALOG_INPUT_ADDR: {},
        Parameter.SW_VERSION: {},
        Parameter.USER_1_SPARE: {},
        Parameter.VELOCITY_ADJ_TABLE: {},
        Parameter.COMMENTS: {},
        Parameter.WAVE_MEASUREMENT_MODE: {},
        Parameter.DYN_PERCENTAGE_POSITION: {},
        Parameter.WAVE_TRANSMIT_PULSE: {},
        Parameter.WAVE_BLANKING_DISTANCE: {},
        Parameter.WAVE_CELL_SIZE: {},
        Parameter.NUMBER_DIAG_SAMPLES: {},
        Parameter.A1_2_SPARE: {},
        Parameter.B0_2_SPARE: {},
        Parameter.NUMBER_SAMPLES_PER_BURST: {},
        Parameter.USER_2_SPARE: {},
        Parameter.ANALOG_OUTPUT_SCALE: {},
        Parameter.CORRELATION_THRESHOLD: {},
        Parameter.USER_3_SPARE: {},
        Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG: {},
        Parameter.USER_4_SPARE: {},
        Parameter.QUAL_CONSTANTS: {},
        EngineeringParameter.CLOCK_SYNC_INTERVAL: {},
        EngineeringParameter.ACQUIRE_STATUS_INTERVAL: {},
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

    def assert_particle_id(self, data_particle, verify_values=False):
        """
        Verify [flortd]_sample particle
        @param data_particle:  [FlortDSample]_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(NortekEngIdDataParticleKey, self._id_parameter)
        self.assert_data_particle_header(data_particle, NortekDataParticleType.ID_STRING)
        self.assert_data_particle_parameters(data_particle, self._id_parameter, verify_values)

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class NortekUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_base_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the capabilities
        """
        self.assert_enum_has_no_duplicates(NortekDataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(InstrumentPrompts())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_enums(self):
        raise NotImplementedException('Implement in child class!')

    def test_chunker(self):
        raise NotImplementedException('Implement in child class!')

    def test_base_driver_protocol_filter_capabilities(self):
        """
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="PortAgentClient")
        protocol = NortekInstrumentProtocol(InstrumentPrompts, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_date_conversion(self):
        """
        Verify the date is converted correctly from hex to ASCII then back to hex
        """
        date = "\x09\x07\x02\x11\x10\x12"
        datetime_from_words = NortekProtocolParameterDict.convert_words_to_datetime(date)
        log.debug("Date time conversion from words: %s", datetime_from_words)
        words_from_datetime = NortekProtocolParameterDict.convert_datetime_to_words(datetime_from_words)
        log.debug("Date time conversion back to words: %s", words_from_datetime)
        self.assertEqual(words_from_datetime, date)

    def test_core_chunker(self):
        """
        Verify the chunker can parse each sample type
        1. complete data structure
        2. fragmented data structure
        3. combined data structure
        4. data structure with noise
        """
        chunker = StringChunker(NortekInstrumentProtocol.chunker_sieve_function)

        #test complete data structures
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

        # # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, hw_config_sample())
        self.assert_chunker_sample_with_noise(chunker, head_config_sample())
        self.assert_chunker_sample_with_noise(chunker, user_config_sample())

    def test_core_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, it will not generate
        """
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
        Verify driver can get hardware config sample data out in a
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
        Verify driver can get hardware config sample data out in a
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
        Verify driver can get user config sample data out in a
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
        Verify driver can get clock sample engineering data out in a
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
        Verify driver can get battery sample engineering data out in a
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
        Verify driver can get id sample engineering data out in a
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
            ProtocolState.UNKNOWN:      [ProtocolEvent.DISCOVER,
                                         ProtocolEvent.READ_MODE],

            ProtocolState.COMMAND:      [ProtocolEvent.GET,
                                         ProtocolEvent.SET,
                                         ProtocolEvent.START_DIRECT,
                                         ProtocolEvent.START_AUTOSAMPLE,
                                         ProtocolEvent.CLOCK_SYNC,
                                         ProtocolEvent.ACQUIRE_SAMPLE,
                                         ProtocolEvent.ACQUIRE_STATUS,
                                         ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                         ProtocolEvent.SCHEDULED_ACQUIRE_STATUS],

            ProtocolState.AUTOSAMPLE:   [ProtocolEvent.STOP_AUTOSAMPLE,
                                         ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                         ProtocolEvent.SCHEDULED_ACQUIRE_STATUS,
                                         ProtocolEvent.READ_MODE],

            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT,
                                          ProtocolEvent.READ_MODE]
        }

        driver = NortekInstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_scheduled_clock_sync_acquire_status(self):
        """
        Verify the scheduled clock sync and acquire status is added to the protocol
        Verify if there is no scheduling, nothing is added to the protocol
        """
        mock_callback = Mock(spec="PortAgentClient")
        protocol = NortekInstrumentProtocol(InstrumentPrompts, NEWLINE, mock_callback)

        #Verify there is nothing scheduled
        self.assertEqual(protocol._scheduler_callback.get(ScheduledJob.CLOCK_SYNC), None)
        self.assertEqual(protocol._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS), None)

        protocol._param_dict.add_parameter(NortekParameterDictVal(EngineeringParameter.CLOCK_SYNC_INTERVAL,
                                   INTERVAL_TIME_REGEX,
                                   lambda match: match.group(1),
                                   str,
                                   type=ParameterDictType.STRING,
                                   display_name="clock sync interval",
                                   default_value='00:00:10'))
        protocol._param_dict.add_parameter(
                                   NortekParameterDictVal(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
                                   INTERVAL_TIME_REGEX,
                                   lambda match: match.group(1),
                                   str,
                                   type=ParameterDictType.STRING,
                                   display_name="acquire status interval",
                                   default_value='00:00:10'))
        #set the values of the dictionary using set_default
        protocol._param_dict.set_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
                                   protocol._param_dict.get_default_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL))
        protocol._param_dict.set_value(EngineeringParameter.CLOCK_SYNC_INTERVAL,
                                   protocol._param_dict.get_default_value(EngineeringParameter.CLOCK_SYNC_INTERVAL))
        protocol._handler_autosample_enter()

        #Verify there is scheduled events
        self.assertTrue(protocol._scheduler_callback.get(ScheduledJob.CLOCK_SYNC))
        self.assertTrue(protocol._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS))


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class NortekIntTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_set_init_params(self):
        """
        Verify the instrument will set the init params from a config file
        """
        self.assert_initialize_driver()
        log.debug("FINISHED INIT DRIVER")

        values_before = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        log.debug("VALUES_BEFORE = %s", values_before)
        self.assertEquals(values_before[Parameter.MEASUREMENT_INTERVAL], 3600)
        self.assertEquals(values_before[Parameter.NUMBER_SAMPLES_PER_BURST], 0)

        self.driver_client.cmd_dvr('set_init_params',
                                   {DriverConfigKey.PARAMETERS:
                                       {DriverParameter.ALL:
                                        base64.b64encode(user_config1())}})

        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)
        log.debug("VALUES_AFTER = %s", values_after)

        # check to see if startup config got set in instrument
        self.assertEquals(values_after[Parameter.MEASUREMENT_INTERVAL], 500)
        self.assertEquals(values_after[Parameter.NUMBER_SAMPLES_PER_BURST], 20)

    def test_set_get_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set direct access
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #test parameter w/direct access only
        self.assert_set(Parameter.COMPASS_UPDATE_RATE, 1, no_get=True)

        #test start parameter
        self.assert_set_exception(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, '00:20:00', exception_class=InstrumentParameterException)

        #test read only parameter
        self.assert_set_exception(Parameter.USER_4_SPARE, 'blah', exception_class=InstrumentParameterException)


    def test_instrument_clock_sync(self):
        """
        Verify the driver can sync the clock
        """
        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)

    def test_acquire_sample(self):
        """
        Verify the driver send the acquire sample command and receive the events.
        1. initialize the instrument to COMMAND state
        2. command the driver to ACQUIRE SAMPLE
        3. verify the particle coming in

        Implement in child class because the particles being generated are specific to the instrument
        """
        raise NotImplementedException('Implement in child class!')

    def test_command_autosample(self):
        """
        Verify the driver can send the autosample command and receive the events.
        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE state
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        5. verify the sampling is continuous by gathering several samples

        Implement in child class because the particles being generated are specific to the instrument
        """
        raise NotImplementedException('Implement in child class!')

    def test_metadata_generation(self):
        """
        Verify the driver generates metadata information
        """
        self.assert_initialize_driver()

        params = EngineeringParameter.list()
        #need to remove, otherwise there will be two DriverParameter.ALL in list
        params.remove(DriverParameter.ALL)

        self.assert_metadata_generation(instrument_params=Parameter.list() + params,
                                        commands=Capability.list())

        # check one to see that the file is loading data from somewhere.
        json_result = self.driver_client.cmd_dvr("get_config_metadata")
        result = json.loads(json_result)

        params = result[ConfigMetadataKey.PARAMETERS]
        self.assertEqual(params[Parameter.TRANSMIT_PULSE_LENGTH][ParameterDictKey.DISPLAY_NAME],
                         "transmit pulse length")

        cmds = result[ConfigMetadataKey.COMMANDS]
        self.assertEqual(cmds[Capability.ACQUIRE_SAMPLE][CommandDictKey.DISPLAY_NAME],
                         "acquire sample")

    def test_command_acquire_status(self):
        """
        Test acquire status command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRE STATUS (BV, RC, GH, GP, GC, ID)
        3. verify the particle coming in
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

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
        #ID
        #self.assert_async_particle_generation(NortekDataParticleType.ID_STRING, self.assert_particle_id)

    def test_direct_access(self):
        """
        Verify the driver can enter/exit the direct access state
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        log.debug('in command mode')
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)
        log.debug('in direct access')

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_DIRECT)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        log.debug('leaving direct access')

    def test_errors(self):
        """
        Verify response to erroneous commands and setting bad parameters.
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #Assert an invalid command
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(ProtocolEvent.STOP_AUTOSAMPLE, exception_class=InstrumentCommandException)

        # Assert set fails with a bad parameter (not ALL or a list).
        self.assert_set_exception('I am a bogus param.', exception_class=InstrumentParameterException)

        #Assert set fails with bad parameter and bad value
        self.assert_set_exception('I am a bogus param.', value='bogus value', exception_class=InstrumentParameterException)

        # put driver in disconnected state.
        self.driver_client.cmd_dvr('disconnect')

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)

        # Test that the driver is in state disconnected.
        self.assert_state_change(DriverConnectionState.DISCONNECTED, timeout=TIMEOUT)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('initialize')

        # Test that the driver is in state unconfigured.
        self.assert_state_change(DriverConnectionState.UNCONFIGURED, timeout=TIMEOUT)

        # Assert we forgot the comms parameter.
        self.assert_driver_command_exception('configure', exception_class=InstrumentParameterException)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.assert_state_change(DriverConnectionState.DISCONNECTED, timeout=TIMEOUT)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class NortekQualTest(InstrumentDriverQualificationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_sync_clock(self):
        """
        Verify the driver can command a clock sync to the instrument
        """
        self.assert_enter_command_mode()

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.CLOCK_SYNC)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=TIMEOUT)

        log.debug('retval = %s', retval)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def test_acquire_status(self):
        """
        Verify the driver can command an acquire status from the instrument
        """
        self.assert_enter_command_mode()

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.ACQUIRE_STATUS)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=TIMEOUT)

        log.debug('retval = %s', retval)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def test_direct_access_telnet_mode(self):
        """
        Verify while in Direct Access, we can manually set DA parameters.  After stopping DA, the instrument
        will enter Command State and any parameters set during DA are reset to previous values.  Also verifying
        timeouts with inactivity, with activity, and without activity.
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        log.debug("DA Server Started.  Reading battery voltage")
        self.tcp_client.send_data("BV")
        self.tcp_client.expect("\x06\x06")

        self.tcp_client.send_data("CC" + user_config2())
        self.tcp_client.expect("\x06\x06")

        self.assert_direct_access_stop_telnet()

        # # verify the setting got restored.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
        self.assert_get_parameter(Parameter.DIAGNOSTIC_INTERVAL, 10800)

        ###
        # Test direct access inactivity timeout
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test session timeout without activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test direct access session timeout with activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            gevent.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 45)


    def test_direct_access_telnet_mode_autosample(self):
        """
        Verify Direct Access can start autosampling for the instrument, and if stopping DA, the
        driver will resort to Autosample State. Also, testing disconnect
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        log.debug("DA Server Started. Put system into autosample")
        self.tcp_client.send_data("ST")
        log.debug("DA autosample started")

        #Assert if stopping DA while autosampling, discover will put driver into Autosample state
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, timeout=10)

    def test_get_set_parameters(self):
        """
        Verify that parameters can be get set properly
        """
        self.assert_enter_command_mode()

        value_before_set = self.get_parameter(Parameter.BLANKING_DISTANCE)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 40)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, value_before_set)

        value_before_set = self.get_parameter(Parameter.AVG_INTERVAL)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, 4)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, value_before_set)

    def test_instrument_set_configuration(self):
        """
        Verify driver can set the instrument configuration
        """
        self.assert_enter_command_mode()

        # command the instrument to set the user configuration.
        cmd = AgentCommand(command=ResourceAgentEvent.EXECUTE_RESOURCE,
                           args=[ProtocolEvent.SET_CONFIGURATION],
                           kwargs={'user_configuration': base64.b64encode(user_config2())})
        try:
            self.instrument_agent_client.execute_agent(cmd)
            pass
        except Exception:
            self.fail('test of set_configuration command failed')

    def test_get_capabilities(self):
        """
        Verify that the correct capabilities are returned from
        get_capabilities at various driver/agent states.
        """
        ##################
        #  Command Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.COMMAND)
        capabilities[AgentCapabilityType.AGENT_PARAMETER] = self._common_agent_parameters()
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [ProtocolEvent.ACQUIRE_SAMPLE,
                                                   ProtocolEvent.GET,
                                                   ProtocolEvent.SET,
                                                   ProtocolEvent.ACQUIRE_STATUS,
                                                   ProtocolEvent.CLOCK_SYNC,
                                                   ProtocolEvent.START_AUTOSAMPLE,
                                                   ProtocolEvent.START_DIRECT]
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [ProtocolEvent.STOP_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        # ##################
        # #  DA Mode
        # ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [ProtocolEvent.STOP_DIRECT]

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
