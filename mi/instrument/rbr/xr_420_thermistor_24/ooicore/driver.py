"""
@package mi.instrument.rbr.xr-420_thermistor_24.ooicore.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/rbr/xr-420_thermistor_24/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the RBR Thermistor String (24 thermistors)
Release notes:

initial release
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'


import time
import re
import datetime
import ntplib

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               SampleException, \
                               InstrumentStateException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.common import InstErrorCode
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger
log = get_logger()

SAMPLE_DATA_PATTERN = (r'(\d+\s+\d+\s+\d+)' +    # date
                       '\s+(\d+\s+\d+\s+\d+)' +  # time
                       '\.(\d+)' +               # fractional second
                       '\s+(\w+)' +              # vector A
                       '\s+(\w+)' +              # vector B
                       '\s+(\w+)' +              # vector C
                       '\s+(\w+)' +              # vector D
                       '\s+(-*\d+\.\d+)' +       # east
                       '\s+(-*\d+\.\d+)' +       # north
                       '\s+(-*\d+\.\d+)' +       # west
                       '\s+(-*\d+\.\d+)' +       # temperature
                       '\s+(-*\d+\.\d+)' +       # MX
                       '\s+(-*\d+\.\d+)' +       # MY
                       '\s+(-*\d+\.\d+)' +       # pitch
                       '\s+(-*\d+\.\d+)\s+')     # roll

SAMPLE_DATA_REGEX = re.compile(SAMPLE_DATA_PATTERN)

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    SAMPLE = 'sample'
    STATUS = 'status'

INSTRUMENT_NEWLINE = '\r\n'
WRITE_DELAY = 0

# default timeout.
INSTRUMENT_TIMEOUT = 5

# Device responses.
class InstrumentResponses(BaseEnum):
    """
    XR-420 responses.
    """
    STATUS          = 'Logger status '
    LINE_TERMINATOR = INSTRUMENT_NEWLINE
        
class InstrumentCmds(BaseEnum):   
    GET_IDENTIFICATION       = 'A' 
    GET_LOGGER_DATE_AND_TIME = 'B'
    GET_SAMPLE_INTERVAL      = 'C'
    GET_START_DATE_AND_TIME  = 'D'  
    GET_END_DATE_AND_TIME    = 'E' 
    GET_STATUS               = 'T'
    GET_CHANNEL_CALIBRATION  = 'Z'
    GET_BATTERY_VOLTAGE      = '!D'
    SET_LOGGER_DATE_AND_TIME = 'J'
    SET_SAMPLE_INTERVAL      = 'K'
    SET_START_DATE_AND_TIME  = 'L'  
    SET_END_DATE_AND_TIME    = 'M'
    TAKE_SAMPLE_IMMEDIATELY  = 'F' 
    RESET_SAMPLING           = 'N'
    START_SAMPLING           = 'P'
    STOP_SAMPLING            = '!9'
    SUSPEND_SAMPLING         = '!S'
    RESUME_SAMPLING          = '!R'
    SET_ADVANCED_CONTROLS    = '!1'
    GET_ADVANCED_CONTROLS    = '!2'

class ProtocolStates(BaseEnum):
    """
    Protocol states for XR-420. Cherry picked from DriverProtocolState enum.
    """
    UNKNOWN       = DriverProtocolState.UNKNOWN
    COMMAND       = DriverProtocolState.COMMAND
    AUTOSAMPLE    = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ProtocolEvent(BaseEnum):
    """
    Protocol events for XR-420. Cherry picked from DriverEvent enum.
    """
    ENTER            = DriverEvent.ENTER
    EXIT             = DriverEvent.EXIT
    GET              = DriverEvent.GET
    SET              = DriverEvent.SET
    DISCOVER         = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT   = DriverEvent.EXECUTE_DIRECT
    START_DIRECT     = DriverEvent.START_DIRECT
    STOP_DIRECT      = DriverEvent.STOP_DIRECT
    CLOCK_SYNC       = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS   = DriverEvent.ACQUIRE_STATUS         

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET              = ProtocolEvent.GET
    SET              = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC       = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS   = ProtocolEvent.ACQUIRE_STATUS         

# Device specific parameters.
class InstrumentParameters(DriverParameter):
    """
    Device parameters for XR-420.
    """
    # main menu parameters
    #IDENTIFICATION       = 'identification'
    #SYS_CLOCK            = 'sys_clock'
    #LOGGER_DATE_AND_TIME = 'logger_date_and_time'
    #SAMPLE_INTERVAL      = 'sample_interval'
    #START_DATE_AND_TIME  = 'start_date_and_time'
    #END_DATE_AND_TIME    = 'end_date_and_time'
    STATUS               = 'status'
    #BATTERY_VOLTAGE      = 'battery_voltage'
    
class Status(DriverParameter):
    NOT_ENABLED_FOR_SAMPLING       = 0x00
    ENABLED_SAMPLING_NOT_STARTED   = 0x01
    STARTED_SAMPLING               = 0x02
    STOPPED_SAMPLING               = 0x04
    TEMPORARILY_SUSPENDED_SAMPLING = 0x05
    HIGH_SPEED_PROFILING_MODE      = 0x06
    ERASING_DATA_MEMORY            = 0x7F
    DATA_MEMORY_ERASE_FAILED       = 0x80
    PASSED_END_TIME                = 0x01
    RCVD_STOP_COMMAND              = 0x02
    DATA_MEMORY_FULL               = 0x03
    CONFIGURATION_ERROR            = 0x05

###
#   Driver for XR-420 Thermistor
###
class InstrumentDriver(SingleConnectionInstrumentDriver):

    """
    Instrument driver class for XR-420 driver.
    Uses CommandResponseInstrumentProtocol to communicate with the device
    """

    def __init__(self, evt_callback):
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

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = InstrumentProtocol(InstrumentResponses, INSTRUMENT_NEWLINE, self._driver_event)
        
###############################################################################
# Data particles
###############################################################################

class XR_420SampleDataParticleKey(BaseEnum):
    TIMESTAMP                = "timestamp"
                
class XR_420SampleDataParticle(DataParticle):
    """
    Class for parsing sample data into a data particle structure for the XR-420 sensor. 
    """
    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("XR_420SampleDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        #log.debug('_build_parsed_values: match=%s' %match.group(0))
                
        try:
            datetime = match.group(1) + ' ' + match.group(2)
            timestamp = time.strptime(datetime, "%m %d %Y %H %M %S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]" %(ex, self.raw_data))
                     
        result = [{DataParticleKey.VALUE_ID: XR_420SampleDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: ntp_timestamp}]
 
        log.debug('XR_420SampleDataParticle: particle=%s' %result)
        return result
    
class XR_420StatusDataParticleKey(BaseEnum):
    BATTERY_VOLTAGE  = InstrumentParameters.STATUS
                
class XR_420StatusDataParticle(DataParticle):
    """
    Class for constructing status data into a status particle structure for the XR-420 sensor. 
    The raw_data variable in the DataParticle base class needs to be initialized to a reference to 
    a dictionary that contains the status parameters.
    """
    _data_particle_type = DataParticleType.STATUS

    def _build_parsed_values(self):
        """
        Build the status particle from a dictionary of parameters adding the appropriate tags.
        NOTE: raw_data references a dictionary with the status parameters, not a line of input
        @throws SampleException If there is a problem with particle creation
        """
                
        if not isinstance(self.raw_data, dict):
            raise SampleException("Error: raw_data is not a dictionary")
                     
        log.debug('XR_420StatusDataParticle: raw_data=%s' %self.raw_data)

        result = []
        for key, value in self.raw_data.items():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})
             
        log.debug('XR_420StatusDataParticle: particle=%s' %result)
        return result
    
###
#   Protocol for XR-420
###
class InstrumentProtocol(CommandResponseInstrumentProtocol):
    """
    This protocol implements a simple command-response interaction for the XR-420 instrument.  
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = INSTRUMENT_NEWLINE
        self.sorted_responses = sorted(InstrumentResponses.list(), key=len, reverse=True)
        
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
                
        self._protocol_fsm = InstrumentFSM(ProtocolStates, 
                                           ProtocolEvent, 
                                           ProtocolEvent.ENTER,
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Set state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolStates.UNKNOWN)

        self._build_command_handlers()
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(InstrumentProtocol.chunker_sieve_function)


    @staticmethod
    def chunker_sieve_function(raw_data):
        # The method that detects data sample structures from instrument
 
        return_list = []
        
        for match in SAMPLE_DATA_REGEX.finditer(raw_data):
            return_list.append((match.start(), match.end()))
                
        return return_list
    
    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _got_chunk(self, structure, timestamp):
        """
        The base class got_data has gotten a structure from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        log.debug("_got_chunk: detected structure = <%s>", structure)
        self._extract_sample(XR_420SampleDataParticle, SAMPLE_DATA_REGEX, structure, timestamp)


    ########################################################################
    # implement virtual methods from base class.
    ########################################################################

    def _send_wakeup(self):
        # Send 'get status' command.
        cmd = InstrumentCmds.GET_STATUS
        log.debug('_send_wakeup: sending <%s>' % cmd)
        self._connection.send(cmd)

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

        log.debug("apply_startup_params: CURRENT STATE = %s" % self.get_current_state())
        if (self.get_current_state() != ProtocolStates.COMMAND):
            raise InstrumentProtocolException("Not in command state. Unable to apply startup parameters")

        # If our configuration on the instrument matches what we think it should be then 
        # we don't need to do anything.
        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s" % startup_params)
        instrument_configured = True
        for param in startup_params:
            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                instrument_configured = False
                break
        if instrument_configured:
            return
        
        config = self.get_startup_config()
        self._handler_command_set(config)


    ########################################################################
    # overridden methods from base class.
    ########################################################################

    def _get_response(self, timeout=10, expected_prompt=None):
        """
        overridden to not strip \r\n, which is one of the responses of interest
        Get a response from the instrument.
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.

        starttime = time.time()
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        while True:
            for item in prompt_list:
                if self._promptbuf.endswith(item):
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def  _wakeup(self, timeout, delay=1):
        """
        overridden to find longest matching prompt anywhere in the buffer
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        self._promptbuf = ''
        
        # Grab time for timeout.
        starttime = time.time()
        
        while True:
            self._send_wakeup()
            time.sleep(delay)

            for item in self.sorted_responses:
                #log.debug("_wakeup: GOT " + repr(self._promptbuf))
                if item in self._promptbuf:
                    log.debug('_wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in _wakeup()")    

    
    ########################################################################
    # State Unknown handlers.
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
        Discover current state; can be COMMAND or AUTOSAMPLE.  
        @retval (next_state, result), (ProtocolStates.COMMAND or ProtocolStates.AUTOSAMPLE, None) if successful.
        """
        next_state = None
        result = None
        
        try:
            self._wakeup(5, .5)
        except InstrumentTimeoutException:
            # didn't get status response, so indicate that there is trouble with the instrument
            raise InstrumentStateException('Unknown state.')
        
        if InstrumentResponses.STATUS in self._promptbuf:
            # got status response, so determine what mode the instrument is in
            parsed = self._promptbuf.split() 
            status = int(parsed[2], 16)
            log.debug("_handler_unknown_discover: parsed=%s, status=%d" %(parsed, status))
            if status > Status.DATA_MEMORY_ERASE_FAILED:
                status = Status.STOPPED_SAMPLING
            if status in [Status.STARTED_SAMPLING,
                          Status.TEMPORARILY_SUSPENDED_SAMPLING,
                          Status.HIGH_SPEED_PROFILING_MODE]:
                next_state = ProtocolStates.AUTOSAMPLE
                result = ResourceAgentState.STREAMING
            else:
                next_state = ProtocolStates.COMMAND
                result = ResourceAgentState.IDLE
        else:
            raise InstrumentStateException('Unknown state.')
            
        return (next_state, result)


    ########################################################################
    # State Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        self._update_params()
        
        log.debug("parameters values are: %s" %str(self._param_dict.get_config()))

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
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.
        try:
            params_to_set = args[0]           
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        else:
            if not isinstance(params_to_set, dict):
                raise InstrumentParameterException('Set parameters not a dict.')
        
        self._set_parameter_sub_parameters(params_to_set)
                
        for (key, val) in params_to_set.iteritems():
            dest_submenu = self._param_dict.get_menu_path_write(key)
            command = self._param_dict.get_submenu_write(key)
            self._navigate_and_execute(command, name=key, value=val, dest_submenu=dest_submenu, timeout=5)

        self._update_params()
            
        return (next_state, result)

    def _handler_command_get(self, *args, **kwargs):
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
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.
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

        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolStates.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        self._navigate_and_execute(InstrumentCmds.DEPLOY_GO, 
                                   dest_submenu=SubMenues.DEPLOY, 
                                   timeout=20, 
                                   *args, **kwargs)
                
        next_state = ProtocolStates.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (ProtocolStates.TEST, None).
        """
        next_state = None
        result = None

        next_state = ProtocolStates.TEST
        
        return (next_state, result)

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolStates.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        
        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        str_time = get_timestamp_delayed("%m/%d/%Y %H:%M:%S")
        log.info("_handler_command_clock_sync: time set to %s" %str_time)
        dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.SYS_CLOCK)
        command = self._param_dict.get_submenu_write(InstrumentParameters.SYS_CLOCK)
        self._navigate_and_execute(command, name=InstrumentParameters.SYS_CLOCK, value=str_time, dest_submenu=dest_submenu, timeout=5)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        
        self._generate_status_event()
    
        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.        
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    
    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolStates.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Issue stop command and switch to command if successful.
        got_root_prompt = False
        for i in range(2):
            try:
                self._go_to_root_menu()
                got_root_prompt = True
                break
            except:
                pass
            
        if not got_root_prompt:                
            raise InstrumentTimeoutException()
        
        next_state = ProtocolStates.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

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
                        
        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolStates.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _generate_status_event(self):
        if not self._driver_event:
            # can't send events, so don't bother creating the particle
            return
        
        # update parameters so param_dict values used for status are latest and greatest.
        self._update_params()

        # build a dictionary of the parameters that are to be returned in the status data particle
        status_params = {}
        for name in XR_420StatusDataParticle.list():
            status_params[name] = self._param_dict.get(name)
            
        # Create status data particle, but pass in a reference to the dictionary just created as first parameter instead of the 'line'.
        # The status data particle class will use the 'raw_data' variable as a reference to a dictionary object to get
        # access to parameter values (see the Mavs4StatusDataParticle class).
        particle = XR_420StatusDataParticle(status_params, preferred_timestamp=DataParticleKey.DRIVER_TIMESTAMP)
        status = particle.generate()

        # send particle as an event
        self._driver_event(DriverAsyncEvent.SAMPLE, status)
    

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()
        
        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(InstrumentParameters.STATUS,
                             r'Logger status (.*)\r\n', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             visibility=ParameterDictVisibility.READ_ONLY,
                             submenu_read=InstrumentCmds.GET_STATUS)

        """
        self._param_dict.add(InstrumentParameters.IDENTIFICATION,
                             r'(.*)\n', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             visibility=ParameterDictVisibility.READ_ONLY,
                             submenu_read=InstrumentCmds.GET_IDENTIFICATION)

        self._param_dict.add(InstrumentParameters.SYS_CLOCK,
                             r'(.*)CTD\n', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             submenu_read=InstrumentCmds.GET_LOGGER_DATE_AND_TIME,
                             submenu_write=InstrumentCmds.SET_LOGGER_DATE_AND_TIME)
        """

    def _build_command_handlers(self):
        
        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.GET_STATUS, self._build_keypress_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.GET_STATUS, self._parse_status_response)
   

    def _parse_status_response(self, response, prompt):
        log.debug("_parse_status_response: response=%s" %response.rstrip())
        if InstrumentResponses.STATUS in response:
            # got status response, so save it
            self._param_dict.update(response)
        else:
            raise InstrumentParameterException('Status response not correct: %s.' %response)
            

    
    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolStates.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        for key in InstrumentParameters.list():
            if key == InstrumentParameters.ALL:
                # this is not the name of any parameter
                continue
            command = self._param_dict.get_submenu_read(key)
            self._do_cmd_resp(command)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            log.debug("_update_params: new_config = %s" %new_config)
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            