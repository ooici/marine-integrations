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
from mi.instrument.seabird.sbe16plus_v2.test.test_driver import VersionSpecificStructures

from mi.instrument.seabird.sbe16plus_v2.driver import DataParticleType
from mi.instrument.seabird.sbe16plus_v2.driver import NEWLINE

from mi.idk.unit_test import InstrumentDriverTestCase

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe16plus_v2.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_preload_id = 'IA5',
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = DataParticleType()
)

###############################################################################
#                   Driver Version Specific Structures                        #
###############################################################################
###
# Test Inputs
###
VersionSpecificStructures.VALID_SAMPLE = "#0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE
VersionSpecificStructures.VALID_SAMPLE2 = "0409DB0A738C81747A84AC0006000A2E541E18BE6ED9" + NEWLINE

VersionSpecificStructures.VALID_DS_RESPONSE =  'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 16:39:31' + NEWLINE + \
    'vbatt = 23.4, vlith =  8.0, ioper =  61.4 ma, ipump =   0.3 ma,' + NEWLINE + \
    'status = not logging' + NEWLINE + \
    'samples = 0, free = 4386542' + NEWLINE + \
    'sample interval = 10 seconds, number of measurements per sample = 4' + NEWLINE + \
    'pump = run pump during sample, delay before sampling = 0.0 seconds, delay after sampling = 0.0 seconds' + NEWLINE + \
    'transmit real-time = yes' + NEWLINE + \
    'battery cutoff =  7.5 volts' + NEWLINE + \
    'pressure sensor = strain gauge, range = 160.0' + NEWLINE + \
    'SBE 38 = no, SBE 50 = no, WETLABS = no, OPTODE = no, SBE63 = no, Gas Tension Device = no' + NEWLINE + \
    'Ext Volt 0 = yes, Ext Volt 1 = yes' + NEWLINE + \
    'Ext Volt 2 = yes, Ext Volt 3 = yes' + NEWLINE + \
    'Ext Volt 4 = yes, Ext Volt 5 = yes' + NEWLINE + \
    'echo characters = yes' + NEWLINE + \
    'output format = raw HEX' + NEWLINE + \
    'serial sync mode disabled' + NEWLINE

VersionSpecificStructures.VALID_DCAL_QUARTZ = 'SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
    'temperature:  18-May-12' + NEWLINE + \
    '    TA0 = 1.561342e-03' + NEWLINE + \
    '    TA1 = 2.561486e-04' + NEWLINE + \
    '    TA2 = 1.896537e-07' + NEWLINE + \
    '    TA3 = 1.301189e-07' + NEWLINE + \
    '    TOFFSET = 0.000000e+00' + NEWLINE + \
    'conductivity:  18-May-11' + NEWLINE + \
    '    G = -9.896568e-01' + NEWLINE + \
    '    H = 1.316599e-01' + NEWLINE + \
    '    I = -2.213854e-04' + NEWLINE + \
    '    J = 3.292199e-05' + NEWLINE + \
    '    CPCOR = -9.570000e-08' + NEWLINE + \
    '    CTCOR = 3.250000e-06' + NEWLINE + \
    '    CSLOPE = 1.000000e+00' + NEWLINE + \
    'pressure S/N = 125270, range = 1000 psia:  02-nov-12' + NEWLINE + \
    '   PC1 = -4.642673e+03' + NEWLINE + \
    '   PC2 = -4.611640e-03' + NEWLINE + \
    '   PC3 = 8.921190e-04' + NEWLINE + \
    '   PD1 = 7.024800e-02' + NEWLINE + \
    '   PD2 = 0.000000e+00' + NEWLINE + \
    '   PT1 = 3.022595e+01' + NEWLINE + \
    '   PT2 = -1.549720e-04' + NEWLINE + \
    '   PT3 = 2.677750e-06' + NEWLINE + \
    '   PT4 = 1.705490e-09' + NEWLINE + \
    '   PSLOPE = 1.000000e+00' + NEWLINE + \
    '   POFFSET = 0.000000e+00' + NEWLINE + \
    'volt 0: offset = -4.650526e-02, slope = 1.246381e+00' + NEWLINE + \
    'volt 1: offset = -4.618105e-02, slope = 1.247197e+00' + NEWLINE + \
    'volt 2: offset = -4.659790e-02, slope = 1.247601e+00' + NEWLINE + \
    'volt 3: offset = -4.502421e-02, slope = 1.246911e+00' + NEWLINE + \
    'volt 4: offset = -4.589158e-02, slope = 1.246346e+00' + NEWLINE + \
    'volt 5: offset = -4.609895e-02, slope = 1.247868e+00' + NEWLINE + \
    '   EXTFREQSF = 9.999949e-01' + NEWLINE

VersionSpecificStructures.VALID_DCAL_STRAIN ='SBE 16plus V 2.5  SERIAL NO. 6841    28 Feb 2013 18:37:40' + NEWLINE + \
    'temperature:  18-May-12' + NEWLINE + \
    '    TA0 = 1.561342e-03' + NEWLINE + \
    '    TA1 = 2.561486e-04' + NEWLINE + \
    '    TA2 = 1.896537e-07' + NEWLINE + \
    '    TA3 = 1.301189e-07' + NEWLINE + \
    '    TOFFSET = 0.000000e+00' + NEWLINE + \
    'conductivity:  18-May-11' + NEWLINE + \
    '    G = -9.896568e-01' + NEWLINE + \
    '    H = 1.316599e-01' + NEWLINE + \
    '    I = -2.213854e-04' + NEWLINE + \
    '    J = 3.292199e-05' + NEWLINE + \
    '    CPCOR = -9.570000e-08' + NEWLINE + \
    '    CTCOR = 3.250000e-06' + NEWLINE + \
    '    CSLOPE = 1.000000e+00' + NEWLINE + \
    'pressure S/N = 3230195, range = 160 psia:  11-May-11' + NEWLINE + \
    '    PA0 = 4.960417e-02' + NEWLINE + \
    '    PA1 = 4.883682e-04' + NEWLINE + \
    '    PA2 = -5.687309e-12' + NEWLINE + \
    '    PTCA0 = 5.249802e+05' + NEWLINE + \
    '    PTCA1 = 7.595719e+00' + NEWLINE + \
    '    PTCA2 = -1.322776e-01' + NEWLINE + \
    '    PTCB0 = 2.503125e+01' + NEWLINE + \
    '    PTCB1 = 5.000000e-05' + NEWLINE + \
    '    PTCB2 = 0.000000e+00' + NEWLINE + \
    '    PTEMPA0 = -6.431504e+01' + NEWLINE + \
    '    PTEMPA1 = 5.168177e+01' + NEWLINE + \
    '    PTEMPA2 = -2.847757e-01' + NEWLINE + \
    '    POFFSET = 0.000000e+00' + NEWLINE + \
    'volt 0: offset = -4.650526e-02, slope = 1.246381e+00' + NEWLINE + \
    'volt 1: offset = -4.618105e-02, slope = 1.247197e+00' + NEWLINE + \
    'volt 2: offset = -4.659790e-02, slope = 1.247601e+00' + NEWLINE + \
    'volt 3: offset = -4.502421e-02, slope = 1.246911e+00' + NEWLINE + \
    'volt 4: offset = -4.589158e-02, slope = 1.246346e+00' + NEWLINE + \
    'volt 5: offset = -4.609895e-02, slope = 1.247868e+00' + NEWLINE + \
    '    EXTFREQSF = 9.999949e-01' + NEWLINE


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(SBEUnitTestCase):
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
