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
    # hardware configuration
    HW_SERIAL_NUMBER = "HwSerialNumber"
    HW_CONFIG = "HwConfig"
    HW_FREQUENCY = "HwFrequency"
    PIC_VERSION = "PicCodeVerNumber"
    HW_REVISION = "HwRevision"
    REC_SIZE = "RecorderSize"
    STATUS = "Status"
    HW_SPARE = 'HwSpare'
    FW_VERSION = "FirmwareVersion"
    
    # head configuration
    HEAD_CONFIG = "HeadConfig"
    HEAD_FREQUENCY = "HeadFrequency"
    HEAD_TYPE = "HeadType"
    HEAD_SERIAL_NUMBER = "HeadSerialNumber"
    HEAD_SYSTEM = 'HeadSystemData'
    HEAD_SPARE = 'HeadSpare'
    HEAD_NUMBER_BEAMS = "HeadNumberOfBeams"
    
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
    A1_1 = 'A1_1'
    B0_1 = 'B0_1'
    B1_1 = 'B1_1'
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
    USER_SPARE1 = 'UserSpare1'
    VELOCITY_ADJ_TABLE = 'VelocityAdjTable'
    COMMENTS = 'Comments'
    WAVE_MEASUREMENT_MODE = 'WaveMeasurementMode'
    DYN_PERCENTAGE_POSITION = 'PercentageForCellPositioning'
    WAVE_TRANSMIT_PULSE = 'WaveTransmitPulse'
    WAVE_BLANKING_DISTANCE = 'WaveBlankingDistance'
    WAVE_CELL_SIZE = 'WaveCellSize'
    NUMBER_DIAG_SAMPLES = 'NumberDiagnosticSamples'
    A1_2 = 'A1_2'
    B0_2 = 'B0_2'
    B1_2 = 'B1_2'
    USER_SPARE2 = 'UserSpare2'
    ANALOG_OUTPUT_SCALE = 'AnalogOutputScale'
    COORELATION_THRESHOLD = 'CoorelationThreshold'
    USER_SPARE3 = 'UserSpare3'
    TRANSMIT_PULSE_LENGTH = 'TransmitPulseWidth'
    USER_SPARE4 = 'UserSpare4'
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
        log.debug('BinaryParameterDictVal.update(): match=<%s>', match.group(1).encode('hex'))
        if match:
            self.value = self.f_getval(match)
            log.debug('BinaryParameterDictVal.update(): updated parameter %s=<%s>', self.name, str(self.value))
            return True
        else:
            log.debug('BinaryParameterDictVal.update(): failed to update parameter %s', self.name)
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
            if not val.update(input):
                log.debug("BinaryProtocolParameterDict.update(): update of %s failed" %name) 
                return False
        return True
    


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
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
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
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

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
    # Private helpers.
    ########################################################################
    
    def _convert_word_to_int(self, word):
        return ord(word[0]) + (0x10 * ord(word[1]))
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        
        HEAD_OFFSET = 48
        USER_OFFSET = HEAD_OFFSET + 224
        
        # The parameter dictionary.
        self._param_dict = BinaryProtocolParameterDict()

        # Add parameter handlers to parameter dict.
        
        # hardware config
        self._param_dict.add(Parameter.HW_SERIAL_NUMBER,
                             r'^.{4}(.{14}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.HW_CONFIG,
                             r'^.{18}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HW_FREQUENCY,
                             r'^.{20}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.PIC_VERSION,
                             r'^.{22}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HW_REVISION,
                             r'^.{24}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.REC_SIZE,
                             r'^.{26}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.STATUS,
                             r'^.{28}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HW_SPARE,
                             r'^.{30}(.{12}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.FW_VERSION,
                             r'^.{42}(.{4}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        
        # head config
        self._param_dict.add(Parameter.HEAD_CONFIG,
                             r'^.{HEAD_OFFSET+4}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HEAD_FREQUENCY,
                             r'^.{HEAD_OFFSET+6}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HEAD_TYPE,
                             r'^.{HEAD_OFFSET+8}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.HEAD_SERIAL_NUMBER,
                             r'^.{HEAD_OFFSET+10}(.{12}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.HEAD_SYSTEM,
                             r'^.{HEAD_OFFSET+22}(.{176}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.HEAD_SPARE,
                             r'^.{HEAD_OFFSET+198}(.{22 }).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.HEAD_NUMBER_BEAMS,
                             r'^.{HEAD_OFFSET+220}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        
        # user config
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                             r'^.{USER_OFFSET+4}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                             r'^.{USER_OFFSET+6}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                             r'^.{USER_OFFSET+8}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                             r'^.{USER_OFFSET+10}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                             r'^.{USER_OFFSET+12}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMMBER_PINGS,
                             r'^.{USER_OFFSET+14}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                             r'^.{USER_OFFSET+16}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                             r'^.{USER_OFFSET+18}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                             r'^.{USER_OFFSET+20}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                             r'^.{USER_OFFSET+22}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                             r'^.{USER_OFFSET+30}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                             r'^.{USER_OFFSET+32}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMBER_BINS,
                             r'^.{USER_OFFSET+34}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.BIN_LENGTH,
                             r'^.{USER_OFFSET+36}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                             r'^.{USER_OFFSET+38}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                             r'^.{USER_OFFSET+40}(.{6}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WRAP_MODE,
                             r'^.{USER_OFFSET+46}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                             r'^.{USER_OFFSET+48}(.{6}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                             r'^.{USER_OFFSET+54}(.{4}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.MODE,
                             r'^.{USER_OFFSET+58}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                             r'^.{USER_OFFSET+60}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                             r'^.{USER_OFFSET+62}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                             r'^.{USER_OFFSET+64}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                             r'^.{USER_OFFSET+66}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.MODE_TEST,
                             r'^.{USER_OFFSET+68}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                             r'^.{USER_OFFSET+70}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.SW_VERSION,
                             r'^.{USER_OFFSET+72}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                             r'^.{USER_OFFSET+76}(.{180}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.COMMENTS,
                             r'^.{USER_OFFSET+256}(.{180}).*',
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                             r'^.{USER_OFFSET+436}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                             r'^.{USER_OFFSET+438}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                             r'^.{USER_OFFSET+440}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                             r'^.{USER_OFFSET+442}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                             r'^.{USER_OFFSET+444}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                             r'^.{USER_OFFSET+446}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                             r'^.{USER_OFFSET+456}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.COORELATION_THRESHOLD,
                             r'^.{USER_OFFSET+458}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                             r'^.{USER_OFFSET+462}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                             r'^.{USER_OFFSET+494}(.{2}).*',
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._int_to_string)

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
            self._connection.send(InstrumentCmds.GET_ALL_CONFIGURATIONS)
            for i in range(20):
                if len(self._promptbuf) == CONFIGURATION_RESPONSE_LENGTH:
                    self._param_dict.update(self._promptbuf)
                    # Get new param dict config. If it differs from the old config,
                    # tell driver superclass to publish a config change event.
                    new_config = self._param_dict.get_config()
                    if new_config != old_config:
                        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                    return
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

