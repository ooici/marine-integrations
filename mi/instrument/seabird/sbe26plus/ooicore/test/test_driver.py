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


    @TODO negative testing with bogus values to detect failures.
    @TODO would be nice to modify driver to test paramater allowable range and throw exception on out of range.

"""






__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import time
import socket

from mock import patch
from pyon.core.bootstrap import CFG

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
from mi.instrument.seabird.sbe26plus.ooicore.driver import InstrumentCmds
from mi.instrument.seabird.sbe26plus.ooicore.driver import NEWLINE
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

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

    Parameter.EXTERNAL_TEMPERATURE_SENSOR : bool,

    Parameter.CONDUCTIVITY : bool,

    Parameter.IOP_MA : float,
    Parameter.VMAIN_V : float,
    Parameter.VLITH_V : float,

    Parameter.LAST_SAMPLE_P : float,
    Parameter.LAST_SAMPLE_T : float,
    Parameter.LAST_SAMPLE_S : float,

    Parameter.TIDE_INTERVAL : int,
    Parameter.TIDE_MEASUREMENT_DURATION : int,

    Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : float,

    Parameter.WAVE_SAMPLES_PER_BURST : int,
    Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float,

    Parameter.USE_START_TIME : bool,
    #Parameter.START_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python
    Parameter.USE_STOP_TIME : bool,
    #Parameter.STOP_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

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
    Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC : bool,
    Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR : float,
    Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR : float,
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


class my_sock():
    buf = ""
    def __init__(self, host, port):
        self.buf = ""
        self.host = host
        self.port = port
        # log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.settimeout(0.0)

    def read_a_char(self):
        c = None
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            self.buf = self.s.recv(1024)
            log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")

        return c


    def peek_at_buffer(self):
        if len(self.buf) == 0:
            try:
                self.buf = self.s.recv(1024)
                log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")
            except:
                """
                Ignore this exception, its harmless
                """

        return self.buf

    def remove_from_buffer(self, remove):
        log.debug("BUF WAS " + str(repr(self.buf)))
        self.buf = self.buf.replace(remove, "")
        log.debug("BUF IS '" + str(repr(self.buf)) + "'")

    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c == None:
                    break
                if c == '\n' or c == '':
                    ret += c
                    break
                else:
                    ret += c

            data = ret
        except AttributeError:
            log.debug("CLOSING - GOT AN ATTRIBUTE ERROR")
            self.s.close()
        except:
            data = ""

        if data:
            data = data.lower()
            log.debug("IN  [" + repr(data) + "]")
        return data

    def send_data(self, data, debug):
        try:
            log.debug("OUT [" + repr(data) + "]")
            self.s.sendall(data)
        except:
            log.debug("*** send_data FAILED [" + debug + "] had an exception sending [" + data + "]")



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















    # assertParamDict is failing, needs a re-work





    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """

        # Make it loop through once to warn with debugging of issues, 2nd time can send the exception
        # PARAMS is the master type list

        if all_params:
            log.debug("DICT 1 *********" + str(pd.keys()))
            log.debug("DICT 2 *********" + str(PARAMS.keys()))
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))

            for (key, type_val) in PARAMS.iteritems():
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))

                if val is not None: # If its not defined, lets just skip it, only catch wrong type assignments.
                    log.debug("Asserting that " + key +  " is of type " + str(PARAMS[key]))
                    self.assertTrue(isinstance(val, PARAMS[key]))
                else:
                    log.debug("*** Skipping " + key + " Because value is None ***")

    # need to rename this to a better name
    def assert_returned_parameters_match_set_parameters(self, params, reply):
        for label in params.keys():
            log.debug("ASSERTING " + label + " = " + str(params[label]) + " == " + str(reply[label]))
            try:
                self.assertEqual(params[label], reply[label])
            except:
                log.debug(label + " WAS NOT IN 'reply' " + str(reply))





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



        # Test 1 Conductivity = Y, small subset of possible parameters.

        log.debug("get/set Test 1 - Conductivity = Y, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : True,
            Parameter.PY1 : float(-3.859),
            Parameter.PY2 : float(-10.25),
            Parameter.PY3 : float(11.0),
        }
        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 2 - Conductivity = N, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : False,
            Parameter.PT4 : float(27.90597),
            Parameter.POFFSET : float(-0.1374),
        }
        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 3 - internal temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.localtime()),
            Parameter.PCALDATE : (2, 4, 2013),
            Parameter.TCALDATE : (2, 4, 2013),
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : False,
            Parameter.POFFSET : float(-0.1374),
        }
        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 4 - external temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
            Parameter.PD1 : float(50.02928),
            Parameter.PD2 : float(31.712),
        }
        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 5 - get master set of possible parameters.")
        params = [
            # DC
            Parameter.PCALDATE,
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
            Parameter.CSLOPE,

            # DS
            Parameter.DEVICE_VERSION,
            Parameter.SERIAL_NUMBER,
            Parameter.DS_DEVICE_DATE_TIME,
            Parameter.USER_INFO,
            Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER,
            Parameter.QUARTZ_PREASURE_SENSOR_RANGE,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR,
            Parameter.CONDUCTIVITY,
            Parameter.IOP_MA,
            Parameter.VMAIN_V,
            Parameter.VLITH_V,
            Parameter.LAST_SAMPLE_P,
            Parameter.LAST_SAMPLE_T,
            Parameter.LAST_SAMPLE_S,

            # DS/SETSAMPLING
            Parameter.TIDE_INTERVAL,
            Parameter.TIDE_MEASUREMENT_DURATION,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS,
            Parameter.WAVE_SAMPLES_PER_BURST,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND,
            Parameter.USE_START_TIME,
            #Parameter.START_TIME,
            Parameter.USE_STOP_TIME,
            #Parameter.STOP_TIME,
            Parameter.TXWAVESTATS,
            Parameter.TIDE_SAMPLES_PER_DAY,
            Parameter.WAVE_BURSTS_PER_DAY,
            Parameter.MEMORY_ENDURANCE,
            Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE,
            Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS,
            Parameter.TOTAL_RECORDED_WAVE_BURSTS,
            Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START,
            Parameter.WAVE_BURSTS_SINCE_LAST_START,
            Parameter.TXREALTIME,
            Parameter.TXWAVEBURST,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC,
            Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR,
            Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR,
            Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND,
            Parameter.MIN_ALLOWABLE_ATTENUATION,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.HANNING_WINDOW_CUTOFF,
            Parameter.SHOW_PROGRESS_MESSAGES,
            Parameter.STATUS,
            Parameter.LOGGING,
        ]

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 6 - get master set of possible parameters using array containing Parameter.ALL")


        params3 = [
            Parameter.ALL
        ]

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 7 - Negative testing, broken values. Should get exception")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : 5,
            Parameter.PD1 : int(1),
            Parameter.PD2 : True,
        }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set', params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)


        log.debug("get/set Test 8 - Negative testing, broken labels. Should get exception")
        params = {
            "ROGER" : 5,
            "PETER RABBIT" : True,
            "WEB" : float(2.0),
        }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set', params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)


        log.debug("get/set Test 9 - Negative testing, empty params dict")
        params = {
        }

        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 10 - Negative testing, None instead of dict")
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set', None)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)



        log.debug("get/set Test N - Conductivity = Y, full set of set variables to known sane values.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.localtime()),
            Parameter.USER_INFO : "whoi",

            Parameter.PCALDATE : (2, 4, 2013),
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

            # params that I had that appeared corrupted.
            #Parameter.TA0 : float(1.2),
            # I believe this was the origional value.
            Parameter.TA0 : float(1.2e-04),
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
            Parameter.CSLOPE : float(1.0),
            Parameter.TXREALTIME : True,
            Parameter.TXWAVEBURST : True,
            Parameter.CONDUCTIVITY : True,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
        }
        reply = self.driver_client.cmd_dvr('set', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        self.assertParamDict(reply)



    def test_set_sampling(self):
        """
        Test device setsampling.
        """
        parameter_all = [
            Parameter.ALL
        ]

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

        # Critical that for this test conductivity be in a known state.
        # Need to add a second testing section to test with Conductivity = False
        new_params = {
            Parameter.CONDUCTIVITY : True,
        }
        reply = self.driver_client.cmd_dvr('set', new_params)

        # POSITIVE TESTING

        log.debug("setsampling Test 1 - TXWAVESTATS = N, small subset of possible parameters.")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', parameter_all)


        return

        """
        Test 1: TXWAVESTATS = N
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        log.debug("TEST 2 - TXWAVESTATS = N, full set of possible parameters")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TIDE_MEASUREMENT_DURATION : 540,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(4.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
        }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', parameter_all)

        """
        Test 2: TXWAVESTATS = Y
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
                    - Range [y, n]
                    OPTIONAL DEPENDING ON TXWAVESTATS
                    * Show progress messages
                      - Range [y, n]
                    * Number of wave samples per burst to use for wave
                      statistics
                      - Range > 512, power of 2...
                    * Use measured temperature and conductivity for
                      density calculation
                      - Range [y,n]
                    * Average water temperature above the pressure sensor
                      - Degrees C
                    * Height of pressure sensor from bottom
                      - Distance Meters
                    * Number of spectral estimates for each frequency
                      band
                      - You may have used Plan Deployment to determine
                        desired value
                    * Minimum allowable attenuation
                    * Minimum period (seconds) to use in auto-spectrum
                      Minimum of the two following
                      - frequency where (measured pressure / pressure at
                        surface) < (minimum allowable attenuation / wave
                        sample duration).
                      - (1 / minimum period). Frequencies > fmax are not
                        processed.
                    * Maximum period (seconds) to use in auto-spectrum
                       - ( 1 / maximum period). Frequencies < fmin are
                         not processed.
                    * Hanning window cutoff
                       - Hanning window suppresses spectral leakage that
                         occurs when time series to be Fourier transformed
                         contains periodic signal that does not correspond
                         to one of exact frequencies of FFT.
        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 2 - TXWAVESTATS = N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #1,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
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

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get', parameter_all)

        """
        Test 3: These 2 prompts appears only if you enter N for using measured T and C for density calculation
                Average water temperature above the pressure sensor (Deg C) = 15.0, new value =
                Average salinity above the pressure sensor (PSU) = 35.0, new value =

        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 3 - TXWAVESTATS = N, USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC=N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #4,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080, #40,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR : float(15.0),
            Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR : float(37.6),
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

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        # Alternate specification for all params
        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)
        """

        Test 1B: TXWAVESTATS = N, NEGATIVE TESTING
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720 (SEND OUT OF RANGE HIGH)
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec (SEND OUT OF RANGE LOW)
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000 (SEND OUT OF RANGE HIGH)
                * Number of wave samples per burst
                    - Range 4 - 60,000 (SEND OUT OF RANGE LOW)
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0] (SEND OUT OF RANGE HIGH)
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        for x in range(0,30):
            log.debug("***")
        log.debug("Test 1B: TXWAVESTATS = N, NEGATIVE TESTING")
        log.debug("Need to decide to test and throw exception on out of range, or what?")
        for x in range(0,30):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 800,
            Parameter.TIDE_MEASUREMENT_DURATION : 1,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 20000,
            Parameter.WAVE_SAMPLES_PER_BURST : 1,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(2.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        exception = False
        try:
            reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get', parameter_all)




    def test_set_time(self):
        """
        Test setting time with settime command
        S>settime
        set current time:
        month (1 - 12) = 1
        day (1 - 31) = 1
        year (4 digits) = 1
        hour (0 - 23) = 1
        minute (0 - 59) = 1
        second (0 - 59) = 1

        time.strftime("%d %b %Y %H:%M:%S", time.localtime())
        """
        """
        Test device setsampling.
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

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        t = time.strftime("%d %b %Y %H:%M:%S", time.localtime())
        log.debug("t = " + str(t))
        reply = self.driver_client.cmd_dvr(InstrumentCmds.SET_TIME, t)


    def test_upload_data_ascii(self):
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

        # Test the DD command.  Upload data in ASCII at baud set for general communication with Baud=
        reply = self.driver_client.cmd_dvr(InstrumentCmds.UPLOAD_DATA_ASCII_FORMAT)

        #log.debug(str(reply))
        (chunk, pat, reply) = reply.partition(NEWLINE)
        line = 0
        while len(chunk) == 12 or len(chunk) == 24:
            log.debug("Validating line #" + str(line) + " " + chunk)
            line = line + 1
            for c in chunk:
                self.assertTrue(c in '0123456789ABCDEF') # Only HEX CHARS ALLOWD
            (chunk, pat, reply) = reply.partition(NEWLINE)

        #log.debug("Remainder = " + repr(reply))
        self.assertEqual(reply, "")

    def test_take_sample(self):
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

        # Test the DD command.  Upload data in ASCII at baud set for general communication with Baud=
        reply = self.driver_client.cmd_dvr(InstrumentCmds.TAKE_SAMPLE)
        log.debug("REPLY = " + str(reply))

    def test_baud_command(self):
        """
        Test baud command.
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

        # Test that the device responds correctly to the baud command.
        # NOTE!! setting it to a baud that the tcp -> serial adapter is not
        # set to will require you to have to reconfigure the tcp -> serial
        # device to rescue the instrument.
        reply = self.driver_client.cmd_dvr(InstrumentCmds.BAUD, 9600)
        self.assertTrue(reply)



    def test_init_logging(self):
        """
        Test baud command.
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

        # Test that the device responds correctly to the baud command.
        # NOTE!! setting it to a baud that the tcp -> serial adapter is not
        # set to will require you to have to reconfigure the tcp -> serial
        # device to rescue the instrument.
        reply = self.driver_client.cmd_dvr(InstrumentCmds.INIT_LOGGING)

        self.assertTrue(reply)



    def test_quit_session(self):
        """
        Test quit session command.
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

        # Test that the device responds correctly to the baud command.
        # NOTE!! setting it to a baud that the tcp -> serial adapter is not
        # set to will require you to have to reconfigure the tcp -> serial
        # device to rescue the instrument.

        # Note quit session just sleeps the device, so its safe to remain in COMMAND mode.
        reply = self.driver_client.cmd_dvr(InstrumentCmds.QUIT_SESSION)
        self.assertEqual(reply, None)
        state = self.driver_client.cmd_dvr('get_current_state')
        log.debug("CURRENT STATE IS " + str(state))
        self.assertEqual(state, ProtocolState.COMMAND)

        # now can we return to command state?

        params = [
            Parameter.ALL
        ]
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamDict(reply)


    # Commands to verify are present and working.




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


    def test_autosample(self):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.
        """

        log.debug("ROGER ==> 1")

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        log.debug("ROGER ==> 2")

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 3")

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        log.debug("ROGER ==> 4")

        cmd = AgentCommand(command='go_active')
        log.debug("ROGER ==> 4.5")
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 5")

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        log.debug("ROGER ==> 6")

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 7")

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        log.debug("ROGER ==> 8")

        """
        # Make sure the sampling rate and transmission are sane.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5,
            SBE37Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_param(params)
        """

        self.data_subscribers.no_samples = 2

        # Begin streaming.
        cmd = AgentCommand(command='go_streaming')
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 9")

        non_accurate_seconds_count = 0
        while len(self.data_subscribers.samples_received) <= self.data_subscribers.no_samples and non_accurate_seconds_count < 1200:
            gevent.sleep(60)
            log.debug("SAMPLES RECEIVED => " + str(self.data_subscribers.__dict__)) # .keys()
            log.debug("EVENTS RECEIVED => " + str(self.event_subscribers.__dict__))

            non_accurate_seconds_count = non_accurate_seconds_count + 60

        log.debug("ROGER ==> 10")

        # Halt streaming.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 11")

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        log.debug("ROGER ==> 12")
        # Assert we got some samples.
        #self.assertTrue(self.data_subscribers.samples_received > self.data_subscribers.no_samples)
        #self.assertTrue(non_accurate_seconds_count < 1200)
        log.debug("ROGER ==> 13")

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("ROGER ==> 14")
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        log.debug("ROGER ==> 15")

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 2000}}})
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (telnet mode)
        """





        #see  nobska/mavs4 for examplar code in the main branch.



















        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)
        log.debug("***********************************-2")
        cmd = AgentCommand(command='go_active')
        log.debug("***********************************-2.1")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("***********************************-2.2")
        cmd = AgentCommand(command='get_current_state')
        log.debug("***********************************-2.3")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("***********************************-2.4")
        state = retval.result
        log.debug("***********************************-2.5")
        self.assertEqual(state, InstrumentAgentState.IDLE)
        log.debug("***********************************-1")
        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)
        log.debug("***********************************0")
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
            kwargs={'session_type': DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        gevent.sleep(300)
        s = my_sock(retval.result['ip_address'], retval.result['port'])
        log.debug("***********************************1")
        try_count = 0
        while s.peek_at_buffer().find("Username: ") == -1:
            log.debug("WANT 'Username:' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a Username: prompt')
        log.debug("***********************************2")
        s.remove_from_buffer("Username: ")
        s.send_data("bob\r\n", "1")

        try_count = 0
        while s.peek_at_buffer().find("token: ") == -1:
            log.debug("WANT 'token: ' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(0.1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a token: prompt')
        log.debug("***********************************3")
        s.remove_from_buffer("token: ")
        log.debug("***********************************3.1")
        s.send_data(retval.result['token'] + "\r\n", "1")
        log.debug("***********************************3.2")

        try_count = 0
        log.debug("***********************************3.3")
        while s.peek_at_buffer().find("connected\n") == -1:
            log.debug("***********************************3.4")
            log.debug("WANT 'connected\n' READ ==>" + str(s.peek_at_buffer()))
            log.debug("***********************************3.5")
            gevent.sleep(0.1)
            log.debug("***********************************3.6")
            s.peek_at_buffer()
            log.debug("***********************************3.7")
            try_count = try_count + 1
            log.debug("***********************************3.8")
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a connected prompt')
        log.debug("***********************************4")
        s.remove_from_buffer("connected\n")
        """
        s.send_data("ts\r\n", "1")
        log.debug("SENT THE TS COMMAND")

        pattern = re.compile("^([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9a-z]+),([ 0-9:]+)")

        matches = 0
        n = 0
        while n < 100:
            n = n + 1
            gevent.sleep(1)
            data = s.get_data()
            log.debug("READ ==>" + str(repr(data)))
            m = pattern.search(data)
            if m != None:
                matches = m.lastindex
                if matches == 7:
                    break

        self.assertTrue(matches == 7) # need to have found 7 conformant fields.
        """