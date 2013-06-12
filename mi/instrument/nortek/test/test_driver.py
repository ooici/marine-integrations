"""
@package mi.instrument.nortek.test.test_driver
@file mi/instrument/nortek/test/test_driver.py
@author Steve Foley
@brief Common test code for Nortek drivers
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import base64

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.data_particle import DataParticleKey
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticleKey
from mi.instrument.nortek.driver import NortekHeadConfigDataParticleKey
from mi.instrument.nortek.driver import NortekUserConfigDataParticleKey
from mi.instrument.nortek.driver import NortekProtocolParameterDict

def hw_config_sample():
    sample_as_hex = "a505180056454320383138312020202020200400ffff0000040090000\
4000000ffff0000ffffffff0000332e3336b048" 
    return sample_as_hex.decode('hex')

hw_config_particle = [{DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.SERIAL_NUM,
                       DataParticleKey.VALUE: "VEC 8181      "}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.RECORDER_INSTALLED,
                       DataParticleKey.VALUE: 0}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.COMPASS_INSTALLED,
                       DataParticleKey.VALUE: 0}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.BOARD_FREQUENCY,
                       DataParticleKey.VALUE: 65535}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.PIC_VERSION,
                       DataParticleKey.VALUE: 0}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.HW_REVISION,
                       DataParticleKey.VALUE: 4}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.RECORDER_SIZE,
                       DataParticleKey.VALUE: 144}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.VELOCITY_RANGE,
                       DataParticleKey.VALUE: 0}, 
                      {DataParticleKey.VALUE_ID:
                        NortekHardwareConfigDataParticleKey.FW_VERSION,
                       DataParticleKey.VALUE: "3.36"}]

def head_config_sample():
    sample_as_hex = "a50470003700701701005645432034393433000000000000000000000\
000992ac3eaabea0e001925dbda7805830589051cbd0d00822becff1dbf05fc222b4200a00f000\
00000ffff0000ffff0000ffff0000000000000000ffff0000010000000100000000000000fffff\
fff00000000ffff0100000000001900a2f65914c9050301d81b5a2a9d9ffefc35325d007b9e4ff\
f92324c00987e0afd48ff0afd547d2b01cffe3602ff7ffafff7fffaff000000000000000000000\
000000000009f14100e100e10275b0000000000000000000000000000000000000000000300065b"
    return sample_as_hex.decode('hex')

head_config_particle = [{DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.PRESSURE_SENSOR,
                         DataParticleKey.VALUE: 1}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.MAG_SENSOR,
                         DataParticleKey.VALUE: 1}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.TILT_SENSOR,
                         DataParticleKey.VALUE: 1}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.TILT_SENSOR_MOUNT,
                         DataParticleKey.VALUE: 0}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.HEAD_FREQ,
                         DataParticleKey.VALUE: 6000}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.HEAD_TYPE,
                         DataParticleKey.VALUE: 1}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.HEAD_SERIAL,
                         DataParticleKey.VALUE: "VEC 4943"}, 
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.SYSTEM_DATA,
                         DataParticleKey.VALUE: base64.b64encode(\
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
                        {DataParticleKey.VALUE_ID:
                          NortekHeadConfigDataParticleKey.NUM_BEAMS,
                         DataParticleKey.VALUE: 3}]

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

user_config_particle = [{DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.TX_LENGTH,
                         DataParticleKey.VALUE: 2}, 
                        {DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.BLANK_DIST,
                         DataParticleKey.VALUE: 16},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.RX_LENGTH,
                         DataParticleKey.VALUE: 7},
                        {DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.TIME_BETWEEN_PINGS,
                         DataParticleKey.VALUE: 44},
                        {DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.TIME_BETWEEN_BURSTS,
                         DataParticleKey.VALUE: 512},
                        {DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.NUM_PINGS,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.AVG_INTERVAL,
                         DataParticleKey.VALUE: 60},
                        {DataParticleKey.VALUE_ID:
                          NortekUserConfigDataParticleKey.NUM_BEAMS,
                         DataParticleKey.VALUE: 3},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.PROFILE_TYPE,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.MODE_TYPE,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.POWER_TCM1,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.POWER_TCM2,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SYNC_OUT_POSITION,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SAMPLE_ON_SYNC,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.START_ON_SYNC,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.POWER_PCR1,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.POWER_PCR2,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.COMPASS_UPDATE_RATE,
                         DataParticleKey.VALUE: 2},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.COORDINATE_SYSTEM,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_CELLS,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.CELL_SIZE,
                         DataParticleKey.VALUE: 7},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.MEASUREMENT_INTERVAL,
                         DataParticleKey.VALUE: 600},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.DEPLOYMENT_NAME,
                         DataParticleKey.VALUE: "4943"},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.WRAP_MODE,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.DEPLOY_START_TIME,
                         DataParticleKey.VALUE: [26, 42, 28, 12, 12, 9]},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.DIAG_INTERVAL,
                         DataParticleKey.VALUE: 43200},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.USE_SPEC_SOUND_SPEED,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.DIAG_MODE_ON,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.ANALOG_OUTPUT_ON,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.OUTPUT_FORMAT,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SCALING,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SERIAL_OUT_ON,
                         DataParticleKey.VALUE: True},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.STAGE_ON,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.ANALOG_POWER_OUTPUT,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SOUND_SPEED_ADJUST,
                         DataParticleKey.VALUE: 16657},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_DIAG_SAMPLES,
                         DataParticleKey.VALUE: 20},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_BEAMS_PER_CELL,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_PINGS_DIAG,
                         DataParticleKey.VALUE: 20},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.USE_DSP_FILTER,
                         DataParticleKey.VALUE: False},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.FILTER_DATA_OUTPUT,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.ANALOG_INPUT_ADDR,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.SW_VER,
                         DataParticleKey.VALUE: 13600},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.VELOCITY_ADJ_FACTOR,
                         DataParticleKey.VALUE: \
                          "Aj0ePTk9Uz1uPYg9oj27PdQ97T0GPh4+Nj5OPmU+fT6TPqo+wD7WPuw+Aj8XPyw/QT9VP2k/fT+RP6Q/uD/KP90/8D8CQBRAJkA3QElAWkBrQHxAjECcQKxAvEDMQNtA6kD5QAhBF0ElQTNBQkFPQV1BakF4QYVBkkGeQatBt0HDQc9B20HnQfJB/UEIQhNCHkIoQjNCPUJHQlFCW0JkQm5Cd0KAQolCkUKaQqJCqkKyQrpC"},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.FILE_COMMENTS,
                         DataParticleKey.VALUE: "3305-00106_00001_28092012"},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.WAVE_DATA_RATE,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.WAVE_CELL_POS,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.DYNAMIC_POS_TYPE,
                         DataParticleKey.VALUE: 1},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.PERCENT_WAVE_CELL_POS,
                         DataParticleKey.VALUE: 32768},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.WAVE_TX_PULSE,
                         DataParticleKey.VALUE: 16384},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.FIX_WAVE_BLANK_DIST,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.WAVE_CELL_SIZE,
                         DataParticleKey.VALUE: 0},                         
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_DIAG_PER_WAVE,
                         DataParticleKey.VALUE: 0},
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.NUM_SAMPLE_PER_BURST,
                         DataParticleKey.VALUE: 10},                         
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.ANALOG_SCALE_FACTOR,
                         DataParticleKey.VALUE: 11185}, 
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.CORRELATION_THRS,
                         DataParticleKey.VALUE: 0}, 
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.TX_PULSE_LEN_2ND,
                         DataParticleKey.VALUE: 2}, 
                        {DataParticleKey.VALUE_ID:
			  NortekUserConfigDataParticleKey.FILTER_CONSTANTS,
                         DataParticleKey.VALUE: 'Cv/N/4sA5QDuAAsAhP89/w=='}]
