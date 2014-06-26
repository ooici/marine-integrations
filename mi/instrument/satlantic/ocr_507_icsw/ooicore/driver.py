"""
@package mi.instrument.satlantic.ocr_507_icsw.ooicore.driver
@file marine-integrations/mi/instrument/satlantic/ocr_507_icsw/ooicore/driver.py
@author Godfrey Duke
@brief Instrument driver classes that provide structure towards interaction
with the Satlantic OCR507 ICSW w/ Midrange Bioshutter

TODO:
The basic interface (and, thus, driver) is very similar to that for PARAD. As a result this driver is based on the
PARAD driver. The following changes are required:
[ ] Rework regex
  [x] Sample pattern
  [ ] Header pattern
  [ ] Init pattern
  [ ] Configuration pattern
[-] Rework data particles
[ ] Add spkir_configuration_record stream
"""
import functools
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_decorator import ChecksumDecorator
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.protocol_param_dict import ParameterDictType, ParameterDictVisibility
from mi.core.util import dict_equal

__author__ = 'Godfrey Duke'
__license__ = 'Apache 2.0'

import time
import re
import struct

from mi.core.log import get_logger, get_logging_metaclass

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver, DriverProtocolState, DriverEvent, \
    DriverAsyncEvent, ResourceAgentState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.common import InstErrorCode
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentProtocolException, \
    InstrumentException, InstrumentDataException, InstrumentTimeoutException, InstrumentCommandException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey


####################################################################
# Module-wide values
####################################################################

SAMPLE_PATTERN = r'(?P<instrument_id>SATDI7)(?P<serial_number>\d{4})(?P<timer>\d{7}\.\d\d)(?P<binary_data>.{38})\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN, re.DOTALL)
CONFIG_PATTERN = '''Satlantic\ OCR.*?
            Firmware\ version:\ (?P<firmware_version>.*?)\s*
            Instrument:\ (?P<instrument_id>\w+)\s*
            S\/N:\ (?P<serial_number>\w+).*?
            Telemetry\ Baud\ Rate:\ (?P<telemetry_baud_rate>\d+)\ bps\s*
            Maximum\ Frame\ Rate:\ (?P<max_frame_rate>\d+)\ Hz\s*
            Initialize\ Silent\ Mode:\ (?P<initialize_silent_mode>off|on)\s*
            Initialize\ Power\ Down:\ (?P<initialize_power_down>off|on)\s*
            Initialize\ Automatic\ Telemetry:\ (?P<initialize_auto_telemetry>off|on)\s*
            Network\ Mode:\ (?P<network_mode>off|on)\s*
            Network\ Address:\ (?P<network_address>\d+)\s*
            Network\ Baud\ Rate:\ (?P<network_baud_rate>\d+)\ bps.*?
            \[Auto'''

CONFIG_REGEX = re.compile(CONFIG_PATTERN, re.DOTALL | re.VERBOSE)
init_pattern = r'Press <Ctrl\+C> for command console. \r\nInitializing system. Please wait...\r\n'
init_regex = re.compile(init_pattern)
WRITE_DELAY = 0.5 # should be 0.2
RESET_DELAY = 6
EOLN = "\r\n"
RETRY = 3


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
    RESET = 0x12                # CTRL-R
    BREAK = 0x03                # CTRL-C
    SWITCH_TO_AUTOSAMPLE = 0x01 # CTRL-A
    SAMPLE = 0x0D               # CR
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
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
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
    GET = SatlanticProtocolEvent.GET
    SET = SatlanticProtocolEvent.SET

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
# Satlantic PAR Sensor Driver.
###############################################################################

class SatlanticOCR507InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    The InstrumentDriver class for the Satlantic PAR sensor PARAD.
    @note If using this via Ethernet, must use a delayed send
    or commands may not make it to the PAR successfully. A delay of 0.1
    appears to be sufficient for most 19200 baud operations (0.5 is more
    reliable), more may be needed for 9600. Note that control commands
    should not be delayed.
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
    CH1_SAMPLE = "channel_1"
    CH2_SAMPLE = "channel_2"
    CH3_SAMPLE = "channel_3"
    CH4_SAMPLE = "channel_4"
    CH5_SAMPLE = "channel_5"
    CH6_SAMPLE = "channel_6"
    CH7_SAMPLE = "channel_7"
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
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    @staticmethod
    def regex():
        return SAMPLE_PATTERN

    @staticmethod
    def regex_compiled():
        return SAMPLE_REGEX

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

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
                = struct.unpack('!h7IHHHBB', match.group('binary_data'))
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
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH1_SAMPLE,
                   DataParticleKey.VALUE: ch1_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH2_SAMPLE,
                   DataParticleKey.VALUE: ch2_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH3_SAMPLE,
                   DataParticleKey.VALUE: ch3_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH4_SAMPLE,
                   DataParticleKey.VALUE: ch4_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH5_SAMPLE,
                   DataParticleKey.VALUE: ch5_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH6_SAMPLE,
                   DataParticleKey.VALUE: ch6_sample},
                  {DataParticleKey.VALUE_ID: SatlanticOCR507DataParticleKey.CH7_SAMPLE,
                   DataParticleKey.VALUE: ch7_sample},
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

        return result


class SatlanticOCR507ConfigurationParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.CONFIG

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = CONFIG_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed configuration data: [%s]" %
                                  self.decoded_raw)

        # Parse the relevant ascii fields
        firmware_version = match.group('firmware_version')
        instrument_id = match.group('instrument_id')
        serial_number = match.group('serial_number')
        telemetry_baud_rate = int(match.group('telemetry_baud_rate'))
        max_frame_rate = match.group('max_frame_rate')
        init_silent_mode = match.group('initialize_silent_mode')
        init_power_down = match.group('initialize_power_down')
        init_auto_telemetry = match.group('initialize_auto_telemetry')
        network_mode = match.group('network_mode')
        network_address = int(match.group('network_address'))
        network_baud_rate = int(match.group('network_baud_rate'))

        # Ensure the expected values were present
        if not firmware_version:
            raise SampleException("No firmware version value parsed")
        if not instrument_id:
            raise SampleException("No instrument id value parsed")
        if not serial_number:
            raise SampleException("No serial number value parsed")
        if not telemetry_baud_rate:
            raise SampleException("No telemetry baud rate value parsed")
        if not max_frame_rate:
            raise SampleException("No max frame rate value parsed")
        if not init_silent_mode:
            raise SampleException("No init silent mode value parsed")
        if not init_power_down:
            raise SampleException("No init power down value parsed")
        if not init_auto_telemetry:
            raise SampleException("No init auto telemetry value parsed")
        if not network_mode:
            raise SampleException("No network mode value parsed")
        if not network_address:
            raise SampleException("No network address value parsed")
        if not network_baud_rate:
            raise SampleException("No network baud rate value parsed")

        # Convert on/off strings to booleans
        init_silent_mode = 'on' == init_silent_mode
        init_power_down = 'on' == init_power_down
        init_auto_telemetry = 'on' == init_auto_telemetry
        network_mode = 'on' == network_mode

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

        return result


####################################################################
# Satlantic OCR507 Sensor Protocol
####################################################################
class SatlanticOCR507InstrumentProtocol(CommandResponseInstrumentProtocol):
    """The instrument protocol classes to deal with a Satlantic PAR sensor.
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    Note protocol state machine must be called "self._protocol_fsm"

    @todo Check for valid state transitions and handle requests appropriately
    possibly using better exceptions from the fsm.on_event() method
    """
    _data_particle_type = SatlanticOCR507DataParticle
    _config_particle_type = SatlanticOCR507ConfigurationParticle
    _data_particle_regex = SAMPLE_REGEX
    _config_particle_regex = CONFIG_REGEX

    __metaclass__=get_logging_metaclass(log_level='debug')
    def __init__(self, callback=None):
        CommandResponseInstrumentProtocol.__init__(self, Prompt, EOLN, callback)

        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = EOLN
        self._firmware = None
        self._serial = None
        self._instrument = None

        self._protocol_fsm = InstrumentFSM(SatlanticProtocolState, SatlanticProtocolEvent, SatlanticProtocolEvent.ENTER, SatlanticProtocolEvent.EXIT)

        self._protocol_fsm.add_handler(SatlanticProtocolState.UNKNOWN, SatlanticProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.UNKNOWN, SatlanticProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        # self._protocol_fsm.add_handler(SatlanticProtocolState.COMMAND, SatlanticProtocolEvent.RESET, self._handler_command_reset)
        self._protocol_fsm.add_handler(SatlanticProtocolState.AUTOSAMPLE, SatlanticProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.AUTOSAMPLE, SatlanticProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        # self._protocol_fsm.add_handler(SatlanticProtocolState.AUTOSAMPLE, SatlanticProtocolEvent.RESET, self._handler_autosample_reset)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(SatlanticProtocolState.DIRECT_ACCESS, SatlanticProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        self._protocol_fsm.start(SatlanticProtocolState.UNKNOWN)

        self._add_build_handler(Command.SET, self._build_set_command)
        self._add_build_handler(Command.GET, self._build_param_fetch_command)
        self._add_build_handler(Command.SAVE, self._build_exec_command)
        self._add_build_handler(Command.EXIT, self._build_exec_command)
        self._add_build_handler(Command.EXIT_AND_RESET, self._build_exec_command)
        self._add_build_handler(Command.SWITCH_TO_AUTOSAMPLE, self._build_control_command)
        self._add_build_handler(Command.RESET, self._build_control_command)
        self._add_build_handler(Command.BREAK, self._build_multi_control_command)
        self._add_build_handler(Command.SAMPLE, self._build_control_command)
        self._add_build_handler(Command.ID, self._build_id_command)
        self._add_build_handler(Command.SHOW_ALL, self._build_show_all_command)
        self._add_build_handler(Command.INVALID, self._build_invalid_command)

        self._add_response_handler(Command.GET, self._parse_get_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.INVALID, self._parse_invalid_response)
        self._add_response_handler(Command.SAMPLE, self._parse_cmd_prompt_response, SatlanticProtocolState.COMMAND)
        self._add_response_handler(Command.BREAK, self._parse_silent_response, SatlanticProtocolState.COMMAND)
        self._add_response_handler(Command.BREAK, self._parse_header_response, SatlanticProtocolState.AUTOSAMPLE)
        self._add_response_handler(Command.RESET, self._parse_silent_response, SatlanticProtocolState.COMMAND)
        self._add_response_handler(Command.RESET, self._parse_reset_response, SatlanticProtocolState.AUTOSAMPLE)

        self._param_dict.add(Parameter.MAX_RATE,
                             r"Maximum\ Frame\ Rate:\ ([(\d|.]+)\ Hz\s*",
                             lambda match : float(match.group(1)),
                             lambda fVal : '%.1f' % fVal,
                             type=ParameterDictType.FLOAT,
                             display_name="Max Rate",
                             default_value=15,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.INIT_AT,
                             r"Initialize Automatic Telemetry: (off|on)",
                             lambda match : True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Init AT",
                             default_value='on',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.INIT_SM,
                             r"Initialize Silent Mode: (off|on)",
                             lambda match : True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Init SM",
                             default_value='on',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.NET_MODE,
                             r"Network Mode: (off|on)",
                             lambda match : True if match.group(1) == 'on' else False,
                             self._boolean_to_off_on,
                             type=ParameterDictType.BOOL,
                             display_name="Net Mode",
                             default_value='off',
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._cmd_dict.add(SatlanticCapability.START_AUTOSAMPLE, display_name="Start Autosample")
        self._cmd_dict.add(SatlanticCapability.STOP_AUTOSAMPLE, display_name="Stop Autosample")
        self._cmd_dict.add(SatlanticCapability.ACQUIRE_STATUS, display_name="Acquire Status")

        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

        self._chunker = StringChunker(self.sieve_function)

        # To "override" this:
        # super(Protocol, self)._do_cmd_resp
        self._do_cmd_resp = functools.partial(self._do_cmd_resp,
                                              expected_prompt=[Prompt.INVALID_COMMAND, Prompt.USAGE, Prompt.COMMAND], write_delay=self.write_delay)

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
        else:
            return 'off'


    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        log.debug("Rawr Data: %r, len: %d", raw_data, len(raw_data))
        log.debug(SAMPLE_REGEX.pattern)
        matchers = [SAMPLE_REGEX, CONFIG_REGEX]
        return_list = []

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                log.warn("FOUND A MATCH for: %s...", raw_data[0:9])
                return_list.append((match.start(), match.end()))

        return return_list


    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if SatlanticCapability.has(x)]
        return events_out

    # TODO Is this sufficient?
    def get_config(self, *args, **kwargs):
        """ Get the entire configuration for the instrument

        @param params The parameters and values to set
        @retval None if nothing was done, otherwise result of FSM event handle
        Should be a dict of parameters and values
        @throws InstrumentProtocolException On invalid parameter
        """
        for param in Parameter.list():
            if param != Parameter.ALL:
                self._do_cmd_resp(Command.GET, param, **kwargs)

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

    # TODO: Avoid resetting instrument during discovery (could enter a CR/LF and parse response)
    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (SatlanticProtocolState.COMMAND, ResourceAgentState.IDLE or
        SatlanticProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING) if successful.
        """
        try:
            invalidCommandResponse = self._do_cmd_resp(Command.INVALID, timeout=10, expected_prompt=Prompt.INVALID_COMMAND, write_delay=WRITE_DELAY)
        except InstrumentTimeoutException as ex:
            invalidCommandResponse = None # The instrument is not in COMMAND: it must be polled or AUTOSAMPLE

        log.debug("_handler_unknown_discover: returned: %s", invalidCommandResponse)
        if invalidCommandResponse:
            return SatlanticProtocolState.COMMAND, ResourceAgentState.IDLE
        else:
            # Put the instrument back into full autosample
            self._do_cmd_no_resp(Command.SWITCH_TO_AUTOSAMPLE)
            return SatlanticProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

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
        # self._update_params(timeout=3)
        self._init_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """Handle getting data from command mode

        @param params List of the parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        return self._handler_get(*args, **kwargs)

    def _get_from_instrument(self, param):
        '''
        instruct the instrument to get a parameter value from the instrument
        @param param: name of the parameter
        @return: value read from the instrument.  None otherwise.
        @raise: InstrumentProtocolException when fail to get a response from the instrument
        '''
        for attempt in range(RETRY):
            # retry up to RETRY times
            try:
                val = self._do_cmd_resp(Command.GET, param,
                    expected_prompt=Prompt.COMMAND,
                    write_delay=self.write_delay)
                return val.get(param)
            except InstrumentProtocolException as ex:
                pass   # GET failed, so retry again
        else:
            # retries exhausted, so raise exception
            raise ex

    def _handler_command_set(self, *args, **kwargs):
        """Handle setting data from command mode

        @param params Dict of the parameters and values to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_autosample(self, params=None, *args, **kwargs):
        """
        Handle getting an start autosample event when in command mode
        @param params List of the parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        next_state = None
        result = None

        self._do_cmd_no_resp(Command.EXIT_AND_RESET, None, write_delay=self.write_delay)
        time.sleep(RESET_DELAY)
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        next_state = SatlanticProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = SatlanticProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """Handle PARProtocolState.POLL PARProtocolEvent.ACQUIRE_SAMPLE

        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid command
        """
        next_state = None
        next_agent_state = None
        result = None

        # This sometimes takes a few seconds, so stall after our sample cmd
        # and before the read/parse
        delay = self.write_delay + 2
        self._do_cmd_no_resp(Command.ID, write_delay=delay)
        self._do_cmd_no_resp(Command.SHOW_ALL, write_delay=delay)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """ Handle PARProtocolState.AUTOSAMPLE PARProtocolEvent.ENTER

        @param params Parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        next_state = None
        result = None

        if not self._confirm_autosample_mode:
            # TODO: seems like some kind of recovery should occur here
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR,
                                              msg="Not in the correct mode!")

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return (next_state, result)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """Handle PARProtocolState.AUTOSAMPLE stop

        @param params Parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        next_state = None
        result = None

        try:
            self._send_break()
            self._driver_event(DriverAsyncEvent.STATE_CHANGE)
            next_state = SatlanticProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        except InstrumentException:
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR,
                                              msg="Could not break from autosample!")

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
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = SatlanticProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ###################################################################
    # Builders
    ###################################################################
    def _build_set_command(self, cmd, param, value):
        """
        Build a command that is ready to send out to the instrument. Checks for
        valid parameter name, only handles one value at a time.

        @param cmd The command...in this case, Command.SET
        @param param The name of the parameter to set. From Parameter enum
        @param value The value to set for that parameter
        @retval Returns string ready for sending to instrument
        """
        # Check to make sure all parameters are valid up front
        assert Parameter.has(param)
        assert cmd == Command.SET
        return "%s %s %s%s" % (Command.SET, param, value, self.eoln)

    def _build_param_fetch_command(self, cmd, param):
        """
        Build a command to fetch the desired argument.

        @param cmd The command being used (Command.GET in this case)
        @param param The name of the parameter to fetch
        @retval Returns string ready for sending to instrument
        """
        assert Parameter.has(param)
        return "%s %s%s" % (Command.GET, param, self.eoln)

    def _build_exec_command(self, cmd, *args):
        """
        Builder for simple commands

        @param cmd The command being used (Command.GET in this case)
        @param args Unused arguments
        @retval Returns string ready for sending to instrument
        """
        return "%s%s" % (cmd, self.eoln)

    def _build_control_command(self, cmd, *args):
        """ Send a single control char command

        @param cmd The control character to send
        @param args Unused arguments
        @retval The string with the complete command
        """
        return "%c" % (cmd)

    def _build_id_command(self, cmd, *args):
        """ Send an invalid command (useful for state discovery)

        @param cmd The command to send
        @param args Unused arguments
        @retval The string with the complete command
        """
        return "%s%s" % (Command.ID, self.eoln)

    def _build_show_all_command(self, cmd, *args):
        """ Send an invalid command (useful for state discovery)

        @param cmd The command to send
        @param args Unused arguments
        @retval The string with the complete command
        """
        return "%s%s" % (Command.SHOW_ALL, self.eoln)

    def _build_invalid_command(self, cmd, *args):
        """ Send an invalid command (useful for state discovery)

        @param cmd The command to send
        @param args Unused arguments
        @retval The string with the complete command
        """
        return "%s%s" % (cmd, self.eoln)

    def _build_multi_control_command(self, cmd, *args):
        """ Send a quick series of control char command

        @param cmd The control character to send
        @param args Unused arguments
        @retval The string with the complete command
        """
        return "%c%c%c%c%c%c%c" % (cmd, cmd, cmd, cmd, cmd, cmd, cmd)

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
        @retval return The numerical value of the parameter in the known units
        @raise InstrumentProtocolException When a bad response is encountered
        """
        # should end with the response, an eoln, and a prompt
        update_dict = self._param_dict.update_many(response)
        log.debug("GODFREY: %r", update_dict)
        if not update_dict or len(update_dict) > 1:
            log.warn("Get response set multiple parameters (%r): expected only 1", update_dict)
            raise InstrumentProtocolException("Invalid response. Bad command?")

        return self._param_dict.get_all()
        #update_dict.values()[0]

    def _parse_invalid_response(self, response, prompt):
        """ Parse the response from the instrument for a couple of different
        query responses.

        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return true iff Prompt.INVALID_COMMAND was returned
        @raise InstrumentProtocolException When a bad response is encountered
        """
        # should end with the response, an eoln, and a prompt
        return Prompt.INVALID_COMMAND == prompt

    def _parse_silent_response(self, response, prompt):
        """Parse a silent response

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing silent response of [%s] with prompt [%s]",
                        response, prompt)
        if ((response == "") or (response == prompt)) and \
           ((prompt == Prompt.NULL) or (prompt == Prompt.COMMAND)):
            return InstErrorCode.OK
        else:
            return InstErrorCode.HARDWARE_ERROR

    # TODO: OBE?
    def _parse_header_response(self, response, prompt):
        """ Parse what the header looks like to make sure if came up.

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing header response of [%s] with prompt [%s]",
                        response, prompt)
        if HEADER_REGEX.search(response):
            return InstErrorCode.OK
        else:
            return InstErrorCode.HARDWARE_ERROR

    def _parse_reset_response(self, response, prompt):
        """ Parse the results of a reset

        This is basically a header followed by some initialization lines
        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing reset response of [%s] with prompt [%s]",
                        response, prompt)

        lines = response.split(self.eoln)
        for line in lines:
            if init_regex.search(line):
                return InstErrorCode.OK

        # else
        return InstErrorCode.HARDWARE_ERROR

    def _parse_cmd_prompt_response(self, response, prompt):
        """Parse a command prompt response

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing command prompt response of [%s] with prompt [%s]",
                        response, prompt)
        if (response == Prompt.COMMAND):
            # yank out the command we sent, split at the self.eoln
            split_result = response.split(self.eoln, 1)
            if len(split_result) > 1:
                response = split_result[1]
            return InstErrorCode.OK
        else:
            return InstErrorCode.HARDWARE_ERROR

    ###################################################################
    # Helpers
    ###################################################################
    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        Also called when setting parameters during startup and direct access
        """

        params = args[0]

        # try:
        self._verify_not_readonly(*args, **kwargs)
        old_config = self._param_dict.get_config()

        for key in params:
            val = self._param_dict.format(key, params[key])
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            # Check for existance in dict (send only on change)
            if not self._do_cmd_resp(Command.SET, key, val):
                raise InstrumentCommandException('Error setting: %s = %s', key, val)
            self._param_dict.set_value(key, params[key])

        self._update_params()
        result = self._do_cmd_resp(Command.SAVE, None, None,
                                   expected_prompt=Prompt.COMMAND,
                                   write_delay=self.write_delay)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s", new_config, old_config)
        if not dict_equal(old_config, new_config):
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
        pass

    def _update_params(self, *args, **kwargs):
        """Fetch the parameters from the device, and update the param dict.

        @param args Unused
        @param kwargs Takes timeout value
        @throws InstrumentProtocolException
        @throws InstrumentTimeoutException
        """
        log.debug("Updating parameter dict")
        old_config = self._param_dict.get_config()
        self.get_config()
        new_config = self._param_dict.get_config()
        if (new_config != old_config):
            log.debug('Whiskey Tango Foxtrot: %r != %r', new_config, old_config)
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _send_reset(self, timeout=10):
        """Send a reset command out to the device

        @throw InstrumentTimeoutException
        @throw InstrumentProtocolException
        @todo handle errors correctly here, deal with repeats at high sample rate
        """
        write_delay = 0.2
        log.debug("Sending reset chars")

        if self._protocol_fsm.get_current_state() == SatlanticProtocolState.COMMAND:
            return InstErrorCode.OK

        # TODO: infinite loop bad idea
        while True:
            self._do_cmd_no_resp(Command.RESET, timeout=timeout,
                                 write_delay=write_delay)
            time.sleep(RESET_DELAY)
            if self._confirm_autosample_mode():
                break

    def _send_break(self, timeout=10):
        """Send a blind break command to the device, confirm command mode after

        @throw InstrumentTimeoutException
        @throw InstrumentProtocolException
        @todo handle errors correctly here, deal with repeats at high sample rate
        """
        write_delay = 0.2
        log.debug("Sending break char")
        # do the magic sequence of sending lots of characters really fast...
        # but not too fast
        if self._protocol_fsm.get_current_state() == SatlanticProtocolState.COMMAND:
            return

        # TODO: infinite loop bad idea
        while True:
            self._do_cmd_no_resp(Command.BREAK, timeout=timeout,
                                 expected_prompt=Prompt.COMMAND,
                                 write_delay=write_delay)
            if self._confirm_command_mode():
                break


    def _got_chunk(self, chunk, timestamp):
        '''
        extract samples from a chunk of data
        @param chunk: bytes to parse into a sample.
        '''
        sample = self._extract_sample(self._data_particle_type, self._data_particle_regex, chunk, timestamp) or \
            self._extract_sample(self._config_particle_type, self._config_particle_regex, chunk, timestamp)
        if sample:
            return sample

        return InstrumentProtocolException(u'unhandled chunk received by _got_chunk: [{0!r:s}]'.format(chunk))

        # self._extract_header(chunk)

    # def _extract_header(self, chunk):
    #     '''
    #     Extract key parameters from the instrument header streamed on reset.  This method
    #     caches the values internally in the protocol and return with get_resource calls.
    #     @param chunk: header bytes from the instrument.
    #     @return:
    #     '''
    #     match = HEADER_REGEX.match(chunk)
    #     if match:
    #         self._instrument = match.group(1)
    #         self._serial = match.group(2)
    #         self._firmware = match.group(3)


    def _confirm_autosample_mode(self):
        """Confirm we are in autosample mode

        This is done by waiting for a sample to come in, and confirming that
        it does or does not.
        @retval True if in autosample mode, False if not
        """
        log.debug("Confirming autosample mode...")
        # timestamp now,
        start_time = self._last_data_timestamp
        # wait a sample period,
        time_between_samples = (1/self._param_dict.get_config()[Parameter.MAX_RATE])+1
        time.sleep(time_between_samples)
        end_time = self._last_data_timestamp
        log.debug("_confirm_autosample_mode: end_time=%s, start_time=%s" %(end_time, start_time))
        if (end_time != start_time):
            log.debug("Confirmed in autosample mode")
            return True
        else:
            log.debug("Confirmed NOT in autosample mode")
            return False

    def _confirm_command_mode(self):
        """Confirm we are in command mode

        This is done by issuing a bogus command and getting a prompt
        @retval True if in command mode, False if not
        """
        log.debug("Confirming command mode...")
        try:
            # suspend our belief that we are in another state, and behave
            # as if we are in command mode long enough to confirm or deny it
            self._do_cmd_no_resp(Command.SAMPLE, timeout=2,
                                 expected_prompt=Prompt.COMMAND)
            (prompt, result) = self._get_response(timeout=2,
                                                  expected_prompt=Prompt.COMMAND)
        except InstrumentTimeoutException:
            # If we timed out, its because we never got our $ prompt and must
            # not be in command mode (probably got a data value in POLL mode)
            log.debug("Confirmed NOT in command mode via timeout")
            return False
        except InstrumentProtocolException:
            log.debug("Confirmed NOT in command mode via protocol exception")
            return False
        # made it this far
        log.debug("Confirmed in command mode")
        time.sleep(0.5)

        return True

# TODO: verify this
####################################################################
# Satlantic Checksum Decorator
####################################################################
class SatlanticChecksumDecorator(ChecksumDecorator):
    """Checks the data checksum for the Satlantic PAR sensor"""

    def handle_incoming_data(self, original_data=None, chained_data=None):
        if (self._checksum_ok(original_data)):
            if self.next_decorator == None:
                return (original_data, chained_data)
            else:
                self.next_decorator.handle_incoming_data(original_data, chained_data)
        else:
            raise InstrumentDataException(error_code=InstErrorCode.HARDWARE_ERROR,
                                          msg="Checksum failure!")

    def _checksum_ok(self, data):
        """Confirm that the checksum is valid for the data line

        @param data The entire line of data, including the checksum
        @retval True if the checksum fits, False if the checksum is bad
        """
        assert (data != None)
        assert (data != "")
        match = SAMPLE_REGEX.match(data)
        if not match:
            return False
        try:
            received_checksum = int(match.group('checksum'))
            line_end = match.start('checksum')-1
        except IndexError:
            # Didnt have a checksum!
            return False

        line = data[:line_end]
        # Calculate checksum on line
        checksum = 0
        for char in line:
            checksum += ord(char)
        checksum = checksum & 0xFF

        return (checksum == received_checksum)