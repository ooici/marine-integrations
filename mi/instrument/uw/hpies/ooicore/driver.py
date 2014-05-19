"""
@package mi.instrument.uw.hpies.ooicore.driver
@file marine-integrations/mi/instrument/uw/hpies/ooicore/driver.py
@author Dan Mergens
@brief Driver for the ooicore
Release notes:

initial_rev
"""
import re

from mi.core.exceptions import SampleException, InstrumentProtocolException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.instrument.uw.hpies.crclib import crc3kerm


__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

from mi.core.log import \
    get_logger, \
    get_logging_metaclass

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType, DataParticleKey, DataParticle
from mi.core.instrument.chunker import StringChunker


# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

common_matches = {
    'float': r'-?\d*\.?\d+',
    'int': r'-?\d+',
    'str': r'\w+',
    'fn': r'\S+',
    'rest': r'.*',
    'tod': r'\d{8}T\d{6}',
    'data': r'[^\*]+',
    'crc': r'[0-9a-fA-F]{4}'
}


def build_command(address, command, *args):
    s = '#' + address + '_' + command
    s += " ".join([str(x) for x in args])
    s = s + str.format('*{0:04x}', crc3kerm(s)) + '\r'
    return s


def valid_response(resp):
    """
    @brief Check response for valid checksum.
    @param resp response line
    @return - whether or not checksum matches data
    """
    pattern = re.compile(
        r'^(?P<tod>%(tod)s) (?P<resp>%(data)s)\*(?P<crc>%(crc)s)' % common_matches)
    matches = re.match(pattern, resp)
    resp_crc = int(matches.group('crc'), 16)
    data = matches.group('resp')
    calc_crc = crc3kerm(data)
    return calc_crc == resp_crc


def stm_command(s, *args):
    """
    Create fully qualified STM command (add prefix and postfix the CRC).
    """
    return build_command('1', s, args)


def hef_command(s, *args):
    """
    Create fully qualified HEF command (add prefix and postfix the CRC).
    """
    return build_command('3', s, args)


def ies_command(s, *args):
    """
    Create fully qualified IES command (add prefix and postfix the CRC).
    """
    return build_command('4', s, args)


###
#    Driver Constant Definitions
###

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    # TEST = DriverProtocolState.TEST  # no test defined
    # CALIBRATE = DriverProtocolState.CALIBRATE  # instrument auto-calibrates


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
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Instrument specific parameters
    """
    # HEF parameters
    SERIAL = 'serno'
    DEBUG_LEVEL = 'debug'
    WSRUN_PINCH = 'wsrun pinch secs'  # half cycle interval between water switch tube pinch
    # EF_SKIP = 'ef skip secs'  # time in seconds to wait fbefore using EF data after moving motors
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
    POWER_COMPASS_W_MOTOR = 'do_compass_pwr_with_motor'  # false
    KEEP_AWAKE_W_MOTOR = 'do_keep_awake_with_motor'  # true
    MOTOR_TIMEOUTS_1A = 'm1a_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_1B = 'm1b_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_2A = 'm2a_tmoc'  # timeout counts for motor - 200
    MOTOR_TIMEOUTS_2B = 'm2b_tmoc'  # timeout counts for motor - 200
    RSN_CONFIG = 'do_rsn'  # configured for RSN (instead of autonomous) - true
    INVERT_LED_DRIVERS = 'led_drivers_invert'  # false
    M1A_LED = 'm1a_led'  # 1
    M2A_LED = 'm2a_led'  # 3

    # Inverter Echo Sounder parameters - all these are read-only
    IES_TIME = 'date_time'  # current time from IES internal clock
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

    BLILEY_0 = 'bliley B0'  # -0.575100
    BLILEY_1 = 'bliley B1'  # -0.5282501
    BLILEY_2 = 'bliley B2'  # -0.013084390
    BLILEY_3 = 'bliley B3'  # 0.00004622697


class Prompt(BaseEnum):
    """
    Device I/O prompts
    """


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
    SYNC_CLOCK = 'force_RTC_update'  # align STM clock to RSN date/time

    # HEF specific commands
    PREFIX = 'prefix'
    MISSION_START = 'mission start'
    MISSION_STOP = 'mission stop'

    # 'term hef'  # change HEF parameters interactively
    # 'term ies'  # change IES parameters interactively
    # 'term tod'  # display RSN time of day
    # 'term aux'  # display IES AUX2 port
    # 'baud'  # display baud rate (serial RSN to STM)
    # 'baud #'  # set baud rate


class Response(BaseEnum):
    """
    Expected responses from HPIES
    """
    TIMESTAMP = re.compile(r'^(?P<tod>%(tod)s)' % common_matches)
    UNKNOWN_COMMAND = re.compile(r'.*?unknown command: .*?')
    # Expected responses from HPIES
    PROMPT = re.compile(r'^%(tod)s STM> .*?' % common_matches)
    REBOOT = re.compile(r'.*?File system mounted.*?')
    ACQUISITION_START = re.compile(r'.*?opened ofile.*?')
    HEF_OPTO_ON = PROMPT
    HEF_POWER_ON = PROMPT


###
# Data Particle Definitions
###

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver.
    """
    RAW = CommonDataParticleType.RAW
    HORIZONTAL_FIELD = 'horizontal_electric_field'
    MOTOR_CURRENT = 'motor_current'
    ECHO_SOUNDING = 'echo_sounding'
    CALIBRATION_STATUS = 'calibration_status'
    HPIES_STATUS = 'hpies_status'


