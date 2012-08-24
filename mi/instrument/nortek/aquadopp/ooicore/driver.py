"""
@package mi.instrument.nortek.aquadopp.ooicore.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the ooicore
Release notes:

Driver for Aquadopp DW
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import time
import string
import re
import copy

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               InstrumentStateException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.common import InstErrorCode

from mi.core.log import get_logger ; log = get_logger()


# newline.
NEWLINE = '\n\r'

# default timeout.
TIMEOUT = 10

CONFIGURATION_RESPONSE_LENGTH = 786

# Packet config
PACKET_CONFIG = {
    'parsed' : None,
    'raw' : None
}

# Device prompts.
class InstrumentPrompts(BaseEnum):
    """
    aquadopp prompts.
    """
    COMMAND_MODE  = 'Command mode'
    CONFIRMATION  = 'Confirm:'
    Z_ACK         = '\x06\x06'  # attach a 'Z' to the front of these two items to force them to the end of the list
    Z_NACK        = '\x15\x15'  # so the other responses will have priority to be detected if they are present

    
class InstrumentCmds(BaseEnum):
    SOFT_BREAK_FIRST_HALF              = '@@@@@@'
    SOFT_BREAK_SECOND_HALF             = 'K1W%!Q'
    CMD_WHAT_MODE                      = 'II'   
    SAMPLE_WHAT_MODE                   = 'I'   
    POWER_DOWN                         = 'PD'     
    IDENTIFY                           = 'ID'
    CONFIRMATION                       = 'MC'
    SAMPLE_AVG_TIME                    = 'A'
    SAMPLE_INTERVAL_TIME               = 'M'
    START_MEASUREMENT_WITHOUT_RECORDER = 'ST'
    GET_ALL_CONFIGURATIONS             = 'GA'
    GET_USER_CONFIGURATION             = 'GC'
    CONFIGURE_INSTRUMENT               = 'CC'
    
class InstrumentModes(BaseEnum):
    FIRMWARE_UPGRADE = '\x00\x00\x06\x06'
    MEASUREMENT      = '\x01\x00\x06\x06'
    COMMAND          = '\x02\x00\x06\x06'
    DATA_RETRIEVAL   = '\x04\x00\x06\x06'
    CONFIRMATION     = '\x05\x00\x06\x06'
    

class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """
    """
    # these are read only and not included for now
    # hardware configuration
    HW_SERIAL_NUMBER = "HardwareSerialNumber"
    HW_CONFIG = "HardwareConfig"
    HW_FREQUENCY = "HardwareFrequency"
    PIC_VERSION = "HardwarePicCodeVerNumber"
    HW_REVISION = "HardwareRevision"
    REC_SIZE = "HardwareRecorderSize"
    STATUS = "HardwareStatus"
    HW_SPARE = 'HardwareSpare'
    FW_VERSION = "HardwareFirmwareVersion"
    
    # head configuration
    HEAD_CONFIG = "HeadConfig"
    HEAD_FREQUENCY = "HeadFrequency"
    HEAD_TYPE = "HeadType"
    HEAD_SERIAL_NUMBER = "HeadSerialNumber"
    HEAD_SYSTEM = 'HeadSystemData'
    HEAD_SPARE = 'HeadSpare'
    HEAD_NUMBER_BEAMS = "HeadNumberOfBeams"
    """
    
    # user configuration
    TRANSMIT_PULSE_LENGTH = "TransmitPulseLength"                # T1
    BLANKING_DISTANCE = "BlankingDistance"                       # T2
    RECEIVE_LENGTH = "ReceiveLength"                             # T3
    TIME_BETWEEN_PINGS = "TimeBetweenPings"                      # T4
    TIME_BETWEEN_BURST_SEQUENCES = "TimeBetweenBurstSequences"   # T5 
    NUMMBER_PINGS = "NumberPings"     # number of beam sequences per burst
    AVG_INTERVAL = "AvgInterval"
    USER_NUMBER_BEAMS = "UserNumberOfBeams" 
    TIMING_CONTROL_REGISTER = "TimingControlRegister"
    POWER_CONTROL_REGISTER = "PowerControlRegister"
    A1_1_SPARE = 'A1_1Spare'
    B0_1_SPARE = 'B0_1Spare'
    B1_1_SPARE = 'B1_1Spare'
    COMPASS_UPDATE_RATE ="CompassUpdateRate"  
    COORDINATE_SYSTEM = "CoordinateSystem"
    NUMBER_BINS = "NumberOfBins"      # number of cells
    BIN_LENGTH = "BinLength"          # cell size
    MEASUREMENT_INTERVAL = "MeasurementInterval"
    DEPLOYMENT_NAME = "DeploymentName"
    WRAP_MODE = "WrapMode"
    CLOCK_DEPLOY = "ClockDeploy"      # deployment stgart time
    DIAGNOSTIC_INTERVAL = "DiagnosticInterval"
    MODE = "Mode"
    ADJUSTMENT_SOUND_SPEED = 'AdjustmentSoundSpeed'
    NUMBER_SAMPLES_DIAGNOSTIC = 'NumberSamplesInDiagMode'
    NUMBER_BEAMS_CELL_DIAGNOSTIC = 'NumberBeamsPerCellInDiagMode'
    NUMBER_PINGS_DIAGNOSTIC = 'NumberPingsInDiagMode'
    MODE_TEST = 'ModeTest'
    ANALOG_INPUT_ADDR = 'AnalogInputAddress'
    SW_VERSION = 'SwVersion'
    USER_1_SPARE = 'User1Spare'
    VELOCITY_ADJ_TABLE = 'VelocityAdjTable'
    COMMENTS = 'Comments'
    WAVE_MEASUREMENT_MODE = 'WaveMeasurementMode'
    DYN_PERCENTAGE_POSITION = 'PercentageForCellPositioning'
    WAVE_TRANSMIT_PULSE = 'WaveTransmitPulse'
    WAVE_BLANKING_DISTANCE = 'WaveBlankingDistance'
    WAVE_CELL_SIZE = 'WaveCellSize'
    NUMBER_DIAG_SAMPLES = 'NumberDiagnosticSamples'
    A1_2_SPARE = 'A1_2Spare'
    B0_2_SPARE = 'B0_2Spare'
    B1_2_SPARE = 'B1_2Spare'
    USER_2_SPARE = 'User2Spare'
    ANALOG_OUTPUT_SCALE = 'AnalogOutputScale'
    COORELATION_THRESHOLD = 'CoorelationThreshold'
    USER_3_SPARE = 'User3Spare'
    TRANSMIT_PULSE_LENGTH_SECOND_LAG = 'TransmitPulseLengthSecondLag'
    USER_4_SPARE = 'User4Spare'
    QUAL_CONSTANTS = 'StageMatchFilterConstants'
    
    
