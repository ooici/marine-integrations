"""
@package mi.instrument.uw.hpies.ooicore.driver
@file marine-integrations/mi/instrument/uw/hpies/ooicore/driver.py
@author Dan Mergens
@brief Driver for the ooicore
Release notes:

initial_rev
"""

__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import time
import re
import tempfile

from mi.core.exceptions import \
    SampleException, \
    InstrumentProtocolException, \
    InstrumentParameterException, \
    InstrumentTimeoutException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.core.util import dict_equal
from mi.core.log import \
    get_logger, \
    get_logging_metaclass
from mi.core.common import BaseEnum, Units
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import \
    SingleConnectionInstrumentDriver, DriverEvent, DriverAsyncEvent, DriverProtocolState, DriverParameter, \
    ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType, DataParticleKey, DataParticle, DataParticleValue
from mi.core.instrument.chunker import StringChunker
from mi.instrument.uw.hpies.crclib import crc3kerm



# newline.
NEWLINE = '\r\n'
log = get_logger()

# default timeout.
TIMEOUT = 10

common_matches = {
    'float': r'-?\d*\.?\d+',
    'int': r'-?\d+',
    'str': r'\w+',
    'fn': r'\S+',
    'rest': r'.*',
    'tod': r'\d{8}T\d{6}',
    'data': r'#\d[^\*]+',
    'crc': r'[0-9a-fA-F]{4}'
}


def build_command(address, command, *args):
    """
    Create an instrument command string.
    :param address:  1 - STM, 3 - HEF, 4 - IES
    :param command:  command string
    :param args:     arguments for command
    :return:         fully qualified command string
    """
    s = '#' + address + '_' + command
    formatted_list = []  # convert all booleans to integers
    for x in args:
        if type(x) is bool:
            formatted_list.append(int(x))
        else:
            formatted_list.append(x)

    if formatted_list:
        s += ' ' + ' '.join([str(x) for x in formatted_list])
    s = s + str.format('*{0:04x}', crc3kerm(s)) + NEWLINE
    return s


def calc_crc(line):
    """
    Check response for valid checksum.
    @param line data line which may contain extra characters at beginning or end
    @retval
        - computed value of the CRC for the data
        - regex match for the crc value provided with the data
    """
    pattern = re.compile(
        r'(?P<resp>%(data)s)\*(?P<crc>%(crc)s)' % common_matches)
    matches = re.search(pattern, line)
    if not matches:  # skip any lines that do not have a checksum match
        return 0, 0
    resp_crc = int(matches.group('crc'), 16)
    data = matches.group('resp')
    crc = crc3kerm(data)
    return crc, resp_crc


def valid_response(resp):
    """
    Check response for valid checksum.
    @param resp response line
    @return - whether or not checksum matches data
    """
    crc, resp_crc = calc_crc(resp)
    return crc == resp_crc


def stm_command(s, *args):
    """
    Create fully qualified STM command (add prefix and postfix the CRC).
    """
    return build_command('1', s, *args)


def hef_command(s, *args):
    """
    Create fully qualified HEF command (add prefix and postfix the CRC).
    """
    return build_command('3', s, *args)


def ies_command(s, *args):
    """
    Create fully qualified IES command (add prefix and postfix the CRC).
    """
    return build_command('4', s, *args)


# ##
# Driver Constant Definitions
###
class HPIESUnits(Units):
    CYCLE = 'cycle'
    HALF_CYCLE = 'half cycle'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
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
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE


class Parameter(DriverParameter):
    """
    Instrument specific parameters
    """
    # HEF parameters
    SERIAL = 'serno'
    DEBUG_LEVEL = 'debug'
    WSRUN_PINCH = 'wsrun pinch secs'  # half cycle interval between water switch tube pinch
    # EF_SKIP = 'ef skip secs'  # time in seconds to wait before using EF data after moving motors
    NFC_CALIBRATE = 'nfc calibrate'  # number of cycles of water switch between applying 'cal'
    CAL_HOLD = 'cal hold secs'  # hold time of calibration voltage
    CAL_SKIP = 'cal skip'  # time in seconds to wait before using data after changing the calibration signal state
    NHC_COMPASS = 'nhc compass'  # number of half cycles between compass measurements
    COMPASS_SAMPLES = 'compass nget'  # number of compass samples to acquire in a burst
    COMPASS_DELAY = 'compass dsecs'  # time between measurements in a burst
    INITIAL_COMPASS = 'icompass run'  # initial compass measurement (in seconds)
    INITIAL_COMPASS_DELAY = 'icompass dsecs'  #
    # FILE_LENGTH = 'secs per ofile'  # seconds per file (default 86400 - one day)
    MOTOR_SAMPLES = 'navg mot'  # number of samples to average
    EF_SAMPLES = 'navg ef'  # number of samples to average
    CAL_SAMPLES = 'navg cal'  # number of samples to average
    CONSOLE_TIMEOUT = 'console off timeout'  # sleep timeout for UART drivers (use hef_wake to resume)
    WSRUN_DELAY = 'wsrun delay secs'  #
    MOTOR_DIR_NHOLD = 'motor dir nhold'  #
    MOTOR_DIR_INIT = 'motor dir init'
    # 'ies baud'
    # 'ies hcvals use'
    # 'ies delay'
    # 'ies sf efo'
    # 'ies sf cal'
    # 'ies sf efm'
    POWER_COMPASS_W_MOTOR = 'dcpwm'  # false
    KEEP_AWAKE_W_MOTOR = 'dkawm'  # true
    MOTOR_TIMEOUTS_1A = 'm1a_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_1B = 'm1b_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_2A = 'm2a_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_2B = 'm2b_tmoc'  # timeout counts for motor - 200
    RSN_CONFIG = 'do_rsn'  # configured for RSN (instead of autonomous) - true
    INVERT_LED_DRIVERS = 'led_drivers_invert'  # false
    M1A_LED = 'm1a_led'  # 1
    M2A_LED = 'm2a_led'  # 3

    # Inverter Echo Sounder parameters - all these are read-only
    ECHO_SAMPLES = 'Travel Time Measurements: 4 pings every 10 minutes'
    WATER_DEPTH = 'Estimated Water Depth: 3000 meters'
    ACOUSTIC_LOCKOUT = 'Acoustic Lockout: 3.60 seconds'
    ACOUSTIC_OUTPUT = 'Acoustic output set at 186 dB'
    RELEASE_TIME = 'Release Time: Thu Dec 25 12:00:00 2014'
    COLLECT_TELEMETRY = 'Telemetry data file enabled'
    MISSION_STATEMENT = 'Mission Statement: No mission statement has been entered'
    PT_SAMPLES = 'Pressure and Temperature measured every 10 minutes'

    TEMP_COEFF_U0 = 'temp coeff u0'  # default 5.814289
    TEMP_COEFF_Y1 = 'temp coeff y1'  # default -3978.811
    TEMP_COEFF_Y2 = 'temp coeff y2'  # default -10771.79
    TEMP_COEFF_Y3 = 'temp coeff y3'  # default 0.00
    PRES_COEFF_C1 = 'pressure coeff c1'  # default -30521.42
    PRES_COEFF_C2 = 'pressure coeff c2'  # default -2027.363
    PRES_COEFF_C3 = 'pressure coeff c3'  # default 95228.34
    PRES_COEFF_D1 = 'pressure coeff d1'  # default 0.039810
    PRES_COEFF_D2 = 'pressure coeff d2'  # default 0.00
    PRES_COEFF_T1 = 'pressure coeff t1'  # default 30.10050
    PRES_COEFF_T2 = 'pressure coeff t2'  # default 0.096742
    PRES_COEFF_T3 = 'pressure coeff t3'  # default 56.45416
    PRES_COEFF_T4 = 'pressure coeff t4'  # default 151.539900
    PRES_COEFF_T5 = 'pressure coeff t5'  # default 0.00

    TEMP_OFFSET = 'temp offset'  # default -0.51 degrees C
    PRES_OFFSET = 'press offset'  # default 0.96 psi

    BLILEY_0 = 'bliley B0'  # -0.575100
    BLILEY_1 = 'bliley B1'  # -0.5282501
    BLILEY_2 = 'bliley B2'  # -0.013084390
    BLILEY_3 = 'bliley B3'  # 0.00004622697

    @classmethod
    def reverse_dict(cls):
        return dict((v, k) for k, v in cls.dict().iteritems())


