"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.rsn.test.test_driver
@author Roger Unwin
@brief Test cases for InstrumentDriver

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
from nose.plugins.attrib import attr
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverUnitTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverIntegrationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverQualificationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverPublicationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import DataParticleType
from mi.idk.unit_test import InstrumentDriverTestCase


from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ScheduledJob
###
#   Driver parameters for tests
###

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_75_khz.rsn.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_preload_id = 'IA7',
    instrument_agent_name = 'teledyne_workhorse_monitor_75_khz',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.SERIAL_FLOW_CONTROL: '11110',
            Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.SAVE_NVRAM_TO_RECORDER: True,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.COORDINATE_TRANSFORMATION: '00111',
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            #Parameter.TIME_OF_FIRST_PING: '****/**/**,**:**:**',
            Parameter.TIME_PER_PING: '00:01.00',
            #Parameter.TIME: ,
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.WATER_PROFILING_MODE: 1,
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        },
        DriverStartupConfigKey.SCHEDULER: {
            ScheduledJob.GET_CALIBRATION: {},
            ScheduledJob.GET_CONFIGURATION: {},
            ScheduledJob.CLOCK_SYNC: {}
        }
    }
)
###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(WorkhorseDriverUnitTest):
    pass

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(WorkhorseDriverIntegrationTest):
    pass

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(WorkhorseDriverQualificationTest):
    pass

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(WorkhorseDriverPublicationTest):
    pass
