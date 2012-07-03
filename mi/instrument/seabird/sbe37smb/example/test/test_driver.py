#!/usr/bin/env python

"""
@package mi.instrument.seabird.sbe37smb.example.test.test_driver
@file mi/instrument/seabird/sbe37smb/example/driver.py
@author Bill French
@brief Test cases for example driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a UNIT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a INT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe37smb/example/test/test_driver.py -a QUAL
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe37smb.example.driver',
    driver_class="InstrumentDriver",

    # Set these parameters!
    instrument_agent_resource_id = 'seabird_sbe37smb_example',
    instrument_agent_name = 'seabird_sbe37smb_example',
    instrument_agent_packet_config = {},
    instrument_agent_stream_definition = {}
)

@attr('UNIT', group='mi')
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)


