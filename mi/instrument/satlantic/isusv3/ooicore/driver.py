#!/usr/bin/env python

"""
@package mi.instrument.satlantic.isusv3.ooicore.driver
@file /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/satlantic/isusv3/ooicore/driver.py
@author Steve Foley
@brief Driver for the ooicore

Development notes/todo list:
* Menu handlers need to find the operating mode they will be returning to
when bumping off the end of the root menu and starting operations again.

Release notes:

Satlantic MBARI-ISUSv3 Nutrient sampler
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'


import time
import datetime
import re
import array
import struct

from mi.core.common import BaseEnum

from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import SampleException

from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

from mi.core.log import get_logger
log = get_logger()

"""
Module wide values
"""
INSTRUMENT_NEWLINE = '\r\n'
WRITE_DELAY = 0
READ_DELAY = .25
RESET_DELAY = 25
EOLN = "\n"
COMMAND_MODE = 'COMMAND'
AUTOSAMPLE_MODE = 'AUTOSAMPLE'


SAMPLE_PATTERN_ASCII = r'^SAT(.{3}).{4},(.{4,7}),(.{,9})'
#SAMPLE_PATTERN = r'SAT(.{3})(.{4})(.{4})(.{8})'
SAMPLE_PATTERN = r'SAT'         #      Sentinal
SAMPLE_PATTERN += r'(.{3})'     #   1: Frame Type
SAMPLE_PATTERN += r'(.{4})'     #   2: Serial Number
SAMPLE_PATTERN += r'(.{4})'     #   3: Date
SAMPLE_PATTERN += r'(.{8})'     #   4: Time
SAMPLE_PATTERN += r'(.{4})'     #   5: Nitrate Concentration
SAMPLE_PATTERN += r'(.{4})'     #   6: AUX1
SAMPLE_PATTERN += r'(.{4})'     #   7: AUX2
SAMPLE_PATTERN += r'(.{4})'     #   8: AUX3
SAMPLE_PATTERN += r'(.{4})'     #   9: RMS ERROR
SAMPLE_PATTERN += r'(.{4})'     #  10: t_int Interior Temp
SAMPLE_PATTERN += r'(.{4})'     #  11: t_spec Spectrometer Temp
SAMPLE_PATTERN += r'(.{4})'     #  12: t_lamp Lamp Temp
SAMPLE_PATTERN += r'(.{4})'     #  13: lamp_time Lamp Time
SAMPLE_PATTERN += r'(.{4})'     #  14: humidity Interior Humidity
SAMPLE_PATTERN += r'(.{4})'     #  15: volt_12 Lamp Power Supply Voltage
SAMPLE_PATTERN += r'(.{4})'     #  16: volt_5 Internal Analog Power Supply Voltage
SAMPLE_PATTERN += r'(.{4})'     #  17: volt_main Main Internal Power Supply Voltage
SAMPLE_PATTERN += r'(.{4})'     #  18: ref_avg Reference Channel Average
SAMPLE_PATTERN += r'(.{4})'     #  19: ref_std Reference Channel Variance
SAMPLE_PATTERN += r'(.{4})'     #  20: sw_dark Sea-Water Dark
SAMPLE_PATTERN += r'(.{4})'     #  21: spec_avg All Channels Average
SAMPLE_PATTERN += r'(.{2})'     #  22: Channel 1
SAMPLE_PATTERN += r'(.{2})'     #  23: Channel 2
SAMPLE_PATTERN += r'(.{2})'     #  24: Channel 3
SAMPLE_PATTERN += r'(.{2})'     #  25: Channel 4
SAMPLE_PATTERN += r'(.{2})'     #  26: Channel 5
SAMPLE_PATTERN += r'(.{2})'     #  27: Channel 6
SAMPLE_PATTERN += r'(.{2})'     #  28: Channel 7
SAMPLE_PATTERN += r'(.{2})'     #  29: Channel 8
SAMPLE_PATTERN += r'(.{2})'     #  30: Channel 9
SAMPLE_PATTERN += r'(.{2})'     #  31: Channel 10
SAMPLE_PATTERN += r'(.{2})'     #  32: Channel 11
SAMPLE_PATTERN += r'(.{2})'     #  33: Channel 12
SAMPLE_PATTERN += r'(.{2})'     #  34: Channel 13
SAMPLE_PATTERN += r'(.{2})'     #  35: Channel 14
SAMPLE_PATTERN += r'(.{2})'     #  36: Channel 15
SAMPLE_PATTERN += r'(.{2})'     #  37: Channel 16
SAMPLE_PATTERN += r'(.{2})'     #  38: Channel 17
SAMPLE_PATTERN += r'(.{2})'     #  39: Channel 18
SAMPLE_PATTERN += r'(.{2})'     #  40: Channel 19
SAMPLE_PATTERN += r'(.{2})'     #  41: Channel 20
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

# Packet config for ISUSV3 data granules.
STREAM_NAME_PARSED = 'parsed'
STREAM_NAME_RAW = 'raw'

"""
DHE: Using ctd values right now; not sure what to use for isus yet.
"""
PACKET_CONFIG = {
        'parsed' : ('prototype.sci_data.stream_defs', 'ctd_stream_packet'),
        'raw' : None            
}


# @todo May need some regex(s) for data format returned...at least to confirm
# that it is data.

"""
Static Enumerations
"""
class State(BaseEnum):
    """
    Enumerated driver states.  Your driver will likly only support a subset of these.
    """
    #UNCONFIGURED_MODE = DriverProtocolState.UNKNOWN
    UNKNOWN = DriverProtocolState.UNKNOWN
    #BENCHTOP_MODE = "ISUS_STATE_BENCHTOP"
    POLL =  DriverProtocolState.POLL
    #TRIGGERED_MODE =  DriverProtocolState.POLL
    CONTINUOUS_MODE =  "ISUS_STATE_CONTINUOUS"
    AUTOSAMPLE=  DriverProtocolState.AUTOSAMPLE
    #FIXEDTIME_MODE = "ISUS_STATE_FIXEDTIME"
    SCHEDULED_MODE = "ISUS_STATE_SCHEDULED"
    #MENU_MODE =  DriverProtocolState.COMMAND
    COMMAND =  DriverProtocolState.COMMAND
    FILE_UPLOADING = "ISUS_STATE_FILE_UPLOADING"
    ROOT_MENU = "ISUS_STATE_ROOT_MENU"
    CONFIG_MENU = "ISUS_STATE_CONFIG_MENU"
    SETUP_MENU = "ISUS_STATE_SETUP_MENU"
    OUTPUT_SETUP_MENU = "ISUS_STATE_OUTPUT_SETUP_MENU"
    DEPLOYMENT_SETUP_MENU = "ISUS_STATE_DEPLOYMENT_SETUP_MENU"
    SPECTROMETER_SETUP_MENU = "ISUS_STATE_SPECTROMETER_SETUP_MENU"
    LAMP_SETUP_MENU = "ISUS_STATE_LAMP_SETUP_MENU"
    FITTING_SETUP_MENU = "ISUS_STATE_FITTING_SETUP_MENU"
    FILE_MENU = "ISUS_STATE_FILE_MENU"
    INFO_MENU = "ISUS_STATE_INFO_MENU"
    
    #TEST =  DriverState.TEST
    #CALIBRATE =  DriverState.CALIBRATE

class Event(BaseEnum):
    """
    Enumerated driver events.  Your driver will likly only support a subset of these.
    """
    CONFIGURE = DriverEvent.CONFIGURE
    INITIALIZE = DriverEvent.INITIALIZE
    DISCOVER = DriverEvent.DISCOVER
    SET = DriverEvent.SET
    GET = DriverEvent.GET
    EXECUTE = DriverEvent.EXECUTE
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    
    """
    DHE: The ISUS commands collide (ex., several 'S' events/commands), and the 
    base class response handler is set up to use just the value.  Need a better way, like use a dict with
    a unique string as the key (for instance, "setup_menu_reponse", or "show_config_response" for
    two different keys for the that have the same command value.
    """

    # Menu and operation commands
    QUIT_CMD = 'Q'
    GO_CMD = 'G'
    STOP_CMD = 'S'
    MENU_CMD = 'M'
    ANY_KEY = 'Z'
    YES = 'Y'
    NO = 'N'
    ACCEPT = 0x0D

    # Main menu commands
    CONFIG_MENU = 'C'
    SETUP_MENU = 'S'
    FILE_MENU = 'F'
    INFO_MENU = 'I'
    UP_MENU_LEVEL = 'Q'
    OUTPUT_SETUP_MENU = 'O'
    DEPLOYMENT_SETUP_MENU = 'D'
    SPECTROMETER_SETUP_MENU = 'S'
    LAMP_SETUP_MENU = 'L'
    
    # Config menu parameters
    SHOW_CONFIG = 'S'
    BAUD_RATE = 'B'
    DEPLOYMENT_COUNTER = 'D'
    
    # Output setup menu
    STATUS_MESSAGES = 'S'
    LOGGING_FRAME_MODE = 'L'
    TRANSFER_FRAME_MODE = 'T'
    DAILY_LOG_TOGGLE = 'D'
    NITRATE_DAC_RANGE = 'N'
    AUX_DAC_RANGE = 'A'
    
    # Deployment setup menu
    OPERATIONAL_MODE = 'O'
    INITIAL_DELAY = 'D'
    FIXED_TIME_DURATION = 'F'
    START_COMMAND_TRIGGERED = 'T'
    STOP_COMMAND_TRIGGERED = 'S'
    
    # Spectrometer setup menu
    INTEGRATION_PERIOD = 'I'
    COLLECTION_RATE = 'C'
    LOAD_SPECTROMETER_COEFFICIENTS = 'L'
    
    # Lamp setup menu
    POWER_ON_WARM_UP_PERIOD = 'P'
    REFERENCE_DETECTOR = 'R'
    
    # Fitting setup menu
    FITTING_RANGE = 'F'
    BASELINE_ORDER = 'B'
    SEAWATER_DARK_SAMPLES = 'S'

    # File menu
    FILE_LIST_PROGRAM = "LP"
    FILE_LIST_COEFFICIENT = "LC"
    FILE_LIST_LOG = "LL"
    FILE_LIST_DATA = "LD"
    FILE_OUTPUT_EXTINCT = "OE"
    FILE_OUTPUT_WAVELENGTH = "OW"
    FILE_OUTPUT_SCHEDULE = "OS"
    FILE_OUTPUT_LOG = "OL"
    FILE_OUTPUT_DATA = "OD"
    FILE_UPLOAD_SCHEDULE = "US"
    FILE_UPLOAD_EXTINCT = "UE"
    FILE_UPLOAD_PROGRAM = "UP"
    FILE_ERASE_EXTINCT = "EE"
    FILE_ERASE_LOG = "EL"
    FILE_ERASE_DATA = "ED"
    FILE_ERASE_ALL_DATA = "EAD"

    # Info menu
    BUILD_INFO = 'B'
    DISK_INFO = 'D'
    CLOCK_INFO = 'C'
    PIXEL_TO_WAVELENGTH = 'P'
    FITTING_COEFFICIENTS = 'F'
    LAMP_ON_TIME = 'L'
    DAC_MENU = 'A'
    GENERATE_DUMP_FILE = 'G'
    
    REBOOT = "REBOOT"

class Prompt(BaseEnum):
    ROOT_MENU = "ISUS> [H]"
    CONFIG_MENU_1 = "ISUS Configuration Menu (<H> for Help)"
    #CONFIG_MENU = "ISUS_CONFIG> [H] ?"
    # DHE This is bogus; seems to timeout looking for this sometimes.
    CONFIG_MENU = "ISUS_CONFIG>"
    SETUP_MENU = "ISUS_SETUP> [H]"
    SETUP_OUTPUT_MENU = "ISUS_SETUP_OUTPUT> [H] ?"
    SETUP_DEPLOY_MENU = "ISUS_SETUP_DEPLOY"
    SETUP_FIT_MENU = "ISUS_SETUP_FIT> [H] ?"
    SETUP_SPEC_MENU = "ISUS_SETUP_SPEC> [H] ?"
    SETUP_LAMP_MENU = "ISUS_SETUP_LAMP> [H] ?"
    FILE_MENU = "ISUS_FILE> [H] ?"
    INFO_MENU = "ISUS_INFO> [H] ?"
    #SAVE_SETTINGS = "Save current settings? (Otherwise changes are lost at next power-down) [Y] ?"
    SAVE_SETTINGS = "Save current settings? (Otherwise changes are lost at next power-down)"
    #REPLACE_SETTINGS = "Replace existing setting by current? [N] ?"
    REPLACE_SETTINGS = "Replace existing setting by current?"
    MODIFY = "Modify?  [N]" 
    ENTER_CHOICE = "Enter number to assign new value"
    ENTER_DEPLOYMENT_COUNTER = "Enter deployment counter. ?"
    WAITING_FOR_GO = "Waiting for 'g'"
    AUTO_START_RESTARTING = "ISUS will start in 0 seconds"
    AUTOSAMPLE_STOP_RESTARTING = "ISUS will start in"  # Used to top autosample
    STOP_SAMPLING = "Stop command received, exiting"

class Parameter(DriverParameter):
    """ The parameters that drive/control the operation and behavior of the device """
    BAUDRATE = "BAUDRATE"
    DEPLOYMENT_COUNTER = "DEPLOYMENT_COUNTER"
    STATUS_MESSAGES = "STATUS_MESSAGES"
    LOGGING_FRAME_MODE = "LOGGING_FRAME_MODE"
    TRANSFER_FRAME_MODE = "TRANSFER_FRAME_MODE"
    DAILY_LOG_TOGGLE = "DAILY_LOG_TOGGLE"
    NITRATE_DAC_RANGE_MIN = "NITRATE_DAC_RANGE_MIN"
    NITRATE_DAC_RANGE_MAX = "NITRATE_DAC_RANGE_MAX"
    AUX_DAC_RANGE_MIN = "AUX_DAC_RANGE_MIN"
    AUX_DAC_RANGE_MAX = "AUX_DAC_RANGE_MAX"
    DEPLOYMENT_MODE = "DEPLOYMENT_MODE"
    INITIAL_DELAY = "INITIAL_DELAY"
    FIXED_OP_TIME = "FIXED_OP_TIME"
    COLLECTION_RATE = "COLLECTION_RATE"
    BUILD_INFO = "BUILD_INFO"
    DISK_INFO = "DISK_INFO"
    CLOCK_INFO = "CLOCK_INFO"
    PIXEL = "PIXEL"
    DAC_MENU = "DAC_MENU"

    # Read-only
    SPEC_COEFF = "SPEC_COEFF" # R/O
    
    # Direct access only
    INTEGRATION_PERIOD = "INTEGRATION_PERIOD" # Direct Access
    WARM_UP_PERIOD = "WARM_UP_PERIOD" # DA
    REFERENCE_DIODE = "REFERENCE_DIODE" # DA
    FITTING_RANGE = "FITTING_RANGE" # DA
    BASELINE_ORDER = "BASELINE_ORDER" # DA
    SEAWATER_DARK_SAMPLES = "SEAWATER_DARK_SAMPLES" # DA

#class Command(BaseEnum):
class Command(object):
    """
    DHE: Commenting these out for now..
    REBOOT = "REBOOT"
    GENERATE_DUMP_FILE = 'GENERATE_DUMP_FILE'
    FILE_LIST_PROGRAM = "LP"
    FILE_LIST_COEFFICIENT = "LC"
    FILE_LIST_LOG = "LL"
    FILE_LIST_DATA = "LD"
    FILE_OUTPUT_EXTINCT = "OE"
    FILE_OUTPUT_WAVELENGTH = "OW"
    FILE_OUTPUT_SCHEDULE = "OS"
    FILE_OUTPUT_LOG = "OL"
    FILE_OUTPUT_DATA = "OD"
    FILE_UPLOAD_SCHEDULE = "US"
    FILE_UPLOAD_EXTINCT = "UE"
    FILE_UPLOAD_PROGRAM = "UP"
    FILE_ERASE_EXTINCT = "EE"
    FILE_ERASE_LOG = "EL"
    FILE_ERASE_DATA = "ED"
    FILE_ERASE_ALL_DATA = "EAD"
    #SUBMIT_SCHEDULE = "SUBMIT_SCHEDULE"
    #SUBMIT_CALIBRATION = "SUBMIT_CALIBRATION"
    #GET_CALIBRATION = "GET_CALIBRATION"
    """

    # Main menu commands
    DEPLOYMENT_MODE_YES = ('deployment_mode_yes', 'Y')
    DEPLOYMENT_MODE_NO = ('deployment_mode_no', 'N')
    CONFIG_MENU_CMD = ('config_menu_cmd', 'C')
    """
    DHE: Need to include an expected response
    """
    SHOW_CONFIG_CMD = ('show_config_cmd', 'S', Prompt.CONFIG_MENU)
    BAUD_RATE_CMD = ('baud_rate_cmd', 'B')
    SETUP_MENU_CMD = ('setup_menu_cmd', 'S')
    DEPLOYMENT_COUNTER_CMD = ('deployment_counter_cmd', 'D')
    DEPLOYMENT_MODE_CMD = ('deployment_mode_cmd', 'D')
    OPERATIONAL_MODE_CMD = ('operational_mode_cmd', 'O')


    #FILE_MENU_CMD = 'F'
    #INFO_MENU_CMD = 'I'
    #UP_MENU_LEVEL_CMD = 'Q'
    #OUTPUT_SETUP_MENU_CMD = 'O'
    #DEPLOYMENT_SETUP_MENU_CMD = 'D'
    #SPECTROMETER_SETUP_MENU_CMD = 'S'
    #LAMP_SETUP_MENU_CMD = 'L'
    
        
class Status(BaseEnum):
    """ Values that are real-time/transient/in-flux, read-only """
    TRANSFER_FRAME_MODE = "TRANSFER_FRAME_MODE"
    LAMP_ON_TIME = "LAMP_ON_TIME"
    
class MetadataParameter(BaseEnum):
    pass

class Error(BaseEnum):
    pass

class Status(BaseEnum):
    pass

class ooicoreParameter():
    """
    """
class SubMenues(BaseEnum):
    CONFIG_MENU = 'config_menu'
    SHOW_CONFIG_MENU = 'show_config_menu'
    SETUP_MENU = 'setup_menu'
    DEPLOYMENT_COUNTER_MENU = 'deployment_counter_menu'
    DEPLOYMENT_MODE_MENU = 'deployment_mode_menu'
    OPERATIONAL_MODE_MENU = 'operational_mode_menu'
    OPERATIONAL_MODE_SET= 'operational_mode_set'

class InstrumentPrompts(BaseEnum):
    MAIN_MENU = "ISUS> [H] ?"

###
#   Driver for ooicore
###
#class ooicoreInstrumentDriver(InstrumentDriver):
class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    """
    def __init__(self, evt_callback):
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)


    # DHE Added
    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()


    # DHE Added
    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, INSTRUMENT_NEWLINE, self._driver_event) 

