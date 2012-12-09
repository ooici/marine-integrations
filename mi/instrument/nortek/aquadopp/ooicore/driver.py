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
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               InstrumentStateException, \
                               SampleException, \
                               ReadOnlyException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType


from mi.core.common import InstErrorCode

from mi.core.log import get_logger ; log = get_logger()


# newline.
NEWLINE = '\n\r'

# default timeout.
TIMEOUT = 10

# set up the 'structure' lengths (in bytes) and sync/id/size constants   
USER_CONFIG_LEN = 512
USER_CONFIG_SYNC_BYTES = '\xa5\x00\x00\x01'
HW_CONFIG_LEN = 48
HW_CONFIG_SYNC_BYTES   = '\xa5\x05\x18\x00'
HEAD_CONFIG_LEN = 224
HEAD_CONFIG_SYNC_BYTES = '\xa5\x04\x70\x00'
VELOCITY_DATA_LEN = 42
VELOCITY_DATA_SYNC_BYTES = '\xa5\x01\x15\x00'
DIAGNOSTIC_DATA_HEADER_LEN = 36
DIAGNOSTIC_DATA_HEADER_SYNC_BYTES = '\xa5\x06\x12\x00'
DIAGNOSTIC_DATA_LEN = 42
DIAGNOSTIC_DATA_SYNC_BYTES = '\xa5\x80\x15\x00'
CHECK_SUM_SEED = 0xb58c