class BinaryParameterDictVal(ParameterDictVal):
    
    def __init__(self, name, pattern, f_getval, f_format, value=None,
                 visibility=ParameterDictVisibility.READ_WRITE,
                 menu_path_read=None,
                 submenu_read=None,
                 menu_path_write=None,
                 submenu_write=None):
        """
        Parameter value constructor.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).
        """
        self.name = name
        self.pattern = pattern
        #log.debug('BinaryParameterDictVal.__int__(); pattern=%s' %pattern)
        self.regex = re.compile(pattern, re.DOTALL)
        self.f_getval = f_getval
        self.f_format = f_format
        self.value = value
        self.menu_path_read = menu_path_read
        self.submenu_read = submenu_read
        self.menu_path_write = menu_path_write
        self.submenu_write = submenu_write
        self.visibility = visibility

    def update(self, input):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        match = self.regex.match(input)
        if match:
            log.debug('BinaryParameterDictVal.update(): match=<%s>', match.group(1).encode('hex'))
            self.value = self.f_getval(match)
            if isinstance(self.value, int):
                log.debug('BinaryParameterDictVal.update(): updated parameter %s=<%d>', self.name, self.value)
            else:
                log.debug('BinaryParameterDictVal.update(): updated parameter %s=\"%s\" <%s>', self.name, 
                          self.value, str(self.value).encode('hex'))
            return True
        else:
            log.debug('BinaryParameterDictVal.update(): failed to update parameter %s', self.name)
            log.debug('input=%s' %input.encode('hex'))
            log.debug('regex=%s' %str(self.regex))
            return False
        

