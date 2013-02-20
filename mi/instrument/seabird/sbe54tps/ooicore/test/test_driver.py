"""
@package mi.instrument.seabird.sbe54plus.ooicore.test.test_driver
@file mi/instrument/seabird/sbe54plus/ooicore/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon

"""
__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mi.instrument.seabird.sbe54tps.test.test_driver import SeaBird54PlusUnitTest
from mi.instrument.seabird.sbe54tps.test.test_driver import SeaBird54PlusIntegrationTest
from mi.instrument.seabird.sbe54tps.test.test_driver import SeaBird54PlusQualificationTest
from mi.instrument.seabird.sbe54tps.test.test_driver import SeaBird54PlusPublicationTest
from mi.instrument.seabird.sbe54tps.driver import DataParticleType
from mi.instrument.seabird.sbe54tps.driver import ScheduledJob
from mi.instrument.seabird.sbe54tps.driver import Parameter
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import DriverStartupConfigKey

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe54tps.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = '123xyz',
    instrument_agent_preload_id = 'ID7',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.SAMPLE_PERIOD: 15,
            Parameter.BATTERY_TYPE: 1,
            Parameter.ENABLE_ALERTS: 1,
        },
        DriverStartupConfigKey.SCHEDULER: {
            ScheduledJob.ACQUIRE_STATUS: {},
            ScheduledJob.STATUS_DATA: {},
            ScheduledJob.HARDWARE_DATA: {},
            ScheduledJob.EVENT_COUNTER_DATA: {},
            ScheduledJob.CONFIGURATION_DATA: {},
            ScheduledJob.CLOCK_SYNC: {}
        }
    }
)

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SeaBird54PlusUnitTest):
    pass

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SeaBird54PlusIntegrationTest):
    pass

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(SeaBird54PlusQualificationTest):
    pass

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(SeaBird54PlusPublicationTest):
    pass
