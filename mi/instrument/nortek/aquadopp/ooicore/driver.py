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
import base64

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

# set up configuration length and sync constants   
USER_CONFIG_LEN = 512
HW_CONFIG_LEN = 48
HEAD_CONFIG_LEN = 224
USER_SYNC_BYTES = '\xa5\x00\x00\x01'
HW_SYNC_BYTES   = '\xa5\x05\x18\x00'
HEAD_SYNC_BYTES = '\xa5\x04\x70\x00'

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
    CONFIGURE_INSTRUMENT               = 'CC'        # sets the user configuration
    SOFT_BREAK_FIRST_HALF              = '@@@@@@'
    SOFT_BREAK_SECOND_HALF             = 'K1W%!Q'
    READ_REAL_TIME_CLOCK               = 'RC'        
    SET_REAL_TIME_CLOCK                = 'SC'
    CMD_WHAT_MODE                      = 'II'        # to determine the mode of the instrument
    READ_USER_CONFIGURATION            = 'GC'
    READ_HW_CONFIGURATION              = 'GP'
    READ_HEAD_CONFIGURATION            = 'GH'
    POWER_DOWN                         = 'PD'     
    READ_BATTERY_VOLTAGE               = 'BV'
    READ_ID                            = 'ID'
    START_MEASUREMENT_AT_SPECIFIC_TIME = 'SD'
    START_MEASUREMENT_WITH_RECORDER    = 'SR'
    CONFIRMATION                       = 'MC'        # confirm a break request
    # SAMPLE_AVG_TIME                    = 'A'
    # SAMPLE_INTERVAL_TIME               = 'M'
    # GET_ALL_CONFIGURATIONS             = 'GA'
    # GET_USER_CONFIGURATION             = 'GC'
    # SAMPLE_WHAT_MODE                   = 'I'   
    
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
    
