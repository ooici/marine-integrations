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

PARAMS = {
    # DS # parameters - contains all setsampling parameters
    Parameter.DEVICE_VERSION : str,
    Parameter.SERIAL_NUMBER : str,
    Parameter.DS_DEVICE_DATE_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

    Parameter.USER_INFO : str,
    Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER : float,
    Parameter.QUARTZ_PREASURE_SENSOR_RANGE : float,

    Parameter.TEMPERATURE_SENSOR : str,

    Parameter.CONDUCTIVITY : bool,

    Parameter.IOP_MA : float,
    Parameter.VMAIN_V : float,
    Parameter.VLITH_V : float,

    Parameter.LAST_SAMPLE_P : float,
    Parameter.LAST_SAMPLE_T : float,
    Parameter.LAST_SAMPLE_S : float,

    Parameter.TIDE_INTERVAL : int,
    Parameter.TIDE_MEASUREMENT_DURATION : int,

    Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : int,

    Parameter.WAVE_SAMPLES_PER_BURST : int,
    Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float,
    Parameter.WAVE_SAMPLE_DURATION : float,

    Parameter.USE_START_TIME : bool,
    Parameter.START_TIME : long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python
    Parameter.USE_STOP_TIME : bool,
    Parameter.STOP_TIME : long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

    Parameter.TIDE_SAMPLES_PER_DAY : float,
    Parameter.WAVE_BURSTS_PER_DAY : float,
    Parameter.MEMORY_ENDURANCE : float,
    Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE : float,
    Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS : float,
    Parameter.TOTAL_RECORDED_WAVE_BURSTS : float,
    Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START : float,
    Parameter.WAVE_BURSTS_SINCE_LAST_START : float,
    Parameter.TXREALTIME : bool,
    Parameter.TXWAVEBURST : bool,
    Parameter.TXWAVESTATS : bool,
    Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : int,
    Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : bool,
    Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM : float,
    Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : int,
    Parameter.MIN_ALLOWABLE_ATTENUATION : float,
    Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.HANNING_WINDOW_CUTOFF : float,
    Parameter.SHOW_PROGRESS_MESSAGES : bool,
    Parameter.STATUS : str,
    Parameter.LOGGING : bool,

# DC # parameters verified to match 1:1 to DC output
    Parameter.PCALDATE : tuple,
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
    Parameter.FACTORY_M : float,
    Parameter.FACTORY_B : float,
    Parameter.POFFSET : float,
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
    Parameter.CTCOR : float,
    Parameter.CPCOR : float,
    Parameter.CSLOPE : float,

    # End of DC
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
            log.debug("assertParamDict *********" + str(pd.keys()))
            for (key, type_val) in PARAMS.iteritems():
                log.debug(key + " is " + str(pd[key]) + " an instance of " + str(type_val) + " = " + str(isinstance(pd[key], type_val)))
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
                self.assertTrue(isinstance(val, PARAMS[key]))

    def test_log(self):
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")
        log.debug("****************************** LOG TEST ")

    def test_get_set2(self):
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
        #state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        new_params = {
            Parameter.TA0 : float(1.2),
            Parameter.PC2 : float(1.0),
            Parameter.PU0 : float(5.1),
            Parameter.PY1 : float(-3910.859),
            Parameter.PY2 : float(-10708.25),
            Parameter.PY3 : float(0.0),
            Parameter.PC1 : float(607.2786),
            Parameter.PC2 : float(1.0),
            Parameter.PC3 : float(-1024.374),
            Parameter.PD1 : float(0.02928),
            Parameter.PD2 : float(0.0),
            Parameter.PT1 : float(27.83369),
            Parameter.PT2 : float(0.607202),
            Parameter.PT3 : float(18.21885),
            Parameter.PT4 : float(27.90597),
            Parameter.POFFSET : float(-0.1374),
            Parameter.TCALDATE : (2, 4, 2013),
            Parameter.TA0 : float(1.2),
            Parameter.TA1 : float(0.0002558291),
            Parameter.TA2 : float(-2.073449e-06),
            Parameter.TA3 : float(1.640089e-07),
            Parameter.CCALDATE : (28, 3, 2012),
            Parameter.CG : float(-10.25348),
            Parameter.CH : float(1.557569),
            Parameter.CI : float(-0.001737222),
            Parameter.CJ : float(0.0002268556),
            Parameter.CTCOR : float(3.25e-06),
            Parameter.CPCOR : float(-9.57e-08),
            Parameter.CSLOPE : float(1.0)
        }

        reply = self.driver_client.cmd_dvr('set', new_params)
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        params = [
            Parameter.TA0,
            Parameter.PC2,
            Parameter.PU0,
            Parameter.PY1,
            Parameter.PY2,
            Parameter.PY3,
            Parameter.PC1,
            Parameter.PC2,
            Parameter.PC3,
            Parameter.PD1,
            Parameter.PD2,
            Parameter.PT1,
            Parameter.PT2,
            Parameter.PT3,
            Parameter.PT4,
            Parameter.FACTORY_M,
            Parameter.FACTORY_B,
            Parameter.POFFSET,
            Parameter.TCALDATE,
            Parameter.TA0,
            Parameter.TA1,
            Parameter.TA2,
            Parameter.TA3,
            Parameter.CCALDATE,
            Parameter.CG,
            Parameter.CH,
            Parameter.CI,
            Parameter.CJ,
            Parameter.CTCOR,
            Parameter.CPCOR,
            Parameter.CSLOPE
        ]

        reply = self.driver_client.cmd_dvr('get', params)
        log.debug("******************************TEST1*****************************")
        self.assertParamDict(reply)
        log.debug("******************************TEST2*****************************")


    def test_set_sampling(self):
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

        sampling_params = {
            Parameter.TIDE_INTERVAL : 1,
            Parameter.TIDE_MEASUREMENT_DURATION : 1,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1,
            Parameter.WAVE_SAMPLE_DURATION : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False
        }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)
        reply = self.driver_client.cmd_dvr('setsampling', sampling_params)

        sampling_params2 = {
            Parameter.TIDE_INTERVAL : 5,
            Parameter.TIDE_MEASUREMENT_DURATION : 5,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 5,
            Parameter.WAVE_SAMPLES_PER_BURST : 5,
            Parameter.WAVE_SAMPLE_DURATION : float(0.25),
            Parameter.USE_START_TIME : True,
            Parameter.USE_STOP_TIME : True,
            Parameter.TXWAVESTATS : True,

            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 1,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : True,
            Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM: 1.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
        }
        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)
        reply = self.driver_client.cmd_dvr('setsampling', sampling_params2)



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


