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
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a INT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a QUAL
"""

__author__ = 'Roger Unwin'
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


from mi.instrument.seabird.sbe26plus.ooicore.driver import Parameter
from mi.instrument.seabird.sbe26plus.ooicore.driver import ProtocolState
from mi.core.instrument.instrument_driver import DriverConnectionState
###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe26plus.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '2E7GNV',
    instrument_agent_name = 'seabird_sbe26plus_ooicore',
    instrument_agent_packet_config = {},
    instrument_agent_stream_definition = {}
)
"""
Parameter.OUTPUTSAL : bool,
Parameter.OUTPUTSV : bool,
Parameter.NAVG : int,
Parameter.SAMPLENUM : int,
Parameter.INTERVAL : int,
Parameter.STORETIME : bool,
Parameter.TXREALTIME : bool,
Parameter.SYNCMODE : bool,
Parameter.SYNCWAIT : int,
Parameter.TCALDATE : tuple,
Parameter.TA0 : float,
Parameter.TA1 : float,
Parameter.TA2 : float,
Parameter.TA3 : float,
Parameter.CCALDATE : tuple,
Parameter.CG : float,
Parameter.CH : float,
Parameter.CI : float,
Parameter.CJ : float,
Parameter.WBOTC : float,
Parameter.CTCOR : float,
Parameter.CPCOR : float,
Parameter.PCALDATE : tuple,
Parameter.PA0 : float,
Parameter.PA1 : float,
Parameter.PA2 : float,
#Parameter.PTCA0 : float,
#Parameter.PTCA1 : float,
#Parameter.PTCA2 : float,
Parameter.PTCB0 : float,
Parameter.PTCB1 : float,
Parameter.PTCB2 : float,
Parameter.POFFSET : float,
Parameter.RCALDATE : tuple,
Parameter.RTCA0 : float,
Parameter.RTCA1 : float,
Parameter.RTCA2 : float
ABOVE IS EXAMPLE

NEED TO VERIFY ALL OF BELOW ARE SPECIFIED CORRECTLY AND IT IS A MASTER LIST,
AS IT WAS DONE BEFORE THE LIST WAS FINALIZED
"""
PARAMS = {
    Parameter.TXREALTIME : bool,
    Parameter.TXWAVEBURST : bool,
    Parameter.TXWAVESTATS : bool,
    Parameter.TIDE_SAMPLES_PER_DAY : float,
    Parameter.WAVE_BURSTS_PER_DAY : float,
    Parameter.MEMORY_ENDURANCE_DAYS : float,
    Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE_DAYS : float,
    Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS : float,
    Parameter.TOTAL_RECORDED_WAVE_BURSTS : float,
    Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START : float,
    Parameter.WAVE_BURSTS_SINCE_LAST_START : float,
    Parameter.TIDE_SAMPLES_BETWEEN_WAVE_MEASUREMENTS : float,
    Parameter.LOGGING : float,
    Parameter.STATUS : float,
    Parameter.CONDUCTIVITY : bool,
    Parameter.USER_INFO : str,
    Parameter.TIDE_MEASUREMENT_INTERVAL : float,
    Parameter.TIDE_MEASUREMENT_DURATION : float,
    Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER : float,
    Parameter.QUARTZ_PREASURE_SENSOR_RANGE : float,
    Parameter.WAVE_SAMPLES_PER_BURST : float,
    #Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float,
    #Parameter.WAVE_SAMPLES_DURATION_SECONDS : float,
    Parameter.LAST_SAMPLE_P : float,
    Parameter.LAST_SAMPLE_T : float,
    Parameter.LAST_SAMPLE_S : float,
    Parameter.IOP_MA : float,
    Parameter.VMAIN_V : float,
    Parameter.VLITH_V : float,

    # DC
    Parameter.PCALDATE : tuple,
    Parameter.TCALDATE : tuple,
    Parameter.CCALDATE : tuple,
    Parameter.PU0 : float,
    Parameter.PY1 : float,
    Parameter.PY2 : float,
    Parameter.PY3 : float,
    Parameter.PC1 : float,
    Parameter.PC2 : float,
    Parameter.PC3 : float,
    Parameter.PD1 : float,
    Parameter.PD2 : float,
    Parameter.PT1 : float,
    Parameter.PT2 : float,
    Parameter.PT3 : float,
    Parameter.PT4 : float,
    Parameter.PA0 : float,
    Parameter.PA1 : float,
    Parameter.PA2 : float,
    #Parameter.PTCA0 : float,
    #Parameter.PTCA1 : float,
    #Parameter.PTCA2 : float,
    Parameter.PTCB0 : float,
    Parameter.PTCB1 : float,
    Parameter.PTCB2 : float,
    #Parameter.PTEMPA0 : float,
    #Parameter.PTEMPA1 : float,
    #Parameter.PTEMPA2 : float,
    Parameter.POFFSET : float,
    Parameter.TA0 : float,
    Parameter.TA1 : float,
    Parameter.TA2 : float,
    Parameter.TA3 : float,
    Parameter.CG : float,
    Parameter.CH : float,
    Parameter.CI : float,
    Parameter.CJ : float,
    Parameter.CTCOR : float,
    Parameter.CPCOR : float,
    Parameter.CSLOPE : float,
    Parameter.FACTORY_M : float,
    Parameter.FACTORY_B : float
}
#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    ###
    #    Add instrument specific unit tests
    ###


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###

    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            for (key, type_val) in PARAMS.iteritems():
                log.debug(key + " is " + str(pd[key]) + " an instance of " + str(type_val) + " = " + str(isinstance(pd[key], type_val)))
                #self.assertTrue(isinstance(pd[key], type_val))
        #else:
            #for (key, val) in pd.iteritems():
                #self.assertTrue(PARAMS.has_key(key))
                #self.assertTrue(isinstance(val, PARAMS[key]))

    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        new_params = {
            Parameter.TA0 : float(1.2),
            Parameter.PC2 : float(1.0)
        }

        reply = self.driver_client.cmd_dvr('set', new_params)
        state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, ProtocolState.COMMAND)

        log.warn("BEFORE DEFINE====================================================vvvvvv")

        define_params = {
            Parameter.TA0 : float(1.0)
        }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, ProtocolState.COMMAND)
        #reply = self.driver_client.cmd_dvr('setsampling', define_params)


        log.warn("REPLY ===================================================== " + str(reply))



        #reply = self.driver_client.cmd_dvr('set', new_params)



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    ###
    #    Add instrument specific qualification tests
    ###