class ISUSDataParticleKey(BaseEnum):
    FRAME_TYPE = "frame_type"
    SERIAL_NUM = "serial_num"
    DATE = "date"
    TIME = "time"
    NTR_CONC = "ntr_conc"
    AUX1 = "aux1"
    AUX2 = "aux2"
    AUX3 = "aux3"
    RMS_ERROR = "rms_error"
    T_INT = "t_int"
    T_SPEC = "t_spec"
    T_LAMP = "t_lamp"
    LAMP_TIME = "lamp_time"
    HUMIDITY = "humidity"
    VOLT_12 = "volt_12"
    VOLT_5 = "volt_5"
    VOLT_MAIN = "volt_main"
    REF_AVG = "ref_avg"
    REF_STD = "ref_std"
    SW_DARK = "sw_dark"
    SPEC_AVG = "spec_avg"
    CH001 = "ch001"
    CH002 = "ch002"
    CH003 = "ch003"
    CH004 = "ch004"
    CH005 = "ch005"
    CH006 = "ch006"
    CH007 = "ch007"
    CH008 = "ch008"
    CH009 = "ch009"
    CH010 = "ch010"
    CH011 = "ch011"
    CH012 = "ch012"
    CH013 = "ch013"
    CH014 = "ch014"
    CH015 = "ch015"
    CH016 = "ch016"
    CH017 = "ch017"
    CH018 = "ch018"
    CH019 = "ch019"
    CH020 = "ch020"

class ISUSDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            frame_type = str(match.group(1))
            serial_num = str(match.group(2))
            date = struct.unpack_from('>i', match.group(3))
            time = struct.unpack_from('>d', match.group(4))
            ntr_conc = struct.unpack_from('>f', match.group(5))
            aux1 = struct.unpack_from('>f', match.group(6))
            aux2 = struct.unpack_from('>f', match.group(7))
            aux3 = struct.unpack_from('>f', match.group(8))
            rms_error = struct.unpack_from('>f', match.group(9))
            t_int = struct.unpack_from('>f', match.group(10))
            t_spec = struct.unpack_from('>f', match.group(11))
            t_lamp = struct.unpack_from('>f', match.group(12))
            lamp_time = struct.unpack_from('>f', match.group(13))
            humidity = struct.unpack_from('>f', match.group(14))
            volt_12 = struct.unpack_from('>f', match.group(15))
            volt_5 = struct.unpack_from('>f', match.group(16))
            volt_main = struct.unpack_from('>f', match.group(17))
            ref_avg = struct.unpack_from('>f', match.group(18))
            ref_std = struct.unpack_from('>f', match.group(19))
            sw_dark = struct.unpack_from('>f', match.group(20))
            spec_avg = struct.unpack_from('>f', match.group(21))
            ch001 = struct.unpack_from('>H', match.group(22))
            ch002 = struct.unpack_from('>H', match.group(23))
            ch003 = struct.unpack_from('>H', match.group(24))
            ch004 = struct.unpack_from('>H', match.group(25))
            ch005 = struct.unpack_from('>H', match.group(26))
            ch006 = struct.unpack_from('>H', match.group(27))
            ch007 = struct.unpack_from('>H', match.group(28))
            ch008 = struct.unpack_from('>H', match.group(29))
            ch009 = struct.unpack_from('>H', match.group(30))
            ch010 = struct.unpack_from('>H', match.group(31))
            ch011 = struct.unpack_from('>H', match.group(32))
            ch012 = struct.unpack_from('>H', match.group(33))
            ch013 = struct.unpack_from('>H', match.group(34))
            ch014 = struct.unpack_from('>H', match.group(35))
            ch015 = struct.unpack_from('>H', match.group(36))
            ch016 = struct.unpack_from('>H', match.group(37))
            ch017 = struct.unpack_from('>H', match.group(38))
            ch018 = struct.unpack_from('>H', match.group(39))
            ch019 = struct.unpack_from('>H', match.group(40))
            ch020 = struct.unpack_from('>H', match.group(41))
        except ValueError:
            raise SampleException("ValueError while parsing data: [%s]" %
                                  self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: ISUSDataParticleKey.FRAME_TYPE,
                   DataParticleKey.VALUE: frame_type},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.SERIAL_NUM,
                   DataParticleKey.VALUE: serial_num},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.DATE,
                    DataParticleKey.VALUE: date},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.TIME,
                    DataParticleKey.VALUE: time},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.NTR_CONC,
                    DataParticleKey.VALUE: ntr_conc},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.AUX1,
                    DataParticleKey.VALUE: aux1},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.AUX2,
                    DataParticleKey.VALUE: aux2},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.AUX3,
                    DataParticleKey.VALUE: aux3},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.RMS_ERROR,
                    DataParticleKey.VALUE: rms_error},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.T_INT,
                    DataParticleKey.VALUE: t_int},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.T_SPEC,
                    DataParticleKey.VALUE: t_spec},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.T_LAMP,
                    DataParticleKey.VALUE: t_lamp},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.LAMP_TIME,
                    DataParticleKey.VALUE: lamp_time},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.HUMIDITY,
                    DataParticleKey.VALUE: humidity},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.VOLT_12,
                    DataParticleKey.VALUE: volt_12},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.VOLT_5,
                    DataParticleKey.VALUE: volt_5},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.VOLT_MAIN,
                    DataParticleKey.VALUE: volt_main},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.REF_AVG,
                    DataParticleKey.VALUE: ref_avg},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.REF_STD,
                    DataParticleKey.VALUE: ref_std},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.SW_DARK,
                    DataParticleKey.VALUE: sw_dark},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.SPEC_AVG,
                    DataParticleKey.VALUE: spec_avg},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH001,
                    DataParticleKey.VALUE: ch001},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH002,
                    DataParticleKey.VALUE: ch002},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH003,
                    DataParticleKey.VALUE: ch003},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH004,
                    DataParticleKey.VALUE: ch004},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH005,
                    DataParticleKey.VALUE: ch005},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH006,
                    DataParticleKey.VALUE: ch006},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH007,
                    DataParticleKey.VALUE: ch007},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH008,
                    DataParticleKey.VALUE: ch008},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH009,
                    DataParticleKey.VALUE: ch009},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH010,
                    DataParticleKey.VALUE: ch010},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH011,
                    DataParticleKey.VALUE: ch011},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH012,
                    DataParticleKey.VALUE: ch012},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH013,
                    DataParticleKey.VALUE: ch013},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH014,
                    DataParticleKey.VALUE: ch014},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH015,
                    DataParticleKey.VALUE: ch015},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH016,
                    DataParticleKey.VALUE: ch016},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH017,
                    DataParticleKey.VALUE: ch017},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH018,
                    DataParticleKey.VALUE: ch018},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH019,
                    DataParticleKey.VALUE: ch019},
                  {DataParticleKey.VALUE_ID: ISUSDataParticleKey.CH020,
                    DataParticleKey.VALUE: ch020}]
        return result

