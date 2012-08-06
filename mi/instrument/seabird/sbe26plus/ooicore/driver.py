"""
@package mi.instrument.seabird.sbe26plus.ooicore.driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore/driver.py
@author Roger Unwin
@brief Driver for the ooicore
Release notes:

None.
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import string

import re
import time

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_protocol import BaseProtocolEvent
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

from mi.core.log import get_logger ; log = get_logger()

# Experimental
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.common import BaseEnum

# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 40

# Packet config
#PACKET_CONFIG = {
#    'parsed' : None,
#    'raw' : None
#}

class InstrumentCmds(BaseEnum):
    """
    Instrument Commands
    These are the commands that according to the science profile must be supported.
    """
    SETSAMPLING = 'setsampling'
    DISPLAY_STATUS = 'ds'
    QUIT_SESSION = 'qs'
    DISPLAY_CALIBRATION = 'dc'
    START_LOGGING = 'start'
    STOP_LOGGING = 'stop'
    UPLOAD_DATA_ASCII_FORMAT = 'dd'
    UPLOAD_DATA_BINARY_FORMAT = 'DBbaud,b,e'
    GET_BYTE_COUNT = 'ByteCount'
    SET_BYTE_COUNT = '*ByteCount'
    SET = 'set' # Unofficial



class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseProtocolEvent):
    """
    Protocol events
    Should only have to define ones to ADD to the base class.  cannot remove from base class gracefully...
    """

    SETSAMPLING = 'PROTOCOL_EVENT_SETSAMPLING' # it HAS to be defined there, OR!!! InstrumentFSM.on_event() CANNOT HANDLE IT. THIS SHOULD BE DOCUMENTED!!!!!!


# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """

    # DS
    DEVICE_VERSION = 'DEVICE_VERSION' # str,
    SERIAL_NUMBER = 'SERIAL_NUMBER' # str,
    DS_DEVICE_DATE_TIME = 'DS_DEVICE_DATE_TIME' # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python,

    USER_INFO = 'USER_INFO' # str,
    QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER = 'QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER' # float,
    QUARTZ_PREASURE_SENSOR_RANGE = 'QUARTZ_PREASURE_SENSOR_RANGE' # float,

    TEMPERATURE_SENSOR = 'TEMPERATURE_SENSOR' # str,

    CONDUCTIVITY = 'CONDUCTIVITY' # bool,

    IOP_MA = 'IOP_MA' # float,
    VMAIN_V = 'VMAIN_V' # float,
    VLITH_V = 'VLITH_V' # float,

    LAST_SAMPLE_P = 'LAST_SAMPLE_P' # float,
    LAST_SAMPLE_T = 'LAST_SAMPLE_T' # float,
    LAST_SAMPLE_S = 'LAST_SAMPLE_S' # float,

    TIDE_INTERVAL = 'TIDE_INTERVAL' # int,
    TIDE_MEASUREMENT_DURATION = 'TIDE_MEASUREMENT_DURATION' # int,

    TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS = 'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS' # int,

    WAVE_SAMPLES_PER_BURST = 'WAVE_SAMPLES_PER_BURST' # float,
    WAVE_SAMPLES_SCANS_PER_SECOND = 'WAVE_SAMPLES_SCANS_PER_SECOND' # float, <--- May be new
    WAVE_SAMPLE_DURATION = 'WAVE_SAMPLE_DURATION' # float, <--- Renamed (... 1/WAVE_SAMPLE_DURATION = scans per second)

    USE_START_TIME = 'USE_START_TIME' # bool,
    START_TIME = 'START_TIME' # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python, <-- new
    USE_STOP_TIME = 'USE_STOP_TIME' # bool,
    STOP_TIME = 'STOP_TIME' # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python, <-- new

    TIDE_SAMPLES_PER_DAY = 'TIDE_SAMPLES_PER_DAY' # float,
    WAVE_BURSTS_PER_DAY = 'WAVE_BURSTS_PER_DAY' # float,
    MEMORY_ENDURANCE = 'MEMORY_ENDURANCE' # float,
    NOMINAL_ALKALINE_BATTERY_ENDURANCE = 'NOMINAL_ALKALINE_BATTERY_ENDURANCE' # float,
    TOTAL_RECORDED_TIDE_MEASUREMENTS = 'TOTAL_RECORDED_TIDE_MEASUREMENTS' # float,
    TOTAL_RECORDED_WAVE_BURSTS = 'TOTAL_RECORDED_WAVE_BURSTS' # float,
    TIDE_MEASUREMENTS_SINCE_LAST_START = 'TIDE_MEASUREMENTS_SINCE_LAST_START' # float,
    WAVE_BURSTS_SINCE_LAST_START = 'WAVE_BURSTS_SINCE_LAST_START' # float,
    TXREALTIME = 'TXREALTIME' # bool, <-- renamed from TRANSMIT_REAL_TIME_TIDE_DATA, TXREALTIME
    TXWAVEBURST = 'TXWAVEBURST' # bool, <-- renamed from TRANSMIT_REAL_TIME_WAVE_BURST_DATA, TXWAVEBURST
    TXWAVESTATS = 'TXWAVESTATS' # bool, <-- renamed from TRANSMIT_REAL_TIME_WAVE_STATS, TXWAVESTATS
    NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS = 'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS' # int,
    USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC = 'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC' # bool,
    PREASURE_SENSOR_HEIGHT_FROM_BOTTOM = 'PREASURE_SENSOR_HEIGHT_FROM_BOTTOM' # float,
    SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND = 'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND' # int, <-- renamed from SPECIAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND
    MIN_ALLOWABLE_ATTENUATION = 'MIN_ALLOWABLE_ATTENUATION' # float,
    MIN_PERIOD_IN_AUTO_SPECTRUM = 'MIN_PERIOD_IN_AUTO_SPECTRUM' # float,
    MAX_PERIOD_IN_AUTO_SPECTRUM = 'MAX_PERIOD_IN_AUTO_SPECTRUM' # float,
    HANNING_WINDOW_CUTOFF = 'HANNING_WINDOW_CUTOFF' # float,
    SHOW_PROGRESS_MESSAGES = 'SHOW_PROGRESS_MESSAGES' # bool,
    STATUS = 'STATUS' # str,
    LOGGING = 'LOGGING' # bool,

    # DC
    PCALDATE = 'PCALDATE' # tuple,
    PU0 = 'PU0' # float,
    PY1 = 'PY1' # float,
    PY2 = 'PY2' # float,
    PY3 = 'PY3' # float,
    PC1 = 'PC1' # float,
    PC2 = 'PC2' # float,
    PC3 = 'PC3' # float,
    PD1 = 'PD1' # float,
    PD2 = 'PD2' # float,
    PT1 = 'PT1' # float,
    PT2 = 'PT2' # float,
    PT3 = 'PT3' # float,
    PT4 = 'PT4' # float,
    FACTORY_M = 'FACTORY_M' # float,
    FACTORY_B = 'FACTORY_B' # float,
    POFFSET = 'POFFSET' # float,
    TCALDATE = 'TCALDATE' # tuple,
    TA0 = 'TA0' # float,
    TA1 = 'TA1' # float,
    TA2 = 'TA2' # float,
    TA3 = 'TA3' # float,

    CCALDATE = 'CCALDATE' # tuple,
    CG = 'CG' # float,
    CH = 'CH' # float,
    CI = 'CI' # float,
    CJ = 'CJ' # float,
    CTCOR = 'CTCOR' # float,
    CPCOR = 'CPCOR' # float,
    CSLOPE = 'CSLOPE' # float,