class ParameterConstraints(BaseEnum):
    """
    type, minimum, maximum values for each settable parameter
    """
    DEBUG_LEVEL = (int, 0, 3)
    WSRUN_PINCH = (int, 1, 3600)
    NFC_CALIBRATE = (int, 1, 3600)
    NHC_COMPASS = (int, 1, 3600)
    COMPASS_SAMPLES = (int, 1, 3600)
    COMPASS_DELAY = (int, 1, 3600)
    MOTOR_SAMPLES = (int, 1, 100)
    EF_SAMPLES = (int, 1, 100)
    CAL_SAMPLES = (int, 1, 100)
    MOTOR_TIMEOUTS_1A = (int, 10, 1000)
    MOTOR_TIMEOUTS_1B = (int, 10, 1000)
    MOTOR_TIMEOUTS_2A = (int, 10, 1000)
    MOTOR_TIMEOUTS_2B = (int, 10, 1000)


class Command(BaseEnum):
    """
    Instrument command strings - base strings, use [stm|hef|ies]_command to build command
    """
    # STM commands
    REBOOT = 'reboot'
    ACQUISITION_START = 'daq_start'
    ACQUISITION_STOP = 'daq_stop'
    IES_PORT_ON = 'ies_opto_on'  # should only be on to change parameters and start mission
    IES_PORT_OFF = 'ies_opto_off'
    IES_POWER_ON = 'ies_pwr_on'
    IES_POWER_OFF = 'ies_pwr_off'  # must power cycle to apply changed parameters
    HEF_PORT_ON = 'hef_opto_on'  # should remain on during mission
    HEF_PORT_OFF = 'hef_opto_off'
    HEF_POWER_ON = 'hef_pwr_on'
    HEF_POWER_OFF = 'hef_pwr_off'
    HEF_WAKE = 'hef_wake'
    HEF_PARAMS = 'params'
    HEF_SAVE = 'params save'
    SYNC_CLOCK = 'force_RTC_update'  # align STM clock to RSN date/time

    # HEF specific commands
    PREFIX = 'prefix'
    MISSION_START = 'mission start'
    MISSION_STOP = 'mission stop'

    # Commands which set parameters
    DEBUG_LEVEL = Parameter.DEBUG_LEVEL
    WSRUN_PINCH = Parameter.WSRUN_PINCH
    NFC_CALIBRATE = Parameter.NFC_CALIBRATE
    CAL_HOLD = Parameter.CAL_HOLD
    NHC_COMPASS = Parameter.NHC_COMPASS
    COMPASS_SAMPLES = Parameter.COMPASS_SAMPLES
    COMPASS_DELAY = Parameter.COMPASS_DELAY
    MOTOR_SAMPLES = Parameter.MOTOR_SAMPLES
    EF_SAMPLES = Parameter.EF_SAMPLES
    CAL_SAMPLES = Parameter.CAL_SAMPLES
    CONSOLE_TIMEOUT = Parameter.CONSOLE_TIMEOUT
    WSRUN_DELAY = Parameter.WSRUN_DELAY
    MOTOR_DIR_NHOLD = Parameter.MOTOR_DIR_NHOLD
    MOTOR_DIR_INIT = Parameter.MOTOR_DIR_INIT
    POWER_COMPASS_W_MOTOR = Parameter.POWER_COMPASS_W_MOTOR
    KEEP_AWAKE_W_MOTOR = Parameter.KEEP_AWAKE_W_MOTOR
    MOTOR_TIMEOUTS_1A = Parameter.MOTOR_TIMEOUTS_1A
    MOTOR_TIMEOUTS_1B = Parameter.MOTOR_TIMEOUTS_1B
    MOTOR_TIMEOUTS_2A = Parameter.MOTOR_TIMEOUTS_2A
    MOTOR_TIMEOUTS_2B = Parameter.MOTOR_TIMEOUTS_2B
    RSN_CONFIG = Parameter.RSN_CONFIG
    INVERT_LED_DRIVERS = Parameter.INVERT_LED_DRIVERS
    M1A_LED = Parameter.M1A_LED
    M2A_LED = Parameter.M2A_LED

    # The following are not implemented commands
    # 'term hef'  # change HEF parameters interactively
    # 'term ies'  # change IES parameters interactively
    # 'term tod'  # display RSN time of day
    # 'term aux'  # display IES AUX2 port
    # 'baud'  # display baud rate (serial RSN to STM)
    # 'baud #'  # set baud rate


class Timeout(BaseEnum):
    """
    Timeouts for instrument commands
    """
    # STM commands
    DEFAULT = 3
    REBOOT = 5
    ACQUISITION_START = DEFAULT
    ACQUISITION_STOP = DEFAULT
    IES_PORT_ON = DEFAULT
    IES_PORT_OFF = DEFAULT
    IES_POWER_ON = 30  # observations from 8-24 seconds
    IES_POWER_OFF = DEFAULT
    HEF_PORT_ON = DEFAULT
    HEF_PORT_OFF = DEFAULT
    HEF_POWER_ON = 6
    HEF_POWER_OFF = DEFAULT
    HEF_WAKE = DEFAULT
    HEF_PARAMS = 6
    HEF_SAVE = DEFAULT
    SYNC_CLOCK = DEFAULT

    # HEF specific commands
    PREFIX = DEFAULT
    MISSION_START = DEFAULT
    MISSION_STOP = DEFAULT


class Prompt(BaseEnum):
    """
    Device I/O prompts
    """
    DEFAULT = 'STM>'
    HEF_PARAMS = '#3_params'
    HEF_PROMPT = '#3_HEF C>'
    HEF_PORT_ON = DEFAULT  # port on command doesn't return the HEF prompt (return is #3_\r\n)


class Response(BaseEnum):
    """
    Expected responses from HPIES
    """
    TIMESTAMP = re.compile(r'^(?P<tod>%(tod)s)' % common_matches)
    UNKNOWN_COMMAND = re.compile(r'.*?unknown command: .*?')
    PROMPT = re.compile(r'^STM> .*?')
    HEF_POWER_ON = re.compile(r'#3_Use <BREAK> to enter command mode')  # last line of HEF power on prompt
    IES_POWER_ON = re.compile(r'#4_\s+Next scheduled 1 minute warning at:')  # last line of IES power on prompt
    ERROR = re.compile(r'.*?port.*?not open')
    OPENED_FILE = re.compile(r'#3_Opened raw output file, (\S+)\\r')
    SET_PARAMETER = re.compile(r'.+\s=\s(%(int)s)' % common_matches)


