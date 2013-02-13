"""
@package mi.instrument.seabird.sbe26plus.ooicore.test.test_driver
@file mi/instrument/seabird/sbe26plus/ooicore/driver.py
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
import unittest
from nose.plugins.attrib import attr
from mi.instrument.seabird.sbe26plus.test.test_driver import SeaBird26PlusUnitTest
from mi.instrument.seabird.sbe26plus.test.test_driver import SeaBird26PlusIntegrationTest
from mi.instrument.seabird.sbe26plus.test.test_driver import SeaBird26PlusQualificationTest
from mi.instrument.seabird.sbe26plus.test.test_driver import SeaBird26PlusPublicationTest
from mi.instrument.seabird.sbe26plus.driver import DataParticleType
from mi.instrument.seabird.sbe26plus.driver import ScheduledJob
from mi.instrument.seabird.sbe26plus.driver import Parameter
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import DriverStartupConfigKey

InstrumentDriverTestCase.initialize(
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType(),

    driver_module='mi.instrument.seabird.sbe26plus.ooicore.driver',
    driver_class="InstrumentDriver",
    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.TXWAVESTATS: False,
            Parameter.TXREALTIME: True,
            Parameter.TXWAVEBURST: False,
        },
        DriverStartupConfigKey.SCHEDULER: {
            ScheduledJob.ACQUIRE_STATUS: {},
            ScheduledJob.CALIBRATION_COEFFICIENTS: {},
            ScheduledJob.CLOCK_SYNC: {}
        }
    }
)

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SeaBird26PlusUnitTest):
    pass


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SeaBird26PlusIntegrationTest):
    pass


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(SeaBird26PlusQualificationTest):
    pass

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                   #
# testing ion publications                                                    #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(SeaBird26PlusPublicationTest):
    pass