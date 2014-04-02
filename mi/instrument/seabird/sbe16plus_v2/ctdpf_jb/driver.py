"""
@package mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver
@file marine-integrations/mi/instrument/seabird/sbe16plus_v2/ctdpf_jb/driver.py
@author Tapana Gupta
@brief Driver for the CTDPF-JB instrument
Release notes:

SBE Driver
"""

__author__ = 'Tapana Gupta'
__license__ = 'Apache 2.0'

import re
import time
import string

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.data_particle import DataParticleKey, CommonDataParticleType
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException

from xml.dom.minidom import parseString

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt
from mi.instrument.seabird.sbe16plus_v2.driver import DataParticleType

from mi.instrument.seabird.driver import SeaBirdParticle
from mi.instrument.seabird.driver import SeaBirdInstrumentDriver
from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT

WAKEUP_TIMEOUT = 60

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    CLOCK_SYNC = 'clock_sync'


class Command(BaseEnum):

        GET_CD = 'GetCD'
        GET_SD = 'GetSD'
        GET_CC = 'GetCC'
        GET_EC = 'GetEC'
        RESET_EC = 'ResetEC'
        GET_HD = 'GetHD'
        START_NOW = 'StartNow'
        STOP = 'Stop'
        TS = 'ts'

        #TODO: not specified in IOS
        SET = 'set'


class Parameter(DriverParameter):
    """
    Device specific parameters for SBE19.
    """
    DATE_TIME = "DateTime"

    #TODO: do we need this?
    LOGGING = "logging"

    ECHO = "Echo"
    OUTPUT_EXEC_TAG = 'OutputExecutedTag'
    PTYPE = "PType"
    VOLT0 = "Volt0"
    VOLT1 = "Volt1"
    VOLT2 = "Volt2"
    VOLT3 = "Volt3"
    VOLT4 = "Volt4"
    VOLT5 = "Volt5"
    SBE38 = "SBE38"
    WETLABS = "WetLabs"
    GTD = "GTD"
    DUAL_GTD = "DUAL_GTD"
    TGTD = "TGTD"
    SEND_GTD = "SendGTD"
    OPTODE = "OPTODE"
    SEND_OPTODE = "SendOptode"
    OUTPUT_FORMAT = "OutputFormat"
    PROFILING_MODE = "MP"
    NUM_AVG_SAMPLES = "Navg"
    MIN_COND_FREQ = "MinCondFreq"
    PUMP_DELAY = "PumpDelay"
    AUTO_RUN = "AutoRun"
    IGNORE_SWITCH = "IgnoreSwitch"



###############################################################################
# Data Particles
###############################################################################

class SBE19StatusParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    DATE_TIME = "date_time_string"
    LOGGING_STATE = "logging_state"
    NUMBER_OF_EVENTS = "num_events"

    BATTERY_VOLTAGE_MAIN = "battery_voltage_main"
    BATTERY_VOLTAGE_LITHIUM = "battery_voltage_lithium"
    OPERATIONAL_CURRENT = "operational_current"
    PUMP_CURRENT = "pump_current"
    EXT_V01_CURRENT = "ext_v01_current"
    SERIAL_CURRENT = "serial_current"

    MEMORY_FREE = "mem_free"
    NUMBER_OF_SAMPLES = "numm_samples"
    SAMPLES_FREE = "samples_free"
    SAMPLE_LENGTH = "sample_length"
    PROFILES = "profiles"