class HEFDataParticleKey(BaseEnum):
    """
    Horizontal Electrical Field data stream
    """
    TIMESTAMP = 'date_time_string'
    INDEX = 'index'
    CHANNEL_1 = 'e1a'
    CHANNEL_2 = 'e1b'
    CHANNEL_3 = 'e2a'
    CHANNEL_4 = 'e2b'


class HEFDataParticle(DataParticle):
    _data_particle_type = DataParticleType.HORIZONTAL_FIELD

    # 20140501T173921 #3__DE 797 79380 192799 192803 192930*56a8

    @staticmethod
    def regex():
        pattern = r"""
            (?x)
            (?P<tod>       %(tod)s) \s
                           \#3__DE  \s
            (?P<index>     %(int)s) \s
            (?P<channel_1> %(int)s) \s
            (?P<channel_2> %(int)s) \s
            (?P<channel_3> %(int)s) \s
            (?P<channel_4> %(int)s)
                           \*
            (?P<crc>       %(crc)s)
            """ % common_matches

        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(HEFDataParticle.regex(), re.VERBOSE)

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        match = HEFDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        try:
            tod = match.group('tod')
            index = int(match.group('index'))
            channel_1 = int(match.group('channel_1'))
            channel_2 = int(match.group('channel_2'))
            channel_3 = int(match.group('channel_3'))
            channel_4 = int(match.group('channel_4'))
            crc = int(match.group('crc'), 16)

        except ValueError:
            raise SampleException("ValueError while converting data: [%r]" % self.raw_data)

        crc_compute = crc3kerm(self.raw_data)
        if not crc_compute == crc:
            raise SampleException("Corrupt data detected: [%r] - CRC %s != %s" %
                                  (self.raw_data, hex(crc_compute), hex(crc)))

        result = [
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: tod},
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.INDEX, DataParticleKey.VALUE: index},
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.CHANNEL_1, DataParticleKey.VALUE: channel_1},
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.CHANNEL_2, DataParticleKey.VALUE: channel_2},
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.CHANNEL_3, DataParticleKey.VALUE: channel_3},
            {DataParticleKey.VALUE_ID: HEFDataParticleKey.CHANNEL_4, DataParticleKey.VALUE: channel_4},
        ]

        return result


class HEFMotorCurrentDataParticleKey(BaseEnum):
    """
    HEF Motor Current data stream
    """
    TIMESTAMP = 'date_time_string'
    INDEX = 'hpies_mindex'
    CURRENT = 'hpies_motor_current'


