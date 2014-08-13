"""
@package mi.instrument.satlantic.ocr_507_icsw.ooicore.driver
@file marine-integrations/mi/instrument/satlantic/ocr_507_icsw/ooicore/driver.py
@author Godfrey Duke
@brief Instrument driver classes that provide structure towards interaction
with the Satlantic OCR507 ICSW w/ Midrange Bioshutter
"""

import time
import re
import struct
import decimal

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol, RE_PATTERN, DEFAULT_CMD_TIMEOUT
from mi.core.instrument.protocol_param_dict import ParameterDictType, ParameterDictVisibility
from mi.core.util import dict_equal
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver, DriverProtocolState, DriverEvent, \
    DriverAsyncEvent, ResourceAgentState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import CommonDataParticleType, DataParticleValue
from mi.core.common import InstErrorCode
from mi.core.instrument.instrument_fsm import InstrumentFSM, ThreadSafeFSM
from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentProtocolException, \
    InstrumentException, InstrumentTimeoutException, InstrumentCommandException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.log import get_logger, get_logging_metaclass


__author__ = 'Godfrey Duke'
__license__ = 'Apache 2.0'

log = get_logger()

# ###################################################################
# Module-wide values
####################################################################

SAMPLE_PATTERN = r'(?P<instrument_id>SATDI7)(?P<serial_number>\d{4})(?P<timer>\d{7}\.\d\d)(?P<binary_data>.{37})(?P<checksum>.)\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN, re.DOTALL)
CONFIG_PATTERN = '''Satlantic\ OCR.*?
            Firmware\ version:\ (?P<firmware_version>.*?)\s*
            Instrument:\ (?P<instrument_id>\w+)\s*
            S\/N:\ (?P<serial_number>\w+).*?
            Telemetry\ Baud\ Rate:\ (?P<telemetry_baud_rate>\d+)\ bps\s*
            Maximum\ Frame\ Rate:\ (?P<max_frame_rate>\S+).*?
            Initialize\ Silent\ Mode:\ (?P<initialize_silent_mode>off|on)\s*
            Initialize\ Power\ Down:\ (?P<initialize_power_down>off|on)\s*
            Initialize\ Automatic\ Telemetry:\ (?P<initialize_auto_telemetry>off|on)\s*
            Network\ Mode:\ (?P<network_mode>off|on)\s*
            Network\ Address:\ (?P<network_address>\d+)\s*
            Network\ Baud\ Rate:\ (?P<network_baud_rate>\d+)\ bps.*?
            \[Auto'''

# CONFIG_PATTERN = '''Satlantic\ OCR.*?
#             Firmware\ version:\ (?P<firmware_version>.*?)\s*
#             Instrument:\ (?P<instrument_id>\w+)\s*
#             S\/N:\ (?P<serial_number>\w+).*?
#             Telemetry\ Baud\ Rate:\ (?P<telemetry_baud_rate>\d+)\ bps\s*
#             Maximum\ Frame\ Rate:\ (?P<max_frame_rate>\d+)\ Hz\s*
#             Initialize\ Silent\ Mode:\ (?P<initialize_silent_mode>off|on)\s*
#             Initialize\ Power\ Down:\ (?P<initialize_power_down>off|on)\s*
#             Initialize\ Automatic\ Telemetry:\ (?P<initialize_auto_telemetry>off|on)\s*
#             Network\ Mode:\ (?P<network_mode>off|on)\s*
#             Network\ Address:\ (?P<network_address>\d+)\s*
#             Network\ Baud\ Rate:\ (?P<network_baud_rate>\d+)\ bps.*?
#             \[Auto'''

CONFIG_REGEX = re.compile(CONFIG_PATTERN, re.DOTALL | re.VERBOSE)
init_pattern = r'Press <Ctrl\+C> for command console. \r\nInitializing system. Please wait...\r\n'
init_regex = re.compile(init_pattern)
COMMAND_PATTERN = 'Command Console'
RESET_DELAY = 6
EOLN = "\r\n"
RETRY = 3
VALID_MAXRATES = (0, 0.125, 0.25, 0.5, 1, 2, 4, 8, 10, 12)


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'spkir_data_record'
    CONFIG = 'spkir_a_configuration_record'