###############################################################################
# Data Particles
###############################################################################


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver.
    """
    RAW = CommonDataParticleType.RAW
    HPIES_DATA_HEADER = 'hpies_data_header'  # DataHeaderParticle
    HORIZONTAL_FIELD = 'horizontal_electric_field'  # HEFDataParticle
    MOTOR_CURRENT = 'motor_current'  # HEFMotorCurrentParticle
    CALIBRATION_STATUS = 'calibration_status'  # CalStatusParticle
    HPIES_STATUS = 'hpies_status'  # HEFStatusParticle
    ECHO_SOUNDING = 'echo_sounding'  # IESDataParticle
    ECHO_STATUS = 'ies_status'  # IESStatusParticle
    TIMESTAMP = 'stm_timestamp'  # TimestampParticle


class DataHeaderParticleKey(BaseEnum):
    """
    Horizontal Electrical Field data field header stream

    Precedes each series of HEF data particles
    """
    DATA_VALID = 'hpies_data_valid'
    VERSION = 'hpies_ver'
    TYPE = 'hpies_type'
    DESTINATION = 'hpies_dest'
    INDEX_START = 'hpies_ibeg'
    INDEX_STOP = 'hpies_iend'
    HCNO = 'hpies_hcno'
    TIME = 'hpies_secs'
    TICKS = 'hpies_tics'
    MOTOR_SAMPLES = 'hpies_navg_mot'
    EF_SAMPLES = 'hpies_navg_ef'
    CAL_SAMPLES = 'hpies_navg_cal'
    STM_TIME = 'hpies_stm_timestamp'


class HPIESDataParticle(DataParticle):
    _compiled_regex = None
    __metaclass__ = get_logging_metaclass(log_level='info')

    def __init__(self, *args, **kwargs):
        super(HPIESDataParticle, self).__init__(*args, **kwargs)

        self.match = self.regex_compiled().match(self.raw_data)
        if not self.match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        self.check_crc()

    def check_crc(self):
        crc_compute, crc = calc_crc(self.raw_data)
        data_valid = crc_compute == crc
        if not data_valid:
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED
            log.warning("Corrupt data detected: [%r] - CRC %s != %s" % (self.raw_data, hex(crc_compute), hex(crc)))

    @staticmethod
    def regex():
        raise NotImplemented()

    def _encode_all(self):
        raise NotImplemented()

    @classmethod
    def regex_compiled(cls):
        if cls._compiled_regex is None:
            cls._compiled_regex = re.compile(cls.regex())
        return cls._compiled_regex

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        try:
            result = self._encode_all()
        except Exception as e:
            raise SampleException("Exception [%s] while converting data: [%s]" % (e, self.raw_data))
        return result


class DataHeaderParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.HPIES_DATA_HEADER

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES data header particle

        Sample Data:
        #3__HE05 E a 0 983 130 3546345513 13126 3 3 3 1398912144*f7aa
        #3__HE05 f a 0 382 0 3546329882 17917 3 3 3 1398896422*d6fe
        #3__HE05 C a 0 978 22 3546332553 34259 3 3 3 1398899184*3e0e
        """
        pattern = r"""
            (?x)
            \#3__HE
            (?P<version>  \d{2})    \s  (?# 05)
            (?P<type>     ([ECfr])) \s  (?# E)
            (?P<dest>     ([ab]))   \s  (?# a)
            (?P<ibegin>   %(int)s)  \s  (?# 0)
            (?P<iend>     %(int)s)  \s  (?# 983)
            (?P<hcno>     %(int)s)  \s  (?# 130)
            (?P<secs>     %(int)s)  \s  (?# 3546345513)
            (?P<tics>     %(int)s)  \s  (?# 13126)
            (?P<navg_mot> %(int)s)  \s  (?# 3)
            (?P<navg_ef>  %(int)s)  \s  (?# 3)
            (?P<navg_cal> %(int)s)  \s  (?# 3)
            (?P<stm_time> %(int)s)      (?# 1398912144)
                           \*
            (?P<crc>       %(crc)s)    (?# f7a9)
            """ % common_matches

        return pattern

    def _encode_all(self):
        return [
            self._encode_value(DataHeaderParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(DataHeaderParticleKey.VERSION, self.match.group('version'), int),
            self._encode_value(DataHeaderParticleKey.TYPE, self.match.group('type'), str),
            self._encode_value(DataHeaderParticleKey.DESTINATION, self.match.group('dest'), str),
            self._encode_value(DataHeaderParticleKey.INDEX_START, self.match.group('ibegin'), int),
            self._encode_value(DataHeaderParticleKey.INDEX_STOP, self.match.group('iend'), int),
            self._encode_value(DataHeaderParticleKey.HCNO, self.match.group('hcno'), int),
            self._encode_value(DataHeaderParticleKey.TIME, self.match.group('secs'), int),
            self._encode_value(DataHeaderParticleKey.TICKS, self.match.group('tics'), int),
            self._encode_value(DataHeaderParticleKey.MOTOR_SAMPLES, self.match.group('navg_mot'), int),
            self._encode_value(DataHeaderParticleKey.EF_SAMPLES, self.match.group('navg_ef'), int),
            self._encode_value(DataHeaderParticleKey.CAL_SAMPLES, self.match.group('navg_cal'), int),
            self._encode_value(DataHeaderParticleKey.STM_TIME, self.match.group('stm_time'), int)
        ]


class HEFDataParticleKey(BaseEnum):
    """
    Horizontal Electrical Field data stream
    """
    DATA_VALID = 'hpies_data_valid'
    INDEX = 'hpies_eindex'
    CHANNEL_1 = 'hpies_e1c'
    CHANNEL_2 = 'hpies_e1a'
    CHANNEL_3 = 'hpies_e1b'
    CHANNEL_4 = 'hpies_e2c'
    CHANNEL_5 = 'hpies_e2a'
    CHANNEL_6 = 'hpies_e2b'


class HEFDataParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.HORIZONTAL_FIELD

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES horizontal electric field data particle

        Sample Data:
        #3__DE 797 79380 192799 192803 192930*56a8
        """
        pattern = r"""
            (?x)
                           \#3__DE  \s
            (?P<index>     %(int)s) \s
            (?P<channel_1> %(int)s) \s
            (?P<channel_2> %(int)s) \s
            (?P<channel_3> %(int)s) \s
            (?P<channel_4> %(int)s) \s
            (?P<channel_5> %(int)s) \s
            (?P<channel_6> %(int)s)
                           \*
            (?P<crc>       %(crc)s)
            """ % common_matches

        return pattern

    def _encode_all(self):
        return [
            self._encode_value(HEFDataParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(HEFDataParticleKey.INDEX, self.match.group('index'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_1, self.match.group('channel_1'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_2, self.match.group('channel_2'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_3, self.match.group('channel_3'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_4, self.match.group('channel_4'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_5, self.match.group('channel_5'), int),
            self._encode_value(HEFDataParticleKey.CHANNEL_6, self.match.group('channel_6'), int),
        ]


class HEFMotorCurrentParticleKey(BaseEnum):
    """
    HEF Motor Current data stream
    """
    DATA_VALID = 'hpies_data_valid'
    INDEX = 'hpies_mindex'
    CURRENT = 'hpies_motor_current'


class HEFMotorCurrentParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.MOTOR_CURRENT

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES motor current particle

        Sample Data:
        #3__DM 11 24425*396b
        """

        pattern = r"""
            (?x)
                               \#3__DM  \s
            (?P<index>         %(int)s) \s
            (?P<motor_current> %(int)s)
                               \*
            (?P<crc>           %(crc)s)
            """ % common_matches

        return pattern

    def _encode_all(self):
        return [
            self._encode_value(HEFMotorCurrentParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(HEFMotorCurrentParticleKey.INDEX, self.match.group('index'), int),
            self._encode_value(HEFMotorCurrentParticleKey.CURRENT, self.match.group('motor_current'), int),
        ]


class CalStatusParticleKey(BaseEnum):
    """
    Calibration status data particle

    Sent every two minutes during autosample.
    """
    DATA_VALID = 'hpies_data_valid'
    INDEX = 'hpies_cindex'
    E1C = 'hpies_c1c'
    E1A = 'hpies_c1a'
    E1B = 'hpies_c1b'
    E2C = 'hpies_c2c'
    E2A = 'hpies_c2a'
    E2B = 'hpies_c2b'


class CalStatusParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.CALIBRATION_STATUS

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES calibration status particle

        Sample Data:
        #3__DC 2 192655 192637 135611 80036 192554 192644*5c28
        """
        pattern = r"""
            (?x)
                       \#3__DC  \s
            (?P<index> %(int)s) \s
            (?P<e1c>   %(int)s) \s
            (?P<e1a>   %(int)s) \s
            (?P<e1b>   %(int)s) \s
            (?P<e2c>   %(int)s) \s
            (?P<e2a>   %(int)s) \s
            (?P<e2b>   %(int)s)
                       \*
            (?P<crc>   %(crc)s)
            """ % common_matches

        return pattern

    def _encode_all(self):
        return [
            self._encode_value(CalStatusParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(CalStatusParticleKey.INDEX, self.match.group('index'), int),
            self._encode_value(CalStatusParticleKey.E1C, self.match.group('e1c'), int),
            self._encode_value(CalStatusParticleKey.E1A, self.match.group('e1a'), int),
            self._encode_value(CalStatusParticleKey.E1B, self.match.group('e1b'), int),
            self._encode_value(CalStatusParticleKey.E2C, self.match.group('e2c'), int),
            self._encode_value(CalStatusParticleKey.E2A, self.match.group('e2a'), int),
            self._encode_value(CalStatusParticleKey.E2B, self.match.group('e2b'), int),
        ]


class HEFStatusParticleKey(BaseEnum):
    """
    HPIES status data particle

    HPIES status is sent every X minutes during autosample
    """
    DATA_VALID = 'hpies_data_valid'
    UNIX_TIME = 'hpies_secs'  # elapsed time since unix epoch
    HCNO = 'hpies_hcno'  # Half cycle number (int)
    HCNO_LAST_CAL = 'hpies_hcno_last_cal'  # Half cycle number of last calibration (int)
    HCNO_LAST_COMP = 'hpies_hcno_last_comp'  # Half cycle number of last compass value	 1	 int
    OFILE = 'hpies_ofile'  # Current output filename	1	str	remove?
    IFOK = 'hpies_ifok'  # File write status	1	str	"NG" on error, "OK" if still appending  remove?
    N_COMPASS_WRITES = 'hpies_compass_fwrite_attempted'  # Number of compass records written to <ofile>	1	int
    # Number of attempts to write compass data when <ofile> is corrupt	1	int
    N_COMPASS_FAIL_WRITES = 'hpies_compass_fwrite_ofp_null'
    MOTOR_POWER_UPS = 'hpies_mot_pwr_count'  # Up/down counter of motor power on/off.  Should be zero.	 1	 int
    # Number of main service loops while motor  current is being sampled.  1	 int
    N_SERVICE_LOOPS = 'hpies_start_motor_count'
    SERIAL_PORT_ERRORS = 'hpies_compass_port_open_errs'  # Number of failures to open the compass  serial port.  1	 int
    COMPASS_PORT_ERRORS = 'hpies_compass_port_nerr'  # int	Always zero (never changed in code).  Remove?
    # Number of times compass port is  found closed when trying to read it.
    COMPASS_PORT_CLOSED_COUNT = 'hpies_tuport_compass_null_count'
    IRQ2_COUNT = 'hpies_irq2_count'  # Number of interrupt requests on IRQ2 line of 68332.	 1	 int	 Should be zero.
    SPURIOUS_COUNT = 'hpies_spurious_count'  # Number of spurious interrupts to the 68332.	 1	 int	 Should be zero.
    # Number of times the SPSR register bits 5 and 6 are set.	 1	 int	 Should be zero.
    SPSR_BITS56_COUNT = 'hpies_spsr_unknown_count'
    # Number of times the programable interval timer (PIT) is zero.	 1	 int	 Should be zero.
    PIT_ZERO_COUNT = 'hpies_pitperiod_zero_count'
    # Number of times the analog to digital converter circular buffer overflows.	 1	 int	 Should be zero.
    ADC_BUFFER_OVERFLOWS = 'hpies_adc_raw_overflow_count'
    # Number of times the max7317 queue overflows.	 1	 int	 Should be zero.
    MAX7317_QUEUE_OVERFLOWS = 'hpies_max7317_add_queue_errs'
    # Number of times water switch pinch timing is incorrect.	 1	 int	 Should be zero.
    PINCH_TIMING_ERRORS = 'hpies_wsrun_rtc_pinch_end_nerr'


class HEFStatusParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.HPIES_STATUS

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES horizontal electric field status particle

        Sample Data:
        #3__s1 -748633661 31 23 0 C:\DATA\12345.000 OK*3e90
        #3__s2 10 0 0 984001 0 0 0*ac87
        #3__s3 0 0 0 0 0 0 1*35b7
        """
        pattern = r"""
            (?x)
                                    \#3__s1  \s+
            (?P<secs>               %(int)s) \s+
            (?P<hcno>               %(int)s) \s+
            (?P<hcno_last_cal>      %(int)s) \s+
            (?P<hcno_last_comp>     %(int)s) \s+
            (?P<ofile>              %(fn)s)  \s+
            (?P<ifok>               %(str)s)
                                    \*
            (?P<crc1>               %(crc)s) \s+
                                    \#3__s2  \s+
            (?P<compass_writes>     %(int)s) \s+
            (?P<compass_fails>      %(int)s) \s+
            (?P<motor_power_cycles> %(int)s) \s+
            (?P<service_loops>      %(int)s) \s+
            (?P<serial_failures>    %(int)s) \s+
            (?P<port_failures>      %(int)s) \s+
            (?P<port_closures>      %(int)s)
                                    \*
            (?P<crc2>               %(crc)s) \s+
                                    \#3__s3  \s+
            (?P<irq2_count>         %(int)s) \s+
            (?P<spurious_count>     %(int)s) \s+
            (?P<spsr_count>         %(int)s) \s+
            (?P<zero_count>         %(int)s) \s+
            (?P<adc_overflows>      %(int)s) \s+
            (?P<queue_overflows>    %(int)s) \s+
            (?P<pinch_errors>       %(int)s)
                                    \*
            (?P<crc3>               %(crc)s)
            """ % common_matches

        return pattern

    def check_crc(self):
        """
        Overridden because HEF Status has multiple lines with CRC
        """
        valid = True
        for line in self.raw_data.split(NEWLINE):
            crc_compute, crc_parse = calc_crc(line)
            data_valid = crc_compute == crc_parse
            if not data_valid:
                self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED
                log.warning("Corrupt data detected: [%r] - CRC %s != %s" % (line, hex(crc_compute), hex(crc_parse)))
                valid = False
        return valid

    def _encode_all(self):
        return [
            self._encode_value(HEFStatusParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(HEFStatusParticleKey.UNIX_TIME, self.match.group('secs'), int),
            self._encode_value(HEFStatusParticleKey.HCNO, self.match.group('hcno'), int),
            self._encode_value(HEFStatusParticleKey.HCNO_LAST_CAL, self.match.group('hcno_last_cal'), int),
            self._encode_value(HEFStatusParticleKey.HCNO_LAST_COMP, self.match.group('hcno_last_comp'), int),
            self._encode_value(HEFStatusParticleKey.OFILE, self.match.group('ofile'), str),
            self._encode_value(HEFStatusParticleKey.IFOK, self.match.group('ifok'), str),

            self._encode_value(HEFStatusParticleKey.N_COMPASS_WRITES, self.match.group('compass_writes'), int),
            self._encode_value(HEFStatusParticleKey.N_COMPASS_FAIL_WRITES, self.match.group('compass_fails'), int),
            self._encode_value(HEFStatusParticleKey.MOTOR_POWER_UPS, self.match.group('motor_power_cycles'), int),
            self._encode_value(HEFStatusParticleKey.N_SERVICE_LOOPS, self.match.group('service_loops'), int),
            self._encode_value(HEFStatusParticleKey.SERIAL_PORT_ERRORS, self.match.group('serial_failures'), int),
            self._encode_value(HEFStatusParticleKey.COMPASS_PORT_CLOSED_COUNT, self.match.group('port_failures'), int),
            self._encode_value(HEFStatusParticleKey.COMPASS_PORT_ERRORS, self.match.group('port_closures'), int),

            self._encode_value(HEFStatusParticleKey.IRQ2_COUNT, self.match.group('irq2_count'), int),
            self._encode_value(HEFStatusParticleKey.SPURIOUS_COUNT, self.match.group('spurious_count'), int),
            self._encode_value(HEFStatusParticleKey.SPSR_BITS56_COUNT, self.match.group('spsr_count'), int),
            self._encode_value(HEFStatusParticleKey.PIT_ZERO_COUNT, self.match.group('zero_count'), int),
            self._encode_value(HEFStatusParticleKey.ADC_BUFFER_OVERFLOWS, self.match.group('adc_overflows'), int),
            self._encode_value(HEFStatusParticleKey.MAX7317_QUEUE_OVERFLOWS, self.match.group('queue_overflows'), int),
            self._encode_value(HEFStatusParticleKey.PINCH_TIMING_ERRORS, self.match.group('pinch_errors'), int),
        ]


class IESDataParticleKey(BaseEnum):
    """
    Inverted Echo-Sounder data stream
    """
    DATA_VALID = 'hpies_data_valid'
    IES_TIMESTAMP = 'hpies_ies_timestamp'
    TRAVEL_TIMES = 'hpies_n_travel_times'
    TRAVEL_TIME_1 = 'hpies_travel_time1'
    TRAVEL_TIME_2 = 'hpies_travel_time2'
    TRAVEL_TIME_3 = 'hpies_travel_time3'
    TRAVEL_TIME_4 = 'hpies_travel_time4'
    PRESSURE = 'hpies_pressure'
    TEMPERATURE = 'hpies_temperature'
    BLILEY_TEMPERATURE = 'hpies_bliley_temperature'
    BLILEY_FREQUENCY = 'hpies_bliley_frequency'
    STM_TIMESTAMP = 'hpies_stm_timestamp'


class IESDataParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.ECHO_SOUNDING

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES echo sounding data particle

        Sample Data:
        #5_AUX,1398880200,04,999999,999999,999999,999999,0010848,021697,022030,04000005.252,1B05,1398966715*c69e
        """
        pattern = r"""
            (?x)
                                \#5_AUX    ,
            (?P<ies_timestamp>  %(int)s)   ,
            (?P<n_travel_times> %(int)s)   ,
            (?P<travel_1>       %(int)s)   ,
            (?P<travel_2>       %(int)s)   ,
            (?P<travel_3>       %(int)s)   ,
            (?P<travel_4>       %(int)s)   ,
            (?P<pressure>       %(int)s)   ,
            (?P<temp>           %(int)s)   ,
            (?P<bliley_temp>    %(int)s)   ,
            (?P<bliley_freq>    %(float)s) ,
                                %(crc)s    ,
            (?P<stm_timestamp>  %(int)s)
                                \*
            (?P<crc>            %(crc)s)
            """ % common_matches

        return pattern

    def _encode_all(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """

        return [
            self._encode_value(IESDataParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(IESDataParticleKey.IES_TIMESTAMP, self.match.group('ies_timestamp'), int),
            self._encode_value(IESDataParticleKey.TRAVEL_TIMES, self.match.group('n_travel_times'), int),
            self._encode_value(IESDataParticleKey.TRAVEL_TIME_1, self.match.group('travel_1'), int),
            self._encode_value(IESDataParticleKey.TRAVEL_TIME_2, self.match.group('travel_2'), int),
            self._encode_value(IESDataParticleKey.TRAVEL_TIME_3, self.match.group('travel_3'), int),
            self._encode_value(IESDataParticleKey.TRAVEL_TIME_4, self.match.group('travel_4'), int),
            self._encode_value(IESDataParticleKey.PRESSURE, self.match.group('pressure'), int),
            self._encode_value(IESDataParticleKey.TEMPERATURE, self.match.group('temp'), int),
            self._encode_value(IESDataParticleKey.BLILEY_TEMPERATURE, self.match.group('bliley_temp'), int),
            self._encode_value(IESDataParticleKey.BLILEY_FREQUENCY, self.match.group('bliley_freq'), float),
            self._encode_value(IESDataParticleKey.STM_TIMESTAMP, self.match.group('stm_timestamp'), int),
        ]


class IESStatusParticleKey(BaseEnum):
    """
    HEF Motor Current data stream
    """
    DATA_VALID = 'hpies_data_valid'
    IES_TIME = 'hpies_ies_timestamp'
    TRAVEL_TIMES = 'hpies_status_travel_times'
    PRESSURES = 'hpies_status_pressures'
    TEMPERATURES = 'hpies_status_temperatures'
    PFREQUENCIES = 'hpies_status_pressure_frequencies'
    TFREQUENCIES = 'hpies_status_temperature_frequencies'
    BACKUP_BATTERY = 'hpies_backup_battery_voltage'
    RELEASE_DRAIN = 'hpies_release_drain'
    SYSTEM_DRAIN = 'hpies_system_drain'
    RELEASE_BATTERY = 'hpies_release_battery_voltage'
    SYSTEM_BATTERY = 'hpies_system_battery_voltage'
    RELEASE_SYSTEM = 'hpies_release_system_voltage'
    INTERNAL_TEMP = 'hpies_internal_temperature'
    MEAN_TRAVEL = 'hpies_average_travel_time'
    MEAN_PRESSURE = 'hpies_average_pressure'
    MEAN_TEMPERATURE = 'hpies_average_temperature'
    LAST_PRESSURE = 'hpies_last_pressure'
    LAST_TEMPERATURE = 'hpies_last_temperature'
    IES_OFFSET = 'hpies_ies_clock_error'


class IESStatusParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.ECHO_STATUS

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES IES status particle

        Sample Data:
        #5_T:388559 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 999999 \r\n*cb7a
        #5_P:388559 10932 23370  10935 23397  10934 23422  10934 23446  10933 23472  10932 23492  \r\n*9c3e
        #5_F:388559 33228500 172170704  33228496 172170928  33228492 172171120  33228488 172171312  33228484 172171504  33228480 172171664  \r\n*e505
        #5_E:388559 2.29 0.01 0.00 14.00 6.93 5.05 23.83 0.0000 10935 1623 33228.480 172171.656 0.109 \r\n*1605
        """
        pattern = r"""
            (?x)
                                 \#5_T:
            (?P<ies_time>        %(int)s) \s
            (?P<travel_times>    (%(int)s \s){24})
                                 \\r\\n\*
            (?P<crc>             %(crc)s) \s+
                                 \#5_P:
            (?P<ies_time2>       %(int)s) \s
            (?P<pt>              (%(int)s \s+){12}) \s+
                                 \\r\\n\*
            (?P<crc2>            %(crc)s) \s+
                                 \#5_F:
            (?P<ies_time3>       %(int)s) \s
            (?P<ptf>             (%(int)s \s+){12}) \s+
                                 \\r\\n\*
            (?P<crc3>            %(crc)s) \s+
                                 \#5_E:
            (?P<ies_time4>       %(int)s)   \s
            (?P<backup_battery>  %(float)s) \s
            (?P<release_drain>   %(float)s) \s
            (?P<system_drain>    %(float)s) \s
            (?P<release_battery> %(float)s) \s
            (?P<system_battery>  %(float)s) \s
            (?P<release_system>  %(float)s) \s
            (?P<internal_temp>   %(float)s) \s
            (?P<mean_travel>     %(float)s) \s
            (?P<mean_pressure>   %(int)s)   \s
            (?P<mean_temp>       %(int)s)   \s
            (?P<last_pressure>   %(float)s) \s
            (?P<last_temp>       %(float)s) \s
            (?P<clock_offset>    %(float)s) \s
                                 \\r\\n\*
            (?P<crc4>             %(crc)s)
            """ % common_matches

        return pattern

    def check_crc(self):
        for line in self.raw_data.split(NEWLINE):
            crc_compute, crc_parse = calc_crc(line)
            data_valid = crc_compute == crc_parse
            if not data_valid:
                self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED
                log.warning("Corrupt data detected: [%r] - CRC %s != %s" % (line, hex(crc_compute), hex(crc_parse)))

    def _encode_all(self):
        travel_times = [int(x) for x in self.match.group('travel_times').split()]

        temp = [int(x) for x in self.match.group('pt').split()]
        pressures = temp[::2]
        temperatures = temp[1::2]

        temp = [int(x) for x in self.match.group('ptf').split()]
        pfrequencies = temp[::2]
        tfrequencies = temp[1::2]

        return [
            self._encode_value(IESStatusParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(IESStatusParticleKey.IES_TIME, self.match.group('ies_time'), int),
            self._encode_value(IESStatusParticleKey.TRAVEL_TIMES, travel_times, int),
            self._encode_value(IESStatusParticleKey.PRESSURES, pressures, int),
            self._encode_value(IESStatusParticleKey.TEMPERATURES, temperatures, int),
            self._encode_value(IESStatusParticleKey.PFREQUENCIES, pfrequencies, int),
            self._encode_value(IESStatusParticleKey.TFREQUENCIES, tfrequencies, int),
            self._encode_value(IESStatusParticleKey.BACKUP_BATTERY, self.match.group('backup_battery'), float),
            self._encode_value(IESStatusParticleKey.RELEASE_DRAIN, self.match.group('release_drain'), float),
            self._encode_value(IESStatusParticleKey.SYSTEM_DRAIN, self.match.group('system_drain'), float),
            self._encode_value(IESStatusParticleKey.RELEASE_BATTERY, self.match.group('release_battery'), float),
            self._encode_value(IESStatusParticleKey.SYSTEM_BATTERY, self.match.group('system_battery'), float),
            self._encode_value(IESStatusParticleKey.RELEASE_SYSTEM, self.match.group('release_system'), float),
            self._encode_value(IESStatusParticleKey.INTERNAL_TEMP, self.match.group('internal_temp'), float),
            self._encode_value(IESStatusParticleKey.MEAN_TRAVEL, self.match.group('mean_travel'), float),
            self._encode_value(IESStatusParticleKey.MEAN_PRESSURE, self.match.group('mean_pressure'), int),
            self._encode_value(IESStatusParticleKey.MEAN_TEMPERATURE, self.match.group('mean_temp'), int),
            self._encode_value(IESStatusParticleKey.LAST_PRESSURE, self.match.group('last_pressure'), float),
            self._encode_value(IESStatusParticleKey.LAST_TEMPERATURE, self.match.group('last_temp'), float),
            self._encode_value(IESStatusParticleKey.IES_OFFSET, self.match.group('clock_offset'), float),
        ]


class TimestampParticleKey(BaseEnum):
    """
    HEF Motor Current data stream
    """
    DATA_VALID = 'hpies_data_valid'
    RSN_TIME = 'hpies_rsn_timestamp'
    STM_TIME = 'hpies_stm_timestamp'


class TimestampParticle(HPIESDataParticle):
    _data_particle_type = DataParticleType.TIMESTAMP

    @staticmethod
    def regex():
        """
        @return regex string for matching HPIES STM timestamp particle

        Sample Data:
        #2_TOD,1398883295,1398883288*0059
        """
        pattern = r"""
            (?x)
                          \#2_TOD  ,
            (?P<rsn_time> %(int)s) ,
            (?P<stm_time> %(int)s)
                                   \*
            (?P<crc>      %(crc)s)
            """ % common_matches

        return pattern

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        return [
            self._encode_value(TimestampParticleKey.DATA_VALID, self.check_crc(), bool),
            self._encode_value(TimestampParticleKey.RSN_TIME, self.match.group('rsn_time'), int),
            self._encode_value(TimestampParticleKey.STM_TIME, self.match.group('stm_time'), int),
        ]


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
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

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
    __metaclass__ = get_logging_metaclass(log_level='debug')

    particles = [
        DataHeaderParticle,  # HPIES_DATA_HEADER
        HEFDataParticle,  # HORIZONTAL_FIELD
        HEFMotorCurrentParticle,  # MOTOR_CURRENT
        CalStatusParticle,  # CALIBRATION_STATUS
        HEFStatusParticle,  # HPIES_STATUS
        IESDataParticle,  # ECHO_SOUNDING
        IESStatusParticle,  # ECHO_STATUS
        TimestampParticle,  # TIMESTAMP

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
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: {
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            },
            ProtocolState.COMMAND: {
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
            },
            ProtocolState.DIRECT_ACCESS: {
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            },
            ProtocolState.AUTOSAMPLE: {
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
            },
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        # Add response handlers for device commands.
        for cmd in Command.list():
            self._add_build_handler(cmd, self._build_command)
            self._add_response_handler(cmd, self._check_command)
        self._add_response_handler(Command.HEF_PARAMS, self._parse_hef_params_response)
        self._add_response_handler(Command.PREFIX, self._parse_prefix_response)
        for cmd in (Command.DEBUG_LEVEL,
                    Command.WSRUN_PINCH,
                    Command.NFC_CALIBRATE,
                    Command.CAL_HOLD,
                    Command.NHC_COMPASS,
                    Command.COMPASS_SAMPLES,
                    Command.COMPASS_DELAY,
                    Command.MOTOR_SAMPLES,
                    Command.EF_SAMPLES,
                    Command.CAL_SAMPLES,
                    Command.CONSOLE_TIMEOUT,
                    Command.WSRUN_DELAY,
                    Command.MOTOR_DIR_NHOLD,
                    Command.POWER_COMPASS_W_MOTOR,
                    Command.KEEP_AWAKE_W_MOTOR,
                    Command.MOTOR_TIMEOUTS_1A,
                    Command.MOTOR_TIMEOUTS_1B,
                    Command.MOTOR_TIMEOUTS_2A,
                    Command.MOTOR_TIMEOUTS_2B,
                    Command.RSN_CONFIG,
                    Command.INVERT_LED_DRIVERS,
                    Command.M1A_LED,
                    Command.M2A_LED, ):
            self._add_response_handler(cmd, self._parse_set_param_response)

        # Add sample handlers.

        self._build_command_dict()
        self._build_driver_dict()

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        for particle in Protocol.particles:
            matchers.append(particle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.SERIAL,
                             r'serno\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Serial Number',
                             description='Instrument serial number',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        self._param_dict.add(Parameter.DEBUG_LEVEL,
                             r'debug\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Debug Level',
                             description='Debug logging control value (0 means no output).',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=0,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.WSRUN_PINCH,
                             r'wsrun pinch secs\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.SECOND,
                             display_name='WS Run Pinch',
                             description='Half cycle interval between water switch tube pinch',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=120,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.NFC_CALIBRATE,
                             r'nfc calibrate\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=HPIESUnits.CYCLE,
                             display_name='Calibration Periodicity',
                             description='Number of cycles of water switch between applying cal',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=15,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.CAL_HOLD,
                             r'cal hold secs\s+= (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units=Units.SECOND,
                             display_name='Calibrate Hold',
                             description='hold time of calibration voltage',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=20,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.CAL_SKIP,
                             r'cal skip secs\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.SECOND,
                             display_name='Calibrate Skip',
                             description='Time to wait before using data after changing the calibration signal state',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        self._param_dict.add(Parameter.NHC_COMPASS,
                             r'nhc compass\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=HPIESUnits.HALF_CYCLE,
                             display_name='Compass Measurement Periodicity',
                             description='Number of half cycles between compass measurements',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=30,
                             direct_access=True,
                             startup_param=True)
        self._param_dict.add(Parameter.COMPASS_SAMPLES,
                             r'compass nget\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Compass Samples',
                             description='Number of compass samples to acquire in a burst',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=1,
                             direct_access=True,
                             startup_param=True)
        # time between measurements in a burst
        self._param_dict.add(Parameter.COMPASS_DELAY,
                             r'compass dsecs\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.SECOND,
                             display_name='Compass Samples',
                             description='Time between measurements in a burst',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=10,
                             startup_param=True,
                             direct_access=True)
        # initial compass measurement (in seconds)
        self._param_dict.add(Parameter.INITIAL_COMPASS,
                             r'icompass run secs\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.SECOND,
                             display_name='Initial Compass Run',
                             description='Initial compass measurement',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        self._param_dict.add(Parameter.INITIAL_COMPASS_DELAY,
                             r'icompass dsecs\s+= (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units=Units.SECOND,
                             display_name='Compass Samples',
                             description='Initial compass delay',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        # FILE_LENGTH = 'secs per ofile'  # seconds per file (default 86400 - one day)
        self._param_dict.add(Parameter.MOTOR_SAMPLES,
                             r'navg mot\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of Motor Samples',
                             description='Number of samples to average (motor is sampled every 25 ms)',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=10,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.EF_SAMPLES,
                             r'navg ef\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of HEF Samples',
                             description='Number of samples to average (EF is sampled every 0.1024 s)',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=10,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.CAL_SAMPLES,
                             r'navg cal\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of Calibration Samples',
                             description='Number of samples to average (ef is sampled every 0.1024 s during cal)',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=10,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(
            Parameter.CONSOLE_TIMEOUT,
            r'console off timeout\s+= (%(int)s)' % common_matches,
            lambda match: int(match.group(1)),
            None,
            type=ParameterDictType.INT,
            units=Units.SECOND,
            display_name='Console Timeout',
            description='UART drivers turns off for console port (will come on temporarily for data out).',
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=300,
            startup_param=True,
            direct_access=True)
        self._param_dict.add(Parameter.WSRUN_DELAY,
                             r'wsrun delay secs\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.SECOND,
                             display_name='WS Run Delay (secs)',
                             description='',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=0,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_DIR_NHOLD,
                             r'motor dir nhold\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Motor Direction',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=0,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_DIR_INIT,
                             r'motor dir init\s+= (\w+)',
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Motor Direction (Initial)',
                             value_description='f - forward, r - reverse',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value='f',  # forward
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.POWER_COMPASS_W_MOTOR,
                             r'do_compass_pwr_with_motor\s+= (%(int)s)' % common_matches,
                             lambda match: bool(int(match.group(1))),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Power Compass with Motor',
                             description='Apply power to compass when motor is on',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=False,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.KEEP_AWAKE_W_MOTOR,
                             r'do_keep_awake_with_motor\s+= (%(int)s)' % common_matches,
                             lambda match: bool(int(match.group(1))),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Keep Awake with Motor',
                             description='Keep instrument awake while motor is running',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=True,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_1A,
                             r'm1a_tmoc\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ' + Units.MILLISECOND,
                             display_name='Motor Timeouts 1A',
                             description='Timeout counts for motor 1A',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=200,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_1B,
                             r'm1b_tmoc\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ' + Units.MILLISECOND,
                             display_name='Motor Timeouts 1B',
                             description='Timeout counts for motor 1B',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=200,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_2A,
                             r'm2a_tmoc\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ' + Units.MILLISECOND,
                             display_name='Motor Timeouts 2A',
                             description='Timeout counts for motor 2A',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=200,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_2B,
                             r'm2b_tmoc\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ' + Units.MILLISECOND,
                             display_name='Motor Timeouts 2B',
                             description='Timeout counts for motor 2B',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             default_value=200,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.RSN_CONFIG,
                             r'do_rsn\s+= (%(int)s)' % common_matches,
                             lambda match: bool(int(match.group(1))),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Configured for RSN',
                             description='Use RSN configuration',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=True,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.INVERT_LED_DRIVERS,
                             r'led_drivers_invert\s+= (%(int)s)' % common_matches,
                             lambda match: bool(int(match.group(1))),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Invert LED Drivers',
                             description='Whether or not LED drivers have been inverted',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=False,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.M1A_LED,
                             r'm1a_led\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='M1A LED',
                             description='',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             default_value=1,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.M2A_LED,
                             r'm2a_led\s+= (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='M2A LED',
                             description='',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)
        # IES Parameters - read only - no defaults
        self._param_dict.add(Parameter.ECHO_SAMPLES,
                             r'Travel Time Measurements: (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='1/600 ' + Units.HERTZ,
                             display_name='Echo Samples',
                             description='Number of travel time measurements',
                             value_description='number of pings every 10 minutes',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WATER_DEPTH,
                             r'Estimated Water Depth: (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.METER,
                             display_name='Estimated Water Depth',
                             description='Estimate of water depth at instrument location',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ACOUSTIC_LOCKOUT,
                             r'Acoustic Lockout: (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units=Units.SECOND,
                             display_name='Acoustic Lockout',
                             description='',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ACOUSTIC_OUTPUT,
                             r'Acoustic Output: (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units=Units.DECIBEL,
                             display_name='Acoustic Output',
                             description='',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.RELEASE_TIME,
                             r'Release Time: (%(rest)s)' % common_matches,
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Release Time',
                             description='',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.COLLECT_TELEMETRY,
                             r'Telemetry data file (enabled|disabled)',
                             lambda match: True if match.group(1) == 'enabled' else False,
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Telemetry Data File',
                             description='',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MISSION_STATEMENT,
                             r'Mission Statement: (%(rest)s)' % common_matches,
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Mission Statement',
                             description='Descriptive statement of the mission purpose',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PT_SAMPLES,
                             r'Pressure and Temperature measured every (%(int)s)' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='1/600 ' + Units.HERTZ,
                             display_name='Pressure/Temperature Samples',
                             description='Periodicity of pressure and temperature sampling',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_U0,
                             r'U0 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-U0',
                             description='Temperature coefficient U0',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y1,
                             r'Y1 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y1',
                             description='Temperature coefficient Y1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y2,
                             r'Y2 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y2',
                             description='Temperature coefficient Y2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y3,
                             r'Y3 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C1,
                             r'C1 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C1',
                             description='Temperature coefficient C1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C2,
                             r'C2 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C2',
                             description='Temperature coefficient C2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C3,
                             r'C3 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C3',
                             description='Temperature coefficient C3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_D1,
                             r'D1 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-D1',
                             description='Temperature coefficient D1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_D2,
                             r'D2 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-D2',
                             description='Temperature coefficient D2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T1,
                             r'T1 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T1',
                             description='Temperature coefficient T1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T2,
                             r'T2 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T2',
                             description='Temperature coefficient T2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T3,
                             r'T3 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T3',
                             description='Temperature coefficient T3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T4,
                             r'T4 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T4',
                             description='Temperature coefficient T4',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T5,
                             r'T5 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T5',
                             description='Temperature coefficient T5',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_OFFSET,
                             r'Temperature offset = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units=Units.DEGREE_CELSIUS,
                             display_name='Temperature Offset',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_OFFSET,
                             r'Pressure offset = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units=Units.POUND_PER_SQUARE_INCH,
                             display_name='Pressure Offset',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_0,
                             r'B0 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B0',
                             description='Bliley temperature coefficient B0',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_1,
                             r'B1 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B1',
                             description='Bliley temperature coefficient B1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_2,
                             r'B2 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B2',
                             description='Bliley temperature coefficient B2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_3,
                             r'B3 = (%(float)s)' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B3',
                             description='Bliley temperature coefficient B3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        for particle in Protocol.particles:
            self._extract_sample(particle, particle.regex_compiled(), chunk, timestamp)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _wakeup(self, wakeup_timeout=10, response_timeout=3):
        """
        Override the default wakeup to do nothing. Instead, an explicit call to _hef_wakeup is required prior
        to sending commands to the instrument.
        """
        pass

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Calls parent _do_cmd_resp and auto-retries if a timeout occurs.

        @param cmd      instrument command
        @param retries  (optional) number of retries (default = 3)
        """
        attempts = 0
        retries = kwargs.get('retries', 3)

        while True:
            try:
                return super(Protocol, self)._do_cmd_resp(cmd, *args, **kwargs)
            except InstrumentTimeoutException as e:
                attempts += 1
                if attempts == retries:
                    raise e
                log.warn('timeout for command (%s): retrying...' % cmd)

    def _hef_wakeup(self):
        """
        wakeup the instrument
        The only current deterministic way to know if the instrument is awake is to see if it responds to a
        parameter request. If it does not, it must be restarted.

        MUST BE CALLED PRIOR TO SENDING A SERIES OF COMMANDS TO THE INSTRUMENT

        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # if we are able to get the parameters from the HEF, it is already awake
        try:
            self._do_cmd_resp(Command.HEF_WAKE, expected_prompt=Prompt.DEFAULT)
            self._do_cmd_resp(Command.HEF_PARAMS, expected_prompt=Prompt.HEF_PROMPT, timeout=Timeout.HEF_PARAMS)
            log.debug('HPIES is awake')

        # otherwise, we need to restart
        except InstrumentTimeoutException:
            self._do_cmd_resp(Command.REBOOT, expected_prompt=Prompt.DEFAULT, timeout=Timeout.REBOOT)
            self._do_cmd_resp(Command.ACQUISITION_START, expected_prompt=Prompt.DEFAULT,
                              timeout=Timeout.ACQUISITION_START)
            self._do_cmd_hef_on()
            self._do_cmd_resp(Command.HEF_PARAMS, expected_prompt=Prompt.HEF_PROMPT, timeout=Timeout.HEF_PARAMS)
            log.debug('HPIES is awake')

    def _build_command(self, cmd, *args):
        """
        @brief assemble command string to send to instrument
        Called by _do_cmd_* functions to build a command string for @a cmd.
        @retval command string to send to the instrument
        """
        if cmd in (Command.REBOOT,
                   Command.ACQUISITION_START,
                   Command.ACQUISITION_STOP,
                   Command.IES_PORT_ON,
                   Command.IES_PORT_OFF,
                   Command.IES_POWER_ON,
                   Command.IES_POWER_OFF,
                   Command.HEF_PORT_ON,
                   Command.HEF_PORT_OFF,
                   Command.HEF_POWER_ON,
                   Command.HEF_POWER_OFF,
                   Command.HEF_WAKE,
                   Command.SYNC_CLOCK):
            return stm_command(cmd, *args)
        elif cmd in (Command.PREFIX,
                     Command.HEF_PARAMS,
                     Command.HEF_SAVE,
                     Command.MISSION_START,
                     Command.MISSION_STOP,
                     Command.DEBUG_LEVEL,
                     Command.WSRUN_PINCH,
                     Command.NFC_CALIBRATE,
                     Command.CAL_HOLD,
                     Command.NHC_COMPASS,
                     Command.COMPASS_SAMPLES,
                     Command.COMPASS_DELAY,
                     Command.MOTOR_SAMPLES,
                     Command.EF_SAMPLES,
                     Command.CAL_SAMPLES,
                     Command.CONSOLE_TIMEOUT,
                     Command.WSRUN_DELAY,
                     Command.MOTOR_DIR_NHOLD,
                     Command.MOTOR_DIR_INIT,
                     Command.POWER_COMPASS_W_MOTOR,
                     Command.KEEP_AWAKE_W_MOTOR,
                     Command.MOTOR_TIMEOUTS_1A,
                     Command.MOTOR_TIMEOUTS_1B,
                     Command.MOTOR_TIMEOUTS_2A,
                     Command.MOTOR_TIMEOUTS_2B,
                     Command.RSN_CONFIG,
                     Command.INVERT_LED_DRIVERS,
                     Command.M1A_LED,
                     Command.M2A_LED):
            return hef_command(cmd, *args)
        raise InstrumentProtocolException('attempt to process unknown command: %r' % cmd)

    def _check_command(self, resp, prompt):
        for line in resp.split(NEWLINE):
            if not valid_response(line):
                raise InstrumentProtocolException('checksum failed (%r)' % line)

    def _build_driver_dict(self):
        """
        @brief Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _build_command_dict(self):
        """
        @brief Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name='start autosample')
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name='stop autosample')

    def _parse_hef_params_response(self, response, prompt):
        """
        @brief process the response for request to get HEF parameters
        @param response command string
        @retval True if able to update parameters, False otherwise
        """
        log.debug('djm parameter dictionary:\r%s', self._param_dict.get_all())
        if re.match(Response.ERROR, response):
            raise InstrumentParameterException('unable to get parameters - data acquisition has not been started')

        param_lines = []
        for line in response.split(NEWLINE):
            log.debug('checking line for parameter: %r' % line)
            if ' = ' in line:
                if valid_response(line):
                    log.debug('checksum valid, setting value')
                    param_lines.append(line)
        dictionary = self._param_dict.update_many(response)
        if dictionary:
            log.debug('djm updated dictionary: %r', self._param_dict.get_all())
            return True

        return False

    def _do_cmd_prefix(self):
        """
        Establish a valid filename to store data.
        """
        prefix_bad = True
        prefix_file = ''
        while prefix_bad:
            prefix_root = tempfile.mktemp(prefix='', dir='')
            prefix_file = self._do_cmd_resp(Command.PREFIX, prefix_root,
                                            expected_prompt=Prompt.HEF_PROMPT,
                                            timeout=Timeout.PREFIX)
            if prefix_file is not None:
                prefix_bad = False
                log.debug('opened file with prefix: %s', prefix_file)
        return prefix_file

    def _do_cmd_ies_on(self):
        """
        Turn on the IES
        """
        try:
            self._do_cmd_resp(Command.IES_PORT_ON, expected_prompt=Prompt.DEFAULT, timeout=Timeout.IES_PORT_ON)
            self._do_cmd_resp(Command.IES_POWER_ON, response_regex=Response.IES_POWER_ON, timeout=Timeout.IES_POWER_ON)
            self._do_cmd_resp(Command.IES_PORT_OFF, expected_prompt=Prompt.DEFAULT, timeout=Timeout.IES_PORT_OFF)
        except InstrumentTimeoutException:
            raise InstrumentTimeoutException('IES did not respond to power on sequence')

    def _do_cmd_hef_on(self):
        """
        Turn on the HEF
        """
        try:
            self._do_cmd_resp(Command.HEF_PORT_ON, expected_prompt=Prompt.HEF_PORT_ON, timeout=Timeout.HEF_PORT_ON)
            self._do_cmd_resp(Command.HEF_POWER_ON, response_regex=Response.HEF_POWER_ON, timeout=Timeout.HEF_POWER_ON)
            self._do_cmd_resp(Command.HEF_WAKE, expected_prompt=Prompt.DEFAULT)
        except InstrumentTimeoutException:
            raise InstrumentTimeoutException('HEF did not respond to power on sequence')

    def _parse_prefix_response(self, response, prompt):
        """
        Check @a response from request to set prefix filename.
        @param response response from instrument
        @param prompt - ??
        @retval filename to be used or None if requested prefix is already in use
        """
        filename = None
        matches = re.search(Response.OPENED_FILE, response)
        if matches:
            filename = matches.group(1)

        return filename

    def _parse_set_param_response(self, response, prompt):
        """
        Check @a response from request to set HEF parameter
        @param response response from instrument
        @param prompt - ??
        @retval value from set or None if there was an error setting value
        """
        try:
            self._check_command(response, prompt)
            self._param_dict.update(response)
        except InstrumentProtocolException:
            pass

        return response

    ########################################################################
    # Unknown handlers
    ########################################################################

    def _handler_unknown_enter(self):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        pass

    def _handler_unknown_discover(self):
        # any existing mission needs to be stopped. If one is not already running, no harm in sending the stop.
        self._do_cmd_no_resp(Command.MISSION_STOP)
        # delay so the instrument doesn't overwrite the next response
        time.sleep(2)

        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self):
        """
        Enter command state.

        Startup HPIES and get it into a state where we can get/set parameters.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        self._init_params()

        try:
            self._do_cmd_resp(Command.REBOOT, expected_prompt=Prompt.DEFAULT, timeout=Timeout.REBOOT)
            self._do_cmd_resp(Command.ACQUISITION_START, expected_prompt=Prompt.DEFAULT,
                              timeout=Timeout.ACQUISITION_START)
            self._do_cmd_ies_on()
            self._do_cmd_hef_on()

            self._do_cmd_resp(Command.HEF_PARAMS, expected_prompt=Prompt.HEF_PROMPT, timeout=Timeout.HEF_PARAMS)

        except InstrumentTimeoutException as e:
            log.error('Unable to initialize HPIES: %r', e.message)
            self._async_raise_fsm_event(ProtocolEvent.EXIT)
            raise e

        # Command device to update parameters and send a config change event.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict
        First we set a baseline timestamp that all data expirations will be calculated against.
        Then we try to get parameter value.  If we catch an expired parameter then we will update
        all parameters and get values using the original baseline time that we set at the beginning of this method.
        Assuming our _update_params is updating all parameter values properly then we can
        ensure that all data will be fresh.  Nobody likes stale data!
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @raise InstrumentParameterException if missing or invalid parameter.
        @raise InstrumentParameterExpirationException If we fail to update a parameter
        on the second pass this exception will be raised on expired data
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args):
        """
        perform a set command
        @param args[0] parameter : value dict.
        @param args[1] parameter : startup parameters?
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        startup = False

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        self._set_params(params, startup)

        return None, None

    def _handler_command_start_autosample(self):
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_direct(self):
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_exit(self, *args, **kwargs):
        pass

    ########################################################################
    # Autosample handlers
    ########################################################################
    def _handler_autosample_enter(self):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        try:
            self._do_cmd_prefix()
            self._do_cmd_resp(Command.MISSION_START, expected_prompt=Prompt.HEF_PROMPT, timeout=Timeout.MISSION_START)
            log.debug('mission start completed')

        except InstrumentTimeoutException as e:
            log.error('Unable to start autosample: %r', e.message)
            self._async_raise_fsm_event(ProtocolEvent.STOP_AUTOSAMPLE)
            raise e

    def _handler_autosample_stop_autosample(self):
        """
        Process command to stop auto-sampling. Return to command state.
        """
        try:
            self._do_cmd_resp(Command.MISSION_STOP, expected_prompt=Prompt.DEFAULT, timeout=Timeout.MISSION_STOP)
            self._do_cmd_resp(Command.ACQUISITION_STOP, expected_prompt=Prompt.DEFAULT,
                              timeout=Timeout.ACQUISITION_STOP)

        except InstrumentTimeoutException as e:
            log.warning('Unable to terminate mission cleanly: %r', e.message)

        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_autosample_exit(self, *args, **kwargs):
        # no special cleanup required
        pass

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_execute_direct(self, data):
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_direct_access_exit(self):
        pass

    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @raise: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("CURRENT STATE: %s", self.get_current_state())
        if (self.get_current_state() != DriverProtocolState.COMMAND and
                    self.get_current_state() != DriverProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if not self._instrument_config_dirty():
            log.debug("configuration not dirty.  Nothing to do here")
            return True

        error = None

        try:
            log.debug("apply_startup_params now")
            self._set_params(self.get_startup_config(), True)
            self._do_cmd_resp(Command.HEF_SAVE, expected_prompt=Prompt.HEF_PROMPT, timeout=Timeout.HEF_SAVE)

        # Catch all errors so we can put driver back into streaming. Then rethrow the error.
        except Exception as e:
            error = e

        if error:
            log.error("Error in apply_startup_params: %s", error)
            raise error

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @raise: InstrumentParameterException
        """
        # Refresh the param dict cache

        self._update_params()

        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s", startup_params)

        for param in startup_params:
            if self._param_dict.get(param) != self._param_dict.get_config_value(param):
                log.debug("DIRTY: %s %s != %s", param, self._param_dict.get(param),
                          self._param_dict.get_config_value(param))
                return True

        log.debug("Clean instrument config")
        return False

    def _update_params(self):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # wakeup will get the latest parameters from the instrument
        self._hef_wakeup()

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()

        log.debug("Old Config: %s", old_config)
        log.debug("New Config: %s", new_config)
        if not dict_equal(new_config, old_config) and self._protocol_fsm.get_current_state() != ProtocolState.UNKNOWN:
            log.debug("parameters updated, sending event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _verify_set_values(self, params):
        """
        Verify supplied values are in range, if applicable
        @param params: Dictionary of Parameter:value to be verified
        @throws InstrumentParameterException
        """
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()

        # step through the list of parameters
        for key, val in params.iteritems():
            # if constraint exists, verify we have not violated it
            constraint_key = parameters.get(key)
            if constraint_key in constraints:
                var_type, minimum, maximum = constraints[constraint_key]
                constraint_string = 'Parameter: %s Value: %s Type: %s Real Type: %s Minimum: %s Maximum: %s' % \
                                    (key, val, var_type, type(val), minimum, maximum)
                log.debug('SET CONSTRAINT: %s', constraint_string)
                # check bool values are actual booleans
                if var_type == bool:
                    if val not in [True, False]:
                        raise InstrumentParameterException('Non-boolean value!: %s' % constraint_string)
                # else, check if we can cast to the correct type
                else:
                    try:
                        val = var_type(val)
                    except ValueError:
                        raise InstrumentParameterException('Type mismatch: %s' % constraint_string)
                    # now, verify we are within min/max
                    if val < minimum or val > maximum:
                        raise InstrumentParameterException('Out of range: %s' % constraint_string)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        old_config = self._param_dict.get_all()

        self._verify_set_values(params)
        self._verify_not_readonly(*args, **kwargs)

        for key, val in params.iteritems():
            if not key in old_config:
                raise InstrumentParameterException('attempted to set unknown parameter: %s to %s' % (key, val))
            command_response = self._do_cmd_resp(key, val, expected_prompt=Prompt.HEF_PROMPT)
            log.debug('command: %r returned: %r', key, command_response)

        new_config = self._param_dict.get_all()
        log.debug('djm old config: %r', old_config)
        log.debug('djm new config: %r', new_config)

        if new_config != old_config:
            log.debug('djm configuration differs, saving parameters and signaling event')
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

