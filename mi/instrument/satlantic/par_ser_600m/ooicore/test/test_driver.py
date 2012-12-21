#!/usr/bin/env python

from nose.plugins.attrib import attr

from mi.instrument.satlantic.par_ser_600m.driver import DataParticleType
from mi.instrument.satlantic.par_ser_600m.test.test_driver import SatlanticParProtocolUnitTest
from mi.instrument.satlantic.par_ser_600m.test.test_driver import SatlanticParProtocolIntegrationTest
from mi.instrument.satlantic.par_ser_600m.test.test_driver import SatlanticParProtocolQualificationTest
from mi.instrument.satlantic.par_ser_600m.driver import Parameter

from mi.idk.unit_test import InstrumentDriverTestCase

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.par_ser_600m.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'satlantic_par_ser_600m_ooicore',
    instrument_agent_name = 'satlantic_par_ser_600m_ooicore_agent',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {
        Parameter.MAXRATE: 2
    }
)

@attr('UNIT', group='mi')
class DriverUnitTest(SatlanticParProtocolUnitTest):
    pass

@attr('INT', group='mi')
class DriverIntegrationTest(SatlanticParProtocolIntegrationTest):
    pass

@attr('QUAL', group='mi')
class DriverQualificationTest(SatlanticParProtocolQualificationTest):
    pass