class SatlanticSpecificDriverEvents(BaseEnum):
    START_POLL = 'DRIVER_EVENT_START_POLL'
    STOP_POLL = 'DRIVER_EVENT_STOP_POLL'
    RESET = "DRIVER_EVENT_RESET"


####################################################################
# Static enumerations for this class
####################################################################


class Command(BaseEnum):
    SAVE = 'save'
    EXIT = 'exit'
    EXIT_AND_RESET = 'exit!'
    GET = 'show'
    SET = 'set'
    RESET = '\x12'  # CTRL-R
    BREAK = '\x03'  # CTRL-C
    SWITCH_TO_AUTOSAMPLE = '\x01'  # CTRL-A
    SAMPLE = '\x0D'  # CR
    ID = 'id'
    SHOW_ALL = 'show all'
    INVALID = 'foo'


class SatlanticProtocolState(BaseEnum):
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    UNKNOWN = DriverProtocolState.UNKNOWN
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class SatlanticProtocolEvent(BaseEnum):
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    RESET = SatlanticSpecificDriverEvents.RESET


class SatlanticCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = SatlanticProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = SatlanticProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = SatlanticProtocolEvent.ACQUIRE_STATUS
    RESET = SatlanticProtocolEvent.RESET


class Parameter(DriverParameter):
    MAX_RATE = 'maxrate'
    INIT_SM = 'initsm'
    INIT_AT = 'initat'
    NET_MODE = 'netmode'


class Prompt(BaseEnum):
    """
    Command Prompt
    """
    USAGE = 'Usage'
    INVALID_COMMAND = 'unknown command'
    COMMAND = ']$'


###############################################################################
# Satlantic OCR507 Sensor Driver.
###############################################################################

