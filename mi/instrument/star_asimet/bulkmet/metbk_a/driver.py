"""
@package mi.instrument.star_asimet.bulkmet.metbk_a.driver
@file marine-integrations/mi/instrument/star_aismet/bulkmet/metbk_a/driver.py
@author Bill Bollenbacher
@brief Driver for the metbk_a
Release notes:

initial version
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import re
import time
import string
import json

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, \
                               InstrumentProtocolException
from mi.core.time import get_timestamp_delayed
                               
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
                                                   ParameterDictType, \
                                                   ParameterDictVisibility

# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

AUTO_SAMPLE_SCHEDULED_JOB = 'auto_sample'
        
####
#    Driver Constant Definitions
####

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CLOCK_SYNC = 'clock_sync'

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN       = DriverProtocolState.UNKNOWN
    COMMAND       = DriverProtocolState.COMMAND
    AUTOSAMPLE    = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER            = DriverEvent.ENTER
    EXIT             = DriverEvent.EXIT
    DISCOVER         = DriverEvent.DISCOVER
    EXECUTE_DIRECT   = DriverEvent.EXECUTE_DIRECT
    START_DIRECT     = DriverEvent.START_DIRECT
    STOP_DIRECT      = DriverEvent.STOP_DIRECT
    GET              = DriverEvent.GET
    SET              = DriverEvent.SET
    ACQUIRE_SAMPLE   = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS   = DriverEvent.ACQUIRE_STATUS
    CLOCK_SYNC       = DriverEvent.CLOCK_SYNC
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = DriverEvent.STOP_AUTOSAMPLE
    FLASH_STATUS     = 'DRIVER_EVENT_FLASH_STATUS'

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_STATUS   = ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_SAMPLE   = ProtocolEvent.ACQUIRE_SAMPLE
    CLOCK_SYNC       = ProtocolEvent.CLOCK_SYNC
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = ProtocolEvent.STOP_AUTOSAMPLE
    FLASH_STATUS     = ProtocolEvent.FLASH_STATUS
 
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    CLOCK = 'clock'
    SAMPLE_INTERVAL = 'sample_interval'

class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    CR_NL   = NEWLINE
    STOPPED = "Sampling STOPPED" + NEWLINE
    GO      = "Sampling GO - synchronizing..." + NEWLINE
    FS      = "bytes free\r" + NEWLINE

class Command(BaseEnum):
    """
    Instrument command strings
    """
    GET_CLOCK = "#CLOCK"
    SET_CLOCK = "#CLOCK="
    D          = "#D"
    FS         = "#FS"
    STAT       = "#STAT"
    GO         = "#GO"
    STOP       = "#STOP"

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW          = CommonDataParticleType.RAW
    METBK_PARSED = 'metbk_parsed'
    METBK_STATUS = 'metbk_status'
    
###############################################################################
# Data Particles
###############################################################################

class METBK_SampleDataParticleKey(BaseEnum):
    BAROMETRIC_PRESSURE = 'barometric_pressure'
    RELATIVE_HUMIDITY = 'relative_humidity'
    AIR_TEMPERATURE = 'air_temperature'
    LONGWAVE_IRRADIANCE = 'longwave_irradiance'
    PRECIPITATION = 'precipitation'
    SEA_SURFACE_TEMPERATURE = 'sea_surface_temperature'
    SEA_SURFACE_CONDUCTIVITY = 'sea_surface_conductivity'
    SHORTWAVE_IRRADIANCE = 'shortwave_irradiance'
    EASTWARD_WIND_VELOCITY = 'eastward_wind_velocity'
    NORTHWARD_WIND_VELOCITY = 'northward_wind_velocity'
    
class METBK_SampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.METBK_PARSED
        
    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        SAMPLE_DATA_PATTERN = (r'(-*\d+\.\d+)' +        # BPR
                                '\s*(-*\d+\.\d+)' +     # RH %
                                '\s*(-*\d+\.\d+)' +     # RH temp
                                '\s*(-*\d+\.\d+)' +     # LWR
                                '\s*(-*\d+\.\d+)' +     # PRC
                                '\s*(-*\d+\.\d+)' +     # ST
                                '\s*(-*\d+\.\d+)' +     # SC
                                '\s*(-*\d+\.\d+)' +     # SWR
                                '\s*(-*\d+\.\d+)' +     # We
                                '\s*(-*\d+\.\d+)' +     # Wn
                                '.*?' + NEWLINE)        # throw away batteries
        return re.compile(SAMPLE_DATA_PATTERN, re.DOTALL)

    def _build_parsed_values(self):
        
        match = METBK_SampleDataParticle.regex_compiled().match(self.raw_data)
        
        if not match:
            raise SampleException("METBK_SampleDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.BAROMETRIC_PRESSURE,
                   DataParticleKey.VALUE: float(match.group(1))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.RELATIVE_HUMIDITY,
                   DataParticleKey.VALUE: float(match.group(2))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.AIR_TEMPERATURE,
                   DataParticleKey.VALUE: float(match.group(3))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.LONGWAVE_IRRADIANCE,
                   DataParticleKey.VALUE: float(match.group(4))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.PRECIPITATION,
                   DataParticleKey.VALUE: float(match.group(5))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.SEA_SURFACE_TEMPERATURE,
                   DataParticleKey.VALUE: float(match.group(6))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.SEA_SURFACE_CONDUCTIVITY,
                   DataParticleKey.VALUE: float(match.group(7))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.SHORTWAVE_IRRADIANCE,
                   DataParticleKey.VALUE: float(match.group(8))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.EASTWARD_WIND_VELOCITY,
                   DataParticleKey.VALUE: float(match.group(9))},
                  {DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.NORTHWARD_WIND_VELOCITY,
                   DataParticleKey.VALUE: float(match.group(10))}]
        
        log.debug("METBK_SampleDataParticle._build_parsed_values: result=%s" %result)
        return result
    
    
class METBK_StatusDataParticleKey(BaseEnum):
    INSTRUMENT_MODEL = 'instrument_model'
    SERIAL_NUMBER = 'serial_number'
    CALIBRATION_DATE = 'calibration_date'
    FIRMWARE_VERSION = 'firmware_version'
    DATE_TIME_STRING = 'date_time_string'
    LOGGING_INTERVAL = 'logging_interval'
    CURRENT_TICK  = 'current_tick'
    RECENT_RECORD_INTERVAL = 'recent_record_interval'
    FLASH_CARD_PRESENCE = 'flash_card_presence'
    BATTERY_VOLTAGE_MAIN = 'battery_voltage_main'
    FAILURE_MESSAGES = 'failure_messages'
    PTT_ID1 = 'ptt_id1'
    PTT_ID2 = 'ptt_id2'
    PTT_ID3 = 'ptt_id3'
    SAMPLING_STATE = 'sampling_state'
    
    
class METBK_StatusDataParticle(DataParticle):
    _data_particle_type = DataParticleType.METBK_STATUS
    
    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        STATUS_DATA_PATTERN = (r'Model:\s+(.+?)\r\n' +     
                                'SerNum:\s+(.+?)\r\n'  +     
                                'CfgDat:\s+(.+?)\r\n' +
                                'Firmware:\s+(.+?)\r\n'  +     
                                'RTClock:\s+(.+?)\r\n'  +     
                                'Logging Interval:\s+(\d+);\s+'  +     
                                'Current Tick:\s+(\d+)\r\n'  +     
                                'R-interval:\s+(.+?)\r\n'  +     
                                '(.+?)\r\n'  +                     # compact flash info
                                'Main Battery Voltage:\s+(.+?)\r\n' +
                                '(.+?)'  +                         # module failures & PTT messages
                                '\r\nSampling\s+(\w+)\r\n') 
           
        return re.compile(STATUS_DATA_PATTERN, re.DOTALL)

    def _build_parsed_values(self):        
        log.debug("METBK_StatusDataParticle: input = %s" %self.raw_data)
            
        match = METBK_StatusDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("METBK_StatusDataParticle: No regex match of parsed status data: [%s]", self.raw_data)

        result = [{DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.INSTRUMENT_MODEL,
                   DataParticleKey.VALUE: match.group(1)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: match.group(2)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.CALIBRATION_DATE,
                   DataParticleKey.VALUE: match.group(3)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: match.group(4)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.DATE_TIME_STRING,
                   DataParticleKey.VALUE: match.group(5)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.LOGGING_INTERVAL,
                   DataParticleKey.VALUE: int(match.group(6))},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.CURRENT_TICK,
                   DataParticleKey.VALUE: int(match.group(7))},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.RECENT_RECORD_INTERVAL,
                   DataParticleKey.VALUE: int(match.group(8))},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.FLASH_CARD_PRESENCE,
                   DataParticleKey.VALUE: match.group(9)},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.BATTERY_VOLTAGE_MAIN,
                   DataParticleKey.VALUE: float(match.group(10))},
                  {DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.SAMPLING_STATE,
                   DataParticleKey.VALUE: match.group(12)}]
        
        lines = match.group(11).split(NEWLINE)
        length = len(lines)
        print ("length=%d; lines=%s" %(length, lines))
        if length < 3:
            raise SampleException("METBK_StatusDataParticle: Not enough PTT lines in status data: [%s]", self.raw_data)

        # grab PTT lines
        result.append({DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.PTT_ID1,
                       DataParticleKey.VALUE: lines[length-3]})
        result.append({DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.PTT_ID2,
                       DataParticleKey.VALUE: lines[length-2]})
        result.append({DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.PTT_ID3,
                       DataParticleKey.VALUE: lines[length-1]})
        
        # grab any module failure lines
        if length > 3:
            length -= 3
            failures = []
            for index in range(0, length):
                failures.append(lines[index])
            result.append({DataParticleKey.VALUE_ID: METBK_StatusDataParticleKey.FAILURE_MESSAGES,
                           DataParticleKey.VALUE: failures})

        log.debug("METBK_StatusDataParticle: result = %s" %result)
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
        # replace the driver's discover handler with one that applies the startup values after discovery
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, 
                                         DriverEvent.DISCOVER, 
                                         self._handler_connected_discover)
    
    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params after we discover. 
        # For this instrument the driver puts the instrument into command mode during discover.
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result


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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    last_sample = ''
    
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
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.FLASH_STATUS, self._handler_flash_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.CLOCK_SYNC, self._handler_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.FLASH_STATUS, self._handler_flash_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Add build handlers for device commands.
        self._add_build_handler(Command.GET_CLOCK, self._build_simple_command)
        self._add_build_handler(Command.SET_CLOCK, self._build_set_clock_command)
        self._add_build_handler(Command.D, self._build_simple_command)
        self._add_build_handler(Command.GO, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.FS, self._build_simple_command)
        self._add_build_handler(Command.STAT, self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.GET_CLOCK, self._parse_clock_response)
        self._add_response_handler(Command.SET_CLOCK, self._parse_clock_response)
        self._add_response_handler(Command.FS, self._parse_fs_response)
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()
        
        self._chunker = StringChunker(Protocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.CLOCK_SYNC)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        matchers = []
        return_list = []

        matchers.append(METBK_SampleDataParticle.regex_compiled())
        matchers.append(METBK_StatusDataParticle.regex_compiled())
                    
        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
                    
        """
        if return_list != []:
            log.debug("sieve_function: raw_data=%s, return_list=%s" %(raw_data, return_list))
        """
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        log.debug("_got_chunk: chunk=%s" %chunk)
        self._extract_sample(METBK_SampleDataParticle, METBK_SampleDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(METBK_StatusDataParticle, METBK_StatusDataParticle.regex_compiled(), chunk, timestamp)


    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # override methods from base class.
    ########################################################################

    def _extract_sample(self, particle_class, regex, line, timestamp, publish=True):
        """
        Overridden to add duplicate sample checking.  This duplicate checking should only be performed
        on sample chunks and not other chunk types, therefore the regex is performed before the string checking.
        Extract sample from a response line if present and publish  parsed particle

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
        @todo Figure out how the agent wants the results for a single poll
            and return them that way from here
        """
        sample = None
        match = regex.match(line)
        if match:
            if particle_class == METBK_SampleDataParticle:
                # check to see if there is a delta from last sample, and don't parse this sample if there isn't
                if match.group(0) == self.last_sample:
                    return
        
                # save this sample as last_sample for next check        
                self.last_sample = match.group(0)
            
            particle = particle_class(line, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)
    
            sample = json.loads(parsed_sample)
            return sample
        return sample

    ########################################################################
    # implement virtual methods from base class.
    ########################################################################

    def apply_startup_params(self):
        """
        Apply sample_interval startup parameter.  
        """

        config = self.get_startup_config()
        log.debug("apply_startup_params: startup config = %s" %config)
        if config.has_key(Parameter.SAMPLE_INTERVAL):
            log.debug("apply_startup_params: setting sample_interval to %d" %config[Parameter.SAMPLE_INTERVAL])
            self._param_dict.set_value(Parameter.SAMPLE_INTERVAL, config[Parameter.SAMPLE_INTERVAL])

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
        Discover current state; can only be COMMAND (instrument has no actual AUTOSAMPLE mode).
        @retval (next_state, result), (ProtocolState.COMMAND, None) if successful.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.IDLE

        log.debug("_handler_unknown_discover: state = %s", next_state)
        return (next_state, result)


    ########################################################################
    # Command handlers.
    # just implemented to make DA possible, instrument has no actual command mode
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """

        # Command device to update parameters and send a config change event if needed.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_set(self, *args, **kwargs):
        """
        no writable parameters so does nothing, just implemented to make framework happy
        """

        next_state = None
        result = None
        return (next_state, result)

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        self._ensure_autosample_config()
        self._add_scheduler_event(AUTO_SAMPLE_SCHEDULED_JOB, ProtocolEvent.ACQUIRE_SAMPLE)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # autosample handlers.
    ########################################################################

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE

        self._remove_scheduler(AUTO_SAMPLE_SCHEDULED_JOB)
        
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
        next_state = None
        result = None

        self._do_cmd_direct(data)
                        
        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # general handlers.
    ########################################################################

    def _handler_flash_status(self, *args, **kwargs):
        """
        Acquire flash status from instrument.
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.FS, expected_prompt=Prompt.FS)

        return (next_state, (next_agent_state, result))

    def _handler_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from instrument.
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.D, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device respond correctly.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        time_format = "%Y/%m/%d %H:%M:%S"
        str_val = get_timestamp_delayed(time_format)
        log.debug("Setting instrument clock to '%s'", str_val)
        self._do_cmd_resp(Command.STOP, expected_prompt=Prompt.STOPPED)
        try:
            self._do_cmd_resp(Command.SET_CLOCK, str_val, expected_prompt=Prompt.CR_NL)
        finally:
            # ensure that we try to start the instrument sampling again
            self._do_cmd_resp(Command.GO, expected_prompt=Prompt.GO)

        return (next_state, (next_agent_state, result))

    def _handler_acquire_status(self, *args, **kwargs):
        """
        Acquire status from instrument.
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.STAT, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################

    def _ensure_autosample_config(self):    
        scheduler_config = self._get_scheduler_config()
        if (scheduler_config == None):
            log.debug("_ensure_autosample_config: adding scheduler element to _startup_config")
            self._startup_config[DriverConfigKey.SCHEDULER] = {}
            scheduler_config = self._get_scheduler_config()
        log.debug("_ensure_autosample_config: adding autosample config to _startup_config")
        config = {DriverSchedulerConfigKey.TRIGGER: {
                     DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                     DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.SAMPLE_INTERVAL)}}
        self._startup_config[DriverConfigKey.SCHEDULER][AUTO_SAMPLE_SCHEDULED_JOB] = config
        if(not self._scheduler):
            self.initialize_scheduler()
        
    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
        pass
    
    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name="synchronize clock")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.ACQUIRE_SAMPLE, display_name="acquire sample")
        self._cmd_dict.add(Capability.FLASH_STATUS, display_name="flash status")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()
        
        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.CLOCK,
                             r'(.*)\r\n', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             type=ParameterDictType.STRING,
                             display_name="clock",
                             expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             r'Not used. This parameter is not parsed from instrument response',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=30,
                             value=30,
                             startup_param=True,
                             display_name="sample_interval",
                             visibility=ParameterDictVisibility.IMMUTABLE)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        
        log.debug("_update_params:")
         # Issue clock command and parse results.  
        # This is the only parameter and it is always changing so don't bother with the 'change' event
        self._do_cmd_resp(Command.GET_CLOCK)

    def _build_set_clock_command(self, cmd, val):
        """
        Build handler for set clock command (cmd=val followed by newline).
        @param cmd the string for setting the clock (this should equal #CLOCK=).
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        """
        cmd = '%s%s' %(cmd, val) + NEWLINE
        return cmd

    def _parse_clock_response(self, response, prompt):
        """
        Parse handler for clock command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if clock command misunderstood.
        """
        log.debug("_parse_clock_response: response=%s, prompt=%s" %(response, prompt))
        if prompt not in [Prompt.CR_NL]: 
            raise InstrumentProtocolException('CLOCK command not recognized: %s.' % response)

        if not self._param_dict.update(response):
            raise InstrumentProtocolException('CLOCK command not parsed: %s.' % response)

        return

    def _parse_fs_response(self, response, prompt):
        """
        Parse handler for FS command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if FS command misunderstood.
        """
        log.debug("_parse_fs_response: response=%s, prompt=%s" %(response, prompt))
        if prompt not in [Prompt.FS]: 
            raise InstrumentProtocolException('FS command not recognized: %s.' % response)

        return response
