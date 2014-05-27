"""
@package mi.instrument.noaa.heat.ooicore.driver
@file marine-integrations/mi/instrument/noaa/heat/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for LILY HEATER on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.instrument.noaa.botpt.driver import BotptProtocol
from mi.instrument.noaa.botpt.driver import NEWLINE
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException


log = get_logger()

###
#    Driver Constant Definitions
###=

OFF_HEAT_DURATION = 0


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class ExportedInstrumentCommand(BaseEnum):
    HEAT_ON = "EXPORTED_INSTRUMENT_CMD_HEAT_ON"
    HEAT_OFF = "EXPORTED_INSTRUMENT_CMD_HEAT_OFF"


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    HEAT_ON = ExportedInstrumentCommand.HEAT_ON
    HEAT_OFF = ExportedInstrumentCommand.HEAT_OFF
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    HEAT_ON = ProtocolEvent.HEAT_ON
    HEAT_OFF = ProtocolEvent.HEAT_OFF


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    HEAT_DURATION = "heat_duration"


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    HEAT_ON = 'HEAT,'  # turns the heater on; HEAT,<number of hours>
    HEAT_OFF = 'HEAT,0'  # turns the heater off


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    HEAT_PARSED = 'botpt_heat_sample'


class HEATDataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "heat_x_tilt"
    Y_TILT = "heat_y_tilt"
    TEMP = "heat_temp"


###############################################################################
# Data Particles
###############################################################################


class HEATDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       HEAT,2013/04/23 18:24:46,0000,0001,0025
       HEAT,2013/04/19 22:54:11,001,0001,0025
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,xxxx,yyyy,tttt

        ID = IIII = HEAT
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = xxxx (integer degrees)
        Y_TILT = yyyy (integer degrees)
        Temp = tttt (integer degrees C)
    """
    _data_particle_type = DataParticleType.HEAT_PARSED
    _compiled_regex = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'HEAT,'  # pattern starts with HEAT '
        pattern += r'(.*),'  # 1 time
        pattern += r'(-*[0-9]+),'  # 2 x-tilt
        pattern += r'(-*[0-9]+),'  # 3 y-tilt
        pattern += r'([0-9]{4})'  # 4 temp
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if HEATDataParticle._compiled_regex is None:
            HEATDataParticle._compiled_regex = re.compile(HEATDataParticle.regex())
        return HEATDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = HEATDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            heat_time = match.group(1)
            timestamp = time.strptime(heat_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            x_tilt = int(match.group(2))
            y_tilt = int(match.group(3))
            temperature = int(match.group(4))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'HEAT'},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.TIME,
             DataParticleKey.VALUE: heat_time},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature}
        ]

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

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal, PyMethodMayBeStatic
class Protocol(BotptProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        BotptProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.HEAT_ON, self._handler_command_heat_on),
                (ProtocolEvent.HEAT_OFF, self._handler_command_heat_off),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.HEAT_ON, self._build_heat_on_command)
        self._add_build_handler(InstrumentCommand.HEAT_OFF, self._build_heat_off_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.HEAT_ON, self._parse_heat_on_off_resp)
        self._add_response_handler(InstrumentCommand.HEAT_OFF, self._parse_heat_on_off_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        self._last_data_timestamp = 0
        self._filter_string = 'HEAT'

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(HEATDataParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.HEAT_ON, display_name="turn heater on")
        self._cmd_dict.add(Capability.HEAT_OFF, display_name="turn heater off")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        # Next 2 work together to pull 2 values out of a single line.

        self._param_dict.add(Parameter.HEAT_DURATION,
                             r'Not used. This is just to satisfy the param_dict',
                             None,
                             int,
                             type=ParameterDictType.INT,
                             display_name="Heat Duration",
                             multi_match=False,
                             visibility=ParameterDictVisibility.READ_WRITE)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, and then pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """
        if not self._extract_sample(HEATDataParticle,
                                    HEATDataParticle.regex_compiled(),
                                    chunk, timestamp):
            raise InstrumentProtocolException("Unhandled chunk")

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _build_heat_on_command(self, cmd, *args, **kwargs):
        return cmd + str(self._param_dict.get(Parameter.HEAT_DURATION)) + NEWLINE

    def _build_heat_off_command(self, cmd, *args, **kwargs):
        return cmd + NEWLINE

    def _parse_heat_on_off_resp(self, response, prompt):
        log.debug("_parse_heat_on_off_resp: response: %r; prompt: %r", response, prompt)
        return response

    def _verify_set_values(self, params):
        if Parameter.HEAT_DURATION in params:
            duration = int(params[Parameter.HEAT_DURATION])
            if duration < 1 or duration > 8:
                raise InstrumentParameterException('Heat duration out of range 1-8')

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_heat_on(self, *args, **kwargs):
        """
        Turn the heater on
        """
        next_state = None
        result = None

        # first, send a heat off.   If the instrument is currently heating, new duration
        # will be appended.  Override this behavior by turning heater off, then on with
        # new duration
        self._handler_command_heat_off()
        # call _do_cmd_resp, passing our heat_duration parameter as the expected_prompt
        return self._handler_command_generic(InstrumentCommand.HEAT_ON, None, None,
                                             expected_prompt=',*%d' % self._param_dict.get(Parameter.HEAT_DURATION))

    def _handler_command_heat_off(self, *args, **kwargs):
        """
        Turn the heater off
        """
        next_state = None
        result = None

        # call _do_cmd_resp, passing our heat_duration parameter as the expected_prompt
        return self._handler_command_generic(InstrumentCommand.HEAT_OFF, None, None, expected_prompt=',*0')