sample_structures = [[VELOCITY_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                     [DIAGNOSTIC_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                     [DIAGNOSTIC_DATA_HEADER_SYNC_BYTES, DIAGNOSTIC_DATA_HEADER_LEN]]

VELOCITY_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)
DIAGNOSTIC_DATA_HEADER_PATTERN = r'^%s(.{2})(.{2})(.{1})(.{1})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{8})' % DIAGNOSTIC_DATA_HEADER_SYNC_BYTES
DIAGNOSTIC_DATA_HEADER_REGEX = re.compile(DIAGNOSTIC_DATA_HEADER_PATTERN, re.DOTALL)
DIAGNOSTIC_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % DIAGNOSTIC_DATA_SYNC_BYTES
DIAGNOSTIC_DATA_REGEX = re.compile(DIAGNOSTIC_DATA_PATTERN, re.DOTALL)

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'parsed'
    DIAGNOSTIC_DATA = 'data'
    DIAGNOSTIC_HEADER = 'header'

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
    START_MEASUREMENT_IMMEDIATE        = 'SR'
    START_MEASUREMENT_WITHOUT_RECORDER = 'ST'
    ACQUIRE_DATA                       = 'AD'
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
    SET_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_SET_CONFIGURATION"
    READ_CLOCK = "EXPORTED_INSTRUMENT_CMD_READ_CLOCK"
    READ_MODE = "EXPORTED_INSTRUMENT_CMD_READ_MODE"
    POWER_DOWN = "EXPORTED_INSTRUMENT_CMD_POWER_DOWN"
    READ_BATTERY_VOLTAGE = "EXPORTED_INSTRUMENT_CMD_READ_BATTERY_VOLTAGE"
    READ_ID = "EXPORTED_INSTRUMENT_CMD_READ_ID"
    GET_HW_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HW_CONFIGURATION"
    GET_HEAD_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HEAD_CONFIGURATION"
    START_MEASUREMENT_AT_SPECIFIC_TIME = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_AT_SPECIFIC_TIME"
    START_MEASUREMENT_IMMEDIATE = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_IMMEDIATE"

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
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    
    # instrument specific events
    SET_CONFIGURATION = ExportedInstrumentCommand.SET_CONFIGURATION
    READ_CLOCK = ExportedInstrumentCommand.READ_CLOCK
    READ_MODE = ExportedInstrumentCommand.READ_MODE
    POWER_DOWN = ExportedInstrumentCommand.POWER_DOWN
    READ_BATTERY_VOLTAGE = ExportedInstrumentCommand.READ_BATTERY_VOLTAGE
    READ_ID = ExportedInstrumentCommand.READ_ID
    GET_HW_CONFIGURATION = ExportedInstrumentCommand.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ExportedInstrumentCommand.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ExportedInstrumentCommand.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATE = ExportedInstrumentCommand.START_MEASUREMENT_IMMEDIATE

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    SET_CONFIGURATION = ProtocolEvent.SET_CONFIGURATION
    READ_CLOCK = ProtocolEvent.READ_CLOCK
    READ_MODE = ProtocolEvent.READ_MODE
    POWER_DOWN = ProtocolEvent.POWER_DOWN
    READ_BATTERY_VOLTAGE = ProtocolEvent.READ_BATTERY_VOLTAGE
    READ_ID = ProtocolEvent.READ_ID
    GET_HW_CONFIGURATION = ProtocolEvent.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ProtocolEvent.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATE = ProtocolEvent.START_MEASUREMENT_IMMEDIATE

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

    REAL_TIME_CLOCK = "RealTimeClock"
    BATTERY_VOLTAGE = "BatteryVoltage"
    IDENTIFICATION_STRING = "IdentificationString"
    """
    
    # user configuration
    TRANSMIT_PULSE_LENGTH = "TransmitPulseLength"                # T1
    BLANKING_DISTANCE = "BlankingDistance"                       # T2
    RECEIVE_LENGTH = "ReceiveLength"                             # T3
    TIME_BETWEEN_PINGS = "TimeBetweenPings"                      # T4
    TIME_BETWEEN_BURST_SEQUENCES = "TimeBetweenBurstSequences"   # T5 
    NUMBER_PINGS = "NumberPings"     # number of beam sequences per burst
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
    CORRELATION_THRESHOLD = 'CorrelationThreshold'
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
                 submenu_write=None,                 
                 multi_match=False,
                 direct_access=False,
                 startup_param=False,
                 default_value=None,
                 init_value=None):
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
        self.multi_match = multi_match
        self.direct_access = direct_access
        self.startup_param = startup_param
        self.default_value = default_value
        self.init_value = init_value

    def update(self, input, **kwargs):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        init_value = kwargs.get('init_value', False)
        match = self.regex.match(input)
        if match:
            log.debug('BinaryParameterDictVal.update(): match=<%s>, init_value=%s', match.group(1).encode('hex'), init_value)
            value = self.f_getval(match)
            if init_value:
                self.init_value = value
            else:
                self.value = value
            if isinstance(value, int):
                log.debug('BinaryParameterDictVal.update(): updated parameter %s=<%d>', self.name, value)
            else:
                log.debug('BinaryParameterDictVal.update(): updated parameter %s=\"%s\" <%s>', self.name, 
                          value, str(self.value).encode('hex'))
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
            menu_path_write=None, submenu_write=None,
            multi_match=False, direct_access=False, startup_param=False,
            default_value=None, init_value=None):
        """
        Add a parameter object to the dictionary.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The function that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param direct_access T/F for tagging this as a direct access parameter
        to be saved and restored in and out of direct access
        @param startup_param T/F for tagging this as a startup parameter to be
        applied when the instrument is first configured
        @param default_value The default value to use for this parameter when
        a value is needed, but no other instructions have been provided.
        @param init_value The value that a parameter should be set to during
        initialization or re-initialization
        @param value The parameter value (initializes to None).        
        """
        val = BinaryParameterDictVal(name, pattern, f_getval, f_format,
                                     value=value,
                                     visibility=visibility,
                                     menu_path_read=menu_path_read,
                                     submenu_read=submenu_read,
                                     menu_path_write=menu_path_write,
                                     submenu_write=submenu_write,
                                     multi_match=multi_match,
                                     direct_access=direct_access,
                                     startup_param=startup_param,
                                     default_value=default_value,
                                     init_value=init_value)
        self._param_dict[name] = val
        
    def update(self, input, **kwargs):
        """
        Update the dictionary with an input. Iterate through all objects
        and attempt to match and update all parameter.s
        @param input A string to match to a dictionary object.
        @retval A boolean to indicate that update was successfully, false if update failed
        """
        log.debug('BinaryProtocolParameterDict.update(): input=%s' %input.encode('hex'))
        for (name, val) in self._param_dict.iteritems():
            #log.debug('BinaryProtocolParameterDict.update(): name=%s' %name)
            if not val.update(input, **kwargs):
                return False
        return True
    
    def get_config(self):
        """
        Retrieve the configuration (all key values not ending in 'Spare').
        """
        config = {}
        for (key, val) in self._param_dict.iteritems():
            if not key.endswith('Spare'):
                config[key] = val.value
        return config
    
    def set_from_value(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        log.debug("BinaryProtocolParameterDict.set_from_value(): name=%s, value=%s" %(name, value))
        
        if not name in self._param_dict:
            raise InstrumentParameterException('Unable to set parameter %s to %s: parameter %s not an dictionary' %(name, value, name))
            
        if ((self._param_dict[name].f_format == BinaryProtocolParameterDict.word_to_string) or
            (self._param_dict[name].f_format == BinaryProtocolParameterDict.double_word_to_string)):
            if not isinstance(value, int):
                raise InstrumentParameterException('Unable to set parameter %s to %s: value not an integer' %(name, value))
        else:
            if not isinstance(value, str):
                raise InstrumentParameterException('Unable to set parameter %s to %s: value not a string' %(name, value))
        
        if self._param_dict[name].visibility == ParameterDictVisibility.READ_ONLY:
            raise ReadOnlyException('Unable to set parameter %s to %s: parameter %s is read only' %(name, value, name))
                
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

    def get_keys(self):
        """
        Return list of device parameters available.  These are a subset of all the parameters
        """
        list = []
        for param in self._param_dict.keys():
            if not param.endswith('Spare'):
                list.append(param) 
        log.debug('get_keys: list=%s' %list)
        return list
    
    def set_params_to_read_write(self):
        for (name, val) in self._param_dict.iteritems():
            val.visibility = ParameterDictVisibility.READ_WRITE

    @staticmethod
    def word_to_string(value):
        low_byte = value & 0xff
        high_byte = (value & 0xff00) >> 8
        return chr(low_byte) + chr(high_byte)
        
    @staticmethod
    def convert_word_to_int(word):
        low_byte = ord(word[0])
        high_byte = 0x100 * ord(word[1])
        #log.debug('w=%s, l=%d, h=%d, v=%d' %(word.encode('hex'), low_byte, high_byte, low_byte + high_byte))
        return low_byte + high_byte
    
    @staticmethod
    def double_word_to_string(value):
        result = BinaryProtocolParameterDict.word_to_string(value & 0xffff)
        result += BinaryProtocolParameterDict.word_to_string((value & 0xffff0000) >> 16)
        return result
        
    @staticmethod
    def convert_double_word_to_int(dword):
        low_word = BinaryProtocolParameterDict.convert_word_to_int(dword[0:2])
        high_word = BinaryProtocolParameterDict.convert_word_to_int(dword[2:4])
        #log.debug('dw=%s, lw=%d, hw=%d, v=%d' %(dword.encode('hex'), low_word, high_word, low_word + (0x10000 * high_word)))
        return low_word + (0x10000 * high_word)
    
    @staticmethod
    def calculate_checksum(input, length):
        #log.debug("calculate_checksum: input=%s, length=%d", input.encode('hex'), length)
        calculated_checksum = CHECK_SUM_SEED
        for word_index in range(0, length-2, 2):
            word_value = BinaryProtocolParameterDict.convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        return calculated_checksum

    @staticmethod
    def convert_time(response):
        time = str(response[2].encode('hex'))  # get day
        time += '/' + str(response[5].encode('hex'))  # get month   
        time += '/20' + str(response[4].encode('hex'))  # get year   
        time += ' ' + str(response[3].encode('hex'))  # get hours   
        time += ':' + str(response[0].encode('hex'))  # get minutes   
        time += ':' + str(response[1].encode('hex'))  # get seconds   
        return time
    
            

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
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)

    def apply_startup_params(self):
        """
        Over-ridden to add the 'NotUserRequested' keyed parameter to allow writing to read-only params
        Apply the startup values previously stored in the protocol to
        the running config of the live instrument. The startup values are the
        values that are (1) marked as startup parameters and are (2) the "best"
        value to use at startup. Preference is given to the previously-set init
        value, then the default value, then the currently used value.
        
        This default method assumes a dict of parameter name and value for
        the configuration.
        @raise InstrumentParameterException If the config cannot be applied
        """
        config = self._protocol.get_startup_config()
        
        if not isinstance(config, dict):
            raise InstrumentParameterException("Incompatible initialization parameters")
        
        self.set_resource(config, NotUserRequested=True)
        
    def restore_direct_access_params(self, config):
        """
        Over-ridden to add the 'NotUserRequested' keyed parameter to allow writing to read-only params
        Restore the correct values out of the full config that is given when
        returning from direct access. By default, this takes a simple dict of
        param name and value. Override this class as needed as it makes some
        simple assumptions about how your instrument sets things.
        
        @param config The configuration that was previously saved (presumably
        to disk somewhere by the driver that is working with this protocol)
        """
        vals = {}
        # for each parameter that is read only, restore
        da_params = self._protocol.get_direct_access_params()        
        for param in da_params:
            vals[param] = config[param]
            
        self.set_resource(vals, NotUserRequested=True)

###############################################################################
# Data particles
###############################################################################

class AquadoppDwDiagnosticHeaderDataParticleKey(BaseEnum):
    RECORDS = "records"
    CELL = "cell"
    NOISE1 = "noise1"
    NOISE2 = "noise2"
    NOISE3 = "noise3"
    NOISE4 = "noise4"
    PROCESSING_MAGNITUDE_BEAM1 = "processing_magnitude_beam1"
    PROCESSING_MAGNITUDE_BEAM2 = "processing_magnitude_beam2"
    PROCESSING_MAGNITUDE_BEAM3 = "processing_magnitude_beam3"
    PROCESSING_MAGNITUDE_BEAM4 = "processing_magnitude_beam4"
    DISTANCE1 = "distance1"
    DISTANCE2 = "distance2"
    DISTANCE3 = "distance3"
    DISTANCE4 = "distance4"
    
            
class AquadoppDwDiagnosticHeaderDataParticle(DataParticle):
    """
    Routine for parsing diagnostic data header into a data particle structure for the Aquadopp DW sensor. 
    """
    _data_particle_type = DataParticleType.DIAGNOSTIC_HEADER

    def _build_parsed_values(self):
        """
        Take something in the diagnostic data header sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = DIAGNOSTIC_DATA_HEADER_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("AquadoppDwDiagnosticHeaderDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        records = BinaryProtocolParameterDict.convert_word_to_int(match.group(1))
        cell = BinaryProtocolParameterDict.convert_word_to_int(match.group(2))
        noise1 = ord(match.group(3))
        noise2 = ord(match.group(4))
        noise3 = ord(match.group(5))
        noise4 = ord(match.group(6))
        proc_magn_beam1 = BinaryProtocolParameterDict.convert_word_to_int(match.group(7))
        proc_magn_beam2 = BinaryProtocolParameterDict.convert_word_to_int(match.group(8))
        proc_magn_beam3 = BinaryProtocolParameterDict.convert_word_to_int(match.group(9))
        proc_magn_beam4 = BinaryProtocolParameterDict.convert_word_to_int(match.group(10))
        distance1 = BinaryProtocolParameterDict.convert_word_to_int(match.group(11))
        distance2 = BinaryProtocolParameterDict.convert_word_to_int(match.group(12))
        distance3 = BinaryProtocolParameterDict.convert_word_to_int(match.group(13))
        distance4 = BinaryProtocolParameterDict.convert_word_to_int(match.group(14))
        
        if None == records:
            raise SampleException("No records value parsed")
        if None == cell:
            raise SampleException("No cell value parsed")
        if None == noise1:
            raise SampleException("No noise1 value parsed")
        if None == noise2:
            raise SampleException("No noise2 value parsed")
        if None == noise3:
            raise SampleException("No noise3 value parsed")
        if None == noise4:
            raise SampleException("No noise4 value parsed")
        if None == proc_magn_beam1:
            raise SampleException("No proc_magn_beam1 value parsed")
        if None == proc_magn_beam2:
            raise SampleException("No proc_magn_beam2 value parsed")
        if None == proc_magn_beam3:
            raise SampleException("No proc_magn_beam3 value parsed")
        if None == proc_magn_beam4:
            raise SampleException("No proc_magn_beam4 value parsed")
        if None == distance1:
            raise SampleException("No distance1 value parsed")
        if None == distance2:
            raise SampleException("No distance2 value parsed")
        if None == distance3:
            raise SampleException("No distance3 value parsed")
        if None == distance4:
            raise SampleException("No distance4 value parsed")
        
        result = [{DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.RECORDS,
                   DataParticleKey.VALUE: records},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.CELL,
                   DataParticleKey.VALUE: cell},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE1,
                   DataParticleKey.VALUE: noise1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE2,
                   DataParticleKey.VALUE: noise2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE3,
                   DataParticleKey.VALUE: noise3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE4,
                   DataParticleKey.VALUE: noise4},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM1,
                   DataParticleKey.VALUE: proc_magn_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM2,
                   DataParticleKey.VALUE: proc_magn_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM3,
                   DataParticleKey.VALUE: proc_magn_beam3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM4,
                   DataParticleKey.VALUE: proc_magn_beam4},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE1,
                   DataParticleKey.VALUE: distance1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE2,
                   DataParticleKey.VALUE: distance2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE3,
                   DataParticleKey.VALUE: distance3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE4,
                   DataParticleKey.VALUE: distance4}]
 
        log.debug('AquadoppDwDiagnosticHeaderDataParticle: particle=%s' %result)
        return result
    
class AquadoppDwVelocityDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"
    ERROR = "error"
    ANALOG1 = "analog1"
    BATTERY_VOLTAGE = "battery_voltage"
    SOUND_SPEED_ANALOG2 = "sound_speed_analog2"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    PRESSURE = "pressure"
    STATUS = "status"
    TEMPERATURE = "temperature"
    VELOCITY_BEAM1 = "velocity_beam1"
    VELOCITY_BEAM2 = "velocity_beam2"
    VELOCITY_BEAM3 = "velocity_beam3"
    AMPLITUDE_BEAM1 = "amplitude_beam1"
    AMPLITUDE_BEAM2 = "amplitude_beam2"
    AMPLITUDE_BEAM3 = "amplitude_beam3"
        
class AquadoppDwVelocityDataParticle(DataParticle):
    """
    Routine for parsing velocity data into a data particle structure for the Aquadopp DW sensor. 
    """
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the velocity data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = VELOCITY_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("AquadoppDwVelocityDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('AquadoppDwVelocityDataParticle: particle=%s' %result)
        return result
            
    def _build_particle(self, match):
        timestamp = BinaryProtocolParameterDict.convert_time(match.group(1))
        error = BinaryProtocolParameterDict.convert_word_to_int(match.group(2))
        analog1 = BinaryProtocolParameterDict.convert_word_to_int(match.group(3))
        battery_voltage = BinaryProtocolParameterDict.convert_word_to_int(match.group(4))
        sound_speed = BinaryProtocolParameterDict.convert_word_to_int(match.group(5))
        heading = BinaryProtocolParameterDict.convert_word_to_int(match.group(6))
        pitch = BinaryProtocolParameterDict.convert_word_to_int(match.group(7))
        roll = BinaryProtocolParameterDict.convert_word_to_int(match.group(8))
        pressure = ord(match.group(9)) * 0x10000
        status = ord(match.group(10))
        pressure += BinaryProtocolParameterDict.convert_word_to_int(match.group(11))
        temperature = BinaryProtocolParameterDict.convert_word_to_int(match.group(12))
        velocity_beam1 = BinaryProtocolParameterDict.convert_word_to_int(match.group(13))
        velocity_beam2 = BinaryProtocolParameterDict.convert_word_to_int(match.group(14))
        velocity_beam3 = BinaryProtocolParameterDict.convert_word_to_int(match.group(15))
        amplitude_beam1 = ord(match.group(16))
        amplitude_beam2 = ord(match.group(17))
        amplitude_beam3 = ord(match.group(18))
        
        if None == timestamp:
            raise SampleException("No timestamp parsed")
        if None == error:
            raise SampleException("No error value parsed")
        if None == analog1:
            raise SampleException("No analog1 value parsed")
        if None == battery_voltage:
            raise SampleException("No battery_voltage value parsed")
        if None == sound_speed:
            raise SampleException("No sound_speed value parsed")
        if None == heading:
            raise SampleException("No heading value parsed")
        if None == pitch:
            raise SampleException("No pitch value parsed")
        if None == roll:
            raise SampleException("No roll value parsed")
        if None == status:
            raise SampleException("No status value parsed")
        if None == pressure:
            raise SampleException("No pressure value parsed")
        if None == temperature:
            raise SampleException("No temperature value parsed")
        if None == velocity_beam1:
            raise SampleException("No velocity_beam1 value parsed")
        if None == velocity_beam2:
            raise SampleException("No velocity_beam2 value parsed")
        if None == velocity_beam3:
            raise SampleException("No velocity_beam3 value parsed")
        if None == amplitude_beam1:
            raise SampleException("No amplitude_beam1 value parsed")
        if None == amplitude_beam2:
            raise SampleException("No amplitude_beam2 value parsed")
        if None == amplitude_beam3:
            raise SampleException("No amplitude_beam3 value parsed")
        
        result = [{DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ERROR,
                   DataParticleKey.VALUE: error},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ANALOG1,
                   DataParticleKey.VALUE: analog1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.BATTERY_VOLTAGE,
                   DataParticleKey.VALUE: battery_voltage},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.SOUND_SPEED_ANALOG2,
                   DataParticleKey.VALUE: sound_speed},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.HEADING,
                   DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.STATUS,
                   DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM1,
                   DataParticleKey.VALUE: velocity_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM2,
                   DataParticleKey.VALUE: velocity_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM3,
                   DataParticleKey.VALUE: velocity_beam3},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM1,
                   DataParticleKey.VALUE: amplitude_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM2,
                   DataParticleKey.VALUE: amplitude_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM3,
                   DataParticleKey.VALUE: amplitude_beam3}]
 
        return result