class SatlanticOCR507InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    The InstrumentDriver class for the Satlantic OCR507 sensor SPKIR.
    """

    def __init__(self, evt_callback):
        """Instrument-specific enums
        @param evt_callback The callback function to use for events
        """
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """ Construct driver protocol state machine """
        self._protocol = SatlanticOCR507InstrumentProtocol(self._driver_event)


class SatlanticOCR507DataParticleKey(BaseEnum):
    INSTRUMENT_ID = "instrument_id"
    SERIAL_NUMBER = "serial_number"
    TIMER = "timer"
    SAMPLE_DELAY = "sample_delay"
    SAMPLES = "spkir_samples"
    REGULATED_INPUT_VOLTAGE = "vin_sense"
    ANALOG_RAIL_VOLTAGE = "va_sense"
    INTERNAL_TEMP = "internal_temperature"
    FRAME_COUNTER = "frame_counter"
    CHECKSUM = "checksum"


class SatlanticOCR507ConfigurationParticleKey(BaseEnum):
    FIRMWARE_VERSION = 'spkir_a_firmware_version'
    INSTRUMENT_ID = "instrument_id"
    SERIAL_NUMBER = "serial_number"
    TELEMETRY_BAUD_RATE = "telemetry_baud_rate"
    MAX_FRAME_RATE = "max_frame_rate"
    INIT_SILENT_MODE = "initialize_silent_mode"
    INIT_POWER_DOWN = "initialize_power_down"
    INIT_AUTO_TELEMETRY = "initialize_auto_telemetry"
    NETWORK_MODE = "network_mode"
    NETWORK_ADDRESS = "network_address"
    NETWORK_BAUD_RATE = "network_baud_rate"


class SatlanticOCR507DataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic OCR507 sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    __metaclass__ = get_logging_metaclass(log_level='debug')
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a OCR507 values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%r]" %
                                  self.raw_data)

        # Parse the relevant ascii fields
        instrument_id = match.group('instrument_id')
        serial_number = match.group('serial_number')
        timer = float(match.group('timer'))

        # Ensure the expected values were present
        if not instrument_id:
            raise SampleException("No instrument id value parsed")
        if not serial_number:
            raise SampleException("No serial number value parsed")
        if not timer:
            raise SampleException("No timer value parsed")

        # Parse the relevant binary data
        """
        Field Name          Field Size (bytes)      Description         Format Char
        ----------          ------------------      -----------         -----------
        sample_delay                2               BS formatted value      h
        ch[1-7]_sample              4               BU formatted value      I
        regulated_input_voltage     2               BU formatted value      H
        analog_rail_voltage         2               BU formatted value      H
        internal_temp               2               BU formatted value      H
        frame_counter               1               BU formatted value      B
        checksum                    1               BU formatted value      B
        """
        try:
            sample_delay, ch1_sample, ch2_sample, ch3_sample, ch4_sample, ch5_sample, ch6_sample, ch7_sample, \
            regulated_input_voltage, analog_rail_voltage, internal_temp, frame_counter, checksum \
                = struct.unpack('!h7IHHHBB', match.group('binary_data') + match.group('checksum'))

        except struct.error, e:
            raise SampleException(e)

        result = [{DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.INSTRUMENT_ID,
                   DataParticleKey.VALUE: instrument_id},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.TIMER,
                   DataParticleKey.VALUE: timer},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.SAMPLE_DELAY,
                   DataParticleKey.VALUE: sample_delay},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.SAMPLES,
                   DataParticleKey.VALUE: [ch1_sample,
                                           ch2_sample,
                                           ch3_sample,
                                           ch4_sample,
                                           ch5_sample,
                                           ch6_sample,
                                           ch7_sample]},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.REGULATED_INPUT_VOLTAGE,
                   DataParticleKey.VALUE: regulated_input_voltage},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.ANALOG_RAIL_VOLTAGE,
                   DataParticleKey.VALUE: analog_rail_voltage},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.INTERNAL_TEMP,
                   DataParticleKey.VALUE: internal_temp},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.FRAME_COUNTER,
                   DataParticleKey.VALUE: frame_counter},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: checksum}]

        if not self._checksum_check(self.raw_data):
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED
            log.warn("Invalid checksum encountered: %r.", checksum)

        log.debug('OCR507 Data Particle raw data: %r', self.raw_data)
        log.debug('OCR507 Data Particle parsed data: %r', result)

        return result

    def _checksum_check(self, data):
        """
        Confirm that the checksum is valid for the data line
        @param data The entire line of data, including the checksum
        @retval True if the checksum fits, False if the checksum is bad
        """
        if data is None or data == '':
            return False

        match = SAMPLE_REGEX.match(data)
        if not match:
            return False
        try:
            line_end = match.end('checksum')
        except IndexError:
            # Didn't have a checksum!
            return False

        line = data[:line_end]
        # Ensure the low order byte of the sum of all characters from the
        # beginning of the frame through the checksum equals 0
        checksum_validation = sum(ord(x) for x in line)

        checksum_validation &= 0xFF

        return checksum_validation == 0


class SatlanticOCR507ConfigurationParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic OCR507 sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.CONFIG

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a OCR507 values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = CONFIG_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed configuration data: [%r]" %
                                  self.raw_data)

        # Parse the relevant ascii fields
        firmware_version = match.group('firmware_version')
        instrument_id = match.group('instrument_id')
        serial_number = match.group('serial_number')
        telemetry_baud_rate = int(match.group('telemetry_baud_rate'))
        max_frame_rate = match.group('max_frame_rate')
        init_silent_mode = True if match.group('initialize_silent_mode') == 'on' else False
        init_power_down = True if match.group('initialize_power_down') == 'on' else False
        init_auto_telemetry = True if match.group('initialize_auto_telemetry') == 'on' else False
        network_mode = True if match.group('network_mode') == 'on' else False
        network_address = int(match.group('network_address'))
        network_baud_rate = int(match.group('network_baud_rate'))

        result = [{DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INSTRUMENT_ID,
                   DataParticleKey.VALUE: instrument_id},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.TELEMETRY_BAUD_RATE,
                   DataParticleKey.VALUE: telemetry_baud_rate},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.MAX_FRAME_RATE,
                   DataParticleKey.VALUE: max_frame_rate},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_SILENT_MODE,
                   DataParticleKey.VALUE: init_silent_mode},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_POWER_DOWN,
                   DataParticleKey.VALUE: init_power_down},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.INIT_AUTO_TELEMETRY,
                   DataParticleKey.VALUE: init_auto_telemetry},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_MODE,
                   DataParticleKey.VALUE: network_mode},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_ADDRESS,
                   DataParticleKey.VALUE: network_address},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507ConfigurationParticleKey.NETWORK_BAUD_RATE,
                   DataParticleKey.VALUE: network_baud_rate}]

        log.debug('OCR507 Configuration Particle raw data: %r', self.raw_data)
        log.debug('OCR507 Configuration Particle parsed data: %r', result)

        return result


####################################################################
# Satlantic OCR507 Sensor Protocol
####################################################################
class SatlanticOCR507InstrumentProtocol(CommandResponseInstrumentProtocol):
    """The instrument protocol classes to deal with a Satlantic OCR507 sensor.
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    Note protocol state machine must be called "self._protocol_fsm"
    """
    _data_particle_type = SatlanticOCR507DataParticle
    _config_particle_type = SatlanticOCR507ConfigurationParticle
    _data_particle_regex = SAMPLE_REGEX
    _config_particle_regex = CONFIG_REGEX

    __metaclass__ = get_logging_metaclass(log_level='debug')

    def __init__(self, callback=None):
        CommandResponseInstrumentProtocol.__init__(self, Prompt, EOLN, callback)

        self._last_data_timestamp = None

        self._protocol_fsm = ThreadSafeFSM(SatlanticProtocolState, SatlanticProtocolEvent, SatlanticProtocolEvent.ENTER,
                                           SatlanticProtocolEvent.EXIT)

        self._protocol_fsm.add_handler(SatlanticProtocolState.UNKNOWN, SatlanticProtocolEvent.ENTER,
                                       self._handler_unknown_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.UNKNOWN, SatlanticProtocolEvent.DISCOVER,
                                       self._handler_unknown_discover)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.ENTER,
                                       self._handler_command_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.GET,
                                       self._handler_command_get)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.SET,
                                       self._handler_command_set)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)
        self._protocol_fsm.add_handler(SatlanticProtocolState.AUTOSAMPLE, SatlanticProtocolEvent.ENTER,
                                       self._handler_autosample_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.AUTOSAMPLE, SatlanticProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)

        self._protocol_fsm.start(SatlanticProtocolState.UNKNOWN)

        self._add_response_handler(Command.GET, self._parse_get_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.INVALID, self._parse_invalid_response)

        self._param_dict.add(Parameter.MAX_RATE,
                             r"Maximum\ Frame\ Rate:\ (\S+).*?\s*",
                             lambda match: match.group(1),
                             lambda sVal: '%s' % sVal,
                             type=ParameterDictType.STRING,
                             display_name="Max Rate",
                             default_value='0',
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.INIT_AT,
                             r"Initialize Automatic Telemetry: (off|on)",
                             lambda match: True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Init AT",
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.INIT_SM,
                             r"Initialize Silent Mode: (off|on)",
                             lambda match: True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Init SM",
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.NET_MODE,
                             r"Network Mode: (off|on)",
                             lambda match: True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Net Mode",
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._cmd_dict.add(SatlanticCapability.START_AUTOSAMPLE, display_name="Start Autosample")
        self._cmd_dict.add(SatlanticCapability.STOP_AUTOSAMPLE, display_name="Stop Autosample")
        self._cmd_dict.add(SatlanticCapability.ACQUIRE_STATUS, display_name="Acquire Status")

        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

        self._chunker = StringChunker(self.sieve_function)

    @staticmethod
    def _boolean_to_off_on(v):
        """
        Write a boolean value to string formatted for sbe16 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value not a bool.
        """

        if not isinstance(v, bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        if v:
            return 'on'
        return 'off'


    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        log.debug("Raw Data: %r, len: %d", raw_data, len(raw_data))
        log.debug(SAMPLE_REGEX.pattern)
        matchers = [SAMPLE_REGEX, CONFIG_REGEX]
        return_list = []

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list


    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if SatlanticCapability.has(x)]
        return events_out

    def get_config(self, *args, **kwargs):
        """ Get the entire configuration for the instrument

        @param params The parameters and values to set
        @retval None if nothing was done, otherwise result of FSM event handle
        Should be a dict of parameters and values
        """
        for param in Parameter.list():
            if param != Parameter.ALL:
                self._do_cmd_resp(Command.GET, param, **kwargs)

    def _do_cmd(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of buffers.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @retval The fully built command that was sent
        """
        expected_prompt = kwargs.get('expected_prompt', None)
        cmd_line = self._build_default_command(cmd, *args)

        # Send command.
        log.debug('_do_cmd: %s, length=%s' % (repr(cmd_line), len(cmd_line)))
        if len(cmd_line) == 1:
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                starttime = time.time()
                self._connection.send(char)
                while len(self._promptbuf) == 0 or char not in self._promptbuf[-1]:
                    time.sleep(0.0015)
                    if time.time() > starttime + 3:
                        break

            time.sleep(0.115)
            starttime = time.time()
            self._connection.send(EOLN)
            while EOLN not in self._promptbuf[len(cmd_line):len(cmd_line) + 2]:
                time.sleep(0.0015)
                if time.time() > starttime + 3:
                    break

            # Limit resend_check_value from expected_prompt to one of the two below
            resend_check_value = None
            if expected_prompt is not None:
                for check in (Prompt.COMMAND, "SATDI7"):
                    if check in expected_prompt:
                        log.trace('_do_cmd: command: %s, check=%s' % (cmd_line, check))
                        resend_check_value = check

            # Resend the EOLN if it did not go through the first time
            starttime = time.time()
            if resend_check_value is not None:
                while True:
                    time.sleep(0.1)
                    if time.time() > starttime + 2:
                        log.debug("Sending eoln again.")
                        self._connection.send(EOLN)
                        starttime = time.time()
                    if resend_check_value in self._promptbuf:
                        break
                    if Prompt.INVALID_COMMAND in self._promptbuf:
                        break

        return cmd_line

    def _do_cmd_no_resp(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of buffers. No response is handled as a result of the command.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        """
        self._do_cmd(cmd, *args, **kwargs)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param expected_prompt kwarg offering a specific prompt to look for
        other than the ones in the protocol class itself.
        @param response_regex kwarg with a compiled regex for the response to
        match. Groups that match will be returned as a string.
        Cannot be supplied with expected_prompt. May be helpful for instruments that do not have a prompt.
        @retval resp_result The (possibly parsed) response result including the
        first instance of the prompt matched. If a regex was used, the prompt
        will be an empty string and the response will be the joined collection of matched groups.
        @raises InstrumentCommandException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response was not recognized.
        """
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', [Prompt.INVALID_COMMAND, Prompt.USAGE, Prompt.COMMAND])
        response_regex = kwargs.get('response_regex', None)

        if response_regex and not isinstance(response_regex, RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')

        retry_count = 5
        retry_num = 0
        cmd_line = ""
        result = ""
        prompt = ""
        for retry_num in xrange(retry_count):
            # Clear line and prompt buffers for result.
            self._linebuf = ''
            self._promptbuf = ''

            cmd_line = self._do_cmd(cmd, *args, **kwargs)

            # Wait for the prompt, prepare result and return, timeout exception
            if response_regex:
                result_tuple = self._get_response(timeout, response_regex=response_regex,
                                                  expected_prompt=expected_prompt)
                result = "".join(result_tuple)
            else:
                (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)

            # Confirm the entire command was sent, otherwise resend retry_count number of times
            if len(cmd_line) > 1 and \
                    (expected_prompt is not None or
                         (response_regex is not None)) \
                    and cmd_line not in result:
                log.debug('_do_cmd_resp: Send command: %s failed %s attempt, result = %s.', cmd, retry_num, result)
                if retry_num >= retry_count:
                    raise InstrumentCommandException('_do_cmd_resp: Failed %s attempts sending command: %s' %
                                                     (retry_count, cmd))
            else:
                break

        log.debug('_do_cmd_resp: Sent command: %s, %s reattempts, expected_prompt=%s, result=%r.',
                  cmd_line, retry_num, expected_prompt, result)

        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
                       self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        time.sleep(0.3)  # give some time for the instrument connection to keep up

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
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (SatlanticProtocolState.COMMAND, ResourceAgentState.IDLE or
        SatlanticProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING) if successful.
        """
        try:
            invalidCommandResponse = self._do_cmd_resp(Command.INVALID, timeout=3,
                                                       expected_prompt=Prompt.INVALID_COMMAND)
        except InstrumentTimeoutException as ex:
            invalidCommandResponse = None  # The instrument is not in COMMAND: it must be polled or AUTOSAMPLE

        log.debug("_handler_unknown_discover: returned: %s", invalidCommandResponse)
        if invalidCommandResponse:
            return SatlanticProtocolState.COMMAND, ResourceAgentState.IDLE
        # Put the instrument back into full autosample
        self._do_cmd_no_resp(Command.SWITCH_TO_AUTOSAMPLE)
        return SatlanticProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        # Command device to update parameters and send a config change event.
        self._init_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """Handle getting data from command mode

        @param params List of the parameters to pass to the state
        @retval return (next state, result)
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """Handle setting data from command mode

        @param params Dict of the parameters and values to pass to the state
        @return (next state, result)
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_autosample(self, params=None, *args, **kwargs):
        """
        Handle getting an start autosample event when in command mode
        @param params List of the parameters to pass to the state
        @return next state (next agent state, result)
        """
        result = None

        self._do_cmd_no_resp(Command.EXIT_AND_RESET)
        time.sleep(RESET_DELAY)
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        next_state = SatlanticProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return next_state, (next_agent_state, result)

    def _handler_command_start_direct(self):
        """
        """
        result = None

        next_state = SatlanticProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        log.debug("_handler_command_start_direct: entering DA mode")
        return next_state, (next_agent_state, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Handle SatlanticProtocolState.COMMAND SatlanticProtocolEvent.ACQUIRE_STATUS

        @return next state (next agent state, result)
        """
        next_state = None
        next_agent_state = None
        result = None

        self._do_cmd_no_resp(Command.ID)
        self._do_cmd_no_resp(Command.SHOW_ALL)

        return next_state, (next_agent_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Handle SatlanticProtocolState.AUTOSAMPLE SatlanticProtocolEvent.ENTER

        @param params Parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        next_state = None
        result = None

        if not self._confirm_autosample_mode:
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR,
                                              msg="Not in the correct mode!")

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return next_state, result

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """Handle SatlanticProtocolState.AUTOSAMPLE stop

        @param params Parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        next_state = None
        result = None

        try:
            self._send_break()
            next_state = SatlanticProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        except InstrumentException:
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR,
                                              msg="Could not break from autosample!")

        return next_state, (next_agent_state, result)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        Tell driver superclass to send a state change event.
        Superclass will query the state.
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _do_cmd_direct(self, cmd):
        """
        Issue an untranslated command to the instrument. No response is handled as a result of the command.
        Overridden: Use _do_cmd to send commands reliably. Remove if digi-serial interface is ever fixed.

        @param cmd The high level command to issue
        """
        self._do_cmd(cmd)

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return next_state, (next_agent_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        """
        next_state, next_agent_state = self._handler_unknown_discover()
        if next_state == DriverProtocolState.COMMAND:
            next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, None)

    ###################################################################
    # Builders
    ###################################################################
    def _build_default_command(self, *args):
        """
        """
        return " ".join(str(x) for x in args)

    ##################################################################
    # Response parsers
    ##################################################################
    def _parse_set_response(self, response, prompt):
        """Determine if a set was successful or not

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        """
        if prompt == Prompt.COMMAND:
            return True
        return False

    def _parse_get_response(self, response, prompt):
        """ Parse the response from the instrument for a couple of different
        query responses.

        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @return The numerical value of the parameter in the known units
        @raise InstrumentProtocolException When a bad response is encountered
        """
        # should end with the response, an eol, and a prompt
        update_dict = self._param_dict.update_many(response)
        if not update_dict or len(update_dict) > 1:
            log.error("Get response set multiple parameters (%r): expected only 1", update_dict)
            raise InstrumentProtocolException("Invalid response. Bad command?")

        return self._param_dict.get_all()

    def _parse_invalid_response(self, response, prompt):
        """ Parse the response from the instrument for a couple of different
        query responses.

        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @return true iff Prompt.INVALID_COMMAND was returned
        """
        # should end with the response, an eoln, and a prompt
        return Prompt.INVALID_COMMAND == prompt

    ###################################################################
    # Helpers
    ###################################################################
    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        Also called when setting parameters during startup and direct access
        In the event an exception is generated dur
        @throws InstrumentParameterException if parameter does not exist or Maxrate is out of range
        @throws InstrumentCommandException if failed to set
        """

        params = args[0]

        self._verify_not_readonly(*args, **kwargs)
        old_config = self._param_dict.get_config()

        exception = None

        for key in params:
            if key not in self._param_dict._param_dict:
                exception = InstrumentParameterException ("Bad parameter: %r" % key)
                break
            val = self._param_dict.format(key, params[key])
            log.debug("KEY = %s VALUE = %s", str(key), str(val))
            if key == Parameter.MAX_RATE and float(params[key]) not in VALID_MAXRATES:
                exception = InstrumentParameterException("Maxrate %s out of range" % val)
                break
            # Check for existance in dict (send only on change)
            if not self._do_cmd_resp(Command.SET, key, val):
                exception = InstrumentCommandException('Error setting: %s = %s' % (key, val))
                break
            self._param_dict.set_value(key, params[key])

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s", new_config, old_config)
        if old_config != new_config:
            self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        # Raise any exceptions encountered due to errors setting the parameter(s)
        if exception is not None:
            raise exception

    def _update_params(self, *args, **kwargs):
        """Fetch the parameters from the device, and update the param dict.

        @param args Unused
        @param kwargs Takes timeout value
        """
        old_config = self._param_dict.get_config()
        self.get_config()
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _send_break(self):
        """
        Send break every 0.3 seconds until the Command Console banner is received.
        @throws InstrumentTimeoutException if not Command Console banner not received within 5 seconds.
        """
        self._promptbuf = ""
        self._connection.send(Command.BREAK)
        starttime = time.time()
        resendtime = time.time()
        while True:
            if time.time() > resendtime + 0.3:
                log.debug("Sending break again.")
                self._connection.send(Command.BREAK)
                resendtime = time.time()

            if COMMAND_PATTERN in self._promptbuf:
                break

            if time.time() > starttime + 10:
                raise InstrumentTimeoutException("Break command failing to stop autosample!")

            time.sleep(0.1)

    def _got_chunk(self, chunk, timestamp):
        """
        extract samples from a chunk of data
        @param chunk: bytes to parse into a sample.
        """
        sample = self._extract_sample(self._data_particle_type, self._data_particle_regex, chunk, timestamp) or \
                 self._extract_sample(self._config_particle_type, self._config_particle_regex, chunk, timestamp)
        if not sample:
            raise InstrumentProtocolException(u'unhandled chunk received by _got_chunk: [{0!r:s}]'.format(chunk))
        return sample

    def _confirm_autosample_mode(self):
        """
        Confirm we are in autosample mode.
        This is done by waiting for a sample to come in, and confirming that
        it does or does not.
        @retval True if in autosample mode, False if not
        """
        # timestamp now,
        start_time = self._last_data_timestamp
        # wait a sample period,
        current_maxrate = self._param_dict.get_config()[Parameter.MAX_RATE]
        if current_maxrate is None:
            current_maxrate = 0.125     # During startup, assume the slowest sample rate
        elif current_maxrate <= 0 or current_maxrate > 8:
            current_maxrate = 8         # Effective current maxrate, despite the instrument accepting higher values
        time_between_samples = (1.0 / current_maxrate) + 1
        time.sleep(time_between_samples)
        end_time = self._last_data_timestamp
        log.debug("_confirm_autosample_mode: end_time=%s, start_time=%s" % (end_time, start_time))
        if end_time != start_time:
            log.debug("Confirmed in autosample mode")
            return True
        log.debug("Confirmed NOT in autosample mode")
        return False