
"""
@package mi.instrument.sami.pco2w.cgsn.driver
@file marine-integrations/mi/instrument/sami/pco2w/cgsn/driver.py
@author Chris Center
@brief Driver for the cgsn
Release notes:

Initial release of the Sami PCO2 driver
  : = Instrument Status Word (Long)
  ? = Instrument Error Return Code (i.e. ?02)
  * = Record (please check)
"""

__author__ = 'Chris Center'
__license__ = 'Apache 2.0'

import re
import string
import time
import datetime
import calendar
import sys      # Exceptions
import copy
from threading import RLock

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import FunctionParameter
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

###############################################################################
# Program Constants
###############################################################################
NEWLINE = '\r'  # CJC Note: Do Not Use '\r\n'
NSECONDS_1904_TO_1970 = 2082844800
TIMEOUT = 10        # Default Timeout.

# This will decode n+1 chars for {n}
REGULAR_STATUS_REGEX = r'[:](\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{3})(\w[0-9A-Fa-f])(\w[0-9A-Fa-f])'
REGULAR_STATUS_REGEX_MATCHER = re.compile(REGULAR_STATUS_REGEX)

# Record Type4 or 5 are 39 bytes (78char)
RECORD_REGEX = r'[*](\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f])'
RECORD_REGEX_MATCHER = re.compile(RECORD_REGEX)

DATA_RECORD_REGEX = r'[*](\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[4-5]{1})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{57})'
CONTROL_RECORD_REGEX = r'[*](\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})([^4-5]{1})(\w[0-9A-Fa-f]{32})'  # This works.
DATA_RECORD_REGEX_MATCHER = re.compile(DATA_RECORD_REGEX)
CONTROL_RECORD_REGEX_MATCHER = re.compile(CONTROL_RECORD_REGEX)

# Note: First string character "C" is valid for current time.
CONFIG_REGEX = r'[C](\w[0-9A-Fa-f]{6})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{7})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{25})(\w[0-9A-Fa-f]{5})(\w[0-9A-Fa-f]{3})(\w[0-9A-Fa-f]{1})(\w[0-9A-Fa-f]{99})'
CONFIG_REGEX_MATCHER = re.compile(CONFIG_REGEX)

ERROR_REGEX = r'[?](\w[0-9A-Fa-f]{1})' # (\w[0-9A-Fa-f])'
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)

IMMEDIATE_STATUS_REGEX = r'(\w[0-9A-Fa-f]{1})'
IMMEDIATE_STATUS_REGEX_MATCHER = re.compile(IMMEDIATE_STATUS_REGEX)

###############################################################################
# Program Declarations
###############################################################################

# Define a default Sami Configuration string used to R/W updates.
# This is the string from the PC02W_Low_Level_SAMI_Use_1.pdf document.
# Note: Zero Padding removed
SAMI_DEFAULT_CONFIG = "CAB39E84000000F401E13380570007080401000258030A0002580017000258011A003840001C071020FFA8181C0100381001012025640004333833350002000102000"

###############################################################################
# Sami Software Utilities
###############################################################################
def convert_timestamp_to_sec(time_str):
    '''
    Convert a time string to seconds since 1970.
    @param time_str: Time String of format "dd-mm-yyyy hr:mn:sec"
    @return: time in seconds since 1970 (Epoc)
    '''
    sec = 0
    timestamp_regex = re.compile(r"(\d\d)-(\d\d)-(\d\d\d\d) (\d\d):(\d\d):(\d\d)")
    match = timestamp_regex.match(time_str)
    if(match):
        dd = match.group(1)
        mm = match.group(2)
        yy = match.group(3)
        hr = match.group(4)
        mn = match.group(5)
        ss = match.group(6)

        # month_mapping: a mapping for 3 letter months to integers
        d1 = datetime.datetime(int(yy), int(mm), int(dd), int(hr), int(mn), int(ss))
        d1_tuple = d1.timetuple()
        secondsF = calendar.timegm(d1_tuple)
        sec = int(secondsF)
    return(sec)


def get_timestamp_delayed_sec():
    """
    Modify the time accessor to get Epoc (Unix time)
    @return: Time in seconds since 1970
    """
    s = get_timestamp_delayed('%d-%m-%Y %H:%M:%S %Z')
    tsec = convert_timestamp_to_sec(s)
    return(tsec)


def get_timestamp_sec():
    """
    Modify the time accessor to get Epoc (Unix time)
    @return: Time in seconds since 1970
    """
    s = get_timestamp('%d-%m-%Y %H:%M:%S %Z')
    tsec = convert_timestamp_to_sec(s)       
#    print("Today: ", time.asctime( time.gmtime(tsec) ))
    return(tsec)


def replace_string_chars(s1, pos, s2):
    """
    Replace characters in a string at the specified string position (index).
    @param s1: Input string for replacement.
    @param pos: Input string index of replace.
    @param s2: - Replacement string.
    @return: New resulting string.
    """
    len2 = len(s2)
    if(pos <= len(s1)):
        if(len2 > 0):
            s1 = s1[0:pos] + s2 + s1[pos+len2:]
    return(s1)