class HEFMotorCurrentDataParticle(DataParticle):
    _data_particle_type = DataParticleType.MOTOR_CURRENT

    # 20140501T173728 #3__DM 11 24425*396b

    @staticmethod
    def regex():
        pattern = r"""
            (?x)
            (?P<tod>           %(tod)s) \s
                               \#3__DM  \s
            (?P<index>         %(int)s) \s
            (?P<motor_current> %(int)s)
                               \*
            (?P<crc>           %(crc)s)
            """ % common_matches

        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(HEFMotorCurrentDataParticle.regex())

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        match = HEFMotorCurrentDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        try:
            tod = match.group('tod')
            index = int(match.group('index'))
            motor_current = int(match.group('motor_current'))
            crc = int(match.group('crc'), 16)

        except ValueError:
            raise SampleException("ValueError while converting data: [%r]" % self.raw_data)

        crc_compute = crc3kerm(self.raw_data)
        if not crc_compute == crc:
            raise SampleException("Corrupt data detected: [%r] - CRC %s != %s" %
                                  (self.raw_data, hex(crc_compute), hex(crc)))

        result = [
            {DataParticleKey.VALUE_ID: HEFMotorCurrentDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: tod},
            {DataParticleKey.VALUE_ID: HEFMotorCurrentDataParticleKey.INDEX, DataParticleKey.VALUE: index},
            {DataParticleKey.VALUE_ID: HEFMotorCurrentDataParticleKey.CURRENT, DataParticleKey.VALUE: motor_current},
        ]

        return result


class IESDataParticleKey(BaseEnum):
    """
    Inverted Echo-Sounder data stream
    """
    TIMESTAMP = 'date_time_string'
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


class IESDataParticle(DataParticle):
    _data_particle_type = DataParticleType.ECHO_SOUNDING

    # 20140501T175203 #5_AUX,1398880200,04,999999,999999,999999,999999,0010848,021697,022030,04000005.252,1B05,1398966715*c69e

    @staticmethod
    def regex():
        pattern = r"""
            (?x)
            (?P<tod>            %(tod)s)   \s
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

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(IESDataParticle.regex())

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        match = IESDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        try:
            tod = match.group('tod')
            ies_timestamp = int(match.group('ies_timestamp'))
            travel_times = int(match.group('n_travel_times'))
            travel_1 = int(match.group('travel_1'))
            travel_2 = int(match.group('travel_2'))
            travel_3 = int(match.group('travel_3'))
            travel_4 = int(match.group('travel_4'))
            pressure = int(match.group('pressure'))
            temp = int(match.group('temp'))
            bliley_temp = int(match.group('bliley_temp'))
            bliley_freq = int(match.group('bliley_freq'))
            stm_timestamp = int(match.group('stm_timestamp'))
            crc = int(match.group('crc'), 16)

        except ValueError:
            raise SampleException("ValueError while converting data: [%r]" % self.raw_data)

        crc_compute = crc3kerm(self.raw_data)
        if not crc_compute == crc:
            raise SampleException("Corrupt data detected: [%r] - CRC %s != %s" %
                                  (self.raw_data, hex(crc_compute), hex(crc)))

        result = [
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: tod},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.IES_TIMESTAMP, DataParticleKey.VALUE: ies_timestamp},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TRAVEL_TIMES, DataParticleKey.VALUE: travel_times},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TRAVEL_TIME_1, DataParticleKey.VALUE: travel_1},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TRAVEL_TIME_2, DataParticleKey.VALUE: travel_2},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TRAVEL_TIME_3, DataParticleKey.VALUE: travel_3},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TRAVEL_TIME_4, DataParticleKey.VALUE: travel_4},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.PRESSURE, DataParticleKey.VALUE: pressure},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.TEMPERATURE, DataParticleKey.VALUE: temp},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.BLILEY_TEMPERATURE, DataParticleKey.VALUE: bliley_temp},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.BLILEY_FREQUENCY, DataParticleKey.VALUE: bliley_freq},
            {DataParticleKey.VALUE_ID: IESDataParticleKey.STM_TIMESTAMP, DataParticleKey.VALUE: stm_timestamp},
        ]

        return result


class CalDataParticleKey(BaseEnum):
    """
    @brief Calibration status data particle

    Calibration data is sent every two minutes during autosample
    """
    TIMESTAMP = 'date_time_string'
    INDEX = 'hpies_cindex'
    E1C = 'hpies_e1c'
    E1A = 'hpies_e1a'
    E1B = 'hpies_e1b'
    E2C = 'hpies_e2c'
    E2A = 'hpies_e2a'
    E2B = 'hpies_e2b'


class CalDataParticle(DataParticle):
    _data_particle_type = DataParticleType.CALIBRATION_STATUS

    # 20140430T230632 #3__DC 2 192655 192637 135611 80036 192554 192644*5c28

    @staticmethod
    def regex():
        pattern = r"""
            (?x)
            (?P<tod>   %(tod)s) \s
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

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(CalDataParticle.regex())

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        match = CalDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        try:
            tod = match.group('tod')
            index = int(match.group('index'))
            e1c = int(match.group('e1c'))
            e1a = int(match.group('e1a'))
            e1b = int(match.group('e1b'))
            e2c = int(match.group('e2c'))
            e2a = int(match.group('e2a'))
            e2b = int(match.group('e2b'))
            crc = int(match.group('crc'), 16)

        except ValueError:
            raise SampleException("ValueError while converting data: [%r]" % self.raw_data)

        crc_compute = crc3kerm(self.raw_data)
        if not crc_compute == crc:
            raise SampleException("Corrupt data detected: [%r] - CRC %s != %s" %
                                  (self.raw_data, hex(crc_compute), hex(crc)))

        result = [
            {DataParticleKey.VALUE_ID: CalDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: tod},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.INDEX, DataParticleKey.VALUE: index},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E1C, DataParticleKey.VALUE: e1c},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E1A, DataParticleKey.VALUE: e1a},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E1B, DataParticleKey.VALUE: e1b},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E2C, DataParticleKey.VALUE: e2c},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E2A, DataParticleKey.VALUE: e2a},
            {DataParticleKey.VALUE_ID: CalDataParticleKey.E2B, DataParticleKey.VALUE: e2b},
        ]

        return result