"""
Protocol for ooicore
"""
class Protocol(MenuInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        directions = self.MenuTree.Directions

        # DHE NEW METHOD
        # It seems to me that the "command" or "intent" object should contain everything necessary for its
        # execution.  For now, the is no command object.  It was just a string (character).  
        # 
        menu = self.MenuTree({
            SubMenues.CONFIG_MENU: [directions(Command.CONFIG_MENU_CMD, Prompt.CONFIG_MENU)],
            SubMenues.SETUP_MENU: [directions(Command.SETUP_MENU_CMD, Prompt.SETUP_MENU)],
            SubMenues.SHOW_CONFIG_MENU: [directions(SubMenues.CONFIG_MENU)],
            SubMenues.DEPLOYMENT_COUNTER_MENU: [directions(SubMenues.CONFIG_MENU),
                                                directions(Command.DEPLOYMENT_COUNTER_CMD, Prompt.ENTER_DEPLOYMENT_COUNTER)],
            SubMenues.DEPLOYMENT_MODE_MENU: [directions(SubMenues.SETUP_MENU),
                                             directions(Command.DEPLOYMENT_MODE_CMD, Prompt.SETUP_DEPLOY_MENU)],
            SubMenues.OPERATIONAL_MODE_MENU: [directions(SubMenues.DEPLOYMENT_MODE_MENU),
                                             directions(Command.OPERATIONAL_MODE_CMD, Prompt.MODIFY)],
            SubMenues.OPERATIONAL_MODE_SET: [directions(SubMenues.OPERATIONAL_MODE_MENU),
                                             directions(Command.DEPLOYMENT_MODE_YES, Prompt.ENTER_CHOICE)]
        })

        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event, read_delay=READ_DELAY) 
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = EOLN
        
        ##### Setup the state machine
        self._protocol_fsm = InstrumentFSM(State, Event, Event.ENTER, Event.EXIT)
        
        self._protocol_fsm.add_handler(State.UNKNOWN, Event.INITIALIZE,
                              self._handler_initialize) 
        self._protocol_fsm.add_handler(State.UNKNOWN, Event.DISCOVER,
                              self._handler_unknown_discover) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.MENU_CMD,
                              self._handler_continuous_menu) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.GO_CMD,
                              self._handler_continuous_go)
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.STOP_CMD,
                              self._handler_continuous_stop) 
        
        # ... and so on with the operation handler listings...
        # In general, naming is _handler_currentstate_eventreceived

        self._protocol_fsm.add_handler(State.COMMAND, Event.ENTER,
                              self._handler_root_menu_enter) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.CONFIG_MENU,
                              self._handler_root_config) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.SETUP_MENU,
                              self._handler_root_setup) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.FILE_MENU,
                              self._handler_root_file) 
        #
        # DHE added
        #
        self._protocol_fsm.add_handler(State.COMMAND, Event.GET,
                              self._handler_command_get) 
        
        self._protocol_fsm.add_handler(State.COMMAND, Event.SET,
                              self._handler_command_set) 

        # Not handled right now; there is no single acquire sample for the ISUS
        # in "command mode."  It could be simulated by going into triggered mode
        # and starting and stopping, but the state machine needs triggered mode
        # which it doesn't have right now.
        self._protocol_fsm.add_handler(State.COMMAND, Event.ACQUIRE_SAMPLE,
                              self._handler_command_acquire_sample) 
        
        self._protocol_fsm.add_handler(State.COMMAND, Event.START_AUTOSAMPLE,
                              self._handler_command_start_autosample) 
        
        self._protocol_fsm.add_handler(State.AUTOSAMPLE, Event.STOP_AUTOSAMPLE,
                              self._handler_autosample_stop_autosample) 
        
        self._add_build_handler(Command.CONFIG_MENU_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.SHOW_CONFIG_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.BAUD_RATE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_COUNTER_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.SETUP_MENU_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.OPERATIONAL_MODE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_YES[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_NO[0], self._build_simple_command)

        # Add response handlers for parsing command responses
        self._add_response_handler(Command.SHOW_CONFIG_CMD[0], self._parse_show_config_menu_response)
        #self._add_response_handler(Command.DEPLOYMENT_MODE_NO[0], self._parse_deployment_mode_response)
        #self._add_response_handler(Command.DEPLOYMENT_MODE_CMD[0], self._parse_deployment_mode_response)
        self._add_response_handler(Command.OPERATIONAL_MODE_CMD[0], self._parse_deployment_mode_response)
        
        # Add sample handlers.
        #self._sample_pattern = r'^SAT(.{3}).{4},(.{4,7}),(.{,9})'
        #self._sample_pattern += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
        #self._sample_pattern += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'
        #self._sample_pattern += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'        
        #self._sample_regex = re.compile(self._sample_pattern)


        # Construct the parameter dictionary
        self._build_param_dict()

        self._protocol_fsm.start(State.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        """
        @todo ... and so on, continuing with these additional parameters (and any that
        may have been left out...drive the list by the actual interface...
        
        INITIAL_DELAY = "INITIAL_DELAY"
        FIXED_OP_TIME = "FIXED_OP_TIME"
        COLLECTION_RATE = "COLLECTION_RATE"
        BUILD_INFO = "BUILD_INFO"
        DISK_INFO = "DISK_INFO"
        CLOCK_INFO = "CLOCK_INFO"
        PIXEL = "PIXEL"
        DAC_MENU = "DAC_MENU"
    
        # Read-only, so tag the visibility with READ_ONLY
        SPEC_COEFF = "SPEC_COEFF" # R/O
        
        # Direct access only, so tag the visibility with DIRECT_ACCESS
        INTEGRATION_PERIOD = "INTEGRATION_PERIOD" # Direct Access
        WARM_UP_PERIOD = "WARM_UP_PERIOD" # DA
        REFERENCE_DIODE = "REFERENCE_DIODE" # DA
        FITTING_RANGE = "FITTING_RANGE" # DA
        BASELINE_ORDER = "BASELINE_ORDER" # DA
        SEAWATER_DARK_SAMPLES = "SEAWATER_DARK_SAMPLES" # DA
        """

    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        patterns = []
        matchers = []
        return_list = []

        patterns.append((SAMPLE_PATTERN)) 

        for pattern in patterns:
            matchers.append(re.compile(pattern))

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

        
    ##############################
    # execute_* interface routines
    ##############################
    
    # @todo Add execute_* routines to expose. Should line up with commands
    # plus GET, SET, SAMPLE, POLL, RESET, and others of that ilk
    
    ################
    # State handlers
    ################
    def _handler_initialize(self, *args, **kwargs):
        """Handle transition from UNCONFIGURED state to a known one.
        
        This method determines what state the device is in or gets it to a
        known state so that the instrument and protocol are in sync.
        @param params Parameters to pass to the state
        @retval return (next state, result)
        @todo fix this to only do break when connected
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_unknown_discover(self, *args, **kwargs):
        """
        As of now, the IOS states that the ISUS should be in continuous mode.  That means that it
        is probably autosampling upon entry to this handler.  However, it is possible that it has
        been interrupted and is in the menu system.  
        """
        next_state = None
        next_agent_state = None

        log.debug("_handler_unknown_discover")

        try:
            logging_state = self._go_to_root_menu()
        except InstrumentTimeoutException:
            log.error("ISUS driver timed out in _go_to_root_menu()")
            raise InstrumentStateException('Unknown state: Instrument timed out going to root menu.')
        else:
            if logging_state == AUTOSAMPLE_MODE:
                next_state = State.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
            elif logging_state == COMMAND_MODE:
                next_state = State.COMMAND
                next_agent_state = ResourceAgentState.IDLE
            else:
                errorString = 'Unknown state based go_to_root_menu() response: ' + str(logging_state)
                log.error(errorString)
                raise InstrumentStateException(errorString)
        
        return (next_state, next_agent_state)

    def _handler_continuous_menu(self, *args, **kwargs):
        """Handle a menu command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_continuous_go(self, *args, **kwargs):
        """Handle a go command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_continuous_stop(self, *args, **kwargs):
        """Handle a stop command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
                
    def _handler_command_get(self, *args, **kwargs):
        """Handle a config menu command event from root menu.
        
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
            debug_string =  "-----> DHE: result for get DriverParameter.ALL is: " + str(result)
            log.debug(debug_string) 
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

            #
            # There is a problem with the current build_handler scheme; it's keyed by
            # the command.  I need to pass the "final command" parameter as a value,
            # and there is no build handler for all of the possible values.   
            #
            for (key, val) in params.iteritems():
                dest_submenu = self._param_dict.get_menu_path_write(key)
                command = self._param_dict.get_submenu_write(key)
                self._navigate_and_execute(None, value=val, dest_submenu=dest_submenu, timeout=5)
            self._update_params()

        return (next_state, result)


    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from ISUSv3.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).        
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        """
        Can't go to root menu here; the only way this handler will work is if the ISUS is deployed
        in TRIGGERED mode.
        """
        result = self._do_cmd_resp(Command.TS, *args, **kwargs)
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """Handle a start autosample command event from root menu.
        
        """
        delay = 1
        timeout = 25
        next_state = None
        next_agent_state = None
        result = None
        
        #
        # DHE: We need to either put the instrument into continuous mode or triggered mode.  If
        # triggered mode, then we need our own scheduler to cause the periodic sampling that would
        # simulate autosample.
        #
        #self._navigate_and_execute(Command.DEPLOYMENT_MODE_YES, dest_submenu=SubMenues.OPERATIONAL_MODE_MENU, 
        #    expected_prompt=Prompt.SETUP_DEPLOY_MENU, 
        #    timeout=5)
        self._go_to_root_menu()
        

        # Clear the prompt buffer.
        self._promptbuf = ''
        """
        We are keeping the instrument in continuous mode; to start autosample, we enter
        a quit command and look for the 'starting in ...' response
        """
        starttime = time.time()
        while Prompt.AUTO_START_RESTARTING not in self._promptbuf:

            self._connection.send(Event.QUIT_CMD + self.eoln)
            time.sleep(delay)

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed out starting autosample: promptbuf is %s" % self._promptbuf) 
                raise InstrumentTimeoutException()

        log.debug("ISUS now in autosample")

        next_state = State.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        delay = 1
        timeout = 10
        next_state = None
        next_agent_state = None
        result = None
        
        starttime = time.time()

        # Clear the prompt buffer.
        self._promptbuf = ''

        """
        Instrument is autosampling; to stop it enter 's' command, then 'm'
        """
        while Prompt.STOP_SAMPLING not in self._promptbuf:

            self._connection.send(Event.STOP_CMD)
            time.sleep(delay)

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed outawaiting STOP_SAMPLING prompt stop_autosample")
                raise InstrumentTimeoutException()

        starttime = time.time()

        """
        Don't need to clear the prompt buff here; the prompt we're looking for
        will show up as a result of last command
        """
        while Prompt.AUTOSAMPLE_STOP_RESTARTING not in self._promptbuf:

            time.sleep(delay)

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed outawaiting AUTOSAMPLE_STOP_RESTARTING prompt in stop_autosample")
                raise InstrumentTimeoutException()

        starttime = time.time()

        while Prompt.ROOT_MENU not in self._promptbuf:
            self._connection.send(Event.MENU_CMD + self.eoln)
            time.sleep(delay)

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed outawaiting ROOT_MENU prompt stop_autosample")
                raise InstrumentTimeoutException()

        log.info("ISUS autosample stopped")

        next_state = State.COMMAND        
        next_agent_state = ResourceAgentState.COMMAND
        
        return (next_state, (next_agent_state, result))

                
    def _handler_root_menu_enter(self, *args, **kwargs):
        """Entry event for the command state
        """

        self._update_params()

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_root_config(self, *args, **kwargs):
        """Handle a config menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_root_setup(self, *args, **kwargs):
        """Handle a setup menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_root_file(self, *args, **kwargs):
        """Handle a file menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)

    # @todo ...carry on with the rest of the menu system handlers and what they actually do...
    # include handling of MODIFY prompts properly

    ##########
    # Builders
    ##########
    
    # Add additional routines here that build commands to be sent in case
    # _build_simple_command, _build_keypress_command, and
    # _build_multi_keypress_command are insufficient
    
    ##################################################################
    # Response parsers
    ##################################################################
    
    # Add in some parsing routines to handle various types of output such as
    # parameter get, parameter set, exec, into and out of op modes, menu changes?
        
    def _parse_show_config_menu_response(self, response, prompt):
        """
        Parse handler for config menu response.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if config_menu command misunderstood.
        """

        debug_string = "------------> DHE: in _parse_show_config_menu_response: prompt is: " + \
            prompt + ". Response is: " + response
        log.debug(debug_string)

        if prompt != Prompt.CONFIG_MENU:
            raise InstrumentProtocolException('_parse__config_menu: command not recognized: %s.' % response)

        for line in response.split(self.eoln):
            debug_string = "------> DHE: passing line <" + line + "> to _param_dict.update()"
            log.debug(debug_string)
            self._param_dict.update(line)

    def _parse_deployment_mode_response(self, response, prompt):
        """
        Parse handler for config menu response.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if config_menu command misunderstood.
        """

        debug_string =  "------------> DHE: in _parse_deployment_mode_response: prompt is: " + \
            prompt + ". Response is: " + response
        log.debug(debug_string)

        for line in response.split(self.eoln):
            debug_string =  "------> DHE: parse_deployment_mode passing line <" + line + "> to _param_dict.update()"
            log.debug(debug_string)
            self._param_dict.update(line)


    """
    Translation routines
    """
    def _enable_disable_to_bool(self):
        """ Translate ENABLE or DISABLE into a True/False for param dict
        ...or maybe a string is more appropriate?"""
        pass

    def _frametype_to_int(self):
        """ Translate frame type (NONE, FULL_ASCII, FULL_BINARY, CONCENTRATION)
        to the integer that matches it when setting the value
        (0-3 respectively)
        ...or maybe a string is more appropriate?
        """
        pass
    
    def _opmode_to_string(self):
        """ Translate opmode (SCHEDULED, CONTINUOUS, FIXEDTIME, FIXEDTIMEISUS,
        BENCHTOP, TRIGGERED) to matching int (0-5 respectively)
        """
        pass
    
    def _logtoggle_to_int(self):
        """ Translate log message toggling (DAILY, EACHEVENT) to matching int
        (0-1 respectively)
        """
        pass
        
    """
    Helpers
    """
    def _send_wakeup(self):
        """Send a wakeup to this instrument...one that wont hurt if it is awake
        already."""
        self._connection.send(self.eoln)

    def _update_params(self, *args, **kwargs):
        """Fetch the parameters from the device, and update the param dict.
        May be used when transitioning into or out of an operational mode?
        
        @param args Unused
        @param kwargs Takes timeout value
        @throws InstrumentProtocolException
        @throws InstrumentTimeoutException
        """
        log.debug("Updating parameter dict")

        old_config = self._param_dict.get_config()

        self._go_to_root_menu()
        if len(Command.SHOW_CONFIG_CMD) > 2:
            expected_response = Command.SHOW_CONFIG_CMD[2]
        else:
            expected_response = None
        self._navigate_and_execute(Command.SHOW_CONFIG_CMD, expected_response = expected_response, 
                                   dest_submenu=SubMenues.SHOW_CONFIG_MENU, timeout=5)

        self._go_to_root_menu()
        self._navigate_and_execute(Command.DEPLOYMENT_MODE_NO, dest_submenu=SubMenues.OPERATIONAL_MODE_MENU, 
            expected_prompt=Prompt.SETUP_DEPLOY_MENU, timeout=5)
        self._go_to_root_menu()

        new_config = self._param_dict.get_config()            
        if (new_config != old_config) and (None not in old_config.values()):
            debug_string =  "--------> DHE: publishing CONFIG_CHANGE event"
            log.debug(debug_string)
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)            

    def  _wakeup(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        self._promptbuf = ''

        # get new time for timeout.
        starttime = time.time()
        while True:
            # Send a line return and wait a sec.
            log.debug('Sending wakeup.')
            self._send_wakeup()
            time.sleep(delay)

            for item in self._prompts.list():
                if item in self._promptbuf:
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed out awaking instrument")
                raise InstrumentTimeoutException()



    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        self._extract_sample(ISUSDataParticle, SAMPLE_REGEX, chunk)
                    

    def _go_to_root_menu(self):
        """
        Determine if we're at home (root-menu); if not, iterate sending 'Q' (quit) until we get there.
        """
        """
        Clear buffers and send a wakeup command to the instrument
        @throw InstrumentTimeoutException if the device does not get to root.
        """
        #
        # DHE: This doesn't seem very efficient...seems like there should be an expected response optional
        # kwarg so that we don't have to iterate through all the prompts in self._prompts
        #

        timeout = 10
        delay = 1
        prompt = self._wakeup(timeout)
        if prompt == AUTOSAMPLE_MODE:
            return prompt

        # Grab time for timeout.
        starttime = time.time()

        log.debug("_go_to_root_menu")
        """
        Sleep for a bit to let the instrument complete the prompt.
        """
        time.sleep(delay)
        while Prompt.ROOT_MENU not in self._promptbuf:
            # Clear the prompt buffer.
            self._promptbuf = ''

            self._connection.send(Event.QUIT_CMD + self.eoln)
            time.sleep(delay)

            if time.time() > starttime + timeout:
                log.error("ISUS driver timed out returning to root menu")
                raise InstrumentTimeoutException()

            if Prompt.SAVE_SETTINGS in self._promptbuf:
                self._connection.send(Event.YES + self.eoln)
                time.sleep(delay)

            if Prompt.REPLACE_SETTINGS in self._promptbuf:
                self._connection.send(Event.YES + self.eoln)
                time.sleep(delay)
                
        return COMMAND_MODE

    def _do_cmd_resp(self, cmd, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param expected_prompt optional kwarg passed through to _get_response.
        @param timeout=timeout optional wakeup and command timeout.
        @param write_delay optional kwarg for inter-character transmit delay.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)
        
        # Pop off the write_delay; it doesn't get passed on in **kwargs
        write_delay = kwargs.pop('write_delay', 0)

        # Get the value
        value = kwargs.get('value', None)

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd[0], None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd[0])

        """
        DHE: The cmd for menu-driven instruments needs to be an object.  Need to refactor
        """
        cmd_line = build_handler(cmd[1])

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        log.debug('_do_cmd_resp: cmd=%s, timeout=%s, write_delay=%s, expected_prompt=%s,' %
                        (repr(cmd_line), timeout, write_delay, expected_prompt))
        if (write_delay == 0):
            self._connection.send(cmd_line)
        else:
            debug_string = "---> DHE: do_cmd_resp() sending cmd_line: " + cmd_line
            log.debug(debug_string)
            for char in cmd_line:
                self._connection.send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)

        log.debug('_do_cmd_resp: looking for response handler for: %s"' %(cmd[0]))
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd[0]), None) or \
            self._response_handlers.get(cmd[0], None)
        resp_result = None
        if resp_handler:
            log.debug('_do_cmd_resp: calling response handler: %s' %(resp_handler))
            resp_result = resp_handler(result, prompt)
        else:
            log.debug('_do_cmd_resp: no response handler for cmd: %s' %(cmd[0]))

        return resp_result

    def _navigate_and_execute(self, cmd, **kwargs):
        """
        Navigate to a sub-menu and execute a command.  
        @param cmd The command to execute.
        @param expected_prompt optional kwarg passed through to do_cmd_resp.
        @param timeout=timeout optional wakeup and command timeout.
        @param write_delay optional kwarg passed through to do_cmd_resp.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        resp_result = None

        # Get dest_submenu arg
        dest_submenu = kwargs.pop('dest_submenu', None)
        if dest_submenu == None:
            raise InstrumentProtocolException('_navigate_and_execute(): dest_submenu parameter missing')

        # iterate through the directions 
        directions_list = self._menu.get_directions(dest_submenu)
        for directions in directions_list:
            log.debug('_navigate_and_execute: directions: %s' %(directions))
            command = directions.get_command()
            response = directions.get_response()
            timeout = directions.get_timeout()
            self._do_cmd_resp(command, expected_prompt = response, timeout = timeout)

        """
        DHE: this is a kludge; need a way to send a parameter as a "command."  We can't expect to look
        up all possible values in the build_handlers
        """
        value = kwargs.pop('value', None)
        if cmd is None:
            cmd_line = self._build_simple_command(value) 
            log.debug('_navigate_and_execute: sending value: %s to connection.send.' %(cmd_line))
            self._connection.send(cmd_line)
        else:
            log.debug('_navigate_and_execute: sending cmd: %s with kwargs: %s to _do_cmd_resp.' %(cmd, kwargs))
            resp_result = self._do_cmd_resp(cmd, **kwargs)
 
        return resp_result
    
    def _build_param_dict(self):
        """
        Populate the paramenter dictionary with the ISUS parameters.
        For each parameter (the key), add match string, match lambda
        function, value formatting function, visibility (READ or READ_WRITE),
        and the path to the submenu from the root menu.
        """
 
        """
        DHE Trying this new model with menu_path and then final submenu for
        both read and write operations
        """
        self._param_dict.add(Parameter.BAUDRATE,
                             r'Baudrate:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_read=[Event.SHOW_CONFIG, Prompt.CONFIG_MENU],
                             menu_path_write=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_write=[Event.BAUD_RATE, Event.YES])

        self._param_dict.add(Parameter.DEPLOYMENT_COUNTER,
                             r'Deployment Cntr:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_read=[Event.SHOW_CONFIG, Prompt.CONFIG_MENU],
                             #menu_path_write=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             menu_path_write=SubMenues.DEPLOYMENT_COUNTER_MENU,
                             submenu_write=[Event.DEPLOYMENT_COUNTER, Event.YES])

        self._param_dict.add(Parameter.DEPLOYMENT_MODE,
                             r'OpMode = (SCHEDULED|CONTINUOUS|FIXEDTIME|FIXEDTIMEISUS|BENCHTOP|TRIGGERED)',
                             lambda match : str(match.group(1)),
                             self._opmode_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=SubMenues.DEPLOYMENT_MODE_MENU,
                             #menu_path_read=[[Event.SETUP_MENU,
                             #                Event.DEPLOYMENT_SETUP_MENU]],
                             submenu_read=[Event.OPERATIONAL_MODE, Prompt.SETUP_DEPLOY_MENU],
                             menu_path_write=SubMenues.DEPLOYMENT_MODE_MENU,
                             submenu_write=[Event.OPERATIONAL_MODE, Event.YES])


        """
        DHE COMMENTED OUT
        This was Steve's original way
        self._param_dict.add(Parameter.BAUDRATE,
                             r'Baudrate:\s+(\d+) bps',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.CONFIG_MENU,
                                             Event.SHOW_CONFIG],
                             menu_path_write=[Event.CONFIG_MENU,
                                             Event.BAUD_RATE,
                                             Event.YES])
        self._param_dict.add(Parameter.DEPLOYMENT_COUNTER,
                             r'Deployment Cntr:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.CONFIG_MENU,
                                             Event.SHOW_CONFIG],
                             menu_path_write=[Event.CONFIG_MENU,
                                              Event.DEPLOYMENT_COUNTER,
                                              Event.YES])
        self._param_dict.add(Parameter.STATUS_MESSAGES,
                             r'StatusMessages = (ENABLED|DISABLED)',
                             lambda match : int(match.group(1)),
                             self._enable_disable_to_bool,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.STATUS_MESSAGES],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.STATUS_MESSAGES,
                                              Event.YES])
        self._param_dict.add(Parameter.LOGGING_FRAME_MODE,
                             r'FrameLogging = (NONE|FULL_ASCII|FULL_BINARY|CONCENTRATION)',
                             lambda match : int(match.group(1)),
                             self._frametype_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.LOGGING_FRAME_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.LOGGING_FRAME_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.TRANSFER_FRAME_MODE,
                             r'FrameTransfer = (NONE|FULL_ASCII|FULL_BINARY|CONCENTRATION)',
                             lambda match : int(match.group(1)),
                             self._frametype_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.TRANSFER_FRAME_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.TRANSFER_FRAME_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.DAILY_LOG_TOGGLE,
                             r'SchFile = (DAILY|EACHEVENT)',
                             lambda match : int(match.group(1)),
                             self._logtoggle_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.DAILY_LOG_TOGGLE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.DAILY_LOG_TOGGLE,
                                              Event.YES])    
        self._param_dict.add(Parameter.NITRATE_DAC_RANGE_MIN,
                             r'NO3DacMin = ([-+]?\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.NITRATE_DAC_RANGE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.NITRATE_DAC_RANGE,
                                              Event.YES])
        self._param_dict.add(Parameter.NITRATE_DAC_RANGE_MAX,
                             r'NO3DacMax = (\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.NITRATE_DAC_RANGE,
                                             Event.NO],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.NITRATE_DAC_RANGE,
                                              Event.NO,
                                              Event.YES])
        self._param_dict.add(Parameter.AUX_DAC_RANGE_MIN,
                             r'AuxDacMin = ([-+]?\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.AUX_DAC_RANGE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.AUX_DAC_RANGE,
                                              Event.YES])
        self._param_dict.add(Parameter.AUX_DAC_RANGE_MAX,
                             r'AuxDacMax = (\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.AUX_DAC_RANGE,
                                             Event.NO],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.AUX_DAC_RANGE,
                                              Event.NO,
                                              Event.YES])
        self._param_dict.add(Parameter.DEPLOYMENT_MODE,
                             r'OpMode = (SCHEDULED|CONTINUOUS|FIXEDTIME|FIXEDTIMEISUS|BENCHTOP|TRIGGERED)',
                             lambda match : int(match.group(1)),
                             self._opmode_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.DEPLOYMENT_SETUP_MENU,
                                             Event.OPERATIONAL_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.DEPLOYMENT_SETUP_MENU,
                                              Event.OPERATIONAL_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.INITIAL_DELAY,
                             r'ContModeDelay = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.DEPLOYMENT_SETUP_MENU,
                                             Event.INITIAL_DELAY],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.DEPLOYMENT_SETUP_MENU,
                                              Event.INITIAL_DELAY,
                                              Event.YES])

        """


    
    