###############################################################################
# General Class Definitions
###############################################################################   
class SamiConfiguration():
    """
    Sami PCO2W Configuration String Management Class.
    This class is to contain data to manage the Sami Configuration String field formats
    Sami Fields are fixed in position.    """
    _SAMI_DRIVER_PARAM_INDEX = 78  # String index of SAMI-CO2 Driver 4/5 Parameters.   
    _MIN_CONFIG_STR_LENGTH = 132

    # Record types are Control or Data.
    # Data Records: 0x0 - 0x7F
    _DATA_RECORD_RANGE_MIN = 0x00
    _DATA_RECORD_RANGE_MAX = 0x7F

    _DATA_RECORD_TYPE_PH = 0xA  # Not being used right now.
    _DATA_RECORD_TYPE_CO2 = 0x4
    _DATA_RECORD_TYPE_BLANK = 0x5

    # Control Records: 0x80 - 0xFE 
    _CTRL_RECORD_RANGE_MIN = 0x80
    _CTRL_RECORD_RANGE_MAX = 0xFF

    _CTRL_RECORD_TYPE_LAUNCH = 0x80  # Launch - The program started executing, possibly waiting for measurement
    _CTRL_RECORD_TYPE_START = 0x81  # Start - The measurement sequence has started.
    _CTRL_RECORD_TYPE_SHUTDOWN = 0x83  # Good Shutdown.
    _CTRL_RECORD_TYPE_RTS_ENABLE = 0x85  # RTS Handshake is on.
    _CTRL_RECORD_TYPE_GENERIC_EXTERNAL = 0xFF  # Generic External

    # A lock should eliminate concerns about multi-threaded access.
    _lock = None

    # This configuration string is sent to and received from the Sami Instrument.
    # It is used to identify configuration parameters.
    _config_str = None
    _config_valid = False

    # The Unix epoch is the time 00:00:00 UTC on 1 January 1970 (or
    # 1970-01-01T00:00:00Z ISO 8601). 
    _min_time_sec_1970 = 0x0
    _min_time_sec_1904 = 0x0
    _max_time_sec_1970 = 0x0
    _max_time_sec_1904 = 0x0

    def __init__(self):
        self._lock = RLock()
        self._config_str = None
        self._config_valid = False

        # Design Note: This is the max/min time range when setting the
        # instrument time. The time/date should be around "todays" date.

        # Set a time range of allow Confuguration time update.
        # Default earliest time to PDF text book Oct 6, 2011 18:05:56
        t = datetime.datetime(2011, 10, 6, 0, 0)
        tsecF = calendar.timegm(t.timetuple())
        self._min_time_sec_1970 = int(tsecF)
        self._min_time_sec_1904 = self._min_time_sec_1970 + NSECONDS_1904_TO_1970

        # Set a maximum time as current time + 30 days.
        sec_per_day = 3600 * 24
        sec_per_year = 365 * sec_per_day  # good approximation.
        tnow_secF = time.time()   # Current seconds since Epoch
        self._max_time_sec_1970 = int(tnow_secF) + (5 * sec_per_year)
        self._max_time_sec_1904 = self._max_time_sec_1970 + NSECONDS_1904_TO_1970

    def clear(self):
        """
        Clear the configuration string
        """
        self._config_valid = False
        self._config_str = ""
        for i in range(0, 232):
            self._config_str += "0"

    def compare(self, new_config_str):
        """
        Compare a new configuration string against the current.
        @param new_config_str: Sami Instrument Configuration string to check.
        @return: True=Same;None=Invalid;False=Different
        """
        r = None
        min_len = self._MIN_CONFIG_STR_LENGTH
        if((new_config_str != None) & (len(new_config_str) >= min_len)):
            if(self._config_valid is True):
                if( self._config_str[0:min_len] == new_config_str[0:min_len]):
                    r = True
                else:
                    r = False
        return(r)

    def get_config_str(self):
        """
        Get the current configuration string (should have been updated from instrument).
        @return - Configuration String
        """
        return(self._config_str)

    def get_config_time(self, unix_fmt=False):
        """
        Get the current configuration time
        @param unix_fmt: True=Return time in seconds sinc Jan1,1970, False=Time since 1904
        """
        time_txt = self._config_str[0:8]
        if(unix_fmt is True):
            time_sec = int(time_txt, 16)
            time_sec -= NSECONDS_1904_TO_1970
            time_txt = '{:08X}'.format(time_sec)
        return(time_txt)

    def get_start_time(self, unix_fmt=False):
        log.debug("get_start_time...................")
        launch_time_txt = self._config_str[0:8]
        start_offset_txt = self._config_str[8:16]

        launch_time = int(launch_time_txt,16)
        start_offset = int(start_offset_txt,16)

        start_time = launch_time + start_offset
        log.debug("start_time = " + str(hex(start_time)))
        if(unix_fmt is True):
            start_time -= NSECONDS_1904_TO_1970
        return(start_time)

    def is_valid(self):
        """
        Determine if a valid configuration string has been created/read
        @return: True if configuration valid.
        """
        return(self._config_valid)

    def set_config_str(self, s):
        """
        Set a new configuration string.
        @param: s - Configuration String
        @return: False if config-string invalid.
        """
        r = False
        if (self._verify_config(s) is True):
            with self._lock:
                self._config_str = s[0:232]
                self._config_valid = True
                r = True
        return(r)

    def set_config_time(self, time_sec_1970):
        """
        Update the Time/Date field in the configuration string.
        @param: time_sec - Time in seconds since Jan1,1970 (Unix time)
        @return: True if time valid.
        """
        r = False
        # Verify that the time is within the correct range.
        if(time_sec_1970 < self._min_time_sec_1970):
            log.debug("Time too early %d/%d" % (time_sec_1970, self._min_time_sec_1970))
        elif(time_sec_1970 >= self._max_time_sec_1970):
            log.debug("max_time = " + str(self._max_time_sec_1970))
            log.debug("Time too late %d/%d" % (time_sec_1970, self._max_time_sec_1970)
        else:
            sami_time_txt = SamiConfiguration.make_sami_time_string(time_sec_1970)
            self._config_str = sami_time_txt + self._config_str[8:232]
            r = True
        return(r)

    def _verify_config(self, s):
        # Verify length.
        s_len = len(s)
        if( s_len < self._MIN_CONFIG_STR_LENGTH ):
            log.debug("Invalid configuration string length %d/%d [%s]" %(s_len, self._MIN_CONFIG_STR_LENGTH, s))
            return(False)

        # Check for all F's return which indicates configuration is hosed.
        if( s[0:2] == "FF" ):
            log.debug("Error - Configuration File Hosed 0xFF ?")
            return(False)

        # Check time stamp (cheat and use the first two characters).
        # Note as of 2013 CD is the launch time.
        min_launch_time = int("CA",16)
        tcheck = int(s[0:2],16)
        if( tcheck < min_launch_time):
            log.debug("Error - Launch time is before present: CB vs " + str(hex(tcheck)))
            return(False)

        # Check the timestamp now anyway with the early range.
        tsec = 0
        txt = s[0:8]
        try:
            tsec = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Config time invalid %s: [%s]" % (txt,str(e)))

        if( tsec <= self._min_time_sec_1904 ):
            log.debug("Sami Config time invalid " + txt + " " + str(hex(self._min_time_sec_1904)))
            return(False)

        # Sami says these values are always this.
        txt = SamiConfiguration.vb_mid(s,33,2)
        dev_id = int(txt,16)
        txt = SamiConfiguration.vb_mid(s,35,2)
        param_ptr = int(txt,16)
        if( (dev_id > 16) | (param_ptr > 100) ):
            log.debug("Configuration is corrupted or erased! " + str(hex(dev_id)) + " " + str(hex(param_ptr)) )
            return( False )

        return( True )

    @staticmethod
    def calc_crc(s, num_points):
        """
        Compute the checksum for a Sami String.
        @param s: string for check-sum analysis.
        @param num_points: number of bytes (each byte is 2-chars).
        """
        cs = 0
        k = 0
        for i in range(num_points):
    #        print("I= " + str(i) + " " + s[k:k+2] )
            value = int(s[k:k+2],16)  # 2-chars per data point
            cs = cs + value
            k = k + 2
        cs = cs & 0xFF
        return(cs)

    @staticmethod
    def get_error_str(error_no):
        """
        Convert the Sami Error Code into an error string.
        @param error_no: Error Number.
        @return String representation of error number.
        """
        # Error Look Up Table
        # ASCII Hex errors returned from Insturment.
        ERROR_TABLE_SIZE = 18
        sami_error_table = [
            "Wrong Number of Arguments", # 0x00
            "Command Not Implemented",
            "Invalid Arguments",
            "Command Buffer Overflow",
            "Invalid Command Enter A return for a list of commands",
            "Error in config data",
            "> 2000 pages",
            "Invalid Configuration",
            "Bad Key", # 0x08
            "Flash is Open",
            "Flash is Not Open",
            "Too Many Arguments",
            "Too Few Arguments",
            "Memory Full",
            "Not Valid with Echo Off",
            "Unimplemented Extension Index in Configuration",
            "Flash Data not erased",
            "Invalid Arguments"]   # 0x11

        error_str = None
        if((error_no >= 0x0) & (error_no < ERROR_TABLE_SIZE)):
            error_str = sami_error_table[error_no]
        return(error_str)

    @staticmethod
    def vb_mid(s, start, length):
        """
        Basic-Programming mid() function utility.
        Function to extract middle of string (used to be compatible with Sami Sunbeam SW Logic).
        @param: s - Input string
        @param: start - Start Index
        @param: length - Desired string extraction length.
        @return: Middle string
        """
        start = start - 1   # VB uses a 1's based indexing
        end = start + length
        # Limit to input string length.
        s_len = len(s)
        if(end >= s_len):
            s_mid = s[start:]
        else:
            s_mid = s[start:end]
        return s_mid

    @staticmethod
    def make_sami_time_string(time_sec_1970):
        """
        Convert Unix seconds into a Sami-Configuration String time format. 
        @param: time_sec_1970 - Seconds since Jan1,1970 
        """
        sami_time_sec = time_sec_1970 + NSECONDS_1904_TO_1970
        sami_time_str = '{:08X}'.format(sami_time_sec)
        return(sami_time_str)

    @staticmethod
    def make_date_str(time_sec):
        """
        Make a Sami String formatted time.
        @param time_sec: Time (1970 or 1904 based)
        """
        if( time_sec > NSECONDS_1904_TO_1970 ):
            time_sec -= NSECONDS_1904_TO_1970
        txt = time.asctime( time.gmtime(time_sec) )
        return(txt)

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CLOCK_SYNC = 'clock_sync'

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    REGULAR_STATUS_PARSED = 'device_status_parsed'
    IMMEDIATE_STATUS_PARSED = 'immediate_status_parsed'
    CONFIG_PARSED = 'config_parsed'
    DATA_RECORD_PARSED = 'data_record_parsed'
    CONTROL_RECORD_PARSED = 'control_record_parsed'

class InstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that must be sent to the instrument to
    execute the command.
    """
    SET_CONFIGURATION = 'L5A'
    GET_CONFIGURATION = 'L'
    IMMEDIATE_STATUS = 'I'
    QUIT_SESSION = 'Q'
    TAKE_SAMPLE = 'R'
    DEVICE_STATUS = 'S'
    AUTO_STATUS_ON = 'F'           # Automatic Status Update (Ping) at 1Hz.
    AUTO_STATUS_OFF = 'F5A'        # Turn Off 1Hz status updates.

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    # Future: We could add a manual state by putting the configuration "start" time into the future.

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    Extends protocol events to the set defined in the base class.
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER

    ### Common driver commands, should these be promoted?  What if the command isn't supported?
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    
    # Different event because we don't want to expose this as a capability
    ACQUIRE_CONFIGURATION = "PROTOCOL_EVENT_ACQUIRE_CONFIGURATION"
    SCHEDULED_CLOCK_SYNC = 'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_CONFIGURATION = ProtocolEvent.ACQUIRE_CONFIGURATION
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC

class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    # Configuration Parameter Information.
    PUMP_PULSE = 'PUMP_PULSE',
    PUMP_ON_TO_MEASURE = 'PUMP_ON_TO_MEASURE',
    NUM_SAMPLES_PER_MEASURE = 'NUM_SAMPLES_PER_MEASURE',
    NUM_CYCLES_BETWEEN_BLANKS = 'NUM_CYCLES_BETWEEN_BLANKS',
    NUM_REAGENT_CYCLES = 'NUM_REAGENT_CYCLES',
    NUM_BLANK_CYCLES = 'NUM_BLANK_CYCLES',
    FLUSH_PUMP_INTERVAL_SEC = 'FLUSH_PUMP_INTERVAL_SEC',
    STARTUP_BLANK_FLUSH_ENABLE = 'STARTUP_BLANK_FLUSH_ENABLE',
    PUMP_PULSE_POST_MEASURE_ENABLE = 'PUMP_PULSE_POST_MEASURE_ENABLE' # bool
    NUM_EXTRA_PUMP_PULSE_CYCLES = 'num_extra_pump_pulse_cycles'

# Device prompts = There are no prompts.
class Prompt(BaseEnum):
   """
   Device i/o prompts..
   """
   COMMAND = None

###############################################################################
# Data Particles
###############################################################################   
class SamiControlRecordParticleKey(BaseEnum):
    """
    Control Record Data Partical.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    CHECKSUM = 'checksum'

class SamiControlRecordParticle(DataParticle):
    """
    This is for raw Sami PCO2W control record samples.
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

    # Record information received from instrument may be data or control.
    _data_particle_type = DataParticleType.CONTROL_RECORD_PARSED

    def _build_parsed_values(self):
        # Restore the first character we removed for recognition.
        regex1 = CONTROL_RECORD_REGEX_MATCHER
        match = regex1.match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed Record Type4 data: [%s]" % self.raw_data)

        result = self._build_particle(match)
        return(result)

    def _build_particle(self, match):
        result = {}

        # This is the first index of data (after header information)
        DATA_START_INDEX = 15

        unique_id = None
        record_length = None
        record_time = None
        record_type = None
        pt_light_measurements = []
        voltage_battery = None
        thermister_raw = None
        checksum = None

        # Quick verification of match count.
        num_match = match.lastindex + 1
        if( num_match < 4 ):
            log.debug("Control Record - No Match count " + str(num_match))
            return result

        # Quick verification of record_type
        # Avoid issue with match by directly accessing string index.  txt = match.group(3)
        txt = self.raw_data[5:7]
        try:
            record_type = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_type %s: [%s]" % (txt,str(e)))

        if(record_type < 0x80):
            raise SampleException("SamiControlRecordParticle abort on [%s] not in range [0x80-0xFF]" %(txt))

        #
        # Preliminary debug information on record type
        #
        if( record_type == SamiConfiguration._CTRL_RECORD_TYPE_LAUNCH):
            log.debug("start: " + str(record_type))

        elif( record_type == SamiConfiguration._CTRL_RECORD_TYPE_START ):
            log.debug("Control Record Start")

        elif( record_type == SamiConfiguration._CTRL_RECORD_TYPE_SHUTDOWN ):
            log.debug("Good Shutdown")

        elif( record_type == SamiConfiguration._CTRL_RECORD_TYPE_RTS_ENABLE ):
            log.debug("Handshake Turned on (RTS high)")

        # Start: Common record information.
        # Decode Time Stamp since Launch
        txt = match.group(1)
        try:
            unique_id = int(txt, 16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding unique_id %s: [%s]" % (txt,str(e)))

        txt = match.group(2)
        try:
            record_length = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_length %s: [%s]" % (txt,str(e)))

        txt = self.raw_data[7:15]
        try:
            record_time = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_time %s: [%s]" % (txt,str(e)))

        # Compute the checksum for the entire record & compare with data.
        num_bytes = (record_length - 1)  # Do not count last crc-byte.
        num_char = 2 * num_bytes

        # Decode checksum (checksum of data is last record byte).
        txt = self.raw_data[3+num_char:5+num_char]
        try:
            checksum = int(txt, 16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding checksum %s: [%s]" % (txt,str(e)))

        # Compute the checksum now that we have the record length.
        # Skip over the ID character and the 1st byte (+3)
        # Compute the checksum for the entire record & compare with data.
        cs_calc = SamiConfiguration.calc_crc( self.raw_data[3:3+num_char], num_bytes)
        if(checksum != cs_calc):
            raise SampleException("Sami Control Record CRC error %s vs [%s]" %(str(hex(cs_calc)),str(hex(checksum))))
        '''
        log.debug("Control Record Found")
        log.debug("unique_id = " + str(unique_id))    
        log.debug("record_length = " + str(record_length))    
        log.debug("record_type = " + str(hex(record_type)))    
        log.debug("ControlRecord Time = " + str(hex(record_time)) + " " + SamiConfiguration.make_date_str(record_time))
        log.debug("checksum = " + str(checksum))
        '''
        # Extract out the data fields.   
        data_length = record_length
        data_length -= 1 # length byte
        data_length -= 1 # record_type byte
        data_length -= 4 # time.
        data_length -= 1 # checksum byte.

        # nab data.
        k = DATA_START_INDEX
        for i in range(data_length):
            log.debug(self.raw_data[k:k+2])
            k += 2

        result = [{DataParticleKey.VALUE_ID: SamiControlRecordParticleKey.UNIQUE_ID,
                   DataParticleKey.VALUE: unique_id},
                  {DataParticleKey.VALUE_ID: SamiControlRecordParticleKey.RECORD_LENGTH,
                   DataParticleKey.VALUE: record_length},
                  {DataParticleKey.VALUE_ID: SamiControlRecordParticleKey.RECORD_TYPE,
                   DataParticleKey.VALUE: record_type},
                  {DataParticleKey.VALUE_ID: SamiControlRecordParticleKey.RECORD_TIME,
                   DataParticleKey.VALUE: record_time},
                  {DataParticleKey.VALUE_ID: SamiControlRecordParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: checksum}]

        return result

class SamiDataRecordParticleKey(BaseEnum):
    """
    Data Record Data Partical.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    LIGHT_MEASUREMENT = 'light_measurement'
    VOLTAGE_BATTERY = 'voltage_battery'
    THERMISTER_RAW = 'thermister_raw'
    CHECKSUM = 'checksum'

class SamiDataRecordParticle(DataParticle):
    """
    This is for raw Sami PCO2W samples.
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

    # Record information received from instrument may be data or control.
    _data_particle_type = DataParticleType.DATA_RECORD_PARSED

    def _build_parsed_values(self):
        # Restore the first character we removed for recognition.
        regex1 = DATA_RECORD_REGEX_MATCHER
        match = regex1.match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed Record Type4 data: [%s]" % self.raw_data)

        result = self._build_particle(match, len(self.raw_data))
        return(result)

    def _build_particle(self, match,len_raw_data):
        result = {}

        unique_id = None
        record_length = None
        record_time = None
        record_type = None
        pt_light_measurements = []
        voltage_battery = None
        thermister_raw = None
        checksum = None

        # Quick verification of match count.
        num_match = match.lastindex + 1
        if( num_match < 4 ):
            log.debug("SamiDataRecord match invalid")
            return result

        # Do a quick check of the record type.
        # We are ONLY handling record-type 3 or 4.
        txt = match.group(3)
        try:
            record_type = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_type %s: [%s]" % (txt,str(e)))

        if( (record_type != SamiConfiguration._DATA_RECORD_TYPE_CO2) & (record_type != SamiConfiguration._DATA_RECORD_TYPE_BLANK) ):
            raise SampleException("SamiDataRecordParticle abort on [%d] not [%d,%d]" %(record_type, SamiConfiguration._DATA_RECORD_TYPE_CO2, SamiConfiguration._DATA_RECORD_TYPE_BLANK))
            return( result )

        elif( (record_type >= SamiConfiguration._CTRL_RECORD_RANGE_MIN) & (record_type <= SamiConfiguration._CTRL_RECORD_RANGE_MAX) ):
            raise SampleException("SamiDataRecordParticle trying to process Control Record [%d]" %(record_type))
            return( result )

        elif( record_type == SamiConfiguration._DATA_RECORD_TYPE_PH ):
            raise SampleException("SamiDataRecordParticle trying to process Ph Data Record [%d]" %(record_type))
            return( result )

        # Start: Common record information.
        # Decode Time Stamp since Launch
        txt = match.group(1)
        try:
            unique_id = int(txt, 16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding unique_id %s: [%s]" % (txt,str(e)))

        txt = match.group(2)
        try:
            record_length = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_length %s: [%s]" % (txt,str(e)))

        txt = match.group(4)
        try:
            record_time = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Record ValueError decoding record_time %s: [%s]" % (txt,str(e)))
        '''
        log.debug("unique_id = " + str(unique_id))
        log.debug("record_length = " + str(record_length))
        log.debug("record type = " + str(record_type))
        log.debug("record time = " + str(record_time) + " " + txt + " " + SamiConfiguration.make_date_str(record_time))
        '''
        # End: Common Record Information.

        # Verify length information.
        # The record length is the number of "2-char" bytes.
        if((2*record_length) > len_raw_data):
            log.debug("Sami Record String too small %d/%d" %(len_raw_data, (2*record_length)))
            return(result)

        # Record Type #4,#5 have a length of 39 bytes, time & trailing checksum.
        if( (record_type == SamiConfiguration._DATA_RECORD_TYPE_CO2) |
            (record_type == SamiConfiguration._DATA_RECORD_TYPE_BLANK) ):

            # Compute now many 8-bit data bytes we have.
            data_length = record_length
            data_length = data_length - 6  # Adjust for type, 4-bytes of time.
            data_length = data_length - 5  # Adjust for battery, thermister, cs
            num_measurements = data_length / 2  # 2-bytes per record.
            # log.debug("num_measurments = " + str(num_measurements))

            # Start extracting measurements from this string position
            idx = 15
            for i in range(0,num_measurements):
                txt = self.raw_data[idx:idx+4]
                try:
                    val = int(txt, 16)
                except Exception, e:
                    raise SampleException("Sami Record ValueError decoding value %d,%s: [%s]" % (i,txt,str(e)))
                log.debug("light_measurement = " + txt)
                pt_light_measurements.append(val)
                idx = idx + 4

            txt = self.raw_data[idx:idx+3]
            try:
                voltage_battery = int(txt, 16)
            except Exception, e:
                raise SampleException("Sami Record ValueError decoding voltage_battery %s: [%s]" % (txt,str(e)))
            idx = idx + 4

            txt = self.raw_data[idx:idx+3]
            try:
                thermister_raw = int(txt, 16) 
            except Exception, e:
                raise SampleException("Sami Record ValueError decoding thermister_raw %s: [%s]" % (txt,str(e)))
            idx = idx + 4

            # Decode checksum
            txt = self.raw_data[idx:idx+2]
            try:
                checksum = int(txt, 16)
            except Exception, e:
                raise SampleException("Sami Record ValueError decoding checksum %s: [%s]" % (txt,str(e)))

            # Compute the checksum now that we have the record length.
            # Skip over the ID character and the 1st byte (+3)
            # Compute the checksum for the entire record & compare with data.
            num_bytes = (record_length - 1)
            num_char = 2 * num_bytes
            cs_calc = SamiConfiguration.calc_crc( self.raw_data[3:3+num_char], num_bytes)
            if(checksum != cs_calc):
                raise SampleException("Sami Data Record CRC error %s vs [%s]" %(str(hex(cs_calc)),str(hex(checksum))))
            '''
            log.debug("voltage_battery = " + str(voltage_battery))
            log.debug("thermister_raw = " + str(thermister_raw))
            log.debug("Record Checksup = " + str(hex(checksum)) + " versus " + str(hex(cs_calc)))
            '''
            result = [{DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.UNIQUE_ID,
                       DataParticleKey.VALUE: unique_id},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.RECORD_LENGTH,
                       DataParticleKey.VALUE: record_length},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.RECORD_TYPE,
                       DataParticleKey.VALUE: record_type},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.RECORD_TIME,
                       DataParticleKey.VALUE: record_time},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.VOLTAGE_BATTERY,
                       DataParticleKey.VALUE: voltage_battery},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.THERMISTER_RAW,
                       DataParticleKey.VALUE: thermister_raw},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.CHECKSUM,
                       DataParticleKey.VALUE: checksum},
                      {DataParticleKey.VALUE_ID: SamiDataRecordParticleKey.LIGHT_MEASUREMENT,
                       DataParticleKey.VALUE: pt_light_measurements}]

        log.debug("Data Record Decoder End...........")

        return result

class SamiConfigDataParticleKey(BaseEnum):
    """
    Configuration String Data Partical.
    """
    LAUNCH_TIME = 'launch_time'
    START_TIME_OFFSET = 'start_time_offset'
    RECORDING_TIME = 'recording_time'
    # Mode Bits.
    PMI_SAMPLE_SCHEDULE = 'pmi_sample_schedule'
    SAMI_SAMPLE_SCHEDULE = 'sami_sample_schedule'
    SLOT1_FOLLOWS_SAMI_SCHEDULE = 'slot1_follows_sami_sample'
    SLOT1_INDEPENDENT_SCHEDULE  = 'slot1_independent_schedule'
    SLOT2_FOLLOWS_SAMI_SCHEDULE = 'slot2_follows_sami_sample'
    SLOT2_INDEPENDENT_SCHEDULE  = 'slot2_independent_schedule'
    SLOT3_FOLLOWS_SAMI_SCHEDULE = 'slot3_follows_sami_sample'
    SLOT3_INDEPENDENT_SCHEDULE  = 'slot3_independent_schedule'    
    # Timer,Device,Pointer Triples
    TIMER_INTERVAL_SAMI = 'timer_interval_sami'
    DRIVER_ID_SAMI = 'driver_id_sami'
    PARAM_PTR_SAMI = 'param_ptr_sami'
    TIMER_INTERVAL_1 = 'timer_interval_1'
    DRIVER_ID_1 = 'driver_id_1'
    PARAM_PTR_1 = 'param_ptr_1'
    TIMER_INTERVAL_2 = 'timer_interval_2'
    DRIVER_ID_2 = 'driver_id_2'
    PARAM_PTR_2 = 'param_ptr_2'
    TIMER_INTERVAL_3 = 'timer_interval_3'
    DRIVER_ID_3 = 'driver_id_3'
    PARAM_PTR_3 = 'param_ptr_3'
    TIMER_INTERVAL_PRESTART = 'timer_interval_prestart'
    DRIVER_ID_PRESTART = 'driver_id_prestart'
    PARAM_PTR_PRESTART = 'param_ptr_prestart'
    
    # Global Configuration Settings Register for PCO2    
    USE_BAUD_RATE_9600 = "use_baud_rate_9600"
    SEND_RECORD_TYPE_EARLY = "send_record_type_early"
    SEND_LIVE_RECORDS = "send_live_records"

    # PCO2 Pump Driver
    PUMP_PULSE = "pump_pulse"
    PUMP_ON_TO_MEAURSURE = "pump_on_to_measure"
    SAMPLES_PER_MEASURE = "samples_per_measure"
    CYCLES_BETWEEN_BLANKS = "cycles_between_blanks"
    NUM_REAGENT_CYCLES = "num_reagent_cycles"
    NUM_BLANK_CYCLES = "num_blank_cycles"
    FLUSH_PUMP_INTERVAL = "flush_pump_interval"
    BLANK_FLUSH_ON_START_ENABLE = "blank_flush_on_start_enable"
    PUMP_PULSE_POST_MEASURE = "pump_pulse_post_measure"
    NUM_EXTRA_PUMP_PULSE_CYCLES = "num_extra_pump_pulse_cycles"

    # Not in specification.
    # CHECKSUM = "checksum"
    # SERIAL_SETTINGS = 'serial_settings'

class SamiConfigDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.CONFIG_PARSED
    # The CRC is returned from the Sami Instrument when a new configuration is written (L5A)
    _config_crc = None  # Last downloaded configuration CRC value.

    def _build_parsed_values(self):
        result = {}

        log.debug(">>>>>>>>>>>>>>>>>>>> SamiConfigDataParticle Build Parsed Config Values ")
        # Restore the first character we removed for recognition.
        # TODO: Improve logic to not rely on 1st character of "C"

        # Mode Data Bit Definitions.
        MODE_PMI_SAMPLE_SCHEDULE = 0x01           # Prestart Schedule Enabled.
        MODE_SAMI_SAMPLE_SCHEDULE = 0x02          # Sami Schedule Enabled
        MODE_SLOT1_FOLLOWS_SAMI_SAMPLE  = 0x04    # External Device-1
        MODE_SLOT1_INDEPENDENT_SCHEDULE = 0x08
        MODE_SLOT2_FOLLOWS_SAMI_SAMPLE  = 0x10    # External Device-2
        MODE_SLOT2_INDEPENDENT_SCHEDULE = 0x20
        MODE_SLOT3_FOLLOWS_SAMI_SAMPLE  = 0x40     # External Device-3
        MODE_SLOT3_INDEPENDENT_SCHEDULE = 0x80

        # Global Configuration Data Bits Definitions.
        CFG_GLOBAL_BAUD_RATE_57600 = 0x1
        CFG_GLOBAL_SEND_RECORD_TYPE_EARLY = 0x2
        CFG_GLOBAL_SEND_LIVE_RECORDS = 0x4

        # Restore the first character that was used as an indentifier.
        # CJC: This id is not very unique!
        raw_data = self.raw_data
        regex1 = CONFIG_REGEX_MATCHER

        match = regex1.match(raw_data)
        if not match:
            raise SampleException("No regex match of parsed config data: [%s]" % raw_data)

        # Make sure we can decode all the requested groups.
        num_groups = match.lastindex + 1
        if( num_groups < 35 ):
            log.debug("SamiConfig invalid match count %d/35" %(num_groups))
            return(result)

        # Return parameter initialization
        program_date_time = None
        start_time_offset = None
        recording_time = None

        # Mode Bits
        pmi_sample_schedule = None
        sami_sample_schedule = None
        slot1_follows_sami_sample  = None
        slot1_independent_schedule = None
        slot2_follows_sami_sample  = None
        slot2_independent_schedule = None
        slot3_follows_sami_sample  = None
        slot3_independent_schedule = None

        # Global Configuration Register
        use_baud_rate_9600 = None  # 57600 / 9600
        send_record_type_early = None
        send_live_records = None

        # CO2 Settings.
        pump_pulse = None
        pump_on_to_measure = None
        samples_per_measure = None
        cycles_between_blanks = None
        num_reagent_cycles = None
        num_blank_cycles = None
        flush_pump_interval = None
        bit_switch = None
        blank_flush_on_start_enable = None
        pump_pulse_post_measure = None
        num_extra_pump_pulse_cycles = None

        # Not used and hard-coded right now.
        serial_settings = None

        timer_interval_list = []
        driver_id_list = []
        param_ptr_list = []

        # Decode Time Stamp since Launch
        txt = match.group(1)
        txt = "C" + txt   # Add back in Match character.
        try:
            program_date_time = int(txt,16)
        except Exception, e:
            raise SampleException("ValueError decoding Config DateTime: [%s] [%s]" % (txt,str(e)))

        txt = match.group(2)
        try:
            start_time_offset = int(txt,16)
        except Exeption, e:
            raise SampleException("ValueError decoding Config StartTime: [%s] [%s]" % (txt,str(e)))

        txt = match.group(3)
        try:
            recording_time = int(txt,16)
        except Exeption, e:
            raise SampleException("ValueError decoding Config RecordingTime: [%s] [%s]" % (txt,str(e)))

        '''
        log.debug("program_date_time = " + str(hex(program_date_time)))
        log.debug("start_time_offset = " + str(hex(start_time_offset)))
        log.debug("recording_time = " + str(hex(recording_time)))
        '''
        self.contents[SamiConfigDataParticleKey.LAUNCH_TIME] = program_date_time
        self.contents[SamiConfigDataParticleKey.START_TIME_OFFSET] = start_time_offset
        self.contents[SamiConfigDataParticleKey.RECORDING_TIME] = recording_time  # Time from start to stop.

        # Decode the Mode Bits.
        txt = match.group(4)
        mode = int(txt,16)
        pmi_sample_schedule  = bool(mode & MODE_PMI_SAMPLE_SCHEDULE)
        sami_sample_schedule = bool(mode & MODE_SAMI_SAMPLE_SCHEDULE)
        slot1_follows_sami_sample  = bool(mode & MODE_SLOT1_FOLLOWS_SAMI_SAMPLE)
        slot1_independent_schedule = bool(mode & MODE_SLOT1_INDEPENDENT_SCHEDULE)
        slot2_follows_sami_sample  = bool(mode & MODE_SLOT2_FOLLOWS_SAMI_SAMPLE)
        slot2_independent_schedule = bool(mode & MODE_SLOT2_INDEPENDENT_SCHEDULE)
        slot3_follows_sami_sample  = bool(mode & MODE_SLOT3_FOLLOWS_SAMI_SAMPLE)
        slot3_independent_schedule = bool(mode & MODE_SLOT3_INDEPENDENT_SCHEDULE)

        # Debug
        '''
        log.debug("pmi_sample_schedule = " + str(pmi_sample_schedule))
        log.debug("sami_sample_schedule = " + str(sami_sample_schedule))
        log.debug("slot1_follows_sami_sample = " + str(slot1_follows_sami_sample))
        log.debug("slot1_independent_schedule = " + str(slot1_independent_schedule))
        log.debug("slot2_follows_sami_sample = " + str(slot2_follows_sami_sample))
        log.debug("slot2_independent_schedule = " + str(slot2_independent_schedule))
        log.debug("slot3_follows_sami_sample = " + str(slot3_follows_sami_sample))
        log.debug("slot3_independent_schedule = " + str(slot3_independent_schedule))
        '''

        # Loop through the 5 groups of device information.
        timer_interval = None
        driver_id = None
        param_ptr = None

        idx = 5
        device_group = []
        for i in range(5):
            #
            # Decode Timer
            txt = match.group(idx)
            try:
                timer_interval = int(txt,16)
            except Exception, e:
                raise SampleException("ValueError decoding Config Timer %d: [%s] [%s]" % (i,txt,str(e)))

            timer_interval_list.append( timer_interval )
            #
            # Decode Driver ID
            txt = match.group(idx+1)
            try:
                driver_id = int(txt,16)
            except Exception, e:
                raise SampleException("ValueError decoding Config DriverID %d: [%s] [%s]" % (i,txt,str(e)))

            driver_id_list.append( driver_id )

            #
            # Decode Parameter Pointer
            txt = match.group(idx+2)
            try:
                param_ptr = int(txt,16)
            except Exception, e:
                raise SampleException("ValueError decoding Config ParamPtr %d: [%s] [%s]" % (i,txt,str(e)))
            param_ptr_list.append( param_ptr )
            idx = idx + 3

            '''
            log.debug(" timer_interval = " + str(timer_interval))
            log.debug(" driver_id = " + str(driver_id))
            log.debug(" param_ptr = " + str(param_ptr))
            '''

            # Put Timer,Device,Pointer Triples into their categories
            if( i == 0):
                self.contents[SamiConfigDataParticleKey.TIMER_INTERVAL_SAMI] = timer_interval;
                self.contents[SamiConfigDataParticleKey.DRIVER_ID_SAMI] = driver_id;
                self.contents[SamiConfigDataParticleKey.PARAM_PTR_SAMI] = param_ptr;
            elif( i == 1):
                self.contents[SamiConfigDataParticleKey.TIMER_INTERVAL_1] = timer_interval;
                self.contents[SamiConfigDataParticleKey.DRIVER_ID_1] = driver_id;
                self.contents[SamiConfigDataParticleKey.PARAM_PTR_1] = param_ptr;
            elif( i == 2):
                self.contents[SamiConfigDataParticleKey.TIMER_INTERVAL_2] = timer_interval;
                self.contents[SamiConfigDataParticleKey.DRIVER_ID_2] = driver_id;
                self.contents[SamiConfigDataParticleKey.PARAM_PTR_2] = param_ptr;
            elif( i == 3):
                self.contents[SamiConfigDataParticleKey.TIMER_INTERVAL_3] = timer_interval;
                self.contents[SamiConfigDataParticleKey.DRIVER_ID_3] = driver_id;
                self.contents[SamiConfigDataParticleKey.PARAM_PTR_3] = param_ptr;
            elif( i == 4):
                self.contents[SamiConfigDataParticleKey.TIMER_INTERVAL_PRESTART] = timer_interval;
                self.contents[SamiConfigDataParticleKey.DRIVER_ID_PRESTART] = driver_id;
                self.contents[SamiConfigDataParticleKey.PARAM_PTR_PRESTART] = param_ptr;                
        # end for

        # The next byte is the Global Configuration Switches.
        txt = match.group(idx)
        idx = idx + 1
        try:
            cfg_reg = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Config-Global_Register (%s) Fatal: %s" % (txt,str(e)))   

        # A Bit "set" indicates 57600 Baud rate, else 9600 so we have to invert logic
        use_baud_rate_9600 = bool(cfg_reg & CFG_GLOBAL_BAUD_RATE_57600) == False
        send_record_type_early = bool(cfg_reg & CFG_GLOBAL_SEND_RECORD_TYPE_EARLY)
        send_live_records = bool(cfg_reg & CFG_GLOBAL_SEND_LIVE_RECORDS)

        self.contents[SamiConfigDataParticleKey.USE_BAUD_RATE_9600]     = use_baud_rate_9600
        self.contents[SamiConfigDataParticleKey.SEND_RECORD_TYPE_EARLY] = send_record_type_early
        self.contents[SamiConfigDataParticleKey.SEND_LIVE_RECORDS]      = send_live_records

        # Decode the PCO2 Configruation Parameters
        txt = match.group(idx)
        idx = idx + 1
        pump_pulse = int(txt,16)

        txt = match.group(idx)
        idx = idx + 1
        pump_on_to_measure = int(txt,16)

        txt = match.group(idx)
        idx = idx + 1
        samples_per_measure = int(txt,16)

        txt = match.group(idx)
        idx = idx + 1
        cycles_between_blanks = int(txt,16)

        txt = match.group(idx)
        idx = idx + 1
        num_reagent_cycles = int(txt,16)
        
        txt = match.group(idx)
        idx = idx + 1
        num_blank_cycles = int(txt,16)

        txt = match.group(idx)
        idx = idx + 1
        flush_pump_interval = int(txt,16)

        # Read/Decode Bit Switch Settings.
        txt = match.group(idx)
        idx = idx + 1
        try:
            bit_switch = int(txt,16)
        except Exception, e:
            raise SampleException("Sami Config Bit-Switch (%s) Fatal: %s" % (txt,str(e)))   

        blank_flush_on_start_enable = (bool(bit_switch & 0x1) == False)  # Logic Inverted.
        pump_pulse_post_measure = bool(bit_switch & 0x2)

        txt = match.group(idx)
        idx = idx + 1
        num_extra_pump_pulse_cycles = int(txt,16)

        # PCO2 Pump Data Parameter Updates.
        self.contents[SamiConfigDataParticleKey.PUMP_PULSE] = pump_pulse
        self.contents[SamiConfigDataParticleKey.PUMP_ON_TO_MEAURSURE] = pump_on_to_measure
        self.contents[SamiConfigDataParticleKey.SAMPLES_PER_MEASURE] = samples_per_measure
        self.contents[SamiConfigDataParticleKey.CYCLES_BETWEEN_BLANKS] = cycles_between_blanks
        self.contents[SamiConfigDataParticleKey.NUM_REAGENT_CYCLES] = num_reagent_cycles
        self.contents[SamiConfigDataParticleKey.NUM_BLANK_CYCLES] = num_blank_cycles
        self.contents[SamiConfigDataParticleKey.FLUSH_PUMP_INTERVAL] = flush_pump_interval
        self.contents[SamiConfigDataParticleKey.BLANK_FLUSH_ON_START_ENABLE] = blank_flush_on_start_enable
        self.contents[SamiConfigDataParticleKey.PUMP_PULSE_POST_MEASURE] = pump_pulse_post_measure
        self.contents[SamiConfigDataParticleKey.NUM_EXTRA_PUMP_PULSE_CYCLES] = num_extra_pump_pulse_cycles

        '''
        log.debug("Decoding string: " + raw_data[SamiConfiguration._SAMI_DRIVER_PARAM_INDEX:SamiConfiguration._SAMI_DRIVER_PARAM_INDEX+18])
        log.debug("pump_pulse = " + str(hex(pump_pulse)))
        log.debug("pump_on_to_measure = " + str(hex(pump_on_to_measure)))
        log.debug("samples_per_measure = " + str(hex(samples_per_measure)))
        log.debug("cycles_between_blanks = " + str(hex(cycles_between_blanks)))
        log.debug("num_reagent_cycles = " + str(hex(num_reagent_cycles)))
        log.debug("num_blank_cycles = " + str(hex(num_blank_cycles)))
        log.debug("flush_pump_interval = " + str(hex(flush_pump_interval)))
        log.debug("bit_switch = " + str(hex(bit_switch)))                   
        log.debug("blank_flush_on_start_enable = " + str(blank_flush_on_start_enable))
        log.debug("pump_pulse_post_measure = " + str(pump_pulse_post_measure))
        log.debug("num_extra_pump_pulse_cycles = " + str(hex(num_extra_pump_pulse_cycles)))
        '''

        # Serial settings is next match.
        txt = match.group(idx)
        idx = idx + 1
        serial_settings = txt

        # These parameters are not currently used.
        duration_1_txt = match.group(idx)
        idx = idx + 1
        duration_2_txt = match.group(idx)
        idx = idx + 1
        unused_txt = match.group(idx)
        idx = idx + 1

        log.debug("  ** index = " + str(idx))

        '''
        log.debug("serial_settings = " + serial_settings)
        log.debug("duration1: " + duration_1_txt)
        log.debug("duration2: " + duration_2_txt )
        log.debug("Meaningless parameter: " + unused_txt )
        '''

        # Every driver that has a parser that parses a particle timestamp will need to be updated.
        # Store the timestamp using a unix time.
        tsec_unix = program_date_time - NSECONDS_1904_TO_1970
        self.set_internal_timestamp(tsec_unix)

        # Store the timestamp using an ntp timestamp.
        # Return the results as a list.
        result = [{DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.LAUNCH_TIME,
                   DataParticleKey.VALUE: program_date_time},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.START_TIME_OFFSET,
                   DataParticleKey.VALUE: start_time_offset},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.RECORDING_TIME,
                   DataParticleKey.VALUE: recording_time},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PMI_SAMPLE_SCHEDULE,
                   DataParticleKey.VALUE: pmi_sample_schedule},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                   DataParticleKey.VALUE: sami_sample_schedule},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                   DataParticleKey.VALUE: slot1_follows_sami_sample},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                   DataParticleKey.VALUE: slot1_independent_schedule},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                   DataParticleKey.VALUE: slot2_follows_sami_sample},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                   DataParticleKey.VALUE: slot2_independent_schedule},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                   DataParticleKey.VALUE: slot3_follows_sami_sample},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE,
                   DataParticleKey.VALUE: slot3_independent_schedule},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.TIMER_INTERVAL_SAMI,
                   DataParticleKey.VALUE: timer_interval_list[0]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.DRIVER_ID_SAMI,
                   DataParticleKey.VALUE: driver_id_list[0]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PARAM_PTR_SAMI,
                   DataParticleKey.VALUE: param_ptr_list[0]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.TIMER_INTERVAL_1,
                   DataParticleKey.VALUE: timer_interval_list[1]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.DRIVER_ID_1,
                   DataParticleKey.VALUE: driver_id_list[1]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PARAM_PTR_1,
                   DataParticleKey.VALUE: param_ptr_list[1]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.TIMER_INTERVAL_2,
                   DataParticleKey.VALUE: timer_interval_list[2]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.DRIVER_ID_2,
                   DataParticleKey.VALUE: driver_id_list[2]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PARAM_PTR_2,
                   DataParticleKey.VALUE: param_ptr_list[2]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.TIMER_INTERVAL_3,
                   DataParticleKey.VALUE: timer_interval_list[3]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.DRIVER_ID_3,
                   DataParticleKey.VALUE: driver_id_list[3]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PARAM_PTR_3,
                   DataParticleKey.VALUE: param_ptr_list[3]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.TIMER_INTERVAL_PRESTART,
                   DataParticleKey.VALUE: timer_interval_list[4]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.DRIVER_ID_PRESTART,
                   DataParticleKey.VALUE: driver_id_list[4]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PARAM_PTR_PRESTART,
                   DataParticleKey.VALUE: param_ptr_list[4]},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.USE_BAUD_RATE_9600,
                   DataParticleKey.VALUE: use_baud_rate_9600},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SEND_RECORD_TYPE_EARLY,
                   DataParticleKey.VALUE: send_record_type_early},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SEND_LIVE_RECORDS,
                   DataParticleKey.VALUE: send_live_records},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PUMP_PULSE,
                   DataParticleKey.VALUE: pump_pulse},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PUMP_ON_TO_MEAURSURE,
                  DataParticleKey.VALUE: pump_on_to_measure},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.SAMPLES_PER_MEASURE,
                   DataParticleKey.VALUE: samples_per_measure},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.CYCLES_BETWEEN_BLANKS,
                  DataParticleKey.VALUE: cycles_between_blanks},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.NUM_REAGENT_CYCLES,
                  DataParticleKey.VALUE: num_reagent_cycles},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.NUM_BLANK_CYCLES,
                   DataParticleKey.VALUE: num_blank_cycles},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.FLUSH_PUMP_INTERVAL,
                  DataParticleKey.VALUE: flush_pump_interval},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.BLANK_FLUSH_ON_START_ENABLE,
                   DataParticleKey.VALUE: blank_flush_on_start_enable},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.PUMP_PULSE_POST_MEASURE,
                   DataParticleKey.VALUE: pump_pulse_post_measure},
                  {DataParticleKey.VALUE_ID: SamiConfigDataParticleKey.NUM_EXTRA_PUMP_PULSE_CYCLES,
                   DataParticleKey.VALUE: num_extra_pump_pulse_cycles}]
        return result

class SamiImmediateStatusDataParticleKey(BaseEnum):
    PUMP_ON = "pump_on",
    VALVE_ON = "valve_on",
    EXTERNAL_POWER_ON = "external_power_on",
    DEBUG_LED = "debug_led_on",
    DEBUG_ECHO = "debug_echo_on"

class SamiImmediateStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.IMMEDIATE_STATUS_PARSED

    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags
        @throws SampleException If there is a problem with sample creation
        """
        regex1 = IMMEDIATE_STATUS_REGEX_MATCHER
        match = regex1.match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" % self.raw_data)

        pump_on = None
        valve_on = None
        external_power_on = None
        debug_led_on = None
        debug_echo_on = None

        txt = match.group(1)
        status_word = int(txt,16)

        pump_on  = bool(status_word & 0x01)
        valve_on = bool(status_word & 0x02)
        external_power_on = bool(status_word & 0x04)
        debug_led  = bool(status_word & 0x10)
        debug_echo = bool(status_word & 0x20)
        '''
        log.debug("status_word = " + str(hex(status_word)))
        log.debug("pump_on = " + str(pump_on))
        log.debug("valve_on = " + str(valve_on))
        log.debug("external_power_on = " + str(external_power_on))
        log.debug("debug_led_on  = " + str(debug_led))
        log.debug("debug_echo_on = " + str(debug_echo))
        '''
        result = [{DataParticleKey.VALUE_ID: SamiImmediateStatusDataParticleKey.PUMP_ON,
                   DataParticleKey.VALUE: pump_on},
                  {DataParticleKey.VALUE_ID: SamiImmediateStatusDataParticleKey.VALVE_ON,
                   DataParticleKey.VALUE: valve_on},
                  {DataParticleKey.VALUE_ID: SamiImmediateStatusDataParticleKey.EXTERNAL_POWER_ON,
                   DataParticleKey.VALUE: external_power_on},
                  {DataParticleKey.VALUE_ID: SamiImmediateStatusDataParticleKey.DEBUG_LED,
                   DataParticleKey.VALUE: debug_led},
                  {DataParticleKey.VALUE_ID: SamiImmediateStatusDataParticleKey.DEBUG_ECHO,
                   DataParticleKey.VALUE: debug_echo} ]

        return result

class SamiRegularStatusDataParticleKey(BaseEnum):
    ELAPSED_TIME_CONFIG = "elapsed_time_config "
    CLOCK_ACTIVE = "clock_active"
    RECORDING_ACTIVE = "recording_active"
    RECORD_END_ON_TIME = "record_end_on_time"
    RECORD_MEMORY_FULL = "record_memory_full"
    RECORD_END_ON_ERROR = "record_end_on_error"
    DATA_DOWNLOAD_OK = "data_download_ok"
    FLASH_MEMORY_OPEN = "flash_memory_open"
    BATTERY_FATAL_ERROR = "battery_fatal_error"
    BATTERY_LOW_MEASUREMENT = "battery_low_measurement"
    BATTERY_LOW_BANK = "battery_low_bank"
    BATTERY_LOW_EXTERNAL = "battery_low_external"
    EXTERNAL_DEVICE_FAULT = "external_device_fault"
    FLASH_ERASED = "flash_erased"
    POWER_ON_INVALID = "power_on_invalid"

class SamiRegularStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.REGULAR_STATUS_PARSED

    def _build_parsed_values(self):
        """
        The Regular Status information is instrument read-only data.
        @throws SampleException If there is a problem with sample creation
        """
        result = {}

        regex1 = REGULAR_STATUS_REGEX_MATCHER
        match = regex1.match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed regular status data: [%s]" % self.raw_data)

        # 2 Groups of data requlred for decoding.
        num_groups = match.lastindex + 1
        if( num_groups < 2 ):
            log.debug("Sami Regular Status Invalid decode %d/2" %(num_groups))
            return( result )

        # initialize
        elapsed_time_config  = None
        clock_active         = None
        recording_active     = None
        record_end_on_time   = None
        record_memory_full   = None
        record_end_on_error  = None
        record_data_download_ok = None
        record_flash_open    = None
        battery_fatal_error  = None
        battery_low_measurement = None
        battery_low_bank     = None
        battery_low_external = None
        external_device_fault = None
        flash_erased     = None
        power_on_invalid = None

        txt = match.group(1)
        try:
            # Decode Time Stamp since Launch
            time_offset = int(txt,16)
        except ValueError:
            raise SampleException("ValueError while decoding data: [%s]" %
                                  self.raw_data)

        # All F's indicates no valid configuration file defined.
        if( time_offset == 0xFFFFFFFF ):
            log.debug("Invalid Time Offset Found! " + str(hex(time_offset)))
            return(result)

        # Decode the device status word.
        try:
            # Decode Bit-fields.
            txt = match.group(2)
            status_word = int(txt,16)

        except IndexError:
            #These are optional. Quietly ignore if they dont occur.
            pass

        else:
            # Decode the status word.
            clock_active         = bool(status_word & 0x001)
            recording_active     = bool(status_word & 0x002)
            record_end_on_time   = bool(status_word & 0x004)
            record_memory_full   = bool(status_word & 0x008)
            record_end_on_error  = bool(status_word & 0x010)
            data_download_ok     = bool(status_word & 0x020)
            flash_memory_open    = bool(status_word & 0x040)
            battery_fatal_error  = bool(status_word & 0x080)
            battery_low_measurement = bool(status_word & 0x100)
            battery_low_bank     = bool(status_word & 0x200)
            battery_low_external = bool(status_word & 0x400)

            '''
            # Debug Output
            m, s = divmod(time_offset, 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            log.debug("elapsed_time_config " + str(time_offset))
            log.debug("elapsed_time_config = %d %d:%02d:%02d" % (d, h, m, s) )
            log.debug("status word = " + str(hex(status_word)))
            log.debug("clock_active " + str(clock_active))
            log.debug("recording_active " + str(recording_active))
            log.debug("record_end_on_time " + str(record_end_on_time))
            log.debug("record_memory_full " + str(record_memory_full))
            log.debug("record_end_on_error " + str(record_end_on_error))
            log.debug("data_download_ok " + str(data_download_ok))
            log.debug("flash_memory_open " + str(flash_memory_open))
            log.debug("battery_fatal_error " + str(battery_fatal_error))
            log.debug("battery_low_measurement " + str(battery_low_measurement))
            '''
            # Or bits together for External fault information (Bit-0 = Dev-1, Bit-1 = Dev-2)
            external_device_fault = 0x0
            if( bool(status_word & 0x0800) is True ):
                external_device_fault = external_device_fault | 0x1
            if( bool(status_word & 0x1000) is True ):
                external_device_fault = external_device_fault | 0x2
            if( bool(status_word & 0x2000) is True ):
                external_device_fault = external_device_fault | 0x4

            flash_erased     = bool(status_word & 0x4000)
            power_on_invalid = bool(status_word & 0x8000)

            result = [{DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG,
                       DataParticleKey.VALUE: time_offset },
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
                       DataParticleKey.VALUE: clock_active},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.RECORDING_ACTIVE,
                       DataParticleKey.VALUE: recording_active},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME,
                       DataParticleKey.VALUE: record_end_on_time},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL,
                       DataParticleKey.VALUE: record_memory_full},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR,
                       DataParticleKey.VALUE: record_end_on_error},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK,
                       DataParticleKey.VALUE: data_download_ok},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN,
                       DataParticleKey.VALUE: flash_memory_open},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.BATTERY_FATAL_ERROR,
                       DataParticleKey.VALUE: battery_fatal_error},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT,
                       DataParticleKey.VALUE: battery_low_measurement},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK,
                       DataParticleKey.VALUE: battery_low_bank},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL,
                       DataParticleKey.VALUE: battery_low_external},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE_FAULT,
                       DataParticleKey.VALUE: external_device_fault},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.FLASH_ERASED,
                       DataParticleKey.VALUE: flash_erased},
                      {DataParticleKey.VALUE_ID: SamiRegularStatusDataParticleKey.POWER_ON_INVALID,
                       DataParticleKey.VALUE: power_on_invalid}]
        return result

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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    '''
    Note: Manage the current Sami Configuration information with this class.
    Build a new configuration string to send to the instrument (if it has changed)    
    '''
    _sami_config = None
    _sami_new_config_str = None

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build a new configuration string from the parameters and keep it here.
        # If the configuration has changed then we can write a new one to the instrument.
        
        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent, 
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,   self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,   self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_CONFIGURATION,self._handler_command_acquire_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC,       self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC,self._handler_command_clock_sync)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS,  self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC,self._handler_command_clock_sync)

        # Define a method to manage Sami Configuration updates. Sami Instrument Configurations
        # should be kept to a minimum.
        self._sami_config = SamiConfiguration()
        self._sami_new_config_str = None
        
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.AUTO_STATUS_OFF,     self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEVICE_STATUS,       self._build_simple_command)  # Regular Status.
        self._add_build_handler(InstrumentCmds.IMMEDIATE_STATUS,    self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TAKE_SAMPLE,         self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_CONFIGURATION,   self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SET_CONFIGURATION,   self._build_config_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.DEVICE_STATUS,     self._parse_S_response)
        self._add_response_handler(InstrumentCmds.IMMEDIATE_STATUS,  self._parse_I_response)
        self._add_response_handler(InstrumentCmds.TAKE_SAMPLE,       self._parse_R_response)
        self._add_response_handler(InstrumentCmds.GET_CONFIGURATION, self._parse_config_response)
        self._add_response_handler(InstrumentCmds.SET_CONFIGURATION, self._parse_config_response)
        
        # Add sample handlers. 
        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        # self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        # self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)

    @staticmethod
    def _decode_record(s):
        """
        Sieve helper to decode identify a Sami Record data particle.
        @param s: raw_data string
        @return rec_type: Record type [0x0 - 0xFF]
        @return rec_len: Sami Record Length (a field in the Record string).
        """
        rec_type = None
        rec_len = None
        s_len = len(s)
        if(s_len < 8):
            log.debug("Record too small " + str(s_len))
        else:
            # Decode the record length.
            txt = s[3:5]
            try:
                rec_len = int(txt,16)
            except Exception, e:
                raise SampleException("Sami decode_record 1 (%s) Fatal: %s" % (txt,str(e)))
            log.debug("record_length = " + str(rec_len))

            # Decode the record type.
            txt = s[5:7]
            try:
                rec_type = int(txt,16)
            except Exception, e:
                raise SampleException("Sami decode_record 2 (%s) Fatal: %s" % (txt,str(e)))
            log.debug("record_type = " + str(hex(rec_type)))
        return(rec_type,rec_len)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        return_list = []

        # Note: Because the start/stop index "clips" the string to a specified length
        # we must define a new method to extract the actual string length.
        # log.debug("CJC raw_data: %s" % raw_data )
        matcher = DATA_RECORD_REGEX_MATCHER
        for match in matcher.finditer(raw_data):
            i = match.start()
            log.debug("start = " + str(i))
            [rec_type,rec_len] = Protocol._decode_record(raw_data[i:])
            # Identify Data Records
            if((rec_type >= 0x0) & (rec_type < 0x80)):
                n = 3 + (2 * rec_len)
                return_list.append((i, i+n))

        matcher = CONTROL_RECORD_REGEX_MATCHER
        for match in matcher.finditer(raw_data):
            i = match.start()
            log.debug("start = " + str(i))
            [rec_type,rec_len] = Protocol._decode_record(raw_data[i:])
            # Identify Control Records.
            if((rec_type >= 0x80) & (rec_type <= 0xFF)):
                n = 3 + (2 * rec_len)
                return_list.append((i, i+n))

        sieve_matchers = [REGULAR_STATUS_REGEX_MATCHER,  # Reguar Status
                          CONFIG_REGEX_MATCHER]          # PCO2W Configuration

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                # log.debug("match start " + str(match.start()) + " end = " + str(match.end()))
                return_list.append((match.start(), match.end()))

        # print(return_list)
        return return_list

    ########################################################################
    # Private helpers.
    ########################################################################
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Set the sami date/time to the current.
        #tsec = get_timestamp_sec()
        #sami_timedate_str = SamiConfiguration.make_sami_time_string(tsec)
        #log.debug(" Todays Sami Time Is " + sami_timedate_str + " = " + SamiConfiguration.make_date_str(tsec) )        

        # Here we will index to the values in the "fixed string".
        # Pointer to the 1st SAMI Driver 4/5 Parameter String.
        param_index = SamiConfiguration._SAMI_DRIVER_PARAM_INDEX

        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.PUMP_PULSE,
            r'^(.{%s})(.{2}).*' % str(param_index),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index),
            startup_param = False,
            direct_access = False,
            default_value = 16,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.PUMP_ON_TO_MEASURE,      # name, pattern, fget, fformat
            r'^(.{%s})(.{2}).*' % str(param_index+2),           # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+2),                          # Output, note needs to be 7
            startup_param = False,
            direct_access = False,
            default_value = 32,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.NUM_SAMPLES_PER_MEASURE,
            r'^(.{%s})(.{2}).*' % str(param_index+4),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+4),                          # Output, note needs to be 7
            startup_param = False,
            direct_access = False,
            default_value = 255,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.NUM_CYCLES_BETWEEN_BLANKS,
            r'^(.{%s})(.{2}).*' % str(param_index+6),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+6),                          # Output, note needs to be 7
            startup_param = True,
            direct_access = True,
            default_value = 168,
            visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.NUM_REAGENT_CYCLES,
            r'^(.{%s})(.{2}).*' % str(param_index+8),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+8),                          # Output, note needs to be 7
            startup_param = False,
            direct_access = False,
            default_value = 24,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.NUM_BLANK_CYCLES,
            r'^(.{%s})(.{2}).*' % str(param_index+10),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+10),                          # Output, note needs to be 7
            startup_param = False,
            direct_access = False,
            default_value = 28,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.FLUSH_PUMP_INTERVAL_SEC,
            r'^(.{%s})(.{2}).*' % str(param_index+12),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+12),  # Output, note needs to be 7
            startup_param = False,
            direct_access = False,
            default_value = 1,
            visibility=ParameterDictVisibility.READ_ONLY)

        # Special method to populate individual bit-fields
        self._param_dict.add_parameter( 
            FunctionParameter( Parameter.STARTUP_BLANK_FLUSH_ENABLE,
                                  lambda s: self._decode_switch_bit_invert(input=s,bit_offset=0,pos=param_index+14),
                                  lambda x: self._update_configuration_bit(value=(x==0),bit_offset=0,pos=param_index+14),
                                  direct_access = True,
                                  startup_param = True,
                                  default_value = False,
                                  visibility=ParameterDictVisibility.READ_WRITE)
                                         )

        # Special method to populate individual bit-fields
        # Note bit values is inverted for this selection
        self._param_dict.add_parameter(
            FunctionParameter( Parameter.PUMP_PULSE_POST_MEASURE_ENABLE,
                                  lambda s: self._decode_switch_bit(input=s,bit_offset=1,pos=param_index+14),
                                  lambda x: self._update_configuration_bit(value=x,bit_offset=1, pos=param_index+14),
                                  direct_access = True,
                                  startup_param = True,
                                  default_value = False,
                                  visibility=ParameterDictVisibility.READ_ONLY)
                                         )

        self._param_dict.add(Parameter.NUM_EXTRA_PUMP_PULSE_CYCLES,
            r'^(.{%s})(.{2}).*' % str(param_index+16),   # Fixed offset.
            lambda match: self._string_to_int(match.group(2)),
            lambda x: self._update_configuration_byte(value=x,pos=param_index+16),
                                  direct_access = True,
                                  startup_param = True,
                                  default_value = 56,
                                  visibility=ParameterDictVisibility.READ_ONLY)

        # Debugging information.
        #pd = self._param_dict.get_config()
        #print(pd)
    # End _build_param_dict()

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker. Pass it to
        extract_sample with the appropriate parcle objects and REGEXes.
        @param: chunk - byte sequence that we want to create a particle from
        @param: timestamp - port agent timestamp to include in the chunk
        """
        log.debug(" got_chunk ************** " + chunk)
        if(self._extract_sample(SamiDataRecordParticle, DATA_RECORD_REGEX_MATCHER, chunk, timestamp)):
            log.debug("_got_chunk of Data Record = Passed good")

        elif(self._extract_sample(SamiControlRecordParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)):
            log.debug("_got_chunk of Control Record = Passed good")

        elif(self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)):
            log.debug("_got_chunk of Regular Status = Passed good")
            self._parse_S_response(chunk, None)

        elif(self._extract_sample(SamiConfigDataParticle, CONFIG_REGEX_MATCHER, chunk, timestamp)):
            log.debug("_got_chunk of Config = Passed good")
            self._parse_config_response(chunk, None)

        elif(self._extract_sample(SamiErrorDataParticle, ERROR_REGEX_MATCHER, chunk, timestamp)):
            log.debug("_got_chunk of Error = Passed good")

        else:
            log.debug("_got_chunk = Failed")

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        log.debug("Testing _handler_unknown_enter")

        # Initialize the Sami Configuration String for the first time.
        self._sami_config.clear()

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
        log.debug("Testing _handler_unknown_discover")
        next_state = None
        next_agent_state = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE

        # Since we are just starting clear out any configuration information being built.
        self._sami_new_config_str = None

        # Make sure automatic-status update is off
        # This will stop the broadcast of information while we are trying to get data.
        cmd = self._build_simple_command(InstrumentCmds.AUTO_STATUS_OFF, NEWLINE)
        self._do_cmd_direct(cmd)

        # We can actually put Sami in a Poll state by setting the start time way in the future.
        # Acquire one sample and return the result.
        log.debug(">>>>>>>>>>>>>>>> GET_CONFIGURATION")
        cmd = self._build_simple_command(InstrumentCmds.GET_CONFIGURATION, NEWLINE)
        self._do_cmd_direct(cmd)

        return( next_state, next_agent_state )

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # We are now in AutoSample state when we get here.
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        next_state = None
        next_agent_state = None
        return( next_state, next_agent_state)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        log.debug("in hander_autosample_stop_autosample")
        next_state = None
        next_agent_state = None
        result = None

        # Update configuration parameters and send.
        self._do_cmd_resp(InstrumentCmds.IMMEDIATE_STATUS,
                          *args, **kwargs)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

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
        log.debug("*** IN _handler_command_enter(), updating params")

        # Command device to update parameters and send a config change event.
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)


    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from device.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        log.debug("Testing _handler_command_acquire_sample")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30 # samples can take a long time

        # cmd = self._build_simple_command(InstrumentCmds.TAKE_SAMPLE,NEWLINE)
        # self._do_cmd_direct(cmd)
        # Acquire one sample and return the result.
        result = self._do_cmd_resp(InstrumentCmds.TAKE_SAMPLE, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Acquire sample from device.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        log.debug("Testing _handler_command_acquire_status")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30 # samples can take a long time

        # Acquire one sample and return the result.
        # result = self._do_cmd_no_resp(InstrumentCmds.DEVICE_STATUS, *args, **kwargs)
        cmd = self._build_simple_command(InstrumentCmds.DEVICE_STATUS,NEWLINE)
        self._do_cmd_direct(cmd)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_configuration(self, *args, **kwargs):
        """
        Acquire sample from device.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        log.debug("Testing _handler_command_acquire_configuration")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30 # samples can take a long time

        # Acquire one sample and return the result.
        result = self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION, *args, **kwargs)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout,
                                              expected_prompt=expected_prompt)

        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        return (next_state, (next_agent_state, result))

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        log.debug("^^^^^^^^^^^^^^^^^^ in _handler_command_get")
        next_state = ProtocolState.COMMAND
        result = None

        # This is going to clear out all the results so when we get there will be no data.
        self._build_param_dict()     #make sure data is up-to-date

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL or DriverParameter.ALL in params:
            log.debug("DriverParameter.ALL ******************************************** ")
            result_vals = {}
            # result = self._param_dict.get_config()
            log.debug("DriverParameter.ALL 22222222222222222222222222222222222222222222 ")

            result = self._param_dict.get_config()

            log.debug("DriverParameter.ALL 33333333333333333333333333333333333333333333 ")

        else:
            # If not all params, confirm a list or tuple of params to retrieve.
            # Raise if not a list or tuple.
            # Retireve each key in the list, raise if any are invalid.
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')

            result = {}
            for key in params:
                val = self._param_dict.get(key)
                log.debug("get KEY = " + str(key) + " VALUE = " + str(val))
                result[key] = val

        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Note: Issue here with only updating minor parameters.
        """
        next_state = None
        next_agent_state = None
        result = None
        result_vals = {}

        log.debug("Testing _handler_command_set_configuration")

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        # Get the current configuration parameters to see if we need to change.
        if ((params is None) or (not isinstance(params, dict))):
            raise InstrumentParameterException("Not a valid set parameter")

        # These are the parameters we are going to set...
        for (key, val) in params.iteritems():
            log.debug("KEY = %s VALUE = %s", key, val)

        for key in params.keys():
            if not Parameter.has(key):
                raise InstrumentParameterException()
            try:
                str_val = self._param_dict.format(key, params[key])
                log.debug("str_value ========= " + str_val)
                self._param_dict.update(self._sami_new_config_str)
                # Do a get function to make sure it got updated.
                val = self._param_dict.get(key)
                result_vals[key] = val
                log.debug("param from reality 1 = " + str(hex(val)))
            except KeyError:
                raise InstrumentParameterException()

        result = result_vals

        return (next_state, result_vals)

    def _handler_command_start_autosample(self):
        """
        Start autosample
        """
        log.debug("_handler_command_start_autosample:")
        next_state = None
        next_agent_state = None
        result = None

        # self._do_cmd_no_response(Command.GoGo)
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock_sync by checking the current time.
        """
        next_state = None
        next_agent_state = None
        result = None
        # self._do_cmd_device_status();
        # Decode current time from device status.
        # compare time against sync time.
        # if <> by some delta then we must resend configuration to update time.
        timestamp_sec = get_timestamp_sec(True)
        if(self._sami_config.is_valid() is True):
            str_val = self._sami_config.get_time_str(unix_format=True)
        self._do_cmd_resp(InstrumentCmds.SET_REAL_TIME_CLOCK, byte_time, **kwargs)

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
        next_agent_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
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
        if params == DriverParameter.ALL or DriverParameter.ALL in params:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.

        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                val = self._param_dict.get(key)
                result[key] = val

        return (next_state, result)

    ########################################################################
    # Direct access handlers.
    # Not Used - Assuming Command Line is Sufficient.
    ########################################################################

    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @todo: This feels odd.  It feels like some of this logic should
               be handled by the state machine.  It's a pattern that we
               may want to review.  I say this because this command
               needs to be run from autosample or command mode.
        @raise: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("*********** CURRENT STATE: %s" % self.get_current_state())
        if (self.get_current_state() != ProtocolState.COMMAND and
            self.get_current_state() != ProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if(not self._instrument_config_dirty()):
            return True

        error = None

        try:
            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e
            log.debug("Exception Error " + str(e))

        finally:
            log.debug("Finally!!!!!!!!!!!!!")

        if(error):
            raise error

    def _set_params(self, config):
        log.debug("_set_params()...")
        print(config)

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @raise: InstrumentProtocolException if in wrong mode.
        """
        log.debug("*********** _apply_params()")
        config = self.get_startup_config()
        self._set_params(config)

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @raise: InstrumentParameterException
        """
        log.debug(">>>>>>>>>>>>>>>> _instrument_config_dirty()")
        self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION)

        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s" % startup_params)

        for param in startup_params:
            if not Parameter.has(param):
                raise InstrumentParameterException()

            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                log.debug("DIRTY: %s %s != %s" % (param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
                return True

        log.debug("Clean instrument config")
        return False

    ########################################################################
    # Private helpers.
    ########################################################################
    def _is_logging(self, timeout=TIMEOUT):
        """
        Poll the instrument to see if we are in logging mode.  Return True
        if we are, False if not, or None if we couldn't tell.
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging,
                 None - unknown logging state
        """
        # The device status has a flag to indicate if we're recording.
        self._do_cmd_resp(InstrumentCmds.DEVICE_STATUS,timeout=timeout)
        pd = self._param_dict.get_config()
        log.debug("Logging? %s" % pd.get(SamiRegularStatusDataParticleKey.RECORDING_ACTIVE))
        return pd.get(SamiRegularStatusDataParticleKey.RECORDING_ACTIVE)

    def _convert_sami_time_to_sec(self, s):
        """
        Test: CAB39E84 = Time of programming (GMT) Oct 6, 2011 18:05:56 (total seconds from 1/1/1904)
        """
        tsec = int(s,16)
        if( tsec > NSECONDS_1904_TO_1970 ):
            tsec = tsec - NSECONDS_1904_TO_1970
        timestamp = time.gmtime(tsec)   # Convert to tuple for easy decoding.
        log.debug(" sami_string_to_time " + str(hex(tsec)) )
        return(timestamp)

    def _decode_device_status_word(self, status):
        clock_active         = bool(status & 0x001)
        recording_active     = bool(status & 0x002)
        record_end_on_time   = bool(status & 0x004)
        record_memory_full   = bool(status & 0x008)
        record_end_on_error  = bool(status & 0x010)
        record_data_download_ok = bool(status & 0x020)
        record_flash_open    = bool(status & 0x040)
        battery_error_fatal  = bool(status & 0x080)
        battery_low_measurement = bool(status & 0x100)
        battery_low_bank     = bool(status & 0x200)
        battery_low_external = bool(status & 0x400)

        external_device_fault = 0x0
        if( (status & 0x0800) == 0x0800 ):
            external_device_fault = external_device_fault | 0x1
        if( (status & 0x1000) == 0x1000 ):
            external_device_fault = external_device_fault | 0x2
        if( (status & 0x2000) == 0x2000 ):
            external_device_fault = external_device_fault | 0x4

        flash_erased     = bool(status & 0x4000)
        power_on_invalid = bool(status & 0x8000)

        log.debug("status_flags = " + str(hex(status)))
        log.debug("clk_active = " + str(clock_active))
        log.debug("recording_active = " + str(recording_active))
        log.debug("record_end_on_time = " + str(record_end_on_time))
        log.debug("record_memory_full = " + str(record_memory_full))
        log.debug("record_end_on_error = " + str(record_end_on_error))
        log.debug("record_data_download_ok = " + str(record_data_download_ok))
        log.debug("record_flash_open = " + str(record_flash_open))
        log.debug("battery_error_fatal = " + str(battery_error_fatal))
        log.debug("battery_low_measurement = " + str(battery_low_measurement))
        log.debug("battery_low_bank = " + str(battery_low_bank))
        log.debug("battery_low_external = " + str(battery_low_external))
        log.debug("external_device_fault = " + str(external_device_fault))
        log.debug("flash_erased = " + str(flash_erased))
        log.debug("power_on_invalid = " + str(power_on_invalid))

#        # Jump in and update the parameter dictionary here!
#        param = Parameter.PUMP_ON_TO_MEASURE;
#        param['value'] = pump_on;

    def set_from_value(self, name, val):
        pd= self._param_dict.get_config()
        log.debug("  ** old pd = " + str(pd[name]));
        self._param_dict.set(name, val)

    ###################################################################
    # Builders
    ###################################################################

    def _build_config_command(self, cmd, param, value):
        """
        Build a command that is ready to send out to the instrument. Checks for
        valid parameter name, only handles one value at a time.

        @param cmd The command...in this case, Command.SET
        @param param The name of the parameter to set. From Parameter enum
        @param value The value to set for that parameter
        @retval Returns string ready for sending to instrument
        """
        # Check to make sure all parameters are valid up front
        assert cmd == InstrumentCmds.SET_CONFIGURATION
        cmd = self._build_simple_command(cmd,NEWLINE)
        log.debug( "cmd = " + cmd )
        return(cmd)

    ###################################################################
    # Parsers
    ###################################################################
    def _find_error(self, response):
        """
        Find an error xml message in a response
        @param response command response string.
        @return error_no (integer)
        """
        error_no = None # no error
        match = re.search(ERROR_REGEX, response)
        if(match):
            txt = match.group(1)
            try:
                error_no = int(txt,16)
            except Exception, e:
                raise SampleException("Sami _find_error(%s) Fatal: %s" % (txt,str(e)))
        return(error_no)

    def _parse_config_response(self, response, prompt):
        """
        Response handler for configuration "L" command
        """
        log.debug("CCCCCCCCCCCCCCCCCCCCCCCCCCCCC response = " + response)
        result = None

        # Check for error response
        error_no = self._find_error(response)
        if error_no:
            error_no_str = SamiConfiguration.get_error_str(error_no)
            log.error("Sami Config command error; type='%s' msg='%s'", error[0], error_no_str)
            raise InstrumentParameterException('Sami Command failure: type="%d" msg="%s"' % (error_no, error_no_str))

        else:
            # This is how we are populating the Parameter Dictionary.
            self._update_sami_config(response)
            # Parameter data dictionary is extracted from the reponse string.
            # self._param_dict.update(response)
            self._param_dict.update_many(response)
            log.debug("done update with result ")

            # Determine if we are currently sampling.
            start_time = self._sami_config.get_start_time(unix_fmt=True)
            is_recording = self._determine_state(start_time)

        return result

    def _parse_I_response(self, response, prompt):
        """
        Response handler for Device Status command
        """
        result = None
        log.debug("IIIIIIIIIIIIIIIIIIIIIIIIIIIII response = " + response)

        lr = len(response)
        if(not lr):
            log.debug("There is no response")
        else:
            # Check for error response
            error_no = self._find_error(response)
            if error_no:
                error_no_str = SamiConfiguration.get_error_str(error_no)
                log.error("Sami Config command error; type='%s' msg='%s'", error[0], error_no_str)
                raise InstrumentParameterException('Sami Command failure: type="%d" msg="%s"' % (error_no, error_no_str))
            else:
                # Process message
                match = IMMEDIATE_STATUS_REGEX_MATCHER.search(response)
                if match:
                    result = response
                    # This response populates a data particle.
                    if(self._extract_sample(SamiImmediateStatusDataParticle, IMMEDIATE_STATUS_REGEX_MATCHER, response, timestamp=None)):
                        log.debug("_parse_I extract_sample success = ==== " + response)
                else:
                    log.debug("No Match Found " + response)
        return result

    def _parse_S_response(self, response, prompt): #(self, cmd, *args, **kwargs):
        """
        Response handler for Device Status command
        """
        result = None
        log.debug("SSSSSSSSSSSSSSSSSSSSSSSSSSSSS response = " + response)

        # Check for error response
        error_no = self._find_error(response)
        if error_no:
            error_no_str = SamiConfiguration.get_error_str(error_no)
            log.error("Sami Config command error; type='%s' msg='%s'", error[0], error_no_str)
            raise InstrumentParameterException('Sami Command failure: type="%d" msg="%s"' % (error_no, error_no_str))

        return result

    def _parse_R_response(self, response, prompt):
        """
        Response handler for R command.
        @param response command response string.
        @param prompt prompt following command response.
        @retval sample dictionary containig c, t, d values.
        @throws InstrumentProtocolException if ts command misunderstood.
        @throws InstrumentSampleException if response did not contain a sample
        """
        result = None
        log.debug("RRRRRRRRRRRRRRRRRRRRRRRRRRRRR response = " + response)

        lr = len(response)
        if(not lr):
            log.debug("No response found! ")
        else:
            # Check for error response
            error_no = self._find_error(response)
            if error_no:
                error_no_str = SamiConfiguration.get_error_str(error_no)
                log.error("Sami Config command error; type='%s' msg='%s'", error[0], error_no_str)
                raise InstrumentParameterException('Sami Command failure: type="%d" msg="%s"' % (error_no, error_no_str))
            else:
                # Verify match is valid.
                match = DATA_RECORD_REGEX_MATCHER.match(response)
                if match:
                    result = response
                    if(self._extract_sample(SamiDataRecordDataParticle, DATA_RECORD_REGEX_MATCHER, response, timestamp=None)):
                        log.debug("_parse_S extract_sample success = ==== " + response)
                    log.debug("     *** Status match found " + result)
                else:
                    log.debug("No Match Found " + response)

        # Process message
        return result

    ########################################################################
    # Helpers.
    ########################################################################
    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
        pass

    def _determine_state(self, rec_time_sec):
        """
        Determine what state we are in by the instrument time settings.
        @param rec_time_sec: Sami "Time Of Programming" + "Time Until Start".
        """
        is_recording = None
        # Compute the current time in seconds.
        time_now_sec = time.time()   # Current seconds since Epoch

        log.debug("time_now = " + time.asctime( time.gmtime(time_now_sec) ))
        log.debug("rec _now = " + time.asctime( time.gmtime(rec_time_sec) ))

        if( rec_time_sec <= time_now_sec):
            is_recording = True
        else:
            is_recording = False
        return(is_recording)

    def _update_sami_config(self, raw_str):
        """
        Update the Sami Configuration string.
        @param raw_str: Raw input string.
        """
        log.debug("UUUUUUUUUUUUUUUUUUUpdate _update_sami_config()")
        if( self._sami_config.set_config_str(raw_str) is True):
            # Valid configuration string.
            log.debug("GOODDDDD Config String")
            # Initialize the "new" raw string if it has not been built yet!
            if(self._sami_new_config_str is None):
                self._sami_new_config_str = raw_str
                self._sami_new_config_valid = True

            log.debug("Sys Config: " + self._sami_config.get_config_str())
            log.debug("New Config: " + self._sami_new_config_str)
        else:
            log.debug("BADDDDD Config String")

        log.debug("UUUUUUUUUUUUUUUUUU Update _update_sami_config() Done **********")

    def _update_params(self, *args, **kwargs):
        """
        Fetch the parameters from the device, and update the param dict.
        @param args Unused
        @param kwargs Takes timeout value
        @throws InstrumentProtocolException
        @throws InstrumentTimeoutException
        """
        log.debug("_update_params() - Updating parameter dict")

        # Get all the key values.
        chk = self._sami_config.compare(self._sami_new_config_str)  # False is Different.
        if(chk is None):
            log.debug("Invalid configuration string")
        elif(chk is False):
            #??            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            log.debug("UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU Update Configuration Command")
#            self._do_cmd_resp(InstrumentCmds.SET_CONFIGURATION, timeout=timeout)
        elif(chk is True):
            log.debug("No configuration change")
    # End _update_params()

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################
    @staticmethod
    def _string_to_int(v):
        try:
            r = int(v,16)
            log.debug("DDDDDDDDDDDDDDDDD _string to int " + v)
        except Exception, e:
            raise SampleException("Sami _string_to_int(%s) Fatal: %s" % (txt,str(e)))
        return r

    @staticmethod
    def _decode_switch_bit(input, bit_offset, pos):
        r = False
        if( not input ):
            log.debug("not input found")
        elif( input == "" ):
            log.debug("no string found!")
        else:
            log.debug("DDDDDDDDDDDDDDDDD _string to int " + input)

            len_input = len(input)
            if( (pos+2) >= len_input ):
                raise SampleException("Sami _decode_switch_bit Invalid Configuration Length %d/%d" %(pos,len_input))
            else:
                s = input[pos:(pos+2)]
                try:
                    val = int(s,16)
                except Exception, e:
                    raise SampleException("Sami _decode_switch_bit(%s) Fatal: %s" % (txt,str(e)))
                else:
                    iBitValue = (1 << bit_offset)
                    r = bool(val & iBitValue)
        return( r)

    @staticmethod
    def _decode_switch_bit_invert(input, bit_offset, pos):
        return( Protocol._decode_switch_bit(input, bit_offset, pos) == False)

    # Tools for configuration.
    @staticmethod
    def _update_configuration_bit(value, bit_offset, pos):
        """
        Update the configuration string with a 1-bit value at the desired string index
        @param s1: string for bit-field update
        @param value: [0,1] 1-bit value to insert into string 
        @param bit_offset: bit offset into nibble (0-3) 3210
        @param pos: Configuration String position of update.
        @return: 1-char string ???
        """
        # Get the old Nibble (4-bit value) to change
        old_nib_txt = self._sami_new_config_str[pos]
        new_nib = int(old_nib_txt,16)
        # Compute the bit to set in the nibble.
        ibit = 1 << bit_offset
        if( value == 0x0 ):
            new_nib &= ~ibit  # Bit Clear
        else: # value == 0x1
            new_nib |= ibit
        # Compute bits back to nibble character for configuration string.
        msg = hex_to_ascii(new_nib)
        self._sami_new_config_str = replace_string_chars(self._sami_new_config_str, pos, msg)
        return(msg)

    def _update_configuration_byte(self, value, pos):
        """
        Update the configuraiton string with a value at the desired string index
        @param value: 8-bit value to insert into string
        @param pos: Configuration String position (index) to insert updated value.
        @return: 2-byte string
        """
        msg = '{:02X}'.format(value)
        log.debug("Updating index "+ str(pos) + " for value " + msg)
        log.debug("sami_string is was " + self._sami_new_config_str)
        self._sami_new_config_str = replace_string_chars(self._sami_new_config_str, pos, msg)
        log.debug("sami_string is now " + self._sami_new_config_str)
        return(msg)
# End of File