class ExportedInstrumentCommand(BaseEnum):
    READ_CLOCK = "EXPORTED_INSTRUMENT_CMD_READ_CLOCK"
    READ_MODE = "EXPORTED_INSTRUMENT_CMD_READ_MODE"
    POWER_DOWN = "EXPORTED_INSTRUMENT_CMD_POWER_DOWN"
    READ_BATTERY_VOLTAGE = "EXPORTED_INSTRUMENT_CMD_READ_BATTERY_VOLTAGE"
    READ_ID = "EXPORTED_INSTRUMENT_CMD_READ_ID"
    GET_HW_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HW_CONFIGURATION"
    GET_HEAD_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HEAD_CONFIGURATION"
    START_MEASUREMENT_AT_SPECIFIC_TIME = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_AT_SPECIFIC_TIME"
    START_MEASUREMENT_IMMEDIATELY = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_IMMEDIATELY"

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    # common events from base class
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
    
    # instrument specific events
    READ_CLOCK = ExportedInstrumentCommand.READ_CLOCK
    READ_MODE = ExportedInstrumentCommand.READ_MODE
    POWER_DOWN = ExportedInstrumentCommand.POWER_DOWN
    READ_BATTERY_VOLTAGE = ExportedInstrumentCommand.READ_BATTERY_VOLTAGE
    READ_ID = ExportedInstrumentCommand.READ_ID
    GET_HW_CONFIGURATION = ExportedInstrumentCommand.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ExportedInstrumentCommand.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ExportedInstrumentCommand.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATELY = ExportedInstrumentCommand.START_MEASUREMENT_IMMEDIATELY

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT
    EXECUTE_DIRECT = ProtocolEvent.EXECUTE_DIRECT
    READ_CLOCK = ProtocolEvent.READ_CLOCK
    READ_MODE = ProtocolEvent.READ_MODE
    POWER_DOWN = ProtocolEvent.POWER_DOWN
    READ_BATTERY_VOLTAGE = ProtocolEvent.READ_BATTERY_VOLTAGE
    READ_ID = ProtocolEvent.READ_ID
    GET_HW_CONFIGURATION = ProtocolEvent.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ProtocolEvent.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATELY = ProtocolEvent.START_MEASUREMENT_IMMEDIATELY

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
    REAL_TIME_CLOCK = "RealTimeClock"
    BATTERY_VOLTAGE = "BatteryVoltage"
    IDENTIFICATION_STRING = "IdentificationString"
    
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
    CLOCK_DEPLOY = "ClockDeploy"      # deployment start time
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
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_CLOCK, self._handler_command_read_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_MODE, self._handler_command_read_mode)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.POWER_DOWN, self._handler_command_power_down)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_BATTERY_VOLTAGE, self._handler_command_read_battery_voltage)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_ID, self._handler_command_read_id)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HW_CONFIGURATION, self._handler_command_get_hw_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HEAD_CONFIGURATION, self._handler_command_get_head_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME, self._handler_command_start_measurement_specific_time)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_IMMEDIATELY, self._handler_command_start_measurement_immediate)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._add_response_handler(InstrumentCmds.READ_REAL_TIME_CLOCK, self._parse_read_clock_response)
        self._add_response_handler(InstrumentCmds.CMD_WHAT_MODE, self._parse_what_mode_response)
        self._add_response_handler(InstrumentCmds.READ_BATTERY_VOLTAGE, self._parse_read_battery_voltage_response)
        self._add_response_handler(InstrumentCmds.READ_ID, self._parse_read_id)
        self._add_response_handler(InstrumentCmds.READ_HW_CONFIGURATION, self._parse_read_hw_config)
        self._add_response_handler(InstrumentCmds.READ_HEAD_CONFIGURATION, self._parse_read_head_config)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add response handlers for device commands.

        # Add sample handlers.

    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    ########################################################################
    # overridden superclass methods
    ########################################################################

    def got_data(self, paPacket):
        """
        Callback for receiving new data from the device.
        The port agent object fires this when data is received
        @param paPacket The packet of data that was received
        """
        paLength = paPacket.get_data_size()
        paData = paPacket.get_data()

        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
            # direct access mode
            if paLength > 0:
                log.debug("mavs4InstrumentProtocol._got_data(): <" + paData + ">") 
                if self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, paData)
                    # TODO: what about logging this as an event?
            return
        
        if paLength > 0:
            # Call the superclass to update line and prompt buffers.
            CommandResponseInstrumentProtocol.got_data(self, paData)
    
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
        log.debug('_do_cmd_resp: %s, timeout=%s, expected_prompt=%s (%s),' 
                  % (repr(cmd), timeout, expected_prompt, expected_prompt.encode("hex")))
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

        log.debug('_handler_unknown_discover: state=%s', next_state)
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

    def _handler_command_read_clock(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_REAL_TIME_CLOCK, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_read_mode(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.CMD_WHAT_MODE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_power_down(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.POWER_DOWN, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_read_battery_voltage(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_BATTERY_VOLTAGE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_read_id(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_ID, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_get_hw_config(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HW_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_get_head_config(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HEAD_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_start_measurement_specific_time(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HEAD_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, result)

    def _handler_command_start_measurement_immediate(self):
        """
        """
        next_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HEAD_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

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
        self._param_dict.add(Parameter.REAL_TIME_CLOCK,
                             r'(.{6})',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_WRITE)
               
        self._param_dict.add(Parameter.BATTERY_VOLTAGE,
                             r'(.{2})',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
               
        self._param_dict.add(Parameter.IDENTIFICATION_STRING,
                             r'(.{14})',
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
               
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
                             r'^.{%s}(.{2}).*' % str(4),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(6),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(8),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                             r'^.{%s}(.{2}).*' % str(10),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                             r'^.{%s}(.{2}).*' % str(12),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.NUMMBER_PINGS,
                             r'^.{%s}(.{2}).*' % str(14),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(16),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                             r'^.{%s}(.{2}).*' % str(18),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(20),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(22),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.A1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(24),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.B0_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(26),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.B1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(28),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                             r'^.{%s}(.{2}).*' % str(30),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                             r'^.{%s}(.{2}).*' % str(32),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.NUMBER_BINS,
                             r'^.{%s}(.{2}).*' % str(34),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BIN_LENGTH,
                             r'^.{%s}(.{2}).*' % str(36),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(38),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                             r'^.{%s}(.{6}).*' % str(40),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WRAP_MODE,
                             r'^.{%s}(.{2}).*' % str(46),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                             r'^.{%s}(.{6}).*' % str(48),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                             r'^.{%s}(.{4}).*' % str(54),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MODE,
                             r'^.{%s}(.{2}).*' % str(58),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                             r'^.{%s}(.{2}).*' % str(60),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(62),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(64),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(66),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MODE_TEST,
                             r'^.{%s}(.{2}).*' % str(68),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                             r'^.{%s}(.{2}).*' % str(70),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SW_VERSION,
                             r'^.{%s}(.{2}).*' % str(72),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.USER_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(74),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                             r'^.{%s}(.{180}).*' % str(76),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.COMMENTS,
                             r'^.{%s}(.{180}).*' % str(256),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                             r'^.{%s}(.{2}).*' % str(436),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                             r'^.{%s}(.{2}).*' % str(438),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                             r'^.{%s}(.{2}).*' % str(440),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(442),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                             r'^.{%s}(.{2}).*' % str(444),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                             r'^.{%s}(.{2}).*' % str(446),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.A1_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(448),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.B0_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(450),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.B1_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(452),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.USER_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(454),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                             r'^.{%s}(.{2}).*' % str(456),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.COORELATION_THRESHOLD,
                             r'^.{%s}(.{2}).*' % str(458),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.USER_3_SPARE,
                             r'^.{%s}(.{2}).*' % str(460),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                             r'^.{%s}(.{2}).*' % str(462),
                             lambda match : self._convert_word_to_int(match.group(1)),
                             self._word_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.USER_4_SPARE,
                             r'^.{%s}(.{30}).*' % str(464),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                             r'^.{%s}(.{16}).*' % str(494),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        
    def _dump_config(self, input):
        # dump config block
        dump = ''
        for byte_index in range(0, len(input)):
            if byte_index % 0x10 == 0:
                if byte_index != 0:
                    dump += '\n'   # no linefeed on first line
                dump += '{:03x}  '.format(byte_index)
            dump += '{:02x} '.format(ord(input[byte_index]))
        #log.debug("dump = %s", dump)
        return dump
    
    def _check_configuration(self, input, sync, length):        
        log.debug('_check_configuration: config=')
        print self._dump_config(input[0:length-2])
        if len(input) != length+2:
            log.debug('_check_configuration: wrong length, expected length %d != %d' %(length+2, len(input)))
            return False
        
        # check for ACK bytes
        if input[length:length+2] != InstrumentPrompts.Z_ACK:
            log.debug('_check_configuration: ACK bytes in error %s != %s' 
                      %(input[length:length+2].encode('hex'), InstrumentPrompts.Z_ACK.encode('hex')))
            return False
        
        # check the sync bytes 
        if input[0:4] != sync:
            log.debug('_check_configuration: sync bytes in error %s != %s' 
                      %(input[0:4], sync))
            return False
        
        # check user checksum
        calculated_checksum = self.CHECK_SUM_SEED
        for word_index in range(0, length-2, 2):
            word_value = self._convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        log.debug('_check_configuration: user c_c = %s' % calculated_checksum)
        sent_checksum = self._convert_word_to_int(input[length-2:length])
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
        
        # get the RTC from the instrument
        starttime = time.time()
        timeout = 2

        """
        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''

            TO DO: rewrite this to read the clock
            log.debug('Sending get_user_configuration command to the instrument.')
            # Send get_user_cofig command to attempt to get user configuration.
            self._connection.send(InstrumentCmds.GET_USER_CONFIGURATION)
            for i in range(20):   # loop for 2 seconds waiting for response to complete
                if len(self._promptbuf) == self.CONFIGURATION_RESPONSE_LENGTH:
                    if self._check_configuration(self._promptbuf):                    
                        self._param_dict.update(self._promptbuf)
                        # Get new param dict config. If it differs from the old config,
                        # tell driver superclass to publish a config change event.
                        return
                    break
                time.sleep(.1)
            log.debug('_update_params: get_user_configuration command response not right length %d, %s' % (len(self._promptbuf), self._promptbuf.encode("hex")))

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
            
            continue
            """
        
        # get the battery voltage from the instrument
        
        # get the identification string from the instrument
        
        # get user_configuration params from the instrument
        # Grab time for timeout.
        starttime = time.time()
        timeout = 6

        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''

            log.debug('Sending get_user_configuration command to the instrument.')
            # Send get_user_cofig command to attempt to get user configuration.
            self._connection.send(InstrumentCmds.READ_USER_CONFIGURATION)
            for i in range(20):   # loop for 2 seconds waiting for response to complete
                if len(self._promptbuf) == USER_CONFIG_LEN+2:
                    if self._check_configuration(self._promptbuf, USER_SYNC_BYTES, USER_CONFIG_LEN):                    
                        self._param_dict.update(self._promptbuf)
                        # Get new param dict config. If it differs from the old config,
                        # tell driver superclass to publish a config change event.
                        return
                    break
                time.sleep(.1)
            log.debug('_update_params: get_user_configuration command response not right length %d, %s' % (len(self._promptbuf), self._promptbuf.encode("hex")))

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
            
            continue
        
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

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
        # load buffer with sync byte (A5), ID byte (0), and size word (# of words in little-endian form)
        # 'user' configuration is 512 bytes, 256 words long, so size is 0x100
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
    
    def _parse_read_clock_response(self, response, prompt):
        """ Parse the response from the instrument for a read clock command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        # packed BCD format, so convert binary to hex to get value
        # should be the 6 byte response ending with two ACKs
        if (len(response) != 8):
            log.warn("_parse_read_clock_response: Bad read clock response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read clock response. (%s)", response.encode('hex'))
        log.debug("_parse_read_clock_response: response=%s", response.encode('hex')) 
        time = str(response[2].encode('hex'))  # get day
        time += '/' + str(response[5].encode('hex'))  # get month   
        time += '/20' + str(response[4].encode('hex'))  # get year   
        time += ' ' + str(response[3].encode('hex'))  # get hours   
        time += ':' + str(response[0].encode('hex'))  # get minutes   
        time += ':' + str(response[1].encode('hex'))  # get seconds   
        return time

    def _parse_what_mode_response(self, response, prompt):
        """ Parse the response from the instrument for a 'what mode' command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 4):
            log.warn("_parse_what_mode_response: Bad what mode response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid what mode response. (%s)", response.encode('hex'))
        log.debug("_parse_what_mode_response: response=%s", response.encode('hex')) 
        return self._convert_word_to_int(response[0:2])
        

    def _parse_read_battery_voltage_response(self, response, prompt):
        """ Parse the response from the instrument for a read battery voltage command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 4):
            log.warn("_parse_read_battery_voltage_response: Bad read battery voltage response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read battery voltage response. (%s)", response.encode('hex'))
        log.debug("_parse_read_battery_voltage_response: response=%s", response.encode('hex')) 
        return self._convert_word_to_int(response[0:2])
        
    def _parse_read_id(self, response, prompt):
        """ Parse the response from the instrument for a read ID command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 16):
            log.warn("_handler_command_read_id: Bad read ID response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read ID response. (%s)", response.encode('hex'))
        log.debug("_handler_command_read_id: response=%s", response.encode('hex')) 
        return response[0:14]
        
    def _parse_read_hw_config(self, response, prompt):
        """ Parse the response from the instrument for a read hw config command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not self._check_configuration(self._promptbuf, HW_SYNC_BYTES, HW_CONFIG_LEN):                    
            log.warn("_parse_read_hw_config: Bad read hw response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read hw response. (%s)", response.encode('hex'))
        log.debug("_parse_read_hw_config: response=%s", response.encode('hex'))
        parsed = {} 
        parsed['SerialNo'] = response[4:18]  
        parsed['Config'] = self._convert_word_to_int(response[18:20])  
        parsed['Frequency'] = self._convert_word_to_int(response[20:22])  
        parsed['PICversion'] = self._convert_word_to_int(response[22:24])  
        parsed['HWrevision'] = self._convert_word_to_int(response[24:26])  
        parsed['RecSize'] = self._convert_word_to_int(response[26:28])  
        parsed['Status'] = self._convert_word_to_int(response[28:30])  
        parsed['FWversion'] = response[42:46] 
        return parsed
        
    def _parse_read_head_config(self, response, prompt):
        """ Parse the response from the instrument for a read head command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not self._check_configuration(self._promptbuf, HEAD_SYNC_BYTES, HEAD_CONFIG_LEN):                    
            log.warn("_parse_read_head_config: Bad read head response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read head response. (%s)", response.encode('hex'))
        log.debug("_parse_read_head_config: response=%s", response.encode('hex')) 
        parsed = {} 
        parsed['Config'] = self._convert_word_to_int(response[4:6])  
        parsed['Frequency'] = self._convert_word_to_int(response[6:8])  
        parsed['Type'] = self._convert_word_to_int(response[8:10])  
        parsed['SerialNo'] = response[10:22]  
        #parsed['System'] = self._dump_config(response[22:198])
        parsed['System'] = base64.b64encode(response[22:198])
        parsed['NBeams'] = self._convert_word_to_int(response[220:222])  
        return parsed
                    