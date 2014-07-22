#!/usr/bin/env python


"""
@package mi.instrument.satlantic.par_ser_600m.driver Satlantic PAR driver module
@file mi/instrument/satlantic/par_ser_600m/driver.py
@author Steve Foley, Ronald Ronquillo
@brief Instrument driver classes that provide structure towards interaction
with the Satlantic PAR sensor (PARAD in RSN nomenclature).
"""

__author__ = 'Steve Foley & Bill Bollenbacher, Ronald Ronquilllo'
__license__ = 'Apache 2.0'

import time
import re
import json

from mi.core.log import get_logger, get_logging_metaclass
log = get_logger()

from mi.core.common import BaseEnum, Units
from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType
from mi.core.instrument.driver_dict import DriverDict, DriverDictKey
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict

from mi.core.instrument.instrument_protocol import DEFAULT_CMD_TIMEOUT, RE_PATTERN

from mi.core.common import InstErrorCode
from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.exceptions import InstrumentCommandException, InstrumentException, InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException, InstrumentProtocolException, SampleException

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.core.instrument.chunker import StringChunker

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType

####################################################################
# Module-wide values
####################################################################

# ex SATPAR4278190306,55713.85,2206748544,234
SAMPLE_PATTERN = r'SATPAR(?P<sernum>\d{4,10}),(?P<timer>\d{1,7}.\d\d),(?P<counts>\d{10}),(?P<checksum>\d{1,3})\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

HEADER_PATTERN = r'Satlantic Digital PAR Sensor\r\nCopyright \(C\) 2003, Satlantic Inc. All rights reserved.\r\n' \
                 r'Instrument: (?P<instr>.*)\r\nS/N: (?P<sernum>\d{4,10})\r\nFirmware: (?P<firm>.*)\r\n'
HEADER_REGEX = re.compile(HEADER_PATTERN)

COMMAND_PATTERN = 'Command Console'
COMMAND_REGEX = re.compile(COMMAND_PATTERN)

MAXRATE_PATTERN = 'Maximum Frame Rate:\s+(?P<maxrate>\d+\.?\d*) Hz'
MAXRATE_REGEX = re.compile(MAXRATE_PATTERN)

# 9600, 19200, 38400, and 57600.
BAUDRATE_PATTERN = 'Telemetry Baud Rate:\s+(?P<baud>\d{4,5}) bps'
BAUDRATE_REGEX = re.compile(BAUDRATE_PATTERN)

MAXANDBAUDRATE_PATTERN = '%s\r\n\%s' % (MAXRATE_PATTERN, BAUDRATE_PATTERN)
MAXANDBAUDRATE_REGEX = re.compile(MAXANDBAUDRATE_PATTERN)

GET_PATTERN = '^show (?P<param>.*)\r\n(?P<resp>.+)\r?\n?(?P<respbaud>.*)\r?\n?\$'
GET_REGEX = re.compile(GET_PATTERN)

INIT_PATTERN = 'Initializing system. Please wait...'

INTERVAL_TIME_REGEX = r"([0-9][0-9]:[0-9][0-9]:[0-9][0-9])"

VALID_MAXRATES = (0, 0.125, 0.5, 1, 2, 4, 8, 10, 12)
EOLN = "\r\n"


class ParameterUnits(BaseEnum):
    TIME_INTERVAL = 'HH:MM:SS'


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'parad_sa_sample'
    CONFIG = 'parad_sa_config'


class EngineeringParameter(DriverParameter):
    """
    Driver Parameters (aka, engineering parameters)
    """
    ACQUIRE_STATUS_INTERVAL = 'AcquireStatusInterval'


class ScheduledJob(BaseEnum):
    """
    List of schedulable events
    """
    ACQUIRE_STATUS = 'acquire_status'


####################################################################
# Static enumerations for this class
####################################################################
class Command(BaseEnum):
    SAVE = 'save'
    EXIT = 'exit'
    EXIT_AND_RESET = 'exit!'
    GET = 'show'
    SET = 'set'
    RESET = '\x12'                 # CTRL-R
    BREAK = '\x03'                 # CTRL-C
    SWITCH_TO_POLL = '\x13'        # CTRL-S
    SWITCH_TO_AUTOSAMPLE = '\x01'  # CTRL-A
    SAMPLE = '\x0D'                # CR