class BinaryProtocolParameterDict(ProtocolParameterDict):   
    
    def add(self, name, pattern, f_getval, f_format, value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None, submenu_read=None,
            menu_path_write=None, submenu_write=None):
        """
        Add a parameter object to the dictionary.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).        
        """
        val = BinaryParameterDictVal(name, pattern, f_getval, f_format,
                                     value=value,
                                     visibility=visibility,
                                     menu_path_read=menu_path_read,
                                     submenu_read=submenu_read,
                                     menu_path_write=menu_path_write,
                                     submenu_write=submenu_write)
        self._param_dict[name] = val
        
    def update(self, input):
        """
        Update the dictionary with an input. Iterate through all objects
        and attempt to match and update all parameter.s
        @param input A string to match to a dictionary object.
        @retval A boolean to indicate that update was successfully, false if update failed
        """
        log.debug('BinaryProtocolParameterDict.update(): input=%s' %input.encode('hex'))
        for (name, val) in self._param_dict.iteritems():
            #log.debug('BinaryProtocolParameterDict.update(): name=%s' %name)
            if not val.update(input):
                return False
        return True
    
    def set_from_value(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        log.debug("BinaryProtocolParameterDict.set_from_value(): name=%s, value=%s" %(name, value))
        self._param_dict[name].value = value
        
    def format_parameter(self, name):
        """
        Format the parameter for a set command.
        @param name The name of the parameter.
        @retval The value formatted as a string for writing to the device.
        @raises InstrumentProtocolException if the value could not be formatted.
        @raises KeyError if the parameter name is invalid.
        """
        return self._param_dict[name].f_format(self._param_dict[name].value)



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

    def get_resource_params(self):
        """
        Return list of device parameters available.  These are a subset of all the parameters
        """
        list = []
        for param in Parameter:
            if not param.endswith('Spare'):
                list.append(param) 
        return list

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    
    UserParameters = [
        # user configuration
        Parameter.TRANSMIT_PULSE_LENGTH,
        Parameter.BLANKING_DISTANCE,
        Parameter.RECEIVE_LENGTH,
        Parameter.TIME_BETWEEN_PINGS,
        Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
        Parameter.NUMMBER_PINGS,
        Parameter.AVG_INTERVAL,
        Parameter.USER_NUMBER_BEAMS, 
        Parameter.TIMING_CONTROL_REGISTER,
        Parameter.POWER_CONTROL_REGISTER,
        Parameter.A1_1_SPARE,
        Parameter.B0_1_SPARE,
        Parameter.B1_1_SPARE,
        Parameter.COMPASS_UPDATE_RATE,  
        Parameter.COORDINATE_SYSTEM,
        Parameter.NUMBER_BINS,
        Parameter.BIN_LENGTH,
        Parameter.MEASUREMENT_INTERVAL,
        Parameter.DEPLOYMENT_NAME,
        Parameter.WRAP_MODE,
        Parameter.CLOCK_DEPLOY,
        Parameter.DIAGNOSTIC_INTERVAL,
        Parameter.MODE,
        Parameter.ADJUSTMENT_SOUND_SPEED,
        Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
        Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
        Parameter.NUMBER_PINGS_DIAGNOSTIC,
        Parameter.MODE_TEST,
        Parameter.ANALOG_INPUT_ADDR,
        Parameter.SW_VERSION,
        Parameter.USER_1_SPARE,
        Parameter.VELOCITY_ADJ_TABLE,
        Parameter.COMMENTS,
        Parameter.WAVE_MEASUREMENT_MODE,
        Parameter.DYN_PERCENTAGE_POSITION,
        Parameter.WAVE_TRANSMIT_PULSE,
        Parameter.WAVE_BLANKING_DISTANCE,
        Parameter.WAVE_CELL_SIZE,
        Parameter.NUMBER_DIAG_SAMPLES,
        Parameter.A1_2_SPARE,
        Parameter.B0_2_SPARE,
        Parameter.B1_2_SPARE,
        Parameter.USER_2_SPARE,
        Parameter.ANALOG_OUTPUT_SCALE,
        Parameter.COORELATION_THRESHOLD,
        Parameter.USER_3_SPARE,
        Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
        Parameter.USER_4_SPARE,
        Parameter.QUAL_CONSTANTS,
        ]
    
    CHECK_SUM_SEED = 0xb58c

    
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, 
                                           ProtocolEvent,
                                           ProtocolEvent.ENTER, 
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # set up configuration indexing constants
        """  only user config returned for now
        self.HEAD_OFFSET = 48
        self.USER_OFFSET = self.HEAD_OFFSET + 224
        """
        self.USER_OFFSET = 0
        self.ACK_OFFSET = self.USER_OFFSET + 512
        self.CONFIGURATION_RESPONSE_LENGTH = self.ACK_OFFSET + 2 
               
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add response handlers for device commands.

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)


    ########################################################################
    # overridden superclass methods
    ########################################################################

    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """
        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
            # direct access mode
            if len(data) > 0:
                log.debug("mavs4InstrumentProtocol._got_data(): <" + data + ">") 
                if self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)
                    # TODO: what about logging this as an event?
            return
        
        if len(data)>0:
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

    def _get_response(self, timeout=5, expected_prompt=None):
        """
        Get a response from the instrument
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()
                
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            assert isinstance(expected_prompt, str)
            prompt_list = [expected_prompt]            
        while True:
            for item in prompt_list:
                if item in self._promptbuf:
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)
            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', 5)
        expected_prompt = kwargs.get('expected_prompt', None)
                            
        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, expected_prompt=%s (%s),' %
                        (repr(cmd), timeout, expected_prompt, expected_prompt.encode("hex")))
        self._connection.send(cmd)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout,
                                              expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)
        
        return resp_result
            
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
        Discover current state of instrument; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result)
        """
        next_state = None
        result = None

        # try to discover the device mode using timeout if passed.
        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._get_mode(timeout)
        if prompt == InstrumentPrompts.COMMAND_MODE:
            next_state = ProtocolState.COMMAND
            result = ProtocolState.COMMAND
        elif prompt == InstrumentPrompts.CONFIRMATION:    
            next_state = ProtocolState.AUTOSAMPLE
            result = ProtocolState.AUTOSAMPLE
        elif prompt == InstrumentPrompts.Z_ACK:
            log.debug('_handler_unknown_discover: promptbuf=%s (%s)' %(self._promptbuf, self._promptbuf.encode("hex")))
            if InstrumentModes.COMMAND in self._promptbuf:
                next_state = ProtocolState.COMMAND
                result = ProtocolState.COMMAND
            elif (InstrumentModes.MEASUREMENT in self._promptbuf or 
                 InstrumentModes.CONFIRMATION in self._promptbuf):
                next_state = ProtocolState.AUTOSAMPLE
                result = ProtocolState.AUTOSAMPLE
            else:
                raise InstrumentStateException('Unknown state.')
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
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.
        try:
            params_to_set = args[0]           
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        else:
            if not isinstance(params_to_set, dict):
                raise InstrumentParameterException('Set parameters not a dict.')
        
        parameters = copy.copy(self._param_dict)    # get copy of parameters to modify
        
        # For each key, value in the params_to_set list set the value in parameters copy.
        try:
            for (name, value) in params_to_set.iteritems():
                log.debug('setting %s to %s' %(name, value))
                parameters.set_from_value(name, value)
        except Exception as ex:
            raise InstrumentProtocolException('Unable to set parameter %s to %s: %s' %(name, value, ex))
            
        output = self._create_set_output(parameters)
        
        self._connection.send(InstrumentCmds.CONFIGURE_INSTRUMENT)
        self._connection.send(output)

        # Clear the prompt buffer.
        self._promptbuf = ''
        self._get_response(timeout=5, expected_prompt=InstrumentPrompts.Z_ACK)

        self._update_params()
            
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_WITHOUT_RECORDER, 
                                   expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)
                
        next_state = ProtocolState.AUTOSAMPLE        
        
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
        @retval (next_state, result) tuple, (SBE37ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # send soft break
        self._connection.send(InstrumentCmds.SOFT_BREAK_FIRST_HALF)
        time.sleep(.1)
        self._do_cmd_resp(InstrumentCmds.SOFT_BREAK_SECOND_HALF,
                          expected_prompt = InstrumentPrompts.CONFIRMATION, *args, **kwargs)
        
        # Issue the confirmation command.
        self._do_cmd_resp(InstrumentCmds.CONFIRMATION, 
                          expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)

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
    # Common handlers.
    ########################################################################

    def _handler_get(self, *args, **kwargs):
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
        # Retrieve each key in the list, raise if any are invalid.
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
    # Private helpers.
    ########################################################################
    
    def _convert_word_to_int(self, word):
        low_byte = ord(word[0])
        high_byte = 0x100 * ord(word[1])
        #log.debug('w=%s, l=%d, h=%d, v=%d' %(word.encode('hex'), low_byte, high_byte, low_byte + high_byte))
        return low_byte + high_byte
    
    def _word_to_string(self, value):
        low_byte = value & 0xff
        high_byte = (value & 0xff00) >> 8
        return chr(low_byte) + chr(high_byte)
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        
        # The parameter dictionary.
        self._param_dict = BinaryProtocolParameterDict()

        # Add parameter handlers to parameter dict.
        
        """
        These are read only parameters and not processed for now
        # hardware config
        self._param_dict.add(Parameter.HW_SERIAL_NUMBER,
                             r'^.{4}(.{14}).*',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HW_CONFIG,
                             r'^.{18}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HW_FREQUENCY,
                             r'^.{20}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PIC_VERSION,
                             r'^.{22}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HW_REVISION,
                             r'^.{24}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.REC_SIZE,
                             r'^.{26}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.STATUS,
                             r'^.{28}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HW_SPARE,
                             r'^.{30}(.{12}).*',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.FW_VERSION,
                             r'^.{42}(.{4}).*',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        
        # head config
        self._param_dict.add(Parameter.HEAD_CONFIG,
                             r'^.{%s}(.{2}).*' % str(self.HEAD_OFFSET+4),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_FREQUENCY,
                             r'^.{%s}(.{2}).*' % str(self.HEAD_OFFSET+6),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_TYPE,
                             r'^.{%s}(.{2}).*' % str(self.HEAD_OFFSET+8),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_SERIAL_NUMBER,
                             r'^.{%s}(.{12}).*' % str(self.HEAD_OFFSET+10),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_SYSTEM,
                             r'^.{%s}(.{176}).*' % str(self.HEAD_OFFSET+22),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_SPARE,
                             r'^.{%s}(.{22}).*' % str(self.HEAD_OFFSET+198),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.HEAD_NUMBER_BEAMS,
                             r'^.{%s}(.{2}).*' % str(self.HEAD_OFFSET+220),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        """
        
        # user config
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+4),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+6),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+8),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+10),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+12),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMMBER_PINGS,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+14),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+16),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+18),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+20),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+22),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.A1_1,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+24),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B0_1,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+26),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B1_1,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+28),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+30),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+32),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMBER_BINS,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+34),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.BIN_LENGTH,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+36),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+38),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                             r'^.{%s}(.{6}).*' % str(self.USER_OFFSET+40),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WRAP_MODE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+46),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                             r'^.{%s}(.{6}).*' % str(self.USER_OFFSET+48),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                             r'^.{%s}(.{4}).*' % str(self.USER_OFFSET+54),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.MODE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+58),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+60),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+62),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+64),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+66),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.MODE_TEST,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+68),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+70),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.SW_VERSION,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+72),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.USER_SPARE1,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+74),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                             r'^.{%s}(.{180}).*' % str(self.USER_OFFSET+76),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.COMMENTS,
                             r'^.{%s}(.{180}).*' % str(self.USER_OFFSET+256),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+436),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+438),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+440),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+442),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+444),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+446),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.A1_2,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+448),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B0_2,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+450),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B1_2,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+452),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.USER_SPARE2,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+454),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+456),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.COORELATION_THRESHOLD,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+458),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.USER_SPARE3,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+460),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                             r'^.{%s}(.{2}).*' % str(self.USER_OFFSET+462),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string)
        self._param_dict.add(Parameter.USER_SPARE4,
                             r'^.{%s}(.{30}).*' % str(self.USER_OFFSET+464),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                             r'^.{%s}(.{16}).*' % str(self.USER_OFFSET+494),
                             lambda match : match.group(1),
                             lambda string : string)
        
    def _dump_user_config(self, input):
        # dump user section
        for byte_index in range(0, len(input)):
            if byte_index % 0x10 == 0:
                print('\n%03x  ' % byte_index),
            print('%02x ' % ord(input[byte_index])),
        print('')
    
    def _check_configuration(self, input):
        HW_SYNC_BYTES = '\xa5\x05\x18\x00'
        HD_SYNC_BYTES = '\xa5\x04\x70\x00'
        USER_SYNC_BYTES = '\xa5\x00\x00\x01'
        
        log.debug('_check_configuration: user config=\n')
        self._dump_user_config(input[self.USER_OFFSET:self.ACK_OFFSET])
        # check for ACK bytes
        if input[self.ACK_OFFSET:self.ACK_OFFSET+2] != InstrumentPrompts.Z_ACK:
            log.debug('_check_configuration: ACK bytes in error %s != %s' 
                      %(input[self.ACK_OFFSET:self.ACK_OFFSET+2].encode('hex'), InstrumentPrompts.Z_ACK.encode('hex')))
            return False
        
        # check the sync bytes for each of the configuration groups
        """
        if input[0:4] != HW_SYNC_BYTES:
            log.debug('_check_configuration: hardware sync bytes in error %s!=%s' 
                      %(input[0:3], HW_SYNC_BYTES))
            return False
        if input[self.HEAD_OFFSET:self.HEAD_OFFSET+4] != HD_SYNC_BYTES:
            log.debug('_check_configuration: head sync bytes in error %s != %s' 
                      %(input[self.HEAD_OFFSET:self.HEAD_OFFSET+4], HD_SYNC_BYTES))
            return False
        """
        if input[self.USER_OFFSET:self.USER_OFFSET+4] != USER_SYNC_BYTES:
            log.debug('_check_configuration: hardware sync bytes in error %s != %s' 
                      %(input[self.USER_OFFSET:self.USER_OFFSET+4], USER_SYNC_BYTES))
            return False
        
        # check checksum bytes
        
        # check hardware checksum
        """
        calculated_checksum = self.CHECK_SUM_SEED
        for word_index in range(0, self.HEAD_OFFSET-2, 2):
            word_value = self._convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        sent_checksum = self._convert_word_to_int(input[self.HEAD_OFFSET-2:self.HEAD_OFFSET])
        if sent_checksum != calculated_checksum:
            log.debug('_check_configuration: hardware checksum in error %s != %s' 
                      %(calculated_checksum, sent_checksum))
            return False        
        
        # check head checksum
        calculated_checksum = self.CHECK_SUM_SEED
        for word_index in range(self.HEAD_OFFSET, self.USER_OFFSET-2, 2):
            word_value = self._convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        sent_checksum = self._convert_word_to_int(input[self.USER_OFFSET-2:self.USER_OFFSET])
        if sent_checksum != calculated_checksum:
            log.debug('_check_configuration: head checksum in error %s != %s' 
                      %(calculated_checksum, sent_checksum))
            return False        
        """
        
        # check user checksum
        calculated_checksum = self.CHECK_SUM_SEED
        for word_index in range(self.USER_OFFSET, self.ACK_OFFSET-2, 2):
            word_value = self._convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        log.debug('_check_configuration: user c_c = %s' % calculated_checksum)
        sent_checksum = self._convert_word_to_int(input[self.ACK_OFFSET-2:self.ACK_OFFSET])
        if sent_checksum != calculated_checksum:
            log.debug('_check_configuration: user checksum in error %s != %s' 
                      %(calculated_checksum, sent_checksum))
            return False       
        
        return True

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolState.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        # Grab time for timeout.
        starttime = time.time()
        timeout = 6

        # get params from the instrument
        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''

            log.debug('Sending get_all_configurations command to the instrument.')
            # Send what_mode command to attempt to get a response.
            self._connection.send(InstrumentCmds.GET_USER_CONFIGURATION)
            for i in range(20):
                if len(self._promptbuf) == self.CONFIGURATION_RESPONSE_LENGTH:
                    if self._check_configuration(self._promptbuf):                    
                        self._param_dict.update(self._promptbuf)
                        # Get new param dict config. If it differs from the old config,
                        # tell driver superclass to publish a config change event.
                        new_config = self._param_dict.get_config()
                        if new_config != old_config:
                            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                        return
                    break
                time.sleep(.1)
            log.debug('_update_params: response not right length %d, %s' % (len(self._promptbuf), self._promptbuf.encode("hex")))

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
            
            continue
        

    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish to agent.
        @param line string to match for sample.
        @param publsih boolean to publish sample (default True).
        @retval Sample dictionary if present or None.
        """
        return  # TODO remove this when sample format is known
        
    def  _get_mode(self, timeout, delay=1):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        self._promptbuf = ''
        
        # Grab time for timeout.
        starttime = time.time()
        
        while True:
            log.debug('Sending what_mode command to get a response from the instrument.')
            # Send what_mode command to attempt to get a response.
            self._connection.send(InstrumentCmds.CMD_WHAT_MODE)
            time.sleep(delay)
            
            for item in self._prompts.list():
                if item in self._promptbuf:
                    if item != InstrumentPrompts.Z_NACK:
                        log.debug('get_mode got prompt: %s' % repr(item))
                        return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _create_set_output(self, parameters):
        output = '\xa5\x00\x00\x01'
        for name in self.UserParameters:
            output += parameters.format_parameter(name)
        
        checksum = self.CHECK_SUM_SEED
        for word_index in range(0, len(output), 2):
            word_value = self._convert_word_to_int(output[word_index:word_index+2])
            checksum = (checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        log.debug('_create_set_output: user checksum = %s' % checksum)

        output += self._word_to_string(checksum)
        self._dump_user_config(output)                      
        
        return output
