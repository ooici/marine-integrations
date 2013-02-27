"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

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

import time

from gevent import monkey; monkey.patch_all()

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase

from mi.instrument.seabird.driver import SeaBirdProtocol
from mi.instrument.seabird.driver import SeaBirdParticle
from mi.core.exceptions import InstrumentParameterException


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
class SeaBirdUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_hex2value(self):
        """
        Verify the hex2value method works as expected.
        """
        value = SeaBirdParticle.hex2value("F")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 15)

        value = SeaBirdParticle.hex2value("F", 2)
        self.assertIsInstance(value, float)
        self.assertEqual(value, 7.5)

        value = SeaBirdParticle.hex2value("0xF")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 15)

        value = SeaBirdParticle.hex2value("0x1000")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 4096)

        with self.assertRaises(InstrumentParameterException):
            SeaBirdParticle.hex2value("F", 0)

        with self.assertRaises(InstrumentParameterException):
            SeaBirdParticle.hex2value(1, 0)

    def test_sbetime2unixtime(self):
        """
        Verify the sbetime2unixtime method works as expected.
        """
        value = time.localtime(SeaBirdParticle.sbetime2unixtime(0))
        self.assertEqual("2000-01-01 00:00:00", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(5))
        self.assertEqual("2000-01-01 00:00:05", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(604800))
        self.assertEqual("2000-01-08 00:00:00", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(-1))
        self.assertEqual("1999-12-31 23:59:59", time.strftime("%Y-%m-%d %H:%M:%S", value))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SeaBirdIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class SeaBirdQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

###############################################################################
#                             PUBLICATION  TESTS                              #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class SeaBirdPublicationTest(InstrumentDriverPublicationTestCase):
    def setUp(self):
        InstrumentDriverPublicationTestCase.setUp(self)