class SBE19StatusParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS

    @staticmethod
    def regex():
        pattern = r'<StatusData.*?</StatusData>' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19StatusParticle.regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE19StatusParticleKey.BATTERY_VOLTAGE_MAIN: "vMain",
                            SBE19StatusParticleKey.BATTERY_VOLTAGE_LITHIUM: "vLith",
                            SBE19StatusParticleKey.OPERATIONAL_CURRENT: "iMain",
                            SBE19StatusParticleKey.PUMP_CURRENT: "iPump",
                            SBE19StatusParticleKey.EXT_V01_CURRENT: "iExt01",
                            SBE19StatusParticleKey.SERIAL_CURRENT: "iSerial",

                            SBE19StatusParticleKey.MEMORY_FREE: "Bytes",
                            SBE19StatusParticleKey.NUMBER_OF_SAMPLES: "Samples",
                            SBE19StatusParticleKey.SAMPLES_FREE: "SamplesFree",
                            SBE19StatusParticleKey.SAMPLE_LENGTH: "SampleLength",
                            SBE19StatusParticleKey.PROFILES: "Profiles",
                           }
        return map_param_to_tag[parameter_name]

    def _build_parsed_values(self):
        """
        Parse the output of the getSD command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        DATE_TIME = "DateTime"
        LOGGING_STATE = "LoggingState"
        EVENT_SUMMARY = "EventSummary"
        NUMBER_OF_EVENTS = "numEvents"
        POWER = "Power"
        MEMORY_SUMMARY = "MemorySummary"

        # check to make sure there is a correct match before continuing
        match = SBE19StatusParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        date_time = self._extract_xml_element_value(root, DATE_TIME)
        logging_status = self._extract_xml_element_value(root, LOGGING_STATE)
        event_summary = self._extract_xml_elements(root, EVENT_SUMMARY)[0]
        number_of_events = int(event_summary.getAttribute(NUMBER_OF_EVENTS))
        result = [{DataParticleKey.VALUE_ID: SBE19StatusParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.DATE_TIME,
                   DataParticleKey.VALUE: date_time},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.LOGGING_STATE,
                   DataParticleKey.VALUE: logging_status},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.NUMBER_OF_EVENTS,
                   DataParticleKey.VALUE: number_of_events},
                 ]

        element = self._extract_xml_elements(root, POWER)[0]
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.BATTERY_VOLTAGE_MAIN))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.BATTERY_VOLTAGE_LITHIUM))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.OPERATIONAL_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.PUMP_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.EXT_V01_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SERIAL_CURRENT))

        element = self._extract_xml_elements(root, MEMORY_SUMMARY)[0]
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.MEMORY_FREE, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.NUMBER_OF_SAMPLES, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SAMPLES_FREE, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SAMPLE_LENGTH, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.PROFILES, int))

        return result


class SBE19DataParticleKey(BaseEnum):
    TEMP = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    PRESSURE_TEMP = "pressure_temp"
    VOLT0 = "volt0"
    VOLT1 = "volt1"
    OXYGEN = "oxygen"


class SBE19DataParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       #04570F0A1E910828FC47BC59F199952C64C9

    Format:
       #ttttttccccccppppppvvvvvvvvvvvvoooooo

       Temperature = tttttt
       Conductivity = cccccc
       quartz pressure = pppppp
       quartz pressure temperature compensation = vvvv
       First external voltage = vvvv
       Second external voltage = vvvv
       Oxygen = oooooo
    """
    _data_particle_type = DataParticleType.CTD_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        #ttttttccccccppppppvvvvvvvvvvvvoooooo
        pattern = r'#? *' # patter may or may not start with a '
        pattern += r'([0-9A-F]{6})' # temperature
        pattern += r'([0-9A-F]{6})' # conductivity
        pattern += r'([0-9A-F]{6})' # pressure
        pattern += r'([0-9A-F]{4})' # pressure temp
        pattern += r'([0-9A-F]{4})' # volt0
        pattern += r'([0-9A-F]{4})' # volt1
        pattern += r'([0-9A-F]{6})' # oxygen
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE19DataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)

        @throws SampleException If there is a problem with sample creation
        """
        match = SBE19DataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            temperature = self.hex2value(match.group(1))
            conductivity = self.hex2value(match.group(2))
            pressure = self.hex2value(match.group(3))
            pressure_temp = self.hex2value(match.group(4))
            volt0 = self.hex2value(match.group(5))
            volt1 = self.hex2value(match.group(6))
            oxygen = self.hex2value(match.group(7))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [{DataParticleKey.VALUE_ID: SBE19DataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.PRESSURE,
                    DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.PRESSURE_TEMP,
                   DataParticleKey.VALUE: pressure_temp},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.VOLT0,
                   DataParticleKey.VALUE: volt0},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.VOLT1,
                   DataParticleKey.VALUE: volt1},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.OXYGEN,
                    DataParticleKey.VALUE: oxygen}]

        return result

###############################################################################
# Driver
###############################################################################

class SBE19InstrumentDriver(SeaBirdInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SeaBirdInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

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
        self._protocol = SBE19Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class SBE19Protocol(SBE16Protocol):
    """
    Instrument protocol class for SBE19 Driver
    Subclasses SBE16Protocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE19Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE19 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build SBE19 protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RESET_EC, self._handler_command_reset_ec)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.

        self._add_build_handler(Command.GET_CD, self._build_simple_command)
        self._add_build_handler(Command.GET_SD, self._build_simple_command)
        self._add_build_handler(Command.GET_CC, self._build_simple_command)
        self._add_build_handler(Command.GET_EC, self._build_simple_command)
        self._add_build_handler(Command.RESET_EC, self._build_simple_command)
        self._add_build_handler(Command.GET_HD, self._build_simple_command)

        self._add_build_handler(Command.START_NOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.TS, self._build_simple_command)
        self._add_build_handler(Command.SET, self._build_set_command)


        # Add response handlers for device commands.
        # these are here to ensure that correct responses to the commands are received before the next command is sent
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.GET_SD, self._validate_GetSD_response)
        self._add_response_handler(Command.GET_HD, self._validate_GetHD_response)
        self._add_response_handler(Command.GET_CD, self._validate_GetCD_response)
        self._add_response_handler(Command.GET_CC, self._validate_GetCC_response)
        self._add_response_handler(Command.GET_EC, self._validate_GetEC_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        #TODO: what other commands are schedulable?
        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CONFIGURATION_DATA, ProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)


    #TODO: implement this!
    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        return return_list

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        GetCC from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GET_CC, expected_prompt=Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_command_get_configuration: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.GET_SD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        result = self._do_cmd_resp(Command.GET_SD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCC Response: %s", result)

        log.debug("_handler_autosample_acquire_status: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))


    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        GetCC from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GETCC, expected_prompt=Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_autosample_get_configuration: GetCC Response: %s", result)

        log.debug("_handler_autosample_get_configuration: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))


    ########################################################################
    # response handlers.
    ########################################################################
    def _validate_GetSD_response(self, response, prompt):
        """
        validation handler for GetSD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("_validate_GetSD_response: GetSD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetSD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetSD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetSD command - correct instrument prompt missing: %s.' % response)

        if not SBE16StatusDataParticle.regex_compiled().search(response):
            log.error('_validate_GetSD_response: GetSD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetSD command not recognized: %s.' % response)

        return response

    def _validate_GetHD_response(self, response, prompt):
        """
        validation handler for GetHD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetHD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetHD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetHD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetHD command - correct instrument prompt missing: %s.' % response)

        if not SBE16HardwareDataParticle.regex_compiled().search(response):
            log.error('_validate_GetHD_response: GetHD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetHD command not recognized: %s.' % response)

        return response

    def _validate_GetCD_response(self, response, prompt):
        """
        validation handler for GetCD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetCD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetCD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetCD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCD command - correct instrument prompt missing: %s.' % response)

        if not SBE16ConfigurationDataParticle.regex_compiled().search(response):
            log.error('_validate_GetCD_response: GetCD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCD command not recognized: %s.' % response)

        return response

    def _validate_GetCC_response(self, response, prompt):
        """
        validation handler for GetCC command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetCC command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetCC command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetCC_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCC command - correct instrument prompt missing: %s.' % response)

        if not SBE16CalibrationDataParticle.regex_compiled().search(response):
            log.error('_validate_GetCC_response: GetCC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCC command not recognized: %s.' % response)

        return response

    def _validate_GetEC_response(self, response, prompt):
        """
        validation handler for GetEC command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetEC command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetEC command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetEC_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetEC command - correct instrument prompt missing: %s.' % response)

        if not SBE16CalibrationDataParticle.regex_compiled().search(response):
            log.error('_validate_GetEC_response: GetEC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetEC command not recognized: %s.' % response)

        return response

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE19 parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

        #TODO: verify if this lambda function is correct, check for completeness of DATE_TIME
        self._param_dict.add(Parameter.DATE_TIME,
                             r'(\d{4})-(\d{2})-(\d{2})T(\d{2})\:(\d{2})\:(\d{2})',
                             lambda match : match,
                             self._string_to_numeric_date_time_string,
                             type=ParameterDictType.STRING,
                             display_name="Date/Time",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.ECHO,
                             r'<EchoCharacters>(yes|no)</EchoCharacters>',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Echo Characters",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.LOGGING,
                             r'<LoggingState>(not )?logging</LoggingState>',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Is Logging",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)

        #TODO: RegEx for this one?
        self._param_dict.add(Parameter.OUTPUT_EXEC_TAG,
                             r'.',
                             lambda match : True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Output Execute Tag",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: RegEx for this one? This should always be 1
        self._param_dict.add(Parameter.PTYPE,
                             r'',
                             1,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Pressure Sensor Type",
                             startup_param = True,
                             direct_access = True,
                             default_value = 1,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: default value is conditional for Volt0 and Volt1
        #Current defaults assume Anderra Optode
        self._param_dict.add(Parameter.VOLT0,
                             r'<ExtVolt0>([\w]+)</ExtVolt0>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 0",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT1,
                             r'<ExtVolt1>([\w]+)</ExtVolt1>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 1",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT2,
                             r'<ExtVolt2>([\w]+)</ExtVolt2>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 2",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT3,
                             r'<ExtVolt3>([\w]+)</ExtVolt3>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 3",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT4,
                             r'<ExtVolt4>([\w]+)</ExtVolt4>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 4",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT5,
                             r'<ExtVolt5>([\w]+)</ExtVolt5>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 5",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.SBE38,
                             r'<SBE38>(yes|no)</SBE38>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE38 Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.WETLABS,
                             r'<WETLABS>(yes|no)</WETLABS>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Enable Wetlabs sensor",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.GTD,
                             r'<GTD>(yes|no)</GTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.DUAL_GTD,
                             r'<DualGTD>(yes|no)</DualGTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Dual GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.TGTD,
                             r'<TGTD>(yes|no)</TGTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: This assumes we have Anderra Optode
        self._param_dict.add(Parameter.OPTODE,
                             r'<OPTODE>(yes|no)</OPTODE>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Optode Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)


        self._param_dict.add(Parameter.OUTPUT_FORMAT,
                             r'<OutputFormat>([\w]+)</OutputFormat>',
                             self._output_format_string_2_int,
                             int,
                             type=ParameterDictType.INT,
                             display_name="Output Format",
                             startup_param = True,
                             direct_access = True,
                             default_value = 0,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.NUM_AVG_SAMPLES,
                             r'<ScansToAverage>([\d]+)</ScansToAverage>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Scans To Average",
                             startup_param = True,
                             direct_access = True,
                             default_value = 4,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.MIN_COND_FREQ,
                             r'<MinimumCondFreq>([\d]+)</MinimumCondFreq>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Minimum Conductivity Frequency",
                             startup_param = True,
                             direct_access = True,
                             default_value = 500,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.PUMP_DELAY,
                             r'<PumpDelay>([\d]+)</PumpDelay>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Pump Delay",
                             startup_param = True,
                             direct_access = True,
                             default_value = 60,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.AUTO_RUN,
                             r'<AutoRun>(yes|no)</AutoRun>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Auto Run",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.IGNORE_SWITCH,
                             r'<IgnoreSwitch>(yes|no)</IgnoreSwitch>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Ignore Switch",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)


        #TODO: SendGTD, SendOptode, MP?



    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # Static helpers
    ########################################################################

    @staticmethod
    def _string_to_numeric_date_time_string(date_time_string):
        """
        convert string from "2014-03-27T14:36:15" to numeric "mmddyyyyhhmmss"
        """
        return time.strftime("%m%d%Y%H%M%S", time.strptime(date_time_string, "%Y-%m-%dT%H:%M:%S"))


    @staticmethod
    def _output_format_string_2_int(format_string):
        """
        Convert an output format from an string to an int
        @param format_string sbe output format as string or regex match
        @retval int representation of output format
        @raise InstrumentParameterException if format unknown
        """
        if(not isinstance(format_string, str)):
            format_string = format_string.group(1)

        if(format_string.lower() ==  "raw hex"):
            return 0
        elif(format_string.lower() == "converted hex"):
            return 1
        elif(format_string.lower() == "raw decimal"):
            return 2
        elif(format_string.lower() == "converted decimal"):
            return 3
        elif(format_string.lower() == "converted hex for afm"):
            return 4
        elif(format_string.lower() == "converted xml uvic"):
            return 5
        else:
            raise InstrumentParameterException("output format unknown: %s" % format_string)
