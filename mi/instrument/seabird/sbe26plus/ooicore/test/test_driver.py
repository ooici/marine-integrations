"""
@package mi.instrument.seabird.sbe26plus.ooicore.test.test_driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore/driver.py
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
from mock import patch
from nose.plugins.attrib import attr
from mi.instrument.seabird.sbe26plus.test.test_driver import SBE26PlusUnitFromIDK
from mi.instrument.seabird.sbe26plus.test.test_driver import SBE26PlusIntFromIDK
from mi.instrument.seabird.sbe26plus.test.test_driver import SBE26PlusQualFromIDK
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.instrument.seabird.sbe26plus.ooicore.driver import PACKET_CONFIG
#from prototype.sci_data.stream_defs import ctd_stream_definition


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SBE26PlusUnitFromIDK):
    """

    """

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(SBE26PlusIntFromIDK):
    """

    """
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(SBE26PlusQualFromIDK):
    """
    
    """