class StatusDataParticleKey(BaseEnum):
    """
    @brief HPIES status data particle

    HPIES status is sent every X minutes during autosample
    """
    TIMESTAMP = 'date_time_string'
    UNIX_TIME = 'hpies_secs'  # elapsed time since unix epoch
    HCNO = 'hpies_hcno'  # Half cycle number (int)
    HCNO_LAST_CAL = 'hpies_hcno_last_cal'  # Half cycle number of last calibration (int)
    HCNO_LAST_COMP = 'hpies_hcno_last_comp'  # Half cycle number of last compass value	 1	 int
    OFILE = 'hpies_ofile'  # Current output filename	1	str	remove?
    IFOK = 'hpies_ifok'  # File write status	1	str	"NG" on error, "OK" if still appending  remove?
    N_COMPASS_WRITES = 'hpies_compass_fwrite_attempted'  # Number of compass records written to <ofile>	1	int	remove?
    N_COMPASS_FAIL_WRITES = 'hpies_compass_fwrite_ofp_null'  # Number of attempts to write compass data when <ofile> is corrupt	1	int	remove?
    MOTOR_POWER_UPS = 'hpies_mot_pwr_count'  # Up/down counter of motor power on/off.  Should be zero.	 1	 int
    N_SERVICE_LOOPS = 'hpies_start_motor_count'  # Number of main service loops while motor  current is being sampled.  1	 int
    SERIAL_PORT_ERRORS = 'hpies_compass_port_open_errs'  # Number of failures to open the compass  serial port.  1	 int
    COMPASS_PORT_ERRORS = 'hpies_compass_port_nerr'  # int	Always zero (never changed in code).  Remove?
    COMPASS_PORT_CLOSED_COUNT = 'hpies_tuport_compass_null_count'  # Number of times compass port is  found closed when trying to read it.
    IRQ2_COUNT = 'hpies_irq2_count'  # Number of interrupt requests on IRQ2 line of 68332.	 1	 int	 Should be zero.
    SPURIOUS_COUNT = 'hpies_spurious_count'  # Number of spurious interrupts to the 68332.	 1	 int	 Should be zero.
    SPSR_BITS56_COUNT = 'hpies_spsr_unknown_count'  # Number of times the SPSR register bits 5 and 6 are set.	 1	 int	 Should be zero.
    PIT_ZERO_COUNT = 'hpies_pitperiod_zero_count'  # Number of times the programable interval timer (PIT) is zero.	 1	 int	 Should be zero.
    ADC_BUFFER_OVERFLOWS = 'hpies_adc_raw_overflow_count'  # Number of times the analog to digital converter circular buffer overflows.	 1	 int	 Should be zero.
    MAX7317_QUEUE_OVERFLOWS = 'hpies_max7317_add_queue_errs'  # Number of times the max7317 queue overflows.	 1	 int	 Should be zero.
    PINCH_TIMING_ERRORS = 'hpies_wsrun_rtc_pinch_end_nerr'  # Number of times water switch pinch timing is incorrect.	 1	 int	 Should be zero.