class AquadoppDwDiagnosticDataParticle(AquadoppDwVelocityDataParticle):
    """
    Routine for parsing diagnostic data into a data particle structure for the Aquadopp DW sensor. 
    This structure is the same as the velocity data, so particle is built with the same method
    """
    _data_particle_type = DataParticleType.DIAGNOSTIC_DATA

    def _build_parsed_values(self):
        """
        Take something in the diagnostic data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = DIAGNOSTIC_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("AquadoppDwDiagnosticDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('AquadoppDwDiagnosticDataParticle: particle=%s' %result)
        return result
            

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
        Parameter.NUMBER_PINGS,
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
        Parameter.CORRELATION_THRESHOLD,
        Parameter.USER_3_SPARE,
        Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
        Parameter.USER_4_SPARE,
        Parameter.QUAL_CONSTANTS,
        ]
    
    
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
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET_CONFIGURATION, self._handler_command_set_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_CLOCK, self._handler_command_read_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_MODE, self._handler_command_read_mode)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.POWER_DOWN, self._handler_command_power_down)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_BATTERY_VOLTAGE, self._handler_command_read_battery_voltage)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_ID, self._handler_command_read_id)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HW_CONFIGURATION, self._handler_command_get_hw_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HEAD_CONFIGURATION, self._handler_command_get_head_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME, self._handler_command_start_measurement_specific_time)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_IMMEDIATE, self._handler_command_start_measurement_immediate)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.CONFIGURE_INSTRUMENT, self._build_set_configutation_command)
        self._add_build_handler(InstrumentCmds.SET_REAL_TIME_CLOCK, self._build_set_real_time_clock_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.READ_REAL_TIME_CLOCK, self._parse_read_clock_response)
        self._add_response_handler(InstrumentCmds.CMD_WHAT_MODE, self._parse_what_mode_response)
        self._add_response_handler(InstrumentCmds.READ_BATTERY_VOLTAGE, self._parse_read_battery_voltage_response)
        self._add_response_handler(InstrumentCmds.READ_ID, self._parse_read_id)
        self._add_response_handler(InstrumentCmds.READ_HW_CONFIGURATION, self._parse_read_hw_config)
        self._add_response_handler(InstrumentCmds.READ_HEAD_CONFIGURATION, self._parse_read_head_config)

        # Construct the parameter dictionary containing device parameters, current parameter values, and set formatting functions.
        self._build_param_dict()

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(Protocol.chunker_sieve_function)

    @staticmethod
    def chunker_sieve_function(raw_data):
        """ The method that detects data sample structures from instrument
        """
        return_list = []
        
        for structure_sync, structure_len in sample_structures:
            start = raw_data.find(structure_sync)
            if start != -1:    # found a sync pattern
                if start+structure_len <= len(raw_data):    # only check the CRC if all of the structure has arrived
                    calculated_checksum = BinaryProtocolParameterDict.calculate_checksum(raw_data[start:start+structure_len], structure_len)
                    #log.debug('chunker_sieve_function: calculated checksum = %s' % calculated_checksum)
                    sent_checksum = BinaryProtocolParameterDict.convert_word_to_int(raw_data[start+structure_len-2:start+structure_len])
                    if sent_checksum == calculated_checksum:
                        return_list.append((start, start+structure_len))        
                        #log.debug("chunker_sieve_function: found %s", raw_data[start:start+structure_len].encode('hex'))
                
        return return_list
    
    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    ########################################################################
    # overridden superclass methods
    ########################################################################

    def set_init_params(self, config):
        """
        over-ridden to handle binary block configuration
        Set the initialization parameters to the given values in the protocol
        parameter dictionary. 
        @param config The parameter_name/value to set in the initialization
            fields of the parameter dictionary
        @raise InstrumentParameterException If the config cannot be set
        """
        log.debug("set_init_params: config=%s" %config)
        if not isinstance(config, dict):
            raise InstrumentParameterException("Invalid init config format")
                
        if DriverParameter.ALL in config:
            binary_config = config[DriverParameter.ALL]
            # make the configuration string look like it came from instrument to get all the methods to be happy
            binary_config += InstrumentPrompts.Z_ACK    
            log.debug("config len=%d, config=%s" %(len(binary_config), binary_config.encode('hex')))
            
            if len(binary_config) == USER_CONFIG_LEN+2:
                if self._check_configuration(binary_config, USER_CONFIG_SYNC_BYTES, USER_CONFIG_LEN):                    
                    self._param_dict.update(binary_config, init_value=True)
                else:
                    raise InstrumentParameterException("bad configuration")
            else:
                raise InstrumentParameterException("configuration not the correct length")
        else:
            for name in config.keys():
                self._param_dict.set_init_value(name, config[name])
    
    def _got_chunk(self, structure):
        """
        The base class got_data has gotten a structure from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        log.debug("_got_chunk: detected structure = %s", structure.encode('hex'))
        self._extract_sample(AquadoppDwVelocityDataParticle, VELOCITY_DATA_REGEX, structure)
        self._extract_sample(AquadoppDwDiagnosticDataParticle, DIAGNOSTIC_DATA_REGEX, structure)
        self._extract_sample(AquadoppDwDiagnosticHeaderDataParticle, DIAGNOSTIC_DATA_HEADER_REGEX, structure)

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
        expected_prompt = kwargs.get('expected_prompt', InstrumentPrompts.Z_ACK)
                            
        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if build_handler:
            cmd_line = build_handler(cmd, *args, **kwargs)
        else:
            cmd_line = cmd

        # Send command.
        log.debug('_do_cmd_resp: %s(%s), timeout=%s, expected_prompt=%s (%s),' 
                  % (repr(cmd_line), repr(cmd_line.encode("hex")), timeout, expected_prompt, expected_prompt.encode("hex")))
        self._connection.send(cmd_line)

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
            result = ResourceAgentState.IDLE
        elif prompt == InstrumentPrompts.CONFIRMATION:    
            next_state = ProtocolState.AUTOSAMPLE
            result = ResourceAgentState.STREAMING
        elif prompt == InstrumentPrompts.Z_ACK:
            log.debug('_handler_unknown_discover: promptbuf=%s (%s)' %(self._promptbuf, self._promptbuf.encode("hex")))
            if InstrumentModes.COMMAND in self._promptbuf:
                next_state = ProtocolState.COMMAND
                result = ResourceAgentState.IDLE
            elif (InstrumentModes.MEASUREMENT in self._promptbuf or 
                 InstrumentModes.CONFIRMATION in self._promptbuf):
                next_state = ProtocolState.AUTOSAMPLE
                result = ResourceAgentState.STREAMING
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

        not_user_requested = kwargs.get('NotUserRequested', False)

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
        
        # if internal set from apply_startup_params() or restore_direct_access_params()
        # over-ride read-only parameters
        if not_user_requested:
            parameters.set_params_to_read_write()
        
        # For each key, value in the params_to_set list set the value in parameters copy.
        try:
            for (name, value) in params_to_set.iteritems():
                log.debug('_handler_command_set: setting %s to %s' %(name, value))
                parameters.set_from_value(name, value)
        except Exception as ex:
            raise InstrumentParameterException('Unable to set parameter %s to %s: %s' %(name, value, ex))
        
        output = self._create_set_output(parameters)
        
        log.debug('_handler_command_set: writing instrument configuration to instrument')
        self._connection.send(InstrumentCmds.CONFIGURE_INSTRUMENT)
        self._connection.send(output)

        # Clear the prompt buffer.
        self._promptbuf = ''
        self._get_response(timeout=5, expected_prompt=InstrumentPrompts.Z_ACK)

        self._update_params()
            
        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from aquadopp.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).        
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(InstrumentCmds.ACQUIRE_DATA, *args, **kwargs)
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_AT_SPECIFIC_TIME, 
                                   expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)
                
        next_state = ProtocolState.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        next_state = ProtocolState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_set_configuration(self, *args, **kwargs):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue set user configuration command.
        result = self._do_cmd_resp(InstrumentCmds.CONFIGURE_INSTRUMENT, 
                                   expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_clock(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_REAL_TIME_CLOCK, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_mode(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.CMD_WHAT_MODE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_power_down(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.POWER_DOWN, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_battery_voltage(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_BATTERY_VOLTAGE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_id(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_ID, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_hw_config(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HW_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_head_config(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HEAD_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_measurement_specific_time(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_AT_SPECIFIC_TIME, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)
        # TODO: what state should the driver/IA go to? Should this command even be exported?

        return (next_state, (next_agent_state, result))

    def _handler_command_start_measurement_immediate(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_IMMEDIATE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)
        # TODO: what state should the driver/IA go to? Should this command even be exported?

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        str_time = get_timestamp_delayed("%M %S %d %H %y %m")
        byte_time = ''
        for v in str_time.split():
            byte_time += chr(int('0x'+v, base=16))
        values = str_time.split()
        log.info("_handler_command_clock_sync: time set to %s:m %s:s %s:d %s:h %s:y %s:M (%s)" %(values[0], values[1], values[2], values[3], values[4], values[5], byte_time.encode('hex'))) 
        self._do_cmd_resp(InstrumentCmds.SET_REAL_TIME_CLOCK, byte_time, **kwargs)

        return (next_state, (next_agent_state, result))


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
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

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
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

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
    
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        
        # The parameter dictionary.
        self._param_dict = BinaryProtocolParameterDict()

        # Add parameter handlers to parameter dict.
        
        # user config
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(4),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(6),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(8),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                             r'^.{%s}(.{2}).*' % str(10),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                             r'^.{%s}(.{2}).*' % str(12),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.NUMBER_PINGS,
                             r'^.{%s}(.{2}).*' % str(14),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(16),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True,
                             init_value=60)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                             r'^.{%s}(.{2}).*' % str(18),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(20),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(22),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True)
        self._param_dict.add(Parameter.A1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(24),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B0_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(26),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(28),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                             r'^.{%s}(.{2}).*' % str(30),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True,
                             init_value=2)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                             r'^.{%s}(.{2}).*' % str(32),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True,
                             init_value=1)
        self._param_dict.add(Parameter.NUMBER_BINS,
                             r'^.{%s}(.{2}).*' % str(34),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.BIN_LENGTH,
                             r'^.{%s}(.{2}).*' % str(36),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(38),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True,
                             init_value=3600)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                             r'^.{%s}(.{6}).*' % str(40),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WRAP_MODE,
                             r'^.{%s}(.{2}).*' % str(46),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                             r'^.{%s}(.{6}).*' % str(48),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                             r'^.{%s}(.{4}).*' % str(54),
                             lambda match : BinaryProtocolParameterDict.convert_double_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.double_word_to_string,
                             startup_param=True,
                             init_value=43200)
        self._param_dict.add(Parameter.MODE,
                             r'^.{%s}(.{2}).*' % str(58),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                             r'^.{%s}(.{2}).*' % str(60),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(62),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string,
                             startup_param=True,
                             init_value=20)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(64),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(66),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.MODE_TEST,
                             r'^.{%s}(.{2}).*' % str(68),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                             r'^.{%s}(.{2}).*' % str(70),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.SW_VERSION,
                             r'^.{%s}(.{2}).*' % str(72),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.USER_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(74),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                             r'^.{%s}(.{180}).*' % str(76),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.COMMENTS,
                             r'^.{%s}(.{180}).*' % str(256),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                             r'^.{%s}(.{2}).*' % str(436),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                             r'^.{%s}(.{2}).*' % str(438),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                             r'^.{%s}(.{2}).*' % str(440),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(442),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                             r'^.{%s}(.{2}).*' % str(444),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                             r'^.{%s}(.{2}).*' % str(446),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.A1_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(448),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B0_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(450),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.B1_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(452),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.USER_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(454),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                             r'^.{%s}(.{2}).*' % str(456),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
                             r'^.{%s}(.{2}).*' % str(458),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.USER_3_SPARE,
                             r'^.{%s}(.{2}).*' % str(460),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                             r'^.{%s}(.{2}).*' % str(462),
                             lambda match : BinaryProtocolParameterDict.convert_word_to_int(match.group(1)),
                             BinaryProtocolParameterDict.word_to_string)
        self._param_dict.add(Parameter.USER_4_SPARE,
                             r'^.{%s}(.{30}).*' % str(464),
                             lambda match : match.group(1),
                             lambda string : string)
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                             r'^.{%s}(.{16}).*' % str(494),
                             lambda match : match.group(1),
                             lambda string : string)
        
    def _dump_config(self, input):
        # dump config block
        dump = ''
        for byte_index in range(0, len(input)):
            if byte_index % 0x10 == 0:
                if byte_index != 0:
                    dump += '\n'   # no linefeed on first line
                dump += '{:03x}  '.format(byte_index)
            #dump += '0x{:02x}, '.format(ord(input[byte_index]))
            dump += '{:02x} '.format(ord(input[byte_index]))
        #log.debug("dump = %s", dump)
        return dump
    
    def _check_configuration(self, input, sync, length):        
        log.debug('_check_configuration: config=')
        print self._dump_config(input)
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
        
        # check checksum
        calculated_checksum = BinaryProtocolParameterDict.calculate_checksum(input, length)
        log.debug('_check_configuration: user c_c = %s' % calculated_checksum)
        sent_checksum = BinaryProtocolParameterDict.convert_word_to_int(input[length-2:length])
        if sent_checksum != calculated_checksum:
            log.debug('_check_configuration: user checksum in error %s != %s' 
                      %(calculated_checksum, sent_checksum))
            return False       
        
        return True

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and values saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolState.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
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
                    if self._check_configuration(self._promptbuf, USER_CONFIG_SYNC_BYTES, USER_CONFIG_LEN):                    
                        self._param_dict.update(self._promptbuf)
                        new_config = self._param_dict.get_config()
                        if new_config != old_config:
                            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                        return
                    break
                time.sleep(.1)
            log.debug('_update_params: get_user_configuration command response length %d not right, %s' % (len(self._promptbuf), self._promptbuf.encode("hex")))

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
            
            continue
        
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
            log.debug('_create_set_output: adding %s to list' %name)
            output += parameters.format_parameter(name)
        
        checksum = CHECK_SUM_SEED
        for word_index in range(0, len(output), 2):
            word_value = BinaryProtocolParameterDict.convert_word_to_int(output[word_index:word_index+2])
            checksum = (checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        log.debug('_create_set_output: user checksum = %s' % checksum)

        output += BinaryProtocolParameterDict.word_to_string(checksum)
        self._dump_config(output)                      
        
        return output
    
    def _build_set_configutation_command(self, cmd, *args, **kwargs):
        user_configuration = kwargs.get('user_configuration', None)
        if not user_configuration:
            raise InstrumentParameterException('set_configuration command missing user_configuration parameter.')
        if not isinstance(user_configuration, str):
            raise InstrumentParameterException('set_configuration command requires a string user_configuration parameter.')
        self._dump_config(user_configuration)        
            
        cmd_line = cmd + user_configuration
        return cmd_line


    def _build_set_real_time_clock_command(self, cmd, time, **kwargs):
        return cmd + time


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
        time = BinaryProtocolParameterDict.convert_time(response)   
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
        return BinaryProtocolParameterDict.convert_word_to_int(response[0:2])
        

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
        return BinaryProtocolParameterDict.convert_word_to_int(response[0:2])
        
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
        if not self._check_configuration(self._promptbuf, HW_CONFIG_SYNC_BYTES, HW_CONFIG_LEN):                    
            log.warn("_parse_read_hw_config: Bad read hw response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read hw response. (%s)", response.encode('hex'))
        log.debug("_parse_read_hw_config: response=%s", response.encode('hex'))
        parsed = {} 
        parsed['SerialNo'] = response[4:18]  
        parsed['Config'] = BinaryProtocolParameterDict.convert_word_to_int(response[18:20])  
        parsed['Frequency'] = BinaryProtocolParameterDict.convert_word_to_int(response[20:22])  
        parsed['PICversion'] = BinaryProtocolParameterDict.convert_word_to_int(response[22:24])  
        parsed['HWrevision'] = BinaryProtocolParameterDict.convert_word_to_int(response[24:26])  
        parsed['RecSize'] = BinaryProtocolParameterDict.convert_word_to_int(response[26:28])  
        parsed['Status'] = BinaryProtocolParameterDict.convert_word_to_int(response[28:30])  
        parsed['FWversion'] = response[42:46] 
        return parsed
        
    def _parse_read_head_config(self, response, prompt):
        """ Parse the response from the instrument for a read head command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not self._check_configuration(self._promptbuf, HEAD_CONFIG_SYNC_BYTES, HEAD_CONFIG_LEN):                    
            log.warn("_parse_read_head_config: Bad read head response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read head response. (%s)", response.encode('hex'))
        log.debug("_parse_read_head_config: response=%s", response.encode('hex')) 
        parsed = {} 
        parsed['Config'] = BinaryProtocolParameterDict.convert_word_to_int(response[4:6])  
        parsed['Frequency'] = BinaryProtocolParameterDict.convert_word_to_int(response[6:8])  
        parsed['Type'] = BinaryProtocolParameterDict.convert_word_to_int(response[8:10])  
        parsed['SerialNo'] = response[10:22]  
        #parsed['System'] = self._dump_config(response[22:198])
        parsed['System'] = base64.b64encode(response[22:198])
        parsed['NBeams'] = BinaryProtocolParameterDict.convert_word_to_int(response[220:222])  
        return parsed
                    