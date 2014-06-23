#!/usr/bin/env python

from __future__ import division

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

from mi.core.log import get_logger, get_logging_metaclass
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.data_decorator import ChecksumDecorator
from mi.core.instrument.driver_dict import DriverDict, DriverDictKey
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict

from mi.core.instrument.instrument_protocol import DEFAULT_CMD_TIMEOUT, RE_PATTERN

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, CommonDataParticleType
from mi.core.common import InstErrorCode
from mi.core.time import get_timestamp
from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.exceptions import InstrumentCommandException, InstrumentDataException, InstrumentException
from mi.core.exceptions import InstrumentParameterException, InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException, SampleException

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
from mi.core.instrument.chunker import StringChunker

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

####################################################################
# Module-wide values
####################################################################

# ex SATPAR0229,10.01,2206748544,234    # TODO: current example looks like SATPAR4278190306,55713.85,2157022592,6
SAMPLE_PATTERN = r'SATPAR(?P<sernum>\d{4,10}),(?P<timer>\d{1,7}.\d\d),(?P<counts>\d{10}),(?P<checksum>\d{1,3})\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

HEADER_PATTERN = r'Satlantic Digital PAR Sensor\r\nCopyright \(C\) 2003, Satlantic Inc. All rights reserved.\r\n' \
                 r'Instrument: (?P<instr>.*)\r\nS/N: (?P<sernum>\d{4,10})\r\nFirmware: (?P<firm>.*)\r\n'
HEADER_REGEX = re.compile(HEADER_PATTERN)

COMMAND_PATTERN = r'([Cc]ommand)'
COMMAND_REGEX = re.compile(COMMAND_PATTERN)

MAXRATE_PATTERN = 'Maximum Frame Rate:\s+(\d+\.?\d*) Hz'
MAXRATE_REGEX = re.compile(MAXRATE_PATTERN)

GET_PATTERN = '^show (?P<param>.*)\r\n(?P<resp>.*)\r\n\$'
GET_REGEX = re.compile(GET_PATTERN)

init_pattern = 'Initializing system. Please wait...'
init_regex = re.compile(init_pattern)

RESET_DELAY = 6
EOLN = "\r\n"
RETRY = 3


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'parad_sa_sample'


class PARSpecificDriverEvents(BaseEnum):
    START_POLL = 'DRIVER_EVENT_START_POLL'
    STOP_POLL = 'DRIVER_EVENT_STOP_POLL'
    RESET = "DRIVER_EVENT_RESET"


class ScheduledJob(BaseEnum):
    CLOCK_SYNC = 'clock_sync'


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
    POLL = DriverProtocolState.POLL
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    UNKNOWN = DriverProtocolState.UNKNOWN
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class PARProtocolEvent(BaseEnum):
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    # START_POLL = PARSpecificDriverEvents.START_POLL
    # STOP_POLL = PARSpecificDriverEvents.STOP_POLL
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    RESET = PARSpecificDriverEvents.RESET


class PARCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = PARProtocolEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = PARProtocolEvent.ACQUIRE_STATUS
    START_AUTOSAMPLE = PARProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = PARProtocolEvent.STOP_AUTOSAMPLE
    START_DIRECT = PARProtocolEvent.START_DIRECT
    STOP_DIRECT = PARProtocolEvent.STOP_DIRECT
    # START_POLL = PARProtocolEvent.START_POLL
    # STOP_POLL = PARProtocolEvent.STOP_POLL
    RESET = PARProtocolEvent.RESET
    GET = PARProtocolEvent.GET
    SET = PARProtocolEvent.SET


class Parameter(DriverParameter):
    MAXRATE = 'maxrate'
    # BAUDRATE = 'baudrate'
    FIRMWARE = 'firmware'
    SERIAL = 'serial'
    INSTRUMENT = 'instrument'


class Prompt(BaseEnum):
    """
    Command Prompt
    """
    COMMAND = '$'
    NULL = ''


class PARProtocolError(BaseEnum):
    INVALID_COMMAND = "Invalid command"


class KwargsKey(BaseEnum):
    COMMAND = 'command'


###############################################################################
# Satlantic PAR Sensor Driver.
###############################################################################
class SatlanticPARInstrumentDriver(SingleConnectionInstrumentDriver):
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
        self._protocol = SatlanticPARInstrumentProtocol(self._driver_event)


