"""
@package mi.instrument.seabird.sbe16plus_v2.ooicore.test.test_driver
@file ion/services/mi/drivers/sbe16_plus_v2/test_sbe16_driver.py
@author David Everett 
@brief Test cases for InstrumentDriver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

"""
__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import unittest
from nose.plugins.attrib import attr

from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEUnitTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEIntTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEQualTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEPubTestCase
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SeaBird16plusMixin

from mi.instrument.seabird.sbe16plus_v2.driver import DataParticleType

from mi.idk.unit_test import InstrumentDriverTestCase

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe16plus_v2.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_preload_id = 'IA5',
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType(),
    startup_config = {}
)

###############################################################################
#                   Driver Version Specific Structures                        #
###############################################################################
###
# Test Inputs
###

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SBEUnitTestCase, SeaBird16plusMixin):
    pass

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SBEIntTestCase):
    pass

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(SBEQualTestCase):
    pass

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(SBEPubTestCase):
    pass
