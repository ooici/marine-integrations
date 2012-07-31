#!/usr/bin/env python

"""
@package mi.instrument.nobska.mavs4.mavs4.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4/mavs4/driver.py
@author Bill Bollenbacher
@brief Test cases for mavs4 driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent
import socket

# Standard lib imports
import time
import unittest

# 3rd party imports
from nose.plugins.attrib import attr

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.nobska.mavs4.ooicore.driver import PACKET_CONFIG
from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentDriver
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolStates
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentParameters

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'


# Device specific parameters.
class TestInstrumentParameters(DriverParameter):
    """
    Device parameters for MAVS-4.
    """
    SYS_CLOCK = 'sys_clock'
    BAUD_RATE = 'BaudRate'
    VERSION_NUMBER = 'VersionNumber'
    CONFIG_INITIALIZED = 'ConfigInitialized'
    V_OFFSET_0 = 'V_offset_0'
    V_OFFSET_1 = 'V_offset_1'
    V_OFFSET_2 = 'V_offset_2'
    V_OFFSET_3 = 'V_offset_3'
    V_SCALE = 'V_scale'
    ANALOG_OUT = 'AnalogOut'
    COMPASS = 'Compass'
    M0_OFFSET = 'M0_offset'
    M1_OFFSET = 'M1_offset'
    M2_OFFSET = 'M2_offset'
    M0_SCALE = 'M0_scale'
    M1_SCALE = 'M1_scale'
    M2_SCALE = 'M2_scale'
    TILT = 'Tilt'
    TY_OFFSET = 'TY_offset'
    TX_OFFSET = 'TX_offset'
    TY_SCALE = 'TY_scale'
    TX_SCALE = 'TX_scale'
    TY_TEMPCO = 'TY_tempco'
    TX_TEMPCO = 'TX_tempco'
    FAST_SENSOR = 'FastSensor'
    THERMISTOR = 'Thermistor'
    TH_OFFSET = 'Th_offset'
    PRESSURE = 'Pressure'
    P_OFFSET = 'P_offset'
    P_SCALE = 'P_scale'
    P_MA = 'P_mA'
    AUXILIARY1 = 'Auxiliary1'
    A1_OFFSET = 'A1_offset'
    A1_SCALE = 'A1_scale'
    A1_MA = 'A1_mA'
    AUXILIARY2 = 'Auxiliary2'
    A2_OFFSET = 'A2_offset'
    A2_SCALE = 'A2_scale'
    A2_MA = 'A2_mA'
    AUXILIARY3 = 'Auxiliary3'
    A3_OFFSET = 'A3_offset'
    A3_SCALE = 'A3_scale'
    A3_MA = 'A3_mA'
    SENSOR_ORIENTATION = 'SensorOrientation'
    SERIAL_NUMBER = 'SerialNumber'
    QUERY_CHARACTER = 'QueryCharacter'
    POWER_UP_TIME_OUT = 'PowerUpTimeOut'
    DEPLOY_INITIALIZED = 'DeployInitialized'
    LINE1 = 'line1'
    LINE2 = 'line2'
    LINE3 = 'line3'
    START_TIME = 'StartTime'
    STOP_TIME = 'StopTime'
    FRAME = 'FRAME'
    DATA_MONITOR = 'DataMonitor'
    INTERNAL_LOGGING = 'InternalLogging'
    APPEND_MODE = 'AppendMode'
    BYTES_PER_SAMPLE = 'BytesPerSample'
    VERBOSE_MODE = 'VerboseMode'
    QUERY_MODE = 'QueryMode'
    EXTERNAL_POWER = 'ExternalPower'
    MEASUREMENT_FREQUENCY = 'MeasurementFrequency'
    MEASUREMENT_PERIOD_SECS = 'MeasurementPeriod.secs'
    MEASUREMENT_PERIOD_TICKS = 'MeasurementPeriod.ticks'
    MEASUREMENTS_PER_SAMPLE = 'MeasurementsPerSample'
    SAMPLE_PERIOD_SECS = 'SamplePeriod.secs'
    SAMPLE_PERIOD_TICKS = 'SamplePeriod.ticks'
    SAMPLES_PER_BURST = 'SamplesPerBurst'
    INTERVAL_BETWEEN_BURSTS = 'IntervalBetweenBursts'
    BURSTS_PER_FILE = 'BurstsPerFile'
    STORE_TIME = 'StoreTime'
    STORE_FRACTIONAL_TIME = 'StoreFractionalTime'
    STORE_RAW_PATHS = 'StoreRawPaths'
    PATH_UNITS = 'PathUnits'

# Used to validate param config retrieved from driver.
parameter_types = {
    InstrumentParameters.SYS_CLOCK : int,
    InstrumentParameters.BAUD_RATE : int,
    InstrumentParameters.VERSION_NUMBER : int,
    InstrumentParameters.CONFIG_INITIALIZED : int,
    InstrumentParameters.V_OFFSET_0 : int,
    InstrumentParameters.V_OFFSET_1 : int,
    InstrumentParameters.V_OFFSET_2 : int,
    InstrumentParameters.V_OFFSET_3 : int,
    InstrumentParameters.V_SCALE : float,
    InstrumentParameters.ANALOG_OUT : int,
    InstrumentParameters.COMPASS : int,
    InstrumentParameters.M0_OFFSET : int,
    InstrumentParameters.M1_OFFSET : int,
    InstrumentParameters.M2_OFFSET : int,
    InstrumentParameters.M0_SCALE : float,
    InstrumentParameters.M1_SCALE : float,
    InstrumentParameters.M2_SCALE : float,
    InstrumentParameters.TILT : int,
    InstrumentParameters.TY_OFFSET : int,
    InstrumentParameters.TX_OFFSET : int,
    InstrumentParameters.TY_SCALE : float,
    InstrumentParameters.TX_SCALE : float,
    InstrumentParameters.TY_TEMPCO : float,
    InstrumentParameters.TX_TEMPCO : float,
    InstrumentParameters.FAST_SENSOR : int,
    InstrumentParameters.THERMISTOR : int,
    InstrumentParameters.TH_OFFSET : float,
    InstrumentParameters.PRESSURE : int,
    InstrumentParameters.P_OFFSET : int,
    InstrumentParameters.P_SCALE : float,
    InstrumentParameters.P_MA : float,
    InstrumentParameters.AUXILIARY1 : int,
    InstrumentParameters.A1_OFFSET : int,
    InstrumentParameters.A1_SCALE : float,
    InstrumentParameters.A1_MA : float,
    InstrumentParameters.AUXILIARY2 : int,
    InstrumentParameters.A2_OFFSET : int,
    InstrumentParameters.A2_SCALE : float,
    InstrumentParameters.A2_MA : float,
    InstrumentParameters.AUXILIARY3 : int,
    InstrumentParameters.A3_OFFSET : int,
    InstrumentParameters.A3_SCALE : float,
    InstrumentParameters.A3_MA : float,
    InstrumentParameters.SENSOR_ORIENTATION : int,
    InstrumentParameters.SERIAL_NUMBER : int,
    InstrumentParameters.QUERY_CHARACTER : str,
    InstrumentParameters.POWER_UP_TIME_OUT : int,
    InstrumentParameters.DEPLOY_INITIALIZED : int,
    InstrumentParameters.LINE1 : str,
    InstrumentParameters.LINE2 : str,
    InstrumentParameters.LINE3 : str,
    InstrumentParameters.START_TIME : int,
    InstrumentParameters.STOP_TIME : int,
    InstrumentParameters.FRAME : int,
    InstrumentParameters.DATA_MONITOR : int,
    InstrumentParameters.INTERNAL_LOGGING : int,
    InstrumentParameters.APPEND_MODE : int,
    InstrumentParameters.BYTES_PER_SAMPLE : int,
    InstrumentParameters.VERBOSE_MODE : int,
    InstrumentParameters.QUERY_MODE : int,
    InstrumentParameters.EXTERNAL_POWER : int,
    InstrumentParameters.MEASUREMENT_FREQUENCY : float,
    InstrumentParameters.MEASUREMENT_PERIOD_SECS : int,
    InstrumentParameters.MEASUREMENT_PERIOD_TICKS : int,
    InstrumentParameters.MEASUREMENTS_PER_SAMPLE : int,
    InstrumentParameters.SAMPLE_PERIOD_SECS : int,
    InstrumentParameters.SAMPLE_PERIOD_TICKS : int,
    InstrumentParameters.SAMPLES_PER_BURST : int,
    InstrumentParameters.INTERVAL_BETWEEN_BURSTS : int,
    InstrumentParameters.BURSTS_PER_FILE : int,
    InstrumentParameters.STORE_TIME : int,
    InstrumentParameters.STORE_FRACTIONAL_TIME : int,
    InstrumentParameters.STORE_RAW_PATHS : int,
    InstrumentParameters.PATH_UNITS : str
}

parameter_list = [
    InstrumentParameters.SYS_CLOCK,
    InstrumentParameters.BAUD_RATE,
    InstrumentParameters.VERSION_NUMBER,
    InstrumentParameters.CONFIG_INITIALIZED,
    InstrumentParameters.V_OFFSET_0,
    InstrumentParameters.V_OFFSET_1,
    InstrumentParameters.V_OFFSET_2,
    InstrumentParameters.V_OFFSET_3,
    InstrumentParameters.V_SCALE,
    InstrumentParameters.ANALOG_OUT,
    InstrumentParameters.COMPASS,
    InstrumentParameters.M0_OFFSET,
    InstrumentParameters.M1_OFFSET,
    InstrumentParameters.M2_OFFSET,
    InstrumentParameters.M0_SCALE,
    InstrumentParameters.M1_SCALE,
    InstrumentParameters.M2_SCALE,
    InstrumentParameters.TILT,
    InstrumentParameters.TY_OFFSET,
    InstrumentParameters.TX_OFFSET,
    InstrumentParameters.TY_SCALE,
    InstrumentParameters.TX_SCALE,
    InstrumentParameters.TY_TEMPCO,
    InstrumentParameters.TX_TEMPCO,
    InstrumentParameters.FAST_SENSOR,
    InstrumentParameters.THERMISTOR,
    InstrumentParameters.TH_OFFSET,
    InstrumentParameters.PRESSURE,
    InstrumentParameters.P_OFFSET,
    InstrumentParameters.P_SCALE,
    InstrumentParameters.P_MA,
    InstrumentParameters.AUXILIARY1,
    InstrumentParameters.A1_OFFSET,
    InstrumentParameters.A1_SCALE,
    InstrumentParameters.A1_MA,
    InstrumentParameters.AUXILIARY2,
    InstrumentParameters.A2_OFFSET,
    InstrumentParameters.A2_SCALE,
    InstrumentParameters.A2_MA,
    InstrumentParameters.AUXILIARY3,
    InstrumentParameters.A3_OFFSET,
    InstrumentParameters.A3_SCALE,
    InstrumentParameters.A3_MA,
    InstrumentParameters.SENSOR_ORIENTATION,
    InstrumentParameters.SERIAL_NUMBER,
    InstrumentParameters.QUERY_CHARACTER,
    InstrumentParameters.POWER_UP_TIME_OUT,
    InstrumentParameters.DEPLOY_INITIALIZED,
    InstrumentParameters.LINE1,
    InstrumentParameters.LINE2,
    InstrumentParameters.LINE3,
    InstrumentParameters.START_TIME,
    InstrumentParameters.STOP_TIME,
    InstrumentParameters.FRAME,
    InstrumentParameters.DATA_MONITOR,
    InstrumentParameters.INTERNAL_LOGGING,
    InstrumentParameters.APPEND_MODE,
    InstrumentParameters.BYTES_PER_SAMPLE,
    InstrumentParameters.VERBOSE_MODE,
    InstrumentParameters.QUERY_MODE,
    InstrumentParameters.EXTERNAL_POWER,
    InstrumentParameters.MEASUREMENT_FREQUENCY,
    InstrumentParameters.MEASUREMENT_PERIOD_SECS,
    InstrumentParameters.MEASUREMENT_PERIOD_TICKS,
    InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
    InstrumentParameters.SAMPLE_PERIOD_SECS,
    InstrumentParameters.SAMPLE_PERIOD_TICKS,
    InstrumentParameters.SAMPLES_PER_BURST,
    InstrumentParameters.INTERVAL_BETWEEN_BURSTS,
    InstrumentParameters.BURSTS_PER_FILE,
    InstrumentParameters.STORE_TIME,
    InstrumentParameters.STORE_FRACTIONAL_TIME,
    InstrumentParameters.STORE_RAW_PATHS,
    InstrumentParameters.PATH_UNITS]
    
## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nobska.mavs4.ooicore.driver',
    driver_class="mavs4InstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)


class TcpClient():
    # for direct access testing
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
        temp = self.s.recv(1024)
        if len(temp) > 0:
            log.debug("read_a_char got '" + str(repr(temp)) + "'")
            self.buf += temp
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            c = None
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
class Testmavs4_UNIT(InstrumentDriverTestCase):
    """Unit Test Container"""
    
    def setUp(self):
        """
        @brief initialize mock objects for the protocol object.
        """
        #self.callback = Mock(name='callback')
        #self.logger = Mock(name='logger')
        #self.logger_client = Mock(name='logger_client')
        #self.protocol = mavs4InstrumentProtocol()
    
        #self.protocol.configure(self.comm_config)
        #self.protocol.initialize()
        #self.protocol._logger = self.logger 
        #self.protocol._logger_client = self.logger_client
        #self.protocol._get_response = Mock(return_value=('$', None))
        
        # Quick sanity check to make sure the logger got mocked properly
        #self.assertEquals(self.protocol._logger, self.logger)
        #self.assertEquals(self.protocol._logger_client, self.logger_client)
        
    ###
    #    Add driver specific unit tests
    ###
    
    
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testmavs4_INT(InstrumentDriverIntegrationTestCase):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.nobska.mavs4.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'mavs4InstrumentDriver'    
    

    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(parameter_types.keys()),
                             'not all parameters are present')
            for (key, type_val) in parameter_types.iteritems():
                self.assertTrue(isinstance(pd[key], type_val),
                                'parameter %s not type %s' %(key, str(type_val)))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(parameter_types.has_key(key),
                                'unexpected parameter %s' %key)
                self.assertTrue(isinstance(val, parameter_types[key]),
                                'parameter %s not type %s' %(key, str(parameter_types[key])))
    
    def assertParamVals(self, params, correct_params):
        """
        Verify parameters take the correct values.
        """
        self.assertEqual(set(params.keys()), set(correct_params.keys()),
                         '%s != %s' %(params.keys(), correct_params.keys()))
        for (key, val) in params.iteritems():
            self.assertEqual(val, correct_params[key],
                             '%s != %s' %(key, correct_params[key]))

    def assertParamList(self, pl):
        """
        Verify all device parameters.
        """
        self.assertEqual(pl, TestInstrumentParameters.list())
    
    @unittest.skip("override & skip while in development")
    def test_driver_process(self):
        pass 

    
    def Xtest_instrumment_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                
               
    def test_get_set(self):
        """
        Test device parameter access.
        """
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.COMMAND)

        # get the list of device parameters
        reply = self.driver_client.cmd_dvr('get_resource_params')
        self.assertParamList(reply)

        # Get all device parameters. Confirm all expected keys are retrieved
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', InstrumentParameters.ALL)
        self.assertParamDict(reply, True)
        """
        log.debug("test_get_set: parameters:" )
        for parameter in parameter_list:
            log.debug("%s = %s" %(parameter, reply[parameter]))
        """
        
        # Remember original configuration.
        orig_config = reply
        
        # Grab a subset of parameters.
        params = [
            InstrumentParameters.TY_OFFSET,
            InstrumentParameters.TX_OFFSET,
            InstrumentParameters.TY_SCALE,
            InstrumentParameters.TX_SCALE
            ]
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        new_params = {
            InstrumentParameters.TY_OFFSET : orig_params[InstrumentParameters.TY_OFFSET] * 2,
            InstrumentParameters.TX_OFFSET : orig_params[InstrumentParameters.TX_OFFSET] + 1,
            InstrumentParameters.TY_SCALE : orig_params[InstrumentParameters.TY_SCALE] * 2,
            InstrumentParameters.TX_SCALE : orig_params[InstrumentParameters.TX_SCALE] + 1
        }

        # Set parameters and verify.
        reply = self.driver_client.cmd_dvr('set', new_params)
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamVals(reply, new_params)
        
        # Restore original parameters and verify.
        reply = self.driver_client.cmd_dvr('set', orig_params)
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamVals(reply, orig_params)

        # Retrieve the configuration and ensure it matches the original.
        reply = self.driver_client.cmd_dvr('get', InstrumentParameters.ALL)
        self.assertParamVals(reply, orig_config)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is disconnected.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)        

    def Xtest_instrumment_autosample(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                
        # start auto-sample.
        reply = self.driver_client.cmd_dvr('execute_start_autosample')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.AUTOSAMPLE)
                
        # stop auto-sample.
        reply = self.driver_client.cmd_dvr('execute_stop_autosample')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                

    ###
    #    Add driver specific integration tests
    ###

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class Testmavs4_QUAL(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  


    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_down; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_up; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent initialize; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent go_active; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent run; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run


    #@unittest.skip("skip for now")
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
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

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        # start 'telnet' client with returned address and port
        s = TcpClient(retval.result['ip_address'], retval.result['port'])

        # look for and swallow 'Username' prompt
        try_count = 0
        while s.peek_at_buffer().find("Username: ") == -1:
            log.debug("WANT 'Username:' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a Username: prompt')
        s.remove_from_buffer("Username: ")
        # send some username string
        s.send_data("bob\r\n", "1")
        
        # look for and swallow 'token' prompt
        try_count = 0
        while s.peek_at_buffer().find("token: ") == -1:
            log.debug("WANT 'token: ' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a token: prompt')
        s.remove_from_buffer("token: ")
        # send the returned token
        s.send_data(retval.result['token'] + "\r\n", "1")
        
        # look for and swallow telnet negotiation string
        try_count = 0
        while s.peek_at_buffer().find(WILL_ECHO_CMD) == -1:
            log.debug("WANT %s READ ==> %s" %(WILL_ECHO_CMD, str(s.peek_at_buffer())))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get the telnet negotiation string')
        s.remove_from_buffer(WILL_ECHO_CMD)
        # send the telnet negotiation response string
        s.send_data(DO_ECHO_CMD, "1")

        # look for and swallow 'connected' indicator
        try_count = 0
        while s.peek_at_buffer().find("connected\r\n") == -1:
            log.debug("WANT 'connected\n' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a connected prompt')
        s.remove_from_buffer("connected\r\n")
        
        # try to interact with the instrument 
        try_count = 0
        while ((s.peek_at_buffer().find("Enter <CTRL>-<C> now to wake up") == -1) and
              (s.peek_at_buffer().find("Main Menu") == -1)):
            self.assertNotEqual(try_count, 5)
            try_count += 1
            log.debug("WANT %s or %s; READ ==> %s" %("'Enter <CTRL>-<C> now to wake up'", "'Main Menu'", str(s.peek_at_buffer())))
            s.send_data("\r\n\r\n", "1")
            gevent.sleep(2)
               