class SatlanticPARDataParticleKey(BaseEnum):
    SERIAL_NUM = "serial_number"
    COUNTS = "par"
    TIMER = "elapsed_time"
    CHECKSUM = "checksum"


class SatlanticPARDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        sernum = int(match.group('sernum'))
        timer = float(match.group('timer'))
        counts = int(match.group('counts'))
        checksum = int(match.group('checksum'))

        if not sernum:
            raise SampleException("No serial number value parsed")
        if not timer:
            raise SampleException("No timer value parsed")
        if not counts:
            raise SampleException("No counts value parsed")
        if not checksum:
            raise SampleException("No checksum value parsed")

        result = [{DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.SERIAL_NUM,
                   DataParticleKey.VALUE: sernum},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.TIMER,
                   DataParticleKey.VALUE: timer},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.COUNTS,
                   DataParticleKey.VALUE: counts},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: checksum}]

        return result


class SatlanticPARConfigParticleKey(BaseEnum):
    BAUD_RATE = "parad_telbaud"
    MAX_RATE = "parad_maxrate"
    SERIAL_NUM = "serial_number"
    FIRMWARE = "parad_firmware"
    TYPE = "parad_type"


class SatlanticPARConfigParticle(DataParticle):
    """
    Routines for parsing raw data into a config particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)

        @throws SampleException If there is a problem with sample creation
        """
        match = HEADER_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        instr = int(match.group('instr'))
        sernum = float(match.group('sernum'))
        firm = int(match.group('firm'))

        # the following two come from value stored in param dictionary
        # baud = int(match.group('baud'))
        # maxrate = int(match.group('maxrate'))
        # self._param_dict.get(Parameter.MAXRATE)

        if not sernum:
            raise SampleException("No serial number value parsed")
        if not instr:
            raise SampleException("No instrument value parsed")
        if not firm:
            raise SampleException("No firmware value parsed")

        result = [{DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.TYPE,
                   DataParticleKey.VALUE: instr},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.SERIAL_NUM,
                   DataParticleKey.VALUE: sernum},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.FIRMWARE,
                   DataParticleKey.VALUE: firm},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.BAUD_RATE,
                   DataParticleKey.VALUE: baud},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.MAX_RATE,
                   DataParticleKey.VALUE: maxrate}
        ]

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
    # TODO Check for valid state transitions and handle requests appropriately
    # possibly using better exceptions from the fsm.on_event() method

    #logging level
    __metaclass__ = get_logging_metaclass(log_level='debug')


    def __init__(self, callback=None):
        CommandResponseInstrumentProtocol.__init__(self, Prompt, EOLN, callback)

        # TODO: save the polling/free state of the instrument, reset after DA use for setting to polling
        self._last_data_timestamp = None
        self.eoln = EOLN

        self._protocol_fsm = InstrumentFSM(PARProtocolState, PARProtocolEvent, PARProtocolEvent.ENTER, PARProtocolEvent.EXIT)

        self._protocol_fsm.add_handler(PARProtocolState.UNKNOWN, PARProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(PARProtocolState.UNKNOWN, PARProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ACQUIRE_SAMPLE, self._handler_poll_acquire_sample)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status)
        self._protocol_fsm.add_handler(PARProtocolState.COMMAND, PARProtocolEvent.START_DIRECT, self._handler_command_start_direct)

        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(PARProtocolState.AUTOSAMPLE, PARProtocolEvent.RESET, self._handler_autosample_reset)
        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(PARProtocolState.DIRECT_ACCESS, PARProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        self._protocol_fsm.start(PARProtocolState.UNKNOWN)

        self._add_response_handler(Command.GET, self._parse_get_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        # self._add_response_handler(Command.SAMPLE, self._parse_cmd_prompt_response, PARProtocolState.COMMAND)
        self._add_response_handler(Command.SAMPLE, self._parse_response, PARProtocolState.UNKNOWN)

        self._add_response_handler(Command.EXIT_AND_RESET, self._parse_header_response, PARProtocolState.COMMAND)
        self._add_response_handler(Command.RESET, self._parse_reset_response, PARProtocolState.AUTOSAMPLE)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_cmd_dict()
        self._build_driver_dict()

        self._param_dict.add(Parameter.MAXRATE,
                             MAXRATE_PATTERN,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             startup_param=True,
                             init_value=4,
                             display_name='MaxRate',
                             description='Maximum sampling rate in Hz.',
                             units=None,    # TODO: Hz
                             type=ParameterDictType.FLOAT,
                             value_description='Only certain standard frame rates are accepted by this parameter: \
                             0, 0.125, 0.5, 1, 2, 4, 8, 10, and 12. Any non-integer values are truncated. \
                             To specify an automatic (AUTO) frame rate, input "0" as the value parameter. \
                             This will cause the instrument to output frames as fast as possible. \
                             Specifying a frame rate faster than is practically possible will not force the \
                             actual frame rate to that level. The instrument will only transmit as fast as possible \
                             for the given operating parameters.')

        self._param_dict.add(Parameter.INSTRUMENT, HEADER_PATTERN,
                             lambda match: match.group('instr'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Instrument',
                             description='Instrument type.')

        self._param_dict.add(Parameter.SERIAL, HEADER_PATTERN,
                             lambda match: match.group('sernum'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Serial',
                             description='Serial number.')

        self._param_dict.add(Parameter.FIRMWARE, HEADER_PATTERN,
                             lambda match: match.group('firm'),
                             str,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Firmware',
                             description='Instrument firmware.')
        # TODO: add baudrate for reseting after DA!?

        self._chunker = StringChunker(SatlanticPARInstrumentProtocol.sieve_function)

    def _build_cmd_dict(self):
        """
        Build a command dictionary structure, load the strings for the metadata from a file if present.
        """
        self._cmd_dict = ProtocolCommandDict()
        self._cmd_dict.add(PARCapability.SET, display_name='Set')
        self._cmd_dict.add(PARCapability.GET, display_name='Get')
        self._cmd_dict.add(PARCapability.ACQUIRE_SAMPLE, display_name='Acquire Sample')
        self._cmd_dict.add(PARCapability.ACQUIRE_STATUS, display_name='Acquire Status')
        self._cmd_dict.add(PARCapability.START_AUTOSAMPLE, display_name='Start Autosample')
        self._cmd_dict.add(PARCapability.STOP_AUTOSAMPLE, display_name='Stop Autosample')
        self._cmd_dict.add(PARCapability.START_DIRECT, display_name='Start Direct Access')
        self._cmd_dict.add(PARCapability.STOP_DIRECT, display_name='Stop Direct Access')
        self._cmd_dict.add(PARCapability.RESET, display_name='Reset')
        # self._cmd_dict.add(PARCapability.ACQUIRE_STATUS, display_name='Acquire Status')

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
        return_list = []

        for match in SAMPLE_REGEX.finditer(raw_data):
            return_list.append((match.start(), match.end()))
            log.debug("sieve_function: regex found %r", raw_data[match.start():match.end()])

        return return_list

    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if PARCapability.has(x)]
        return events_out

    def _do_cmd(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of
        buffers. No response is handled as a result of the command.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup timeout.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built.
        """
        expected_prompt = kwargs.get('expected_prompt', None)
        cmd_line = self._build_default_command(cmd, *args)

        # Send command.
        log.debug('_do_cmd_no_resp: %s, length=%s' % (repr(cmd_line), len(cmd_line)))
        if len(cmd_line) <= 1:
            self._connection.send(cmd_line)
        else:
            self._connection.send("    ".join(map(None, cmd_line)))

            # send eoln until a '$' response
            while True:
                time.sleep(0.5)
                self._connection.send(self.eoln)

                if expected_prompt != Prompt.COMMAND:
                    break
                time.sleep(0.5)
                index = self._promptbuf.find(Prompt.COMMAND)
                if index >= 0:
                    break

    def _do_cmd_no_resp(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after clearing of
        buffers. No response is handled as a result of the command.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup timeout.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built.
        """
        self._do_cmd(cmd, *args, **kwargs)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        """
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        response_regex = kwargs.get('response_regex', None)

        if response_regex and not isinstance(response_regex, RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        self._do_cmd(cmd, *args, **kwargs)

        # Wait for the prompt, prepare result and return, timeout exception
        if response_regex:
            prompt = ""
            result_tuple = self._get_response(timeout, response_regex=response_regex, expected_prompt=expected_prompt)
            result = "".join(result_tuple)
        else:
            (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)

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

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (SBE37ProtocolState.COMMAND or
        SBE37State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        test = self._do_cmd_resp(Command.SAMPLE, timeout=2, expected_prompt=[PARProtocolError.INVALID_COMMAND, "SATPAR"])
        log.debug("_handler_unknown_discover: returned: %s", test)
        if test == PARProtocolError.INVALID_COMMAND:
            return PARProtocolState.COMMAND, ResourceAgentState.IDLE
        else:
            # Put the instrument back into full autosample
            self._do_cmd_no_resp(Command.SWITCH_TO_AUTOSAMPLE)
            return PARProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
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
        @throw InstrumentProtocolException For invalid parameter
        """
        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')
        # If all params requested, retrieve config.
        if (params == DriverParameter.ALL) or (params == [DriverParameter.ALL]):
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

        log.debug("Get finished, next: %s, result: %s", None, result)
        return None, result

    def _get_header_params(self):
        # cycle thru reset to get the start-up banner which has instrument, serial, & Firmware
        (instr, sernum, firm) = self._do_cmd_resp(Command.EXIT_AND_RESET, expected_prompt=init_pattern, timeout=2)
        self._do_cmd_resp(Command.BREAK, response_regex=COMMAND_REGEX, timeout=2)
        self._param_dict.set_value(Parameter.INSTRUMENT, instr)
        self._param_dict.set_value(Parameter.SERIAL, sernum)
        self._param_dict.set_value(Parameter.FIRMWARE, firm)

    def _update_params(self, startup=False, *args, **kwargs):
        """Fetch the parameters from the device, and update the param dict.

        @param args Unused
        @param kwargs Takes timeout value
        @throws InstrumentProtocolException
        @throws InstrumentTimeoutException
        """
        log.debug("Updating parameter dict")
        old_config = self._param_dict.get_all()  # test purpose only?

        # TODO: baudrate?
        max_rate_response = self._do_cmd_resp(Command.GET, Parameter.MAXRATE, expected_prompt=Prompt.COMMAND)
        self._param_dict.update(max_rate_response)

        if startup:
            self._temp_max_rate(self._get_header_params)

        new_config = self._param_dict.get_all()
        log.debug("Updated parameter dict: old_config = %s, new_config = %s", old_config, new_config)

        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        Also called when setting parameters during startup and direct access

        Issue commands to the instrument to set various parameters.  If
        startup is set to true that means we are setting startup values
        and immutable parameters can be set.  Otherwise only READ_WRITE
        parameters can be set.

        @param params dictionary containing parameter name and value
        @param startup bool True is we are initializing, False otherwise
        @raise NotImplementedException
        """
        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.

        try:
            params = args[0]
            self._verify_not_readonly(*args, **kwargs)
        except IndexError:
            raise InstrumentParameterException('Set params requires a parameter dict.')
        else:
            if not isinstance(params, dict):
                raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, value in the params list set the value in parameters copy.
        name = None
        value = None
        try:
            for (name, value) in params.iteritems():
                log.debug('_set_params: setting %s to %s', name, value)
                if self._do_cmd_resp(Command.SET, name, value, expected_prompt=Prompt.COMMAND):
                    log.debug('_set_params: %s was updated to %s', name, value)
        except Exception as ex:
            raise InstrumentParameterException('Unable to set parameter %s to %s: %s' % (name, value, ex))

        self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)
        self._update_params(args[1])

    def _handler_command_set(self, *args, **kwargs):
        """Handle setting data from command mode

        @param params Dict of the parameters and values to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Handle getting an start autosample event when in command mode
        @param params List of the parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        self._do_cmd_resp(Command.EXIT_AND_RESET, expected_prompt=init_pattern, timeout=2)
        return PARProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_direct(self):
        """
        """
        log.debug("_handler_command_start_direct: entering DA mode")
        return PARProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """ Handle PARProtocolState.AUTOSAMPLE PARProtocolEvent.ENTER

        @param params Parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For hardware error
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return None, None

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """Handle PARProtocolState.AUTOSAMPLE stop

        @param params Parameters to pass to the state
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

    def _handler_autosample_reset(self, *args, **kwargs):
        """Handle PARProtocolState.AUTOSAMPLE reset

        @param params Dict with "command" enum and "params" of the parameters to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        # Switch to polled so reset command can be received consistently
        self._send_break_poll()
        try:
            self._send_reset()
        except InstrumentException:
            raise InstrumentProtocolException(error_code=InstErrorCode.HARDWARE_ERROR, msg="Couldn't reset autosample!")

        return PARProtocolState.AUTOSAMPLE, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Poll handlers.
    ########################################################################

    def _temp_max_rate(self, run_func):
        # save current maxrate, set maxrate to 1 can make this more reliable!
        current_maxrate = self._param_dict.get(Parameter.MAXRATE)
        self._do_cmd_resp(Command.SET, Parameter.MAXRATE, 1, expected_prompt=Prompt.COMMAND)
        self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)
        run_func()
        # set maxrate back
        self._do_cmd_resp(Command.SET, Parameter.MAXRATE, current_maxrate, expected_prompt=Prompt.COMMAND)
        self._do_cmd_resp(Command.SAVE, expected_prompt=Prompt.COMMAND)

    def _get_poll(self):
        self._do_cmd_no_resp(Command.EXIT)
        # switch to poll
        self._connection.send(Command.SWITCH_TO_POLL)
        # collect one poll
        self._do_cmd_resp(Command.SAMPLE, timeout=2, expected_prompt="SATPAR")
        # return to command mode
        self._do_cmd_resp(Command.BREAK, response_regex=COMMAND_REGEX, timeout=2)

    def _handler_poll_acquire_sample(self):
        """Handle PARProtocolState.POLL PARProtocolEvent.ACQUIRE_SAMPLE

        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid command
        """
        self._temp_max_rate(self._get_poll)
        return None, (None, None)

    def _handler_acquire_status(self):
        """

        :return:
        """
        # return parad_sa_config particle: telbaud, maxrate, serial number, fimrware, type

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

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        self._do_cmd_direct(data)
        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)
        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        # TODO restore parameters? happens automatically somewhere, make sure to override the base function
        return PARProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ###################################################################
    # Builders
    ###################################################################

    def _build_default_command(self, *args):
        return " ".join(str(x) for x in args)

    ##################################################################
    # Response parsers
    ##################################################################
    def _parse_response(self, response, prompt):
        """
        """
        return prompt

    def _parse_set_response(self, response, prompt):
        """Determine if a set was successful or not

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        """
        if prompt == Prompt.COMMAND:
            return True
        elif response == PARProtocolError.INVALID_COMMAND:
            return InstErrorCode.SET_DEVICE_ERR
        else:
            return InstErrorCode.HARDWARE_ERROR

    def _parse_get_response(self, response, prompt):
        """ Parse the response from the instrument for a couple of different
        query responses.

        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The numerical value of the parameter in the known units
        @raise InstrumentProtocolException When a bad response is encountered
        """
        log.debug("_parse_get_response: response=%r", response)
        match = GET_REGEX.search(response)
        if not match:
            log.warn("Bad response from instrument")
            raise InstrumentProtocolException("Invalid response. Bad command? %s" % response)
        else:
            log.debug("_parse_get_response: response=%r", match.group(1, 2))
            return match.group('resp')

    def _parse_silent_response(self, response, prompt):
        """Parse a silent response

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing silent response of [%s] with prompt [%s]", response, prompt)
        if (response == "" or response == prompt) and \
           (prompt == Prompt.NULL or prompt == Prompt.COMMAND):
            return InstErrorCode.OK
        else:
            return InstErrorCode.HARDWARE_ERROR

    def _parse_header_response(self, response, prompt): # TODO: rename to exit_reset?
        """ Parse what the header looks like to make sure if came up.

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing header response of %s", response)
        # TODO: we can reset the "polling_state" flag here, since this always resets it to auto

        match = HEADER_REGEX.search(response)
        if match:
            return match.group('instr', 'sernum', 'firm')
        else:
            return InstErrorCode.HARDWARE_ERROR

    def _parse_cmd_prompt_response(self, response, prompt):
        """Parse a command prompt response

        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval return An InstErrorCode value
        """
        log.debug("Parsing command prompt response of [%s] with prompt [%s]", response, prompt)
        if response == Prompt.COMMAND:
            # yank out the command we sent, split at the self.eoln
            split_result = response.split(self.eoln, 1)
            if len(split_result) > 1:
                response = split_result[1]
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
        log.debug("Parsing reset response of [%s] with prompt [%s]", response, prompt)

        lines = response.split(self.eoln)
        for line in lines:
            if init_regex.search(line):
                return InstErrorCode.OK

        return InstErrorCode.HARDWARE_ERROR

    ###################################################################
    # Helpers
    ###################################################################
    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific formatting.

        @param v A float val.
        @retval a float string formatted for "generic" set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%0.3f' % v

    def _send_reset(self, timeout=10):
        """Send a reset command out to the device

        @throw InstrumentTimeoutException
        @throw InstrumentProtocolException
        """
        # TODO handle errors correctly here, deal with repeats at high sample rate
        log.debug("Sending reset chars")

        if self._protocol_fsm.get_current_state() == PARProtocolState.COMMAND:
            return InstErrorCode.OK

        # TODO: infinite loop bad idea
        while True:
            self._do_cmd_no_resp(Command.RESET, timeout=timeout)
            time.sleep(RESET_DELAY)
            if self._confirm_autosample_mode():
                break

    def _send_break_poll(self):
        log.debug("_send_break_poll: maxrate = %s", self._param_dict.get(Parameter.MAXRATE))
        while True:
            for _ in xrange(25):
                self._connection.send(Command.SWITCH_TO_POLL)
                time.sleep(.15)
            # TODO: change this to a loop that tests for Maxrate  of seconds? if None, wait maximum 8 seconds
            if SAMPLE_REGEX.search(self._promptbuf):
                self._promptbuf = ''
            else:
                break
        time.sleep(3)   # put in test to confirm sleep based on maxrate

    def _send_break(self):
        self._send_break_poll()
        self._do_cmd_resp(Command.BREAK, response_regex=COMMAND_REGEX, timeout=2)

    def _got_chunk(self, chunk, timestamp):
        """
        Extract samples from a chunk of data
        @param chunk: bytes to parse into a sample.
        """
        self._extract_sample(SatlanticPARDataParticle, SAMPLE_REGEX, chunk, timestamp)

    def _confirm_autosample_mode(self):
        """
        Confirm we are in autosample mode by waiting for a sample to come in, and confirming that it does or does not.
        @retval True if in autosample mode, False if not
        """
        log.debug("Confirming autosample mode...")
        # timestamp now,
        start_time = self._last_data_timestamp
        # wait a sample period,
        time_between_samples = (1/self._param_dict.get_config()[Parameter.MAXRATE])+1
        time.sleep(time_between_samples)
        end_time = self._last_data_timestamp
        log.debug("_confirm_autosample_mode: end_time=%s, start_time=%s" % (end_time, start_time))
        if end_time != start_time:
            log.debug("Confirmed in autosample mode")
            return True
        else:
            log.debug("Confirmed NOT in autosample mode")
            return False


class SatlanticChecksumDecorator(ChecksumDecorator):
    """
    Checks the data checksum for the Satlantic PAR sensor
    """

    def handle_incoming_data(self, original_data=None, chained_data=None):
        if self._checksum_ok(original_data):
            if self.next_decorator is None:
                return original_data, chained_data
            else:
                self.next_decorator.handle_incoming_data(original_data, chained_data)
        else:
            log.warn("Calculated checksum did not match packet checksum.")
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED

    def _checksum_ok(self, data):
        """
        Confirm that the checksum is valid for the data line
        @param data The entire line of data, including the checksum
        @retval True if the checksum fits, False if the checksum is bad
        """
        assert (data is not None)
        assert (data != "")
        match = SAMPLE_REGEX.match(data)
        if not match:
            return False
        try:
            received_checksum = int(match.group('checksum'))
            line_end = match.start('checksum')-1
        except IndexError:
            # Didn't have a checksum!
            return False

        line = data[:line_end]
        # Calculate checksum on line
        checksum = 0
        for char in line:
            checksum += ord(char)
        checksum &= 0xFF

        return checksum == received_checksum