class StatusDataParticle(DataParticle):
    _data_particle_type = DataParticleType.HPIES_STATUS

    # 20140430T232254 #3__s1 -748633661 31 23 0 C:\\DATA\\12345.000 OK*3e90
    # 20140430T232254 #3__s2 10 0 0 984001 0 0 0*ac87
    # 20140430T232254 #3__s3 0 0 0 0 0 0 1*35b7

    @staticmethod
    def regex():
        pattern = r"""
            (?x)
            (?P<tod>                %(tod)s) \s
                                    \#3__s1  \s
            (?P<secs>               %(int)s) \s
            (?P<hcno>               %(int)s) \s
            (?P<hcno_last_cal>      %(int)s) \s
            (?P<hcno_last_comp>     %(int)s) \s
            (?P<ofile>              %(fn)s)  \s
            (?P<ifok>               %(str)s)
                                    \*
            (?P<crc1>               %(crc)s) \s
            (?P<time2>              %(tod)s) \s
                                    \#3__s2  \s
            (?P<compass_writes>     %(int)s) \s
            (?P<compass_fails>      %(int)s) \s
            (?P<motor_power_cycles> %(int)s) \s
            (?P<service_loops>      %(int)s) \s
            (?P<serial_failures>    %(int)s) \s
            (?P<port_failures>      %(int)s) \s
            (?P<port_closures>      %(int)s)
                                    \*
            (?P<crc2>               %(crc)s) \s
            (?P<time3>              %(tod)s) \s
                                    \#3__s3  \s
            (?P<irq2_count>         %(int)s) \s
            (?P<spurious_count>     %(int)s) \s
            (?P<spsr_count>         %(int)s) \s
            (?P<zero_count>         %(int)s) \s
            (?P<adc_overflows>      %(int)s) \s
            (?P<queue_overflows>    %(int)s) \s
            (?P<pinch_errors>       %(int)s)
                                    \*
            (?P<crc3>               %(crc)s)
            """ % common_matches

        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(StatusDataParticle.regex())

    def _build_parsed_values(self):
        """
        Parse data sample for individual values (statistics)
        @throws SampleException If there is a problem with sample creation
        """
        match = StatusDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

        try:
            time1 = match.group('tod')
            unix_time = int(match.group('secs'))
            hcno = int(match.group('hcno'))
            hcno_last_cal = int(match.group('hcno_last_cal'))
            hcno_last_comp = int(match.group('hcno_last_comp'))
            ofile = match.group('ofile')
            ifok = match.group('ifok')
            crc1 = int(match.group('crc1'), 16)

            # time2 = match.group('time2')  # ignored
            compass_writes = int(match.group('compass_writes'))
            compass_fails = int(match.group('compass_fails'))
            motor_power_cycles = int(match.group('motor_power_cycles'))
            service_loops = int(match.group('service_loops'))
            serial_failures = int(match.group('serial_failures'))
            port_failures = int(match.group('port_failures'))
            port_closures = int(match.group('port_closures'))
            crc2 = int(match.group('crc2'), 16)

            # time3 = match.group('time3')  # ignored
            irq2_count = int(match.group('irq2_count'))
            spurious_count = int(match.group('spurious_count'))
            spsr_count = int(match.group('spsr_count'))
            zero_count = int(match.group('zero_count'))
            adc_overflows = int(match.group('adc_overflows'))
            queue_overflows = int(match.group('queue_overflows'))
            pinch_errors = int(match.group('pinch_errors'))
            crc3 = int(match.group('crc3'), 16)

        except ValueError:
            raise SampleException("ValueError while converting data: [%r]" % self.raw_data)

        crc = [crc1, crc2, crc3]
        i = 0
        for line in self.raw_data.split(NEWLINE):
            if i > 2:
                break
            crc_compute = crc3kerm(line)
            if not crc_compute == crc[i]:
                raise SampleException("Corrupt data detected: [%r] - CRC %s != %s" %
                                      (line, hex(crc_compute), hex(crc[i])))
            i += 1

        result = [
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: time1},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.UNIX_TIME, DataParticleKey.VALUE: unix_time},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.HCNO, DataParticleKey.VALUE: hcno},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.HCNO_LAST_CAL, DataParticleKey.VALUE: hcno_last_cal},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.HCNO_LAST_COMP, DataParticleKey.VALUE: hcno_last_comp},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.OFILE, DataParticleKey.VALUE: ofile},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.IFOK, DataParticleKey.VALUE: ifok},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.N_COMPASS_WRITES, DataParticleKey.VALUE: compass_writes},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.N_COMPASS_FAIL_WRITES,
             DataParticleKey.VALUE: compass_fails},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.MOTOR_POWER_UPS,
             DataParticleKey.VALUE: motor_power_cycles},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.N_SERVICE_LOOPS, DataParticleKey.VALUE: service_loops},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.SERIAL_PORT_ERRORS,
             DataParticleKey.VALUE: serial_failures},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.COMPASS_PORT_CLOSED_COUNT,
             DataParticleKey.VALUE: port_closures},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.COMPASS_PORT_ERRORS, DataParticleKey.VALUE: port_failures},

            {DataParticleKey.VALUE_ID: StatusDataParticleKey.IRQ2_COUNT, DataParticleKey.VALUE: irq2_count},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.SPURIOUS_COUNT, DataParticleKey.VALUE: spurious_count},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.SPSR_BITS56_COUNT, DataParticleKey.VALUE: spsr_count},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.PIT_ZERO_COUNT, DataParticleKey.VALUE: zero_count},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.ADC_BUFFER_OVERFLOWS,
             DataParticleKey.VALUE: adc_overflows},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.MAX7317_QUEUE_OVERFLOWS,
             DataParticleKey.VALUE: queue_overflows},
            {DataParticleKey.VALUE_ID: StatusDataParticleKey.PINCH_TIMING_ERRORS, DataParticleKey.VALUE: pinch_errors},
        ]

        return result


###############################################################################
# Data Particles
###############################################################################


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
    __metaclass__ = get_logging_metaclass(log_level='debug')

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

        # Add sample handlers.

        self._build_command_dict()
        self._build_driver_dict()

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)

        self._prefix = 1

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(CalDataParticle.regex_compiled())
        matchers.append(HEFDataParticle.regex_compiled())
        matchers.append(HEFMotorCurrentDataParticle.regex_compiled())
        matchers.append(IESDataParticle.regex_compiled())
        matchers.append(StatusDataParticle.regex_compiled())

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
                             r'serno\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Serial Number',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        self._param_dict.add(Parameter.DEBUG_LEVEL,
                             r'debug\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Debug Level',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.WSRUN_PINCH,
                             r'wsrun pinch secs\s+= %(int)s s -- half cycle duration' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='WS Run Pinch',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.NFC_CALIBRATE,
                             r'nfc calibrate\s+= %(int)s full cycles -- calibrate every 2880 s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='cycles',
                             display_name='Calibration Periodicity',
                             visibility=ParameterDictVisibility.READ_WRITE,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.CAL_HOLD,
                             r'cal hold secs\s+= %(float)s s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units='secs',
                             display_name='Calibrate Hold',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=True)
        self._param_dict.add(Parameter.CAL_SKIP,
                             r'cal skip secs\s+= %(int)s s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Calibrate Skip',
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=False,
                             direct_access=False)
        self._param_dict.add(Parameter.NHC_COMPASS,
                             r'nhc compass\s+= %(int)s half cycles' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='half cycles',
                             display_name='Compass Measurement Periodicity',
                             direct_access=True,
                             startup_param=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.COMPASS_SAMPLES,
                             r'compass nget\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Compass Samples',
                             direct_access=True,
                             startup_param=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        # time between measurements in a burst
        self._param_dict.add(Parameter.COMPASS_DELAY,
                             r'compass dsecs\s+= %(int)s s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='s',
                             display_name='Compass Samples',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        # initial compass measurement (in seconds)
        self._param_dict.add(Parameter.INITIAL_COMPASS,
                             r'icompass run secs\s+= %(int)s s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='s',
                             display_name='Initial Compass Run',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        # INITIAL_COMPASS_DELAY = 'icompass dsecs'  #
        self._param_dict.add(Parameter.INITIAL_COMPASS_DELAY,
                             r'icompass dsecs\s+= %(float)s s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Compass Samples',
                             startup_param=True,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        # FILE_LENGTH = 'secs per ofile'  # seconds per file (default 86400 - one day)
        self._param_dict.add(Parameter.MOTOR_SAMPLES,
                             r'navg mot\s+= %(int)s --' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of Motor Samples',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.EF_SAMPLES,
                             r'navg ef\s+= %(int)s --' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of HEF Samples',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.CAL_SAMPLES,
                             r'navg cal\s+= %(int)s --' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Number of Calibration Samples',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.CONSOLE_TIMEOUT,
                             r'console off timeout\s+= %(int)s s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Console Timeout',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WSRUN_DELAY,
                             r'wsrun delay secs\s+= %(int)s s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='WS Run Delay (secs)',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MOTOR_DIR_NHOLD,
                             r'motor dir nhold\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Motor TODO',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MOTOR_DIR_INIT,
                             r'motor dir init\s+= (\w+)',
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.POWER_COMPASS_W_MOTOR,
                             r'do_compass_pwr_with_motor\s+= %(int)s',
                             lambda match: bool(match.group(1)),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Power Compass with Motor',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.KEEP_AWAKE_W_MOTOR,
                             r'do_keep_awake_with_motor\s+= %(int)s',
                             lambda match: bool(match.group(1)),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Keep Awake with Motor',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_1A,
                             r'm1a_tmoc\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ms',
                             display_name='Motor Timeouts 1A',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_1B,
                             r'm1b_tmoc\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ms',
                             display_name='Motor Timeouts 1B',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_2A,
                             r'm2a_tmoc\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ms',
                             display_name='Motor Timeouts 2A',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.MOTOR_TIMEOUTS_2B,
                             r'm2b_tmoc\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='25 ms',
                             display_name='Motor Timeouts 2B',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.RSN_CONFIG,
                             r'do_rsn\s+=%(int)s' % common_matches,
                             lambda match: bool(match.group(1)),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Configured for RSN',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.INVERT_LED_DRIVERS,
                             r'led_drivers_invert\s+= %(int)s',
                             lambda match: bool(match.group(1)),
                             None,
                             type=ParameterDictType.BOOL,
                             display_name='Invert LED Drivers',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.M1A_LED,
                             r'm1a_led\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='M1A LED',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.M2A_LED,
                             r'm2a_led\s+= %(int)s' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='M2A LED',
                             startup_param=True,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        # IES Parameters
        self._param_dict.add(Parameter.IES_TIME,
                             r'',
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='IES Clock',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ECHO_SAMPLES,
                             r'Travel Time Measurements: %(int)s pings every 10 minutes' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='1/600 Hz',
                             display_name='Echo Samples',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WATER_DEPTH,
                             r'Estimated Water Depth: %(int)s meters' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             display_name='Estimated Water Depth',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ACOUSTIC_LOCKOUT,
                             r'Acoustic Lockout: %(float)s seconds' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units='secs',
                             display_name='Acoustic Lockout',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ACOUSTIC_OUTPUT,
                             r'Acoustic Output: %(int)s dB' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             units='dB',
                             display_name='Acoustic Output',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.RELEASE_TIME,
                             r'Release Time: %(rest)s' % common_matches,
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Release Time',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.COLLECT_TELEMETRY,
                             r'Telemetry data file (enabled|disabled)',
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Telemetry Data File',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.MISSION_STATEMENT,
                             r'Mission Statement: %(rest)s' % common_matches,
                             lambda match: match.group(1),
                             None,
                             type=ParameterDictType.STRING,
                             display_name='Mission Statement',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PT_SAMPLES,
                             r'Pressure and Temperature measured every %(int)s minutes' % common_matches,
                             lambda match: int(match.group(1)),
                             None,
                             type=ParameterDictType.INT,
                             units='1/600 Hz',
                             display_name='Pressure/Temperature Samples',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_U0,
                             r'U0 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-U0',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y1,
                             r'Y1 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y2,
                             r'Y2 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TEMP_COEFF_Y3,
                             r'Y3 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-Y3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C1,
                             r'C1 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C2,
                             r'C2 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_C3,
                             r'C3 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-C3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_D1,
                             r'D1 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-D1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_D2,
                             r'D2 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-D2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T1,
                             r'T1 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T2,
                             r'T2 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T3,
                             r'T3 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T4,
                             r'T4 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T4',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PRES_COEFF_T5,
                             r'T5 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Pressure Coeff-T5',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        # TODO - missing Temperature offset - -0.51 deg C
        # TODO - missing Pressure offset - 0.96 psi
        self._param_dict.add(Parameter.BLILEY_0,
                             r'B0 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B0',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_1,
                             r'B1 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B1',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_2,
                             r'B2 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B2',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.BLILEY_3,
                             r'B3 = %(float)s' % common_matches,
                             lambda match: float(match.group(1)),
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name='Temp Coeff-B3',
                             startup_param=False,
                             direct_access=False,
                             visibility=ParameterDictVisibility.READ_ONLY)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(CalDataParticle, CalDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(HEFDataParticle, HEFDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(IESDataParticle, IESDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(StatusDataParticle, StatusDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(HEFMotorCurrentDataParticle,
                             HEFMotorCurrentDataParticle.regex_compiled(), chunk, timestamp)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _wakeup(self, wakeup_timeout=10, response_timeout=3):
        """
        Wakeup the instrument
        @param wakeup_timeout The timeout to wake the device.
        @param response_timeout The time to look for response to a wakeup attempt.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        pass

    def _build_command(self, cmd, **kwargs):
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
            return stm_command(cmd, *kwargs)
        elif cmd in (Command.PREFIX,
                     Command.MISSION_START,
                     Command.MISSION_STOP):
            return hef_command(cmd, *kwargs)
        raise InstrumentProtocolException('attempt to process unknown command: %r', cmd)

    def _check_command(self, resp, prompt):
        for line in resp.split(NEWLINE):
            if not valid_response(line):
                raise InstrumentProtocolException('checksum failed (%r)', line)

    def _build_driver_dict(self):
        """
        @brief Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        @brief Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name='start autosample')
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name='stop autosample')

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
        Discover current state
        @retval (next_state, result)
        """
        return ProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_enter(self, *args, **kwargs):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._do_cmd_resp(Command.REBOOT)
        self._do_cmd_resp(Command.ACQUISITION_START)
        self._do_cmd_resp(Command.IES_PORT_ON)
        self._do_cmd_resp(Command.IES_POWER_ON)
        self._do_cmd_resp(Command.IES_PORT_OFF)
        self._do_cmd_resp(Command.HEF_PORT_ON)
        self._do_cmd_resp(Command.HEF_POWER_ON)
        self._do_cmd_resp(Command.HEF_WAKE)
        self._do_cmd_resp(Command.PREFIX, str(self._prefix))
        self._do_cmd_resp(Command.MISSION_START)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Process command to stop autosampling. Return to command state.
        """
        self._do_cmd_resp(Command.MISSION_STOP)
        self._do_cmd_resp(Command.ACQUISITION_STOP)
        self._do_cmd_resp(Command.IES_PORT_OFF)
        self._do_cmd_resp(Command.IES_POWER_OFF)
        self._prefix += 1

        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_autosample_exit(self, *args, **kwargs):
        # no special cleanup required
        pass

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
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        return None, None

    def _handler_command_set(self, *args, **kwargs):
        """
        Set instrument parameters
        """
        return None, None

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        """
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

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
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        """
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state. Restore direct access parameters.
        """
        for key in self.get_direct_access_params():
            value = self._param_dict.get_default_value(key)
            log.debug('restoring parameter: %r - %r', key, value)
            self._param_dict.set_default(key)
        # TODO - self._update_params()
        pass