# Device prompts.
class Prompt(BaseEnum):
    """
    sbe26plus io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '? cmd S>'
    AUTOSAMPLE = 'S>'
"""
S>
time out

SBE 26plus
S>
"""


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    def setsampling(self, *args, **kwargs):
        """
        Set device parameters.
        @param args[0] parameter : value dict of parameters to set.
        @param timeout=timeout Optional command timeout.
        @raises InstrumentParameterException if missing or invalid set parameters.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if set command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        # Forward event and argument to the protocol FSM.
        log.debug("ROGER GOT INTO InstrumentDriver.setsampling() " + str(ProtocolEvent.SETSAMPLING))
        log.debug("args = " + str(args))
        log.debug("kwargs = " + str(kwargs))

        return self._connection_fsm.on_event(DriverEvent.DRIVER_PROTOCOL_PASSTHROUGH, ProtocolEvent.SETSAMPLING, *args, **kwargs)

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################


class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for sbe26plus driver.
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The sbe26plus newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build sbe26plus protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER,                  self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT,                   self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,               self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER,                  self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT,                   self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,         self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET,                    self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET,                    self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SETSAMPLING,            self._handler_command_setsampling)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST,                   self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,           self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,               self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,                self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET,                 self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,     self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER,                     self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT,                      self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST,                  self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET,                       self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,            self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,             self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,   self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,      self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()











        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.SETSAMPLING,                 self._build_setsampling_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_STATUS,              self._build_simple_command)
        self._add_build_handler(InstrumentCmds.QUIT_SESSION,                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_CALIBRATION,         self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_LOGGING,               self._build_simple_command)
        self._add_build_handler(InstrumentCmds.STOP_LOGGING,                self._build_simple_command)
        #self._add_build_handler(InstrumentCmds.UPLOAD_DATA_ASCII_FORMAT,    self._build_XXXXXXXXXXXXXX_command)
        #self._add_build_handler(InstrumentCmds.UPLOAD_DATA_BINARY_FORMAT,   self._build_XXXXXXXXXXXXXX_command)
        #self._add_build_handler(InstrumentCmds.GET_BYTE_COUNT,              self._build_XXXXXXXXXXXXXX_command)
        #self._add_build_handler(InstrumentCmds.SET_BYTE_COUNT,              self._build_XXXXXXXXXXXXXX_command)
        self._add_build_handler(InstrumentCmds.SET,                         self._build_set_command)

        #self._add_build_handler('ts', self._build_simple_command)
        #self._add_build_handler('tc', self._build_simple_command) #NO SUCH COMMAND
        #self._add_build_handler('tt', self._build_simple_command)
        #self._add_build_handler('tp', self._build_simple_command)


        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SETSAMPLING,                  self._parse_setsampling_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_STATUS,               self._parse_ds_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_CALIBRATION,          self._parse_dc_response)
        #self._add_response_handler(InstrumentCmds.QUIT_SESSION,                 self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.START_LOGGING,                self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.STOP_LOGGING,                 self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.UPLOAD_DATA_ASCII_FORMAT,     self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.UPLOAD_DATA_BINARY_FORMAT,    self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.GET_BYTE_COUNT,               self._parse_XXXXXXXXXXXXX)
        #self._add_response_handler(InstrumentCmds.SET_BYTE_COUNT,               self._parse_XXXXXXXXXXXXX)
        self._add_response_handler(InstrumentCmds.SET,                          self._parse_set_response)


        #self._add_response_handler('ts', self._parse_ts_response)
        #self._add_response_handler('tc', self._parse_test_response) #NO SUCH COMMAND
        #self._add_response_handler('tt', self._parse_test_response)
        #self._add_response_handler('tp', self._parse_test_response)










        # ts
        # 14.4309  23.72 -272.3189 -1.02626   0.0000
        # pressure, pressure temperature, temperature, and conductivity

        # Add sample handlers.
        self._sample_pattern = r'^#? *(-?\d+\.\d+), *(-?\d+\.\d+), *(-?\d+\.\d+)'
        self._sample_pattern += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
        self._sample_pattern += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'
        self._sample_pattern += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'
        self._sample_regex = re.compile(self._sample_pattern)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []



    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        next_state = None
        result = None

        # Wakeup the device with timeout if passed.
        timeout = kwargs.get('timeout', TIMEOUT)
        timeout = 30
        delay = 0.1
        prompt = self._wakeup(timeout=timeout, delay=delay)
        prompt = self._wakeup(timeout)

        # Set the state to change.
        # Raise if the prompt returned does not match command or autosample.
        if prompt == Prompt.COMMAND:
            next_state = ProtocolState.COMMAND
            result = ProtocolState.COMMAND
        elif prompt == Prompt.AUTOSAMPLE:
            next_state = ProtocolState.AUTOSAMPLE
            result = ProtocolState.AUTOSAMPLE
        else:
            raise InstrumentStateException('Unknown state.')

        return (next_state, result)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:

            for (key, val) in params.iteritems():
                result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
            self._update_params()

        return (next_state, result)




    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE26 Plus.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        result = None

        result = self._do_cmd_resp('ts', *args, **kwargs)

        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None


        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(InstrumentCmds.START_LOGGING, *args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE

        return (next_state, result)

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (ProtocolState.TEST, None).
        """
        next_state = None
        result = None

        next_state = ProtocolState.TEST

        return (next_state, result)

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS

        return (next_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        # Issue the stop command.
        self._do_cmd_resp(InstrumentCmds.STOP_LOGGING, *args, **kwargs)

        # Prompt device until command prompt is seen.
        self._wakeup_until(timeout, Prompt.COMMAND)

        next_state = ProtocolState.COMMAND

        return (next_state, result)

    ########################################################################
    # Common handlers.
    ########################################################################

    def _handler_command_autosample_test_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.
        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                try:
                    val = self._param_dict.get(key)
                    result[key] = val

                except KeyError:
                    raise InstrumentParameterException(('%s is not a valid parameter.' % key))

        return (next_state, result)

    ########################################################################
    # Test handlers.
    ########################################################################

    def _handler_test_enter(self, *args, **kwargs):
        """
        Enter test state. Setup the secondary call to run the tests.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Forward the test event again to run the test handler and
        # switch back to command mode afterward.
        Timer(1, lambda: self._protocol_fsm.on_event(ProtocolEvent.RUN_TEST)).start()

    def _handler_test_exit(self, *args, **kwargs):
        """
        Exit test state.
        """
        pass

    def _handler_test_run_tests(self, *args, **kwargs):
        """
        Run test routines and validate results.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        tc_pass = False
        tt_pass = False
        tp_pass = False
        tc_result = None
        tt_result = None
        tp_result = None

        test_result = {}

        try:
            tc_pass, tc_result = self._do_cmd_resp('tc', timeout=200)
            tt_pass, tt_result = self._do_cmd_resp('tt', timeout=200)
            tp_pass, tp_result = self._do_cmd_resp('tp', timeout=200)

        except Exception as e:
            test_result['exception'] = e
            test_result['message'] = 'Error running instrument tests.'

        finally:
            test_result['cond_test'] = 'Passed' if tc_pass else 'Failed'
            test_result['cond_data'] = tc_result
            test_result['temp_test'] = 'Passed' if tt_pass else 'Failed'
            test_result['temp_data'] = tt_result
            test_result['pres_test'] = 'Passed' if tp_pass else 'Failed'
            test_result['pres_data'] = tp_result
            test_result['success'] = 'Passed' if (tc_pass and tt_pass and tp_pass) else 'Failed'

        self._driver_event(DriverAsyncEvent.TEST_RESULT, test_result)
        next_state = ProtocolState.COMMAND

        return (next_state, result)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND

        return (next_state, result)

    ########################################################################
    # Private helpers.
    ########################################################################

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the sbe26plus device.
        """
        self._connection.send(NEWLINE)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """


        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS,timeout=timeout)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION,timeout=timeout)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic sbe26plus commands.
        @param cmd the simple sbe37 command to format.
        @retval The command to be sent to the device.
        """
        log.debug("in _build_simple_command() cmd = " + str(cmd))
        return cmd + NEWLINE

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE

        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        log.debug("_build_set_command set_cmd = " + set_cmd)
        return set_cmd

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """

        log.debug("PROMPT = " + str(prompt))
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('1 Set command not recognized: %s' % response)

    def _parse_ds_response(self, response, prompt):
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            #log.debug("DS GOT LINE " + repr(line))
            name = self._param_dict.update(line)
            #log.debug("NAME = " + str(name))



    def _parse_dc_response(self, response, prompt):
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            #log.debug("DS GOT LINE " + repr(line))
            name = self._param_dict.update(line)
            #log.debug("NAME = " + str(name))

    def _parse_dsdc_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt != SBE37Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(SBE37_NEWLINE):
            self._param_dict.update(line)

#    def _parse_ts_response(self, response, prompt):
#        """
#        Response handler for ts command.
#        @param response command response string.
#        @param prompt prompt following command response.
#        @retval sample dictionary containig c, t, d values.
#        @throws InstrumentProtocolException if ts command misunderstood.
#        @throws InstrumentSampleException if response did not contain a sample
#        """
#        log.debug("************ in _parse_ts_response ")
#        """
#        S>ts
#        ts
#           14.6343  22.99  22.7395 -1.02527   0.0000
#        (pressure psia, pressure temperature C, temperature C, conductivity S/m, and salinity psu)
#        """
#
#        log.debug("PROMPT = " + str(prompt) + " WANTED " + str(Prompt.COMMAND))
#        if prompt != Prompt.COMMAND:
#            raise InstrumentProtocolException('ts command not recognized: %s', response)
#
#
#        sample = None
#        for line in response.split(NEWLINE):
#            sample = self._extract_sample(line, True)
#            if sample:
#                break
#
#        if not sample:
#            raise SampleException('Response did not contain sample: %s' % repr(response))
#
#        return sample

#    def _parse_test_response(self, response, prompt):
#        """
#        Do minimal checking of test outputs.
#        @param response command response string.
#        @param promnpt prompt following command response.
#        @retval tuple of pass/fail boolean followed by response
#        """
#        log.debug("************ in _parse_test_response ")
#        success = False
#        lines = response.split()
#        if len(lines)>2:
#            data = lines[1:-1]
#            bad_count = 0
#            for item in data:
#                try:
#                    float(item)
#
#                except ValueError:
#                    bad_count += 1
#
#            if bad_count == 0:
#                success = True
#
#        return (success, response)

    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """

        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
            # direct access mode
            if len(data) > 0:
                #mi_logger.debug("Protocol._got_data(): <" + data + ">")
                # check for echoed commands from instrument (TODO: this should only be done for telnet?)
                if len(self._sent_cmds) > 0:
                    # there are sent commands that need to have there echoes filtered out
                    oldest_sent_cmd = self._sent_cmds[0]
                    if string.count(data, oldest_sent_cmd) > 0:
                        # found a command echo, so remove it from data and delete the command form list
                        data = string.replace(data, oldest_sent_cmd, "", 1)
                        self._sent_cmds.pop(0)
                if len(data) > 0 and self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)
                    # TODO: what about logging this as an event?
            return

        if len(data) > 0:
            # Call the superclass to update line and prompt buffers.
            CommandResponseInstrumentProtocol.got_data(self, data)

            # If in streaming mode, process the buffer for samples to publish.
            cur_state = self.get_current_state()
            if cur_state == ProtocolState.AUTOSAMPLE:
                if NEWLINE in self._linebuf:
                    lines = self._linebuf.split(NEWLINE)
                    self._linebuf = lines[-1]
                    for line in lines:
                        self._extract_sample(line)

    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish to agent.
        @param line string to match for sample.
        @param publsih boolean to publish sample (default True).
        @retval Sample dictionary if present or None.
        """



        """
        tide: start time = 11 Jul 2012 12:53:51, p = 14.6398, pt = 23.321, t = 23.0060, c = -1.02527, s = 0.0000
        tide: start time = 11 Jul 2012 13:01:45, p = 14.6384, pt = 23.251, t = 22.9377, c = -1.02527, s = 0.0000
        """
        log.debug("************ in _extract_sample GOT LINE => " + repr(line))
        sample = None
        match = self._sample_regex.match(line)
        if match:
            sample = {}
            #pressure, pressure temperature, temperature, and conductivity
            sample['t'] = [float(match.group(1))]
            sample['c'] = [float(match.group(2))]
            sample['p'] = [float(match.group(3))]

            # Driver timestamp.
            sample['time'] = [time.time()]
            sample['stream_name'] = 'ctd_parsed'

            if self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, sample)

        return sample

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.

        """
        # Add parameter handlers to parameter dict.
        log.debug("************ in _build_param_dict ")

        # DS

        ds_line_01 = r'SBE 26plus V ([\w.]+) +SN (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #
        ds_line_02 = r'user info=(.*)$'
        ds_line_03 = r'quartz pressure sensor: serial number = ([\d.\-]+), range = ([\d.\-]+) psia'
        ds_line_04 = r'internal temperature sensor' # NOT DONE #
        ds_line_05 = r'conductivity = (YES|NO)'
        ds_line_06 = r'iop = +([\d.\-]+) ma  vmain = +([\d.\-]+) V  vlith = +([\d.\-]+) V'
        ds_line_07 = r'last sample: p = +([\d.\-]+), t = +([\d.\-]+), s = +([\d.\-]+)'

        ds_line_08 = r'tide measurement: interval = ([\d.\-]+) minutes, duration = ([\d.\-]+) seconds'
        ds_line_09 = r'measure waves every ([\d.\-]+) tide samples'
        ds_line_10 = r'([\d.\-]+) wave samples/burst at ([\d.\-]+) scans/sec, duration = ([\d.\-]+) seconds'
        ds_line_11 = r'logging start time =  (\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #
        ds_line_12 = r'logging stop time =  (\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #

        ds_line_13 = r'tide samples/day = (\d+.\d+)'
        ds_line_14 = r'wave bursts/day = (\d+.\d+)'
        ds_line_15 = r'memory endurance = (\d+.\d+) days'
        ds_line_16 = r'nominal alkaline battery endurance = (\d+.\d+) days'
        ds_line_17 = r'total recorded tide measurements = ([\d.\-]+)'
        ds_line_18 = r'total recorded wave bursts = ([\d.\-]+)'
        ds_line_19 = r'tide measurements since last start = ([\d.\-]+)'
        ds_line_20 = r'wave bursts since last start = ([\d.\-]+)'

        ds_line_21 = r'transmit real-time tide data = (YES|NO)'
        ds_line_22 = r'transmit real-time wave burst data = (YES|NO)'
        ds_line_23 = r'transmit real-time wave statistics = (YES|NO)'
        # real-time wave statistics settings:
        ds_line_24 = r' +number of wave samples per burst to use for wave statistics = (\d+)' # REDUNDANT SEE LINE 10#
        ds_line_25 = r' +use measured temperature and conductivity for density calculation' # NOT DONE #
        ds_line_26 = r' +height of pressure sensor from bottom \(meters\) =  ([\d.]+)'
        ds_line_27 = r' +number of spectral estimates for each frequency band = (\d+)'
        ds_line_28 = r' +minimum allowable attenuation = ([\d.]+)'
        ds_line_29 = r' +minimum period \(seconds\) to use in auto-spectrum = (-?[\d.e\-\+]+)'
        ds_line_30 = r' +maximum period \(seconds\) to use in auto-spectrum = (-?[\d.e\-\+]+)'
        ds_line_31 = r' +hanning window cutoff = ([\d.]+)'
        ds_line_32 = r' +show progress messages' # NOT DONE #

        ds_line_33 = r'status = (logging|waiting|stopped)' # status = stopped by user
        ds_line_34 = r'logging = (YES|NO)' # logging = NO, send start command to begin logging
        #S>



        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.DEVICE_VERSION,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            ds_line_01,
            lambda match : string.upper(match.group(2)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.DS_DEVICE_DATE_TIME,
            ds_line_01,
            lambda match : string.upper(match.group(3)),
            self._string_to_string,
            multi_match=True) # will need to make this a date time once that is sorted out

        self._param_dict.add(Parameter.USER_INFO,
            ds_line_02,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER,
            ds_line_03,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.QUARTZ_PREASURE_SENSOR_RANGE,
            ds_line_03,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.CONDUCTIVITY,
            ds_line_05,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.IOP_MA,
            ds_line_06,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)
        self._param_dict.add(Parameter.VMAIN_V,
            ds_line_06,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)
        self._param_dict.add(Parameter.VLITH_V,
            ds_line_06,
            lambda match : float(match.group(3)),
            self._float_to_string,
            multi_match=True)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.LAST_SAMPLE_P,
            ds_line_07,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.LAST_SAMPLE_T,
            ds_line_07,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.LAST_SAMPLE_S,
            ds_line_07,
            lambda match : float(match.group(3)),
            self._float_to_string,
            multi_match=True)

        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.TIDE_INTERVAL,
            ds_line_08,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.TIDE_MEASUREMENT_DURATION,
            ds_line_08,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS,
            ds_line_09,
            lambda match : float(match.group(1)),
            self._float_to_string)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.WAVE_SAMPLES_PER_BURST,
            ds_line_10,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.WAVE_SAMPLES_SCANS_PER_SECOND,
            ds_line_10,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.WAVE_SAMPLE_DURATION,
            ds_line_10,
            lambda match : float(match.group(3)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.START_TIME,
            ds_line_11,
            lambda match : string.upper(match.group(1)),
            self._string_to_string) # will need to make this a date time once that is sorted out

        self._param_dict.add(Parameter.STOP_TIME,
            ds_line_12,
            lambda match : string.upper(match.group(1)),
            self._string_to_string) # will need to make this a date time once that is sorted out

        self._param_dict.add(Parameter.TIDE_SAMPLES_PER_DAY,
            ds_line_13,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.WAVE_BURSTS_PER_DAY,
            ds_line_14,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MEMORY_ENDURANCE,
            ds_line_15,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE,
            ds_line_16,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS,
            ds_line_17,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TOTAL_RECORDED_WAVE_BURSTS,
            ds_line_18,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START,
            ds_line_19,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.WAVE_BURSTS_SINCE_LAST_START,
            ds_line_20,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TXREALTIME,
            ds_line_21,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.TXWAVEBURST,
            ds_line_22,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.TXWAVESTATS,
            ds_line_23,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM,
            ds_line_26,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND,
            ds_line_27,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.MIN_ALLOWABLE_ATTENUATION,
            ds_line_28,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM,
            ds_line_29,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM,
            ds_line_30,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.HANNING_WINDOW_CUTOFF,
            ds_line_31,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.LOGGING,
            ds_line_34,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.STATUS,
            ds_line_33,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        ################################################

        # dc
        dc_line_01 = r'Pressure coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_02 = r' +U0 = (-?[\d.e\-\+]+)'
        dc_line_03 = r' +Y1 = (-?[\d.e\-\+]+)'
        dc_line_04 = r' +Y2 = (-?[\d.e\-\+]+)'
        dc_line_05 = r' +Y3 = (-?[\d.e\-\+]+)'
        dc_line_06 = r' +C1 = (-?[\d.e\-\+]+)'
        dc_line_07 = r' +C2 = (-?[\d.e\-\+]+)'
        dc_line_08 = r' +C3 = (-?[\d.e\-\+]+)'
        dc_line_09 = r' +D1 = (-?[\d.e\-\+]+)'
        dc_line_10 = r' +D2 = (-?[\d.e\-\+]+)'
        dc_line_11 = r' +T1 = (-?[\d.e\-\+]+)'
        dc_line_12 = r' +T2 = (-?[\d.e\-\+]+)'
        dc_line_13 = r' +T3 = (-?[\d.e\-\+]+)'
        dc_line_14 = r' +T4 = (-?[\d.e\-\+]+)'
        dc_line_15 = r' +M = ([\d.]+)'
        dc_line_16 = r' +B = ([\d.]+)'
        dc_line_17 = r' +OFFSET = (-?[\d.e\-\+]+)'
        dc_line_18 = r'Temperature coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_19 = r' +TA0 = (-?[\d.e\-\+]+)'
        dc_line_20 = r' +TA1 = (-?[\d.e\-\+]+)'
        dc_line_21 = r' +TA2 = (-?[\d.e\-\+]+)'
        dc_line_22 = r' +TA3 = (-?[\d.e\-\+]+)'
        dc_line_23 = r'Conductivity coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_24 = r' +CG = (-?[\d.e\-\+]+)'
        dc_line_25 = r' +CH = (-?[\d.e\-\+]+)'
        dc_line_26 = r' +CI = (-?[\d.e\-\+]+)'
        dc_line_27 = r' +CJ = (-?[\d.e\-\+]+)'
        dc_line_28 = r' +CTCOR = (-?[\d.e\-\+]+)'
        dc_line_29 = r' +CPCOR = (-?[\d.e\-\+]+)'
        dc_line_30 = r' +CSLOPE = (-?[\d.e\-\+]+)'
        # S>


        # DC
        self._param_dict.add(Parameter.PCALDATE,
            dc_line_01,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.PU0,
            dc_line_02,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY1,
            dc_line_03,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY2,
            dc_line_04,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY3,
            dc_line_05,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC1,
            dc_line_06,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC2,
            dc_line_07,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC3,
            dc_line_08,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD1,
            dc_line_09,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD2,
            dc_line_10,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT1,
            dc_line_11,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT2,
            dc_line_12,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT3,
            dc_line_13,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT4,
            dc_line_14,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FACTORY_M,
            dc_line_15,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FACTORY_B,
            dc_line_16,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.POFFSET,
            dc_line_17,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TCALDATE,
            dc_line_18,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.TA0,
            dc_line_19,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA1,
            dc_line_20,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA2,
            dc_line_21,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA3,
            dc_line_22,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CCALDATE,
            dc_line_23,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.CG,
            dc_line_24,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CH,
            dc_line_25,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CI,
            dc_line_26,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CJ,
            dc_line_27,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CTCOR,
            dc_line_28,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CPCOR,
            dc_line_29,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CSLOPE,
            dc_line_30,
            lambda match : float(match.group(1)),
            self._float_to_string)


    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _string_to_string(v):
        return v

    @staticmethod
    # Should be renamed boolen_to_string for consistency
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe37 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not a bool.
        """

        if not isinstance(v,bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        if v:
            return 'y'
        else:
            return 'n'

    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for sbe37 set operations.
        @param v An int val.
        @retval an int string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not an int.
        """

        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe37 set operations.
        @param v A float val.
        @retval a float string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value is not a float.
        """


        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe37 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe37 set operations.
        @throws InstrumentParameterException if date tuple is not valid.
        """

        if not isinstance(v,(list,tuple)):
            raise InstrumentParameterException('Value %s is not a list, tuple.' % str(v))

        if not len(v)==3:
            raise InstrumentParameterException('Value %s is not length 3.' % str(v))

        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep',
                  'Oct','Nov','Dec']
        day = v[0]
        month = v[1]
        year = v[2]

        if len(str(year)) > 2:
            year = int(str(year)[-2:])

        if not isinstance(day,int) or day < 1 or day > 31:
            raise InstrumentParameterException('Value %s is not a day of month.' % str(day))

        if not isinstance(month,int) or month < 1 or month > 12:
            raise InstrumentParameterException('Value %s is not a month.' % str(month))

        if not isinstance(year,int) or year < 0 or year > 99:
            raise InstrumentParameterException('Value %s is not a 0-99 year.' % str(year))

        return '%02i-%s-%02i' % (day,months[month-1],year)

    @staticmethod
    def _string_to_date(datestr, fmt):
        """
        Extract a date tuple from an sbe37 date string.
        @param str a string containing date information in sbe37 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """

        if not isinstance(datestr, str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr, fmt)
            date = (date_time[2],date_time[1],date_time[0])

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))

        return date




# EXPERIMENT EXPERIMENT EXPERIMENT BELOW
    def _build_setsampling_command(self, foo, *args, **kwargs):

        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        log.debug(" *******************IN _build_setsampling_command !!!!!!!!!!!!!!!!!!!!!!")
        log.debug("args = " + str(args))
        log.debug("kwargs = " + str(kwargs))
        log.debug("TA0 = " + str(args[0]) )
        # SHOULD STASH THE ARGS INTO SELF.SAMPLING_ARGS OR SOME SUCH.
        #log.debug(str(args{'setsampling'}))
        self._sampling_args = args[0]
        #for (key, val) in self._sampling_args.iteritems():
        #    log.debug("PROOF THAT KEY(" + str(key) + ") = VAL(" + str(val) + ") made it into _build_setsampling_command")

        #try:
        #    str_val = self._param_dict.format(param, val)
        #    set_cmd = '%s=%s' % (param, str_val)
        #    set_cmd = set_cmd + NEWLINE

        #except KeyError:
        #    raise InstrumentParameterException('Unknown driver parameter %s' % param)

        #log.debug("_build_set_command set_cmd = " + set_cmd)
        return InstrumentCmds.SETSAMPLING  + NEWLINE


    def _parse_setsampling_response(self, response, prompt): #(self, cmd, *args, **kwargs):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.

        S>setsampling
        tide interval (integer minutes) = 4, new value = 4
        tide measurement duration (seconds) = 10, new value = 40
        measure wave burst after every N tide samples: N = 1, new value =
        number of wave samples per burst (multiple of 4) = 4, new value =
        wave Sample duration (0.25, 0.50, 0.75, 1.0) seconds = 0.25, new value =
        use start time (y/n) = n, new value =
        use stop time (y/n) = n, new value =
        TXWAVESTATS (real-time wave statistics) (y/n) = n, new value =
        S>
        """


        desired_prompt = ", new value = "
        debug_count = 0
        done = False
        while not done:
            (prompt, response) = self._get_response(expected_prompt=desired_prompt)
            self._promptbuf = ''
            self._linebuf = ''
            time.sleep(0.1)
            #debug_count = debug_count + 1
            #log.debug(str(debug_count) + " times through")
            #log.debug("GOT A PROMPT -- '" + prompt + "'")
            #log.debug("GOT A RESPONSE  -- '" + response + "'")


            if "tide interval (integer minutes) " in response:
                if 'TIDE_INTERVAL' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_INTERVAL']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "tide measurement duration (seconds)" in response:
                if 'TIDE_MEASUREMENT_DURATION' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_MEASUREMENT_DURATION']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "measure wave burst after every N tide samples" in response:
                if 'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of wave samples per burst (multiple of 4)" in response:
                if 'WAVE_SAMPLES_PER_BURST' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['WAVE_SAMPLES_PER_BURST']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "wave Sample duration (0.25, 0.50, 0.75, 1.0) seconds" in response:
                if 'WAVE_SAMPLE_DURATION' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['WAVE_SAMPLE_DURATION']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use start time (y/n)" in response:
                if 'USE_START_TIME' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_START_TIME']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use stop time (y/n)" in response:
                if 'USE_STOP_TIME' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_STOP_TIME']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "TXWAVESTATS (real-time wave statistics) (y/n)" in response:
                if 'TXWAVESTATS' in self._sampling_args:
                    if self._sampling_args['TXWAVESTATS'] == False:
                        done = True
                    self._connection.send(self._true_false_to_string(self._sampling_args['TXWAVESTATS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "show progress messages (y/n) = " in response:
                if 'SHOW_PROGRESS_MESSAGES' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['SHOW_PROGRESS_MESSAGES']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of wave samples per burst to use for wave statistics = " in response:
                if 'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use measured temperature and conductivity for density calculation (y/n) = " in response:
                if 'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "height of pressure sensor from bottom (meters) = " in response:
                if 'PREASURE_SENSOR_HEIGHT_FROM_BOTTOM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['PREASURE_SENSOR_HEIGHT_FROM_BOTTOM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of spectral estimates for each frequency band = " in response:
                if 'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "minimum allowable attenuation = " in response:
                if 'MIN_ALLOWABLE_ATTENUATION' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MIN_ALLOWABLE_ATTENUATION']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "minimum period (seconds) to use in auto-spectrum = " in response:
                if 'MIN_PERIOD_IN_AUTO_SPECTRUM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MIN_PERIOD_IN_AUTO_SPECTRUM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "maximum period (seconds) to use in auto-spectrum = " in response:
                if 'MAX_PERIOD_IN_AUTO_SPECTRUM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MAX_PERIOD_IN_AUTO_SPECTRUM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "hanning window cutoff = " in response:
                done = True
                if 'HANNING_WINDOW_CUTOFF' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['HANNING_WINDOW_CUTOFF']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
                """
                the remaining prompts apply to real-time wave statistics
                    show progress messages (y/n) = n, new value = y
                    number of wave samples per burst to use for wave statistics = 512, new value = 555
                    use measured temperature and conductivity for density calculation (y/n) = y, new value =
                    height of pressure sensor from bottom (meters) = 600.0, new value = 55
                    number of spectral estimates for each frequency band = 5, new value =
                    minimum allowable attenuation = 0.0025, new value =
                    minimum period (seconds) to use in auto-spectrum = 0.0e+00, new value =
                    maximum period (seconds) to use in auto-spectrum = 1.0e+06, new value =
                    hanning window cutoff = 0.10, new value =
                resetting number of wave samples per burst to 512
                resetting number of samples to use for wave statistics to 512
                """
            else:
                log.debug("ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR")
                raise InstrumentProtocolException('HOW DID I GET HERE! %s' % str(response) + str(prompt))




        prompt = ""
        while prompt != Prompt.COMMAND:
            (prompt, response) = self._get_response(expected_prompt=Prompt.COMMAND)
            log.debug("SILENTLY GOBBLING " + repr(response))





    def _handler_command_setsampling(self, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        log.debug(" *******************IN _handler_command_setsampling ")
        next_state = None
        result = None

        kwargs['expected_prompt'] = ", new value = "
        result = self._do_cmd_resp('setsampling', *args, **kwargs)

        return (next_state, result)

        """
        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp('startnow', *args, **kwargs)

        return (next_state, result)

        log.debug("ROGER ARGS = " + str(args))
        log.debug("ROGER KARGS = " + str(kwargs))
        print "ROGER ROGER ROGER"

        log.debug("ROGER ***")
        timeout = kwargs.get('timeout', TIMEOUT)

        result = self._do_cmd_resp('setsampling' + NEWLINE, timeout=timeout, expected_prompt=', new value =')
        result = self._do_cmd_resp('setsampling' + NEWLINE, timeout=timeout, expected_prompt='S>')
        #for char in cmd_line:
        #    self._connection.send(char)
        #    time.sleep(write_delay)
        #(prompt, result) = self._get_response(timeout, expected_prompt=', new value =')

        next_state = None
        result = None


        log.debug("ROGER ARGS = " + str(args))
        log.debug("ROGER KARGS = " + str(kwargs))


        return (next_state, result)
        """