class PARProtocolState(BaseEnum):
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    UNKNOWN = DriverProtocolState.UNKNOWN
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class PARProtocolEvent(BaseEnum):
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    RESET = DriverEvent.RESET
    SCHEDULED_ACQUIRE_STATUS = "DRIVER_EVENT_SCHEDULED_ACQUIRE_STATUS"


class PARCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = PARProtocolEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = PARProtocolEvent.ACQUIRE_STATUS
    START_AUTOSAMPLE = PARProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = PARProtocolEvent.STOP_AUTOSAMPLE
    RESET = PARProtocolEvent.RESET


class Parameter(DriverParameter):
    MAXRATE = 'maxrate'
    FIRMWARE = 'firmware'
    SERIAL = 'serial'
    INSTRUMENT = 'instrument'
    ACQUIRE_STATUS_INTERVAL = EngineeringParameter.ACQUIRE_STATUS_INTERVAL


class PARProtocolError(BaseEnum):
    INVALID_COMMAND = "Invalid command"


class Prompt(BaseEnum):
    """
    Command Prompts
    """
    COMMAND = '$'
    NULL = ''
    ENTER_EXIT_CMD_MODE = '\x0c'
    SAMPLES = 'SATPAR'


###############################################################################
# Satlantic PAR Sensor Driver.
###############################################################################
class SatlanticPARInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    The InstrumentDriver class for the Satlantic PAR sensor PARAD.
    @note If using this via Ethernet, must use a delayed send
    or commands may not make it to the PAR successfully. This is accomplished
    below sending a command one character at a time & confirmation each character
    arrived in the line buffer. This is more reliable then an arbitrary delay time,
    as the digi may buffer characters & attempt to send more then one character at once.
    Note that single character control commands need not be delayed.
    """

    def __init__(self, evt_callback):
        """Instrument-specific enums
        @param evt_callback The callback function to use for events
        """
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    def _build_protocol(self):
        """ Construct driver protocol state machine """
        self._protocol = SatlanticPARInstrumentProtocol(self._driver_event)


class SatlanticPARDataParticleKey(BaseEnum):
    SERIAL_NUM = "serial_number"
    COUNTS = "par"
    TIMER = "elapsed_time"
    CHECKSUM = "checksum"


class SatlanticPARDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the Satlantic PAR sensor.
    Overrides the building of values, and the rest comes along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into PAR values (with an appropriate tag)
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" % self.raw_data)

        try:
            sernum = str(match.group('sernum'))
            timer = float(match.group('timer'))
            counts = int(match.group('counts'))
            checksum = int(match.group('checksum'))
        except ValueError:
            log.warn("_build_parsed_values")
            raise SampleException('malformed particle - missing required value(s)')
        except TypeError:
            log.warn("_build_parsed_values")
            raise SampleException('malformed particle - missing required value(s)')

        if not self._checksum_check(self.raw_data):
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED

        result = [{DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.SERIAL_NUM, DataParticleKey.VALUE: sernum},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.TIMER, DataParticleKey.VALUE: timer},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.COUNTS, DataParticleKey.VALUE: counts},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.CHECKSUM, DataParticleKey.VALUE: checksum}]

        return result

    def _checksum_check(self, data):
            """
            Confirm that the checksum is valid for the data line
            @param data The entire line of data, including the checksum
            @retval True if the checksum fits, False if the checksum is bad
            """
            match = SAMPLE_REGEX.match(data)
            if not match:
                return False
            try:
                received_checksum = int(match.group('checksum'))
                line_end = match.start('checksum')-1
            except IndexError:
                # Didn't have a checksum!
                return False

            line = data[:line_end+1]
            # Calculate checksum on line
            checksum = 0
            for char in line:
                checksum += ord(char)

            checksum = (~checksum + 0x01) & 0xFF

            if checksum != received_checksum:
                log.warn("Calculated checksum %s did not match packet checksum %s.", checksum, received_checksum)
                return False

            return True


class SatlanticPARConfigParticleKey(BaseEnum):
    BAUD_RATE = "parad_telbaud"
    MAX_RATE = "parad_maxrate"
    SERIAL_NUM = "serial_number"
    FIRMWARE = "parad_firmware"
    TYPE = "parad_type"


class SatlanticPARConfigParticle(DataParticle):
    """
    Routines for parsing raw data into a config particle structure for the Satlantic PAR sensor.
    Overrides the building of values, and the rest comes along for free.
    Serial Number, Firmware, & Instrument are read only values retrieved from the param dictionary.
    """
    def __init__(self, serial_num, firmware, instrument, *args, **kwargs):
        self._serial_num = serial_num
        self._firmware = firmware
        self._instrument = instrument
        super(SatlanticPARConfigParticle, self).__init__(*args, **kwargs)

    _data_particle_type = DataParticleType.CONFIG

    def _build_parsed_values(self):
        """
        Take something in the "show configuration" format and split it into PARAD configuration values
        @throws SampleException If there is a problem with sample creation
        """
        match = MAXANDBAUDRATE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" % self.raw_data)

        try:
            maxrate = float(match.group('maxrate'))
            baud = int(match.group('baud'))
        except ValueError:
            log.warn("_build_parsed_values")
            raise SampleException('malformed particle - missing required value(s)')
        except TypeError:
            log.warn("_build_parsed_values")
            raise SampleException('malformed particle - missing required value(s)')

        log.trace("_build_parsed_values: %s, %s, %s, %s, %s",
                  maxrate, baud, self._serial_num, self._firmware, self._instrument)

        result = [{DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.BAUD_RATE, DataParticleKey.VALUE: baud},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.MAX_RATE, DataParticleKey.VALUE: maxrate},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.SERIAL_NUM,
                   DataParticleKey.VALUE: self._serial_num},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.FIRMWARE,
                   DataParticleKey.VALUE: self._firmware},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.TYPE,
                   DataParticleKey.VALUE: self._instrument}]

        return result


####################################################################
# Satlantic PAR Sensor Protocol
####################################################################
class SatlanticPARInstrumentProtocol(CommandResponseInstrumentProtocol):
    """The instrument protocol classes to deal with a Satlantic PAR sensor.
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    Note protocol state machine must be called "self._protocol_fsm"
    """

    #logging level
    __metaclass__ = get_logging_metaclass(log_level='trace')

    def __init__(self, callback=None):
        CommandResponseInstrumentProtocol.__init__(self, Prompt, EOLN, callback)

        self._protocol_fsm = InstrumentFSM(PARProtocolState, PARProtocolEvent, PARProtocolEvent.ENTER, PARProtocolEvent.EXIT)

        self._protocol_fsm.add_handler(PARProtocolState.UNKNOWN, PARProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(PARProtocolState.UNKNOWN, PARProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ACQUIRE_SAMPLE, self._handler_poll_acquire_sample)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS, self._handler_acquire_status)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.START_DIRECT, self._handler_command_start_direct)

        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.RESET, self._handler_autosample_reset)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.ACQUIRE_STATUS, self._handler_autosample_acquire_status)

        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        self._protocol_fsm.start(PARProtocolState.UNKNOWN)

        self._add_response_handler(Command.GET, self._parse_get_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.SAMPLE, self._parse_response)
        self._add_response_handler(Command.EXIT_AND_RESET, self._parse_header_response)
        self._add_response_handler(Command.RESET, self._parse_header_response)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_cmd_dict()
        self._build_driver_dict()

        self._param_dict.add(Parameter.MAXRATE,
                             MAXRATE_PATTERN,
                             lambda match: float(match.group(1)),
                             self._float_or_int_to_string,
                             direct_access=True,
                             startup_param=True,
                             init_value=4,
                             display_name='Max Rate',
                             description='Maximum sampling rate in Hz',
                             type=ParameterDictType.FLOAT,
                             units=Units.HERTZ,
                             value_description='Only certain standard frame rates are accepted by this parameter:'
                             '0, 0.125, 0.5, 1, 2, 4, 8, 10, and 12. Any non-integer values are truncated.'
                             'To specify an automatic (AUTO) frame rate, input "0" as the value parameter.'
                             'This will cause the instrument to output frames as fast as possible.'
                             'Specifying a frame rate faster than is practically possible will not force the'
                             'actual frame rate to that level. The instrument will only transmit as fast as possible'
                             'for the given operating parameters.')

        self._param_dict.add(Parameter.INSTRUMENT,
                             HEADER_PATTERN,
                             lambda match: match.group('instr'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Instrument',
                             description='Instrument type',
                             type=ParameterDictType.STRING)

        self._param_dict.add(Parameter.SERIAL,
                             HEADER_PATTERN,
                             lambda match: match.group('sernum'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Serial',
                             description='Serial number',
                             type=ParameterDictType.STRING)

        self._param_dict.add(Parameter.FIRMWARE,
                             HEADER_PATTERN,
                             lambda match: match.group('firm'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Firmware',
                             description='Instrument firmware',
                             type=ParameterDictType.STRING)

        self._param_dict.add(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
                             INTERVAL_TIME_REGEX,
                             lambda match: match.group(1),
                             str,
                             display_name="Acquire Status Interval",
                             description='Interval for gathering status particles',
                             type=ParameterDictType.STRING,
                             units=ParameterUnits.TIME_INTERVAL,
                             default_value='00:00:00',
                             startup_param=True)

        self._chunker = StringChunker(SatlanticPARInstrumentProtocol.sieve_function)

    def _build_cmd_dict(self):
        """
        Build a command dictionary structure, load the strings for the metadata from a file if present.
        """
        self._cmd_dict = ProtocolCommandDict()
        self._cmd_dict.add(PARCapability.ACQUIRE_SAMPLE, display_name='Acquire Sample')
        self._cmd_dict.add(PARCapability.ACQUIRE_STATUS, display_name='Acquire Status')
        self._cmd_dict.add(PARCapability.START_AUTOSAMPLE, display_name='Start Autosample')
        self._cmd_dict.add(PARCapability.STOP_AUTOSAMPLE, display_name='Stop Autosample')
        self._cmd_dict.add(PARCapability.RESET, display_name='Reset')

    def _build_driver_dict(self):
        """
        Build a driver dictionary structure, load the strings for the metadata from a file if present.
        """
        self._driver_dict = DriverDict()
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = [SAMPLE_REGEX, MAXANDBAUDRATE_REGEX]
        return_list = []

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
                log.trace("sieve_function: regex found %r", raw_data[match.start():match.end()])

        return return_list

    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if PARCapability.has(x)]
        return events_out

    def _do_cmd(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of buffers.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @retval The fully built command that was sent
        @raises InstrumentProtocolException if command could not be built.
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

            # Keep for reference: This is a reliable alternative, but not fully explained & may not work in the future.
            # It somehow corrects bit rate timing issues across the driver-digi-instrument network interface,
            # & allows the entire line of a commands to be sent successfully.
            # self._connection.send("    ".join(map(None, cmd_line)))

            if EOLN not in cmd_line:    # Note: Direct access commands may already include an EOLN
                time.sleep(0.115)
                starttime = time.time()
                self._connection.send(EOLN)
                while EOLN not in self._promptbuf[len(cmd_line):len(cmd_line)+2] and Prompt.ENTER_EXIT_CMD_MODE \
                           not in self._promptbuf[len(cmd_line):len(cmd_line)+2]:
                    time.sleep(0.0015)
                    if time.time() > starttime + 3:
                        break

                # Limit resend_check_value from expected_prompt to one of the two below
                resend_check_value = None
                if expected_prompt is not None:
                    for check in (Prompt.COMMAND, Prompt.SAMPLES):
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
                        if PARProtocolError.INVALID_COMMAND in self._promptbuf:
                            break

        return cmd_line

    def _do_cmd_no_resp(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of buffers. No response is handled as a result of the command.
        Overridden: special "write delay" & command resending
        reliability improvements, no need for wakeup, default build command used for all commands
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @raises InstrumentProtocolException if command could not be built.
        """
        self._do_cmd(cmd, *args, **kwargs)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device. Overridden: special "write delay" & command resending
        reliability improvements, no need for wakeup, default build command used for all commands
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
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response was not recognized.
        """
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
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
                (response_regex is not None))\
                    and not result.startswith(cmd_line):
                    # and cmd_line not in result:
                log.debug("_do_cmd_resp: Send command: %s failed %s attempt, result = %s.", cmd, retry_num, result)
                if retry_num >= retry_count:
                    raise InstrumentCommandException('_do_cmd_resp: Failed %s attempts sending command: %s' %
                                                     (retry_count, cmd))
            else:
                break

        log.debug("_do_cmd_resp: Sent command: %s, %s reattempts, expected_prompt=%s, result=%s.",
                  cmd_line, retry_num, expected_prompt, result)

        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        time.sleep(0.3)     # give some time for the instrument connection to keep up

        return resp_result

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_discover(self):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (PARProtocolState.COMMAND or PARProtocolState.AUTOSAMPLE, None).
        """
        try:
            probe_resp = self._do_cmd_resp(Command.SAMPLE, timeout=2,
                                           expected_prompt=[Prompt.SAMPLES, PARProtocolError.INVALID_COMMAND])
        except InstrumentTimeoutException:
            self._do_cmd_resp(Command.SWITCH_TO_AUTOSAMPLE, expected_prompt=Prompt.SAMPLES, timeout=15)
            return PARProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

        log.trace("_handler_unknown_discover: returned: %s", probe_resp)
        if probe_resp == PARProtocolError.INVALID_COMMAND:
            return PARProtocolState.COMMAND, ResourceAgentState.IDLE
        else:
            # Put the instrument into full autosample in case it isn't already (could be in polled mode)
            self._do_cmd_resp(Command.SWITCH_TO_AUTOSAMPLE, expected_prompt=Prompt.SAMPLES, timeout=15)
            return PARProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self):
        """
        Enter command state.
        """
        # Command device to update parameters and send a config change event.
        self._init_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _get_header_params(self):
        """
        Cycle through sample collection & reset to get the start-up banner
        which contains instrument, serial, & firmware values
        """
        self._do_cmd_resp(Command.EXIT, expected_prompt=Prompt.SAMPLES, timeout=15)
        time.sleep(0.115)
        instr, sernum, firm = self._do_cmd_resp(Command.RESET, expected_prompt=INIT_PATTERN, timeout=5)
        time.sleep(1)
        self._do_cmd_resp(Command.BREAK, response_regex=COMMAND_REGEX, timeout=5)
        self._param_dict.set_value(Parameter.INSTRUMENT, instr)
        self._param_dict.set_value(Parameter.SERIAL, sernum)
        self._param_dict.set_value(Parameter.FIRMWARE, firm)

    def _update_params(self, startup=False):
        """
        Fetch the parameters from the device, and update the param dict.
        """
        log.debug("Updating parameter dict")

        max_rate_response = self._do_cmd_resp(Command.GET, Parameter.MAXRATE, expected_prompt=Prompt.COMMAND)
        self._param_dict.update(max_rate_response)

        if startup:
            self._temp_max_rate_wrapper(self._get_header_params)

    def _set_params(self, params, startup=False, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        Also called when setting parameters during startup and direct access

        Issue commands to the instrument to set various parameters.  If
        startup is set to true that means we are setting startup values
        and immutable parameters can be set.  Otherwise only READ_WRITE
        parameters can be set.

        @param params dictionary containing parameter name and value
        @param startup bool True is we are initializing, False otherwise
        @raise InstrumentParameterException
        """
        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.

        scheduling_interval_changed = False
        instrument_params_changed = False
        old_config = self._param_dict.get_all()

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set params requires a parameter dict.')
        self._verify_not_readonly(params, startup)
        for name, value in params.iteritems():
            if EngineeringParameter.has(name):
                try:
                    old_val = self._param_dict.format(name)
                    new_val = self._param_dict.format(name, params[name])
                except KeyError:
                    raise InstrumentParameterException('No existing key for %s' % name)
                if old_val != new_val:
                    self._param_dict.set_value(name, new_val)
                    scheduling_interval_changed = True
            elif Parameter.has(name):
                if name == Parameter.MAXRATE and value not in VALID_MAXRATES:
                    raise InstrumentParameterException("Maxrate %s out of range" % value)
                try:
                    old_val = self._param_dict.format(name)
                    new_val = self._param_dict.format(name, params[name])
                except KeyError:
                    raise InstrumentParameterException('No existing key for %s' % name)
                if old_val != new_val:
                    if self._do_cmd_resp(Command.SET, name, new_val, expected_prompt=Prompt.COMMAND):
                        instrument_params_changed = True
                        log.debug('_set_params: %s was updated from %s to %s', name, old_val, new_val)
            else:
                raise InstrumentParameterException('No existing key for %s' % name)

        if instrument_params_changed:
            self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)
            self._update_params(startup)

        if scheduling_interval_changed and not startup:
            self._setup_scheduler_config()

        new_config = self._param_dict.get_all()
        log.debug("Updated parameter dict: old_config = %s, new_config = %s", old_config, new_config)
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        for name in params.keys():
            if self._param_dict.format(name, params[name]) != self._param_dict.format(name):
                raise InstrumentParameterException('Failed to update parameter: %s' % name)

    def _handle_scheduling_params_changed(self):
        """
        Required actions when scheduling parameters change
        """
        self._setup_scheduler_config()

    def _setup_scheduler_config(self):
        """
        Set up auto scheduler configuration.
        """

        interval = self._param_dict.format(EngineeringParameter.ACQUIRE_STATUS_INTERVAL).split(':')
        hours = int(interval[0])
        minutes = int(interval[1])
        seconds = int(interval[2])
        log.debug("Setting scheduled interval to: %s %s %s", hours, minutes, seconds)

        if DriverConfigKey.SCHEDULER in self._startup_config:
            self._startup_config[DriverConfigKey.SCHEDULER][ScheduledJob.ACQUIRE_STATUS] = {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.HOURS: int(hours),
                    DriverSchedulerConfigKey.MINUTES: int(minutes),
                    DriverSchedulerConfigKey.SECONDS: int(seconds)}
            }
        else:

            self._startup_config[DriverConfigKey.SCHEDULER] = {
                ScheduledJob.ACQUIRE_STATUS: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.HOURS: int(hours),
                        DriverSchedulerConfigKey.MINUTES: int(minutes),
                        DriverSchedulerConfigKey.SECONDS: int(seconds)}
                },
            }

        # Start the scheduler if it is not running
        if not self._scheduler:
            self.initialize_scheduler()

        # First remove the scheduler, if it exists
        if not self._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS) is None:
            self._remove_scheduler(ScheduledJob.ACQUIRE_STATUS)
            log.debug("Removed scheduler for acquire status")

        # Now Add the scheduler
        if hours > 0 or minutes > 0 or seconds > 0:
            self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS)

    def _handler_command_set(self, *args, **kwargs):
        """
        Handle setting data from command mode.
        @param params Dict of the parameters and values to pass to the state
        @retval return (next state, result)
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_autosample(self):
        """
        Handle getting a start autosample event when in command mode
        @retval return (next state, result)
        """
        self._do_cmd_resp(Command.EXIT, expected_prompt=Prompt.SAMPLES, timeout=15)
        time.sleep(0.115)
        self._do_cmd_resp(Command.SWITCH_TO_AUTOSAMPLE, expected_prompt=Prompt.SAMPLES, timeout=15)
        return PARProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_direct(self):
        """
        """
        return PARProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self):
        """
        Handle PARProtocolState.AUTOSAMPLE PARProtocolEvent.ENTER
        @retval return (next state, result)
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return None, None

    def _handler_autosample_stop_autosample(self):
        """
        Handle PARProtocolState.AUTOSAMPLE stop
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        try:
            self._send_break()
        except InstrumentException, e:
            log.debug("_handler_autosample_stop_autosample error: %s", e)
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR,
                                              msg="Couldn't break from autosample!")

        return PARProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_autosample_acquire_status(self):
        """
        High level command for the operator to get the status from the instrument in autosample state
        """
        try:
            self._handler_autosample_stop_autosample()
            self._handler_acquire_status()
            self._handler_command_start_autosample()

        # Since this is registered only for autosample mode, make sure this ends w/ instrument in autosample mode
        except InstrumentTimeoutException:
            next_state, next_agent_state = self._handler_unknown_discover()
            if next_state != DriverProtocolState.AUTOSAMPLE:
                self._handler_command_start_autosample()

        return None, (None, None)

    def _handler_autosample_reset(self):
        """
        Handle PARProtocolState.AUTOSAMPLE reset
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        # Switch to polled state so reset command can be received reliably
        self._send_break_poll()
        try:
            self._do_cmd_resp(Command.RESET, expected_prompt=INIT_PATTERN, timeout=5)
        except InstrumentException:
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR, msg="Couldn't reset autosample!")

        return PARProtocolState.AUTOSAMPLE, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Poll handlers.
    ########################################################################

    def _temp_max_rate_wrapper(self, run_func):
        """
        Wrapper for functions that rely on getting in and out of sampling mode easily
        Note: The exit sampling mode command works most reliably at a maxrate set to 1
        """
        # save current maxrate, temporarily set maxrate to 1 to make this more reliable!
        current_maxrate = self._param_dict.format(Parameter.MAXRATE)
        self._do_cmd_resp(Command.SET, Parameter.MAXRATE, 1, expected_prompt=Prompt.COMMAND)
        self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)
        run_func()
        # restore previous maxrate value
        self._do_cmd_resp(Command.SET, Parameter.MAXRATE, current_maxrate, expected_prompt=Prompt.COMMAND)
        self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)

    def _get_poll(self):
        self._do_cmd_resp(Command.EXIT, expected_prompt=Prompt.SAMPLES, timeout=15)
        # switch to poll
        time.sleep(0.115)
        self._connection.send(Command.SWITCH_TO_POLL)
        # return to command mode
        time.sleep(0.115)
        self._do_cmd_resp(Command.BREAK, response_regex=COMMAND_REGEX, timeout=5)

    def _handler_poll_acquire_sample(self):
        """
        Handle PARProtocolEvent.ACQUIRE_SAMPLE
        @retval return (next state, result)
        """
        self._temp_max_rate_wrapper(self._get_poll)
        return None, (None, None)

    def _handler_acquire_status(self):
        """
        Return parad_sa_config particle containing telbaud, maxrate, serial number, firmware, & type
        Retreive both telbaud & maxrate from instrument with a "show all" command,
        the last three values are retrieved from the values stored in the param dictionary
        and combined through the got_chunk function.
        @retval return (next state, result)
        """
        self._do_cmd_resp(Command.GET, "all", expected_prompt=Prompt.COMMAND)

        return None, (None, None)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self):
        """
        Exit direct access state.
        """
        pass

    def _do_cmd_direct(self, cmd):
        """
        Issue an untranslated command to the instrument. No response is handled as a result of the command.
        Overridden: Use _do_cmd to send commands reliably. Remove if digi-serial interface is ever fixed.

        @param cmd The high level command to issue
        """
        # Send command.
        self._do_cmd(cmd)

    def _handler_direct_access_execute_direct(self, data):
        """
        Execute Direct Access command(s)
        """
        self._do_cmd_direct(data)
        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)
        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        Stop Direct Access, and put the driver into a healthy state
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
        Join each command component into a string with spaces in between
        """
        return " ".join(str(x) for x in args)

    ##################################################################
    # Response parsers
    ##################################################################
    def _parse_response(self, response, prompt):
        """
        Default response handler
        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        """
        return prompt

    def _parse_set_response(self, response, prompt):
        """
        Determine if a set was successful or not
        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        """
        if PARProtocolError.INVALID_COMMAND in response:
            return InstErrorCode.SET_DEVICE_ERR
        elif prompt == Prompt.COMMAND:
            return True
        else:
            return InstErrorCode.HARDWARE_ERROR

    def _parse_get_response(self, response, prompt):
        """
        Parse the response from the instrument for a couple of different query responses.
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The numerical value of the parameter
        @raise InstrumentProtocolException When a bad response is encountered
        """
        match = GET_REGEX.search(response)
        if not match:
            log.warn("Bad response from instrument")
            raise InstrumentProtocolException("Invalid response. Bad command? %s" % response)
        else:
            log.debug("_parse_get_response: response=%r", match.group(1, 2))
            return match.group('resp')

    def _parse_header_response(self, response, prompt):
        """
        Parse what the header looks like to make sure if came up.
        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return The parsed parameters or an InstErrorCode value
        """
        match = HEADER_REGEX.search(response)
        if match:
            return match.group('instr', 'sernum', 'firm')
        else:
            return InstErrorCode.HARDWARE_ERROR

    ###################################################################
    # Helpers
    ###################################################################
    @staticmethod
    def _float_or_int_to_string(v):
        """
        Write a float or int value to string formatted for "generic" set operations.
        Overloaded to print ints and floats without trailing zeros after the decimal point.
        Also supports passing through a "None" value for the empty param dictionary in startup.
        @param v A float or int val.
        @retval a numerical string formatted for "generic" set operations.
        @throws InstrumentParameterException if value is not a float or an int.
        """
        if isinstance(v, float):
            return ('%0.3f' % v).rstrip('0').rstrip('.')
        elif isinstance(v, int):
            return '%d' % v
        elif v is None:
            return None
        else:
            raise InstrumentParameterException('Value %s is not a float or an int.' % v)

    def _send_break_poll(self):
        """
        Send stop auto poll commands (^S) and wait to confirm success based on current max rate setting.
        Note: Current maxrate can be either 0(maximum output), 0.125, 0.5, 1, 2, 4, 8, 10, or 12.
        At maxrates above 4, sending a single stop auto poll command is highly unreliable.
        Generally, a Digital PAR sensor cannot exceed a frame rate faster than 7.5 Hz.
        """
        send_flag = True
        starttime = time.time()
        current_maxrate = self._param_dict.get(Parameter.MAXRATE)
        if current_maxrate is None:
            current_maxrate = 0.125     # During startup, assume the slowest sample rate
        elif current_maxrate <= 0 or current_maxrate > 8:
            current_maxrate = 8
        time_between_samples = (1.0/current_maxrate)+1

        log.trace("_send_break_poll: maxrate = %s", current_maxrate)

        while True:
            if send_flag:
                if current_maxrate < 8:
                    self._connection.send(Command.SWITCH_TO_POLL)
                else:
                    # Send a burst of stop auto poll commands for high maxrates
                    for _ in xrange(25):    # 25 x 0.15 seconds = 3.75 seconds
                        self._connection.send(Command.SWITCH_TO_POLL)
                        time.sleep(.15)
                send_flag = False
            time.sleep(0.1)

            # Check for incoming samples. Reset timer & resend stop command if found.
            if SAMPLE_REGEX.search(self._promptbuf):
                self._promptbuf = ''
                starttime = time.time()
                send_flag = True

            # Wait the appropriate amount of time to confirm samples are no longer arriving
            elif time.time() > starttime + time_between_samples:
                break

        # For high maxrates, give some time for the buffer to clear from the burst of stop commands
        if current_maxrate >= 8:
            extra_sleep = 5 - (time.time() - (starttime + time_between_samples))
            if extra_sleep > 0:
                time.sleep(extra_sleep)

    def _send_continuous_break(self):
        """
        send break every 0.3 seconds until the Command Console banner
        """
        self._promptbuf = ""
        self._connection.send(Command.BREAK)
        starttime = time.time()
        resendtime = time.time()
        while True:
            time.sleep(0.1)
            if time.time() > resendtime + 0.3:
                log.debug("Sending break again.")
                self._connection.send(Command.BREAK)
                resendtime = time.time()

            if COMMAND_PATTERN in self._promptbuf:
                break

            if time.time() > starttime + 5:
                raise InstrumentTimeoutException("Break command failing to stop autosample!")

    def _send_break(self):
        """
        Send the break command to enter Command Mode, but first stop the incoming samples
        """
        self._send_break_poll()
        self._send_continuous_break()

    def _got_chunk(self, chunk, timestamp):
        """
        Extract samples from a chunk of data
        @param chunk: bytes to parse into a sample.
        """
        self._extract_sample(SatlanticPARDataParticle, SAMPLE_REGEX, chunk, timestamp)
        self._extract_sample_param_dict(self._param_dict.get(Parameter.SERIAL),
                                        self._param_dict.get(Parameter.FIRMWARE),
                                        self._param_dict.get(Parameter.INSTRUMENT),
                                        SatlanticPARConfigParticle, MAXANDBAUDRATE_REGEX, chunk, timestamp)

    def _extract_sample_param_dict(self, serial_num, firmware, instrument,
                                   particle_class, regex, line, timestamp, publish=True):
        """
        Extract sample from a response line if present and publish parsed particle
        This is overridden to pass in parameters stored in the param dictionary to make the particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @param timestamp port agent timestamp to include with the particle
        @param publish boolean to publish samples (default True). If True,
               two different events are published: one to notify raw data and
               the other to notify parsed data.

        @retval dict of dicts {'parsed': parsed_sample, 'raw': raw_sample} if
                the line can be parsed for a sample. Otherwise, None.
        """
        sample = None
        if regex.match(line):

            particle = particle_class(serial_num, firmware, instrument, line, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = json.loads(parsed_sample)

        return sample