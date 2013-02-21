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
    IDENTIFICATION          = 'RBR XR-420'
        
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
    IDENTIFICATION       = 'identification'
    SYS_CLOCK            = 'sys_clock'
    LOGGER_DATE_AND_TIME = 'logger_date_and_time'
    SAMPLE_INTERVAL      = 'sample_interval'
    START_DATE_AND_TIME  = 'start_date_and_time'
    END_DATE_AND_TIME    = 'end_date_and_time'
    STATUS               = 'status'
    BATTERY_VOLTAGE      = 'battery_voltage'
    
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
    BATTERY_VOLTAGE  = InstrumentParameters.BATTERY_VOLTAGE
                
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
        
        CommandResponseInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)
                
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
        Discover current state; can be COMMAND or AUTOSAMPLE.  If the instrument is sleeping
        consider that to be in command state.
        @retval (next_state, result), (ProtocolStates.COMMAND or ProtocolStates.AUTOSAMPLE, None) if successful.
        """
        next_state = None
        result = None
        
        # try to get root menu prompt from the device using timeout if passed.
        # NOTE: this driver always tries to put instrument into command mode so that parameters can be initialized
        try:
            prompt = self._go_to_root_menu()
        except InstrumentTimeoutException:
            # didn't get root menu prompt, so indicate that there is trouble with the instrument
            raise InstrumentStateException('Unknown state.')
        else:
            # got root menu prompt, so device is in command mode           
            next_state = ProtocolStates.COMMAND
            result = ResourceAgentState.IDLE
            
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
        for name in Mavs4StatusDataParticleKey.list():
            status_params[name] = self._param_dict.get(name)
            
        # Create status data particle, but pass in a reference to the dictionary just created as first parameter instead of the 'line'.
        # The status data particle class will use the 'raw_data' variable as a reference to a dictionary object to get
        # access to parameter values (see the Mavs4StatusDataParticle class).
        particle = Mavs4StatusDataParticle(status_params, preferred_timestamp=DataParticleKey.DRIVER_TIMESTAMP)
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
        self._param_dict.add(InstrumentParameters.SYS_CLOCK,
                             r'.*\[(.*)\].*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             menu_path_read=SubMenues.ROOT,
                             submenu_read=InstrumentCmds.SET_TIME,
                             menu_path_write=SubMenues.SET_TIME,
                             submenu_write=InstrumentCmds.ENTER_TIME)

        self._param_dict.add(InstrumentParameters.NOTE1,
                             r'.*Notes 1\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.NOTE2,
                             r'.*2\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.NOTE3,
                             r'.*3\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.VELOCITY_FRAME,
                             r'.*Data  F\| Velocity Frame (.*?) TTag FSec Axes.*', 
                             lambda match : self._parse_velocity_frame(match.group(1)),
                             lambda string : str(string),
                             startup_param=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             default_value='3',
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_VELOCITY_FRAME)

        self._param_dict.add(InstrumentParameters.MONITOR,
                             r'.*M\| Monitor\s+(\w+).*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             value='',
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_MONITOR)

        self._param_dict.add(InstrumentParameters.LOG_DISPLAY_TIME,
                             r'.*M\| Monitor\s+\w+\s+(\w+).*', 
                             lambda match : self._parse_on_off(match.group(1)),
                             lambda string : str(string),
                             value='')

        self._param_dict.add(InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND,
                             r'.*M\| Monitor\s+\w+\s+\w+\s+(\w+).*', 
                             lambda match : self._parse_on_off(match.group(1)),
                             lambda string : str(string),
                             value='')

        self._param_dict.add(InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES,
                             r'.*M\| Monitor\s+\w+\s+\w+\s+\w+\s+(\w+).*', 
                             lambda match : self._parse_on_off(match.group(1)),
                             lambda string : str(string),
                             value='')

        self._param_dict.add(InstrumentParameters.QUERY_MODE,
                             r'.*Q\| Query Mode\s+(\w+).*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             value='',
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_QUERY)

        self._param_dict.add(InstrumentParameters.FREQUENCY,
                             r'.*4\| Measurement Frequency\s+(\d+.\d+)\s+\[Hz\].*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             default_value=1.0,
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_FREQUENCY)

        self._param_dict.add(InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                             r'.*5\| Measurements/Sample\s+(\d+)\s+\[M/S\].*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=1,
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_MEAS_PER_SAMPLE)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD,
                             r'.*6\| Sample Period\s+(\d+.\d+)\s+\[sec\].*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_SAMPLE_PERIOD)

        self._param_dict.add(InstrumentParameters.SAMPLES_PER_BURST,
                             r'.*7\| Samples/Burst\s+(\d+)\s+\[S/B\].*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_SAMPLES_PER_BURST)

        self._param_dict.add(InstrumentParameters.BURST_INTERVAL_DAYS,
                             r'.*8\| Burst Interval\s+(\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=0,
                             menu_path_read=SubMenues.DEPLOY,
                             submenu_read=None,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_BURST_INTERVAL_DAYS)

        self._param_dict.add(InstrumentParameters.BURST_INTERVAL_HOURS,
                             r'.*8\| Burst Interval\s+\d+\s+(\d+):.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=0)

        self._param_dict.add(InstrumentParameters.BURST_INTERVAL_MINUTES,
                             r'.*8\| Burst Interval\s+\d+\s+\d+:(\d+):.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=0)

        self._param_dict.add(InstrumentParameters.BURST_INTERVAL_SECONDS,
                             r'.*8\| Burst Interval\s+\d+\s+\d+:\d+:(\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=0)

        self._param_dict.add(InstrumentParameters.SI_CONVERSION,
                             r'.*<C> Binary to SI Conversion\s+(\d+.\d+)\s+.*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_SI_CONVERSION)

        self._param_dict.add(InstrumentParameters.WARM_UP_INTERVAL,
                             r'.*<W> Warm up interval\s+(\w+)\s+.*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             default_value='fast',
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_WARM_UP_INTERVAL)

        self._param_dict.add(InstrumentParameters.THREE_AXIS_COMPASS,
                             r'.*<1> 3-Axis Compass\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='y',
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_THREE_AXIS_COMPASS)

        self._param_dict.add(InstrumentParameters.SOLID_STATE_TILT,
                             r'.*<2> Solid State Tilt\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='y',
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_SOLID_STATE_TILT)

        self._param_dict.add(InstrumentParameters.THERMISTOR,
                             r'.*<3> Thermistor\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='y',
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_THERMISTOR)

        self._param_dict.add(InstrumentParameters.PRESSURE,
                             r'.*<4> Pressure\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='n',            # this parameter can only be set to 'n' (meaning disabled)
                                                           # support for setting it to 'y' has not been implemented
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_PRESSURE)

        self._param_dict.add(InstrumentParameters.AUXILIARY_1,
                             r'.*<5> Auxiliary 1\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='n',            # this parameter can only be set to 'n' (meaning disabled)
                                                           # support for setting it to 'y' has not been implemented
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_AUXILIARY)

        self._param_dict.add(InstrumentParameters.AUXILIARY_2,
                             r'.*<6> Auxiliary 2\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='n',            # this parameter can only be set to 'n' (meaning disabled)
                                                           # support for setting it to 'y' has not been implemented
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_AUXILIARY)

        self._param_dict.add(InstrumentParameters.AUXILIARY_3,
                             r'.*<7> Auxiliary 3\s+(\w+)\s+.*', 
                             lambda match : self._parse_enable_disable(match.group(1)),
                             lambda string : str(string),
                             default_value='n',            # this parameter can only be set to 'n' (meaning disabled)
                                                           # support for setting it to 'y' has not been implemented
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_AUXILIARY)

        self._param_dict.add(InstrumentParameters.SENSOR_ORIENTATION,
                             r'.*<O> Sensor Orientation\s+(.*)\n.*', 
                             lambda match : self._parse_sensor_orientation(match.group(1)),
                             lambda string : str(string),
                             default_value='2',
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=SubMenues.CONFIGURATION,
                             submenu_write=InstrumentCmds.SET_SENSOR_ORIENTATION)

        self._param_dict.add(InstrumentParameters.SERIAL_NUMBER,
                             r'.*<S> Serial Number\s+(\w+)\s+.*', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CONFIGURATION,
                             submenu_read=None,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.VELOCITY_OFFSET_PATH_A,
                             r'.*Current path offsets:\s+(\w+)\s+.*', 
                             lambda match : int(match.group(1), 16),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.VELOCITY_OFFSET_PATH_B,
                             r'.*Current path offsets:\s+\w+\s+(\w+)\s+.*', 
                             lambda match : int(match.group(1), 16),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.VELOCITY_OFFSET_PATH_C,
                             r'.*Current path offsets:\s+\w+\s+\w+\s+(\w+)\s+.*', 
                             lambda match : int(match.group(1), 16),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.VELOCITY_OFFSET_PATH_D,
                             r'.*Current path offsets:\s+\w+\s+\w+\s+\w+\s+(\w+)\s+.*', 
                             lambda match : int(match.group(1), 16),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_OFFSET_0,
                             r'.*Current compass offsets:\s+([-+]?\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_OFFSET_1,
                             r'.*Current compass offsets:\s+[-+]?\d+\s+([-+]?\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_OFFSET_2,
                             r'.*Current compass offsets:\s+[-+]?\d+\s+[-+]?\d+\s+([-+]?\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_SCALE_FACTORS_0,
                             r'.*Current compass scale factors:\s+(\d+.\d+)\s+.*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_SCALE_FACTORS_1,
                             r'.*Current compass scale factors:\s+\d+.\d+\s+(\d+.\d+)\s+.*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.COMPASS_SCALE_FACTORS_2,
                             r'.*Current compass scale factors:\s+\d+.\d+\s+\d+.\d+\s+(\d+.\d+)\s+.*', 
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.TILT_PITCH_OFFSET,
                             r'.*Current tilt offsets:\s+(\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             value=-1,     # to indicate that the parameter has not been read from the instrument
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.TILT_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

        self._param_dict.add(InstrumentParameters.TILT_ROLL_OFFSET,
                             r'.*Current tilt offsets:\s+\d+\s+(\d+)\s+.*', 
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             value=-1,     # to indicate that the parameter has not been read from the instrument
                             visibility=ParameterDictVisibility.READ_ONLY,
                             menu_path_read=SubMenues.CALIBRATION,
                             submenu_read=InstrumentCmds.TILT_OFFSETS,
                             menu_path_write=None,
                             submenu_write=None)

    def _build_command_handlers(self):
        # these build handlers will be called by the base class during the navigate_and_execute sequence.        
        self._add_build_handler(InstrumentCmds.TILT_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TILT_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_SCALE_FACTORS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_SCALE_FACTORS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.VELOCITY_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.VELOCITY_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SENSOR_ORIENTATION, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SENSOR_ORIENTATION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_AUXILIARY, self._build_enter_auxiliary_command)
        self._add_build_handler(InstrumentCmds.SET_AUXILIARY, self._build_set_auxiliary_command)
        self._add_build_handler(InstrumentCmds.ENTER_PRESSURE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_PRESSURE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ANSWER_THERMISTOR_NO, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_THERMISTOR, self._build_enter_thermistor_command)
        self._add_build_handler(InstrumentCmds.SET_THERMISTOR, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ANSWER_SOLID_STATE_TILT_YES, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SOLID_STATE_TILT, self._build_enter_solid_state_tilt_command)
        self._add_build_handler(InstrumentCmds.SET_SOLID_STATE_TILT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_THREE_AXIS_COMPASS, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_THREE_AXIS_COMPASS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_WARM_UP_INTERVAL, self._build_enter_warm_up_interval_command)
        self._add_build_handler(InstrumentCmds.SET_WARM_UP_INTERVAL, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SI_CONVERSION, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SI_CONVERSION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_SECONDS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_MINUTES, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_HOURS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_DAYS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.SET_BURST_INTERVAL_DAYS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SAMPLES_PER_BURST, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SAMPLES_PER_BURST, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SAMPLE_PERIOD, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SAMPLE_PERIOD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_MEAS_PER_SAMPLE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_MEAS_PER_SAMPLE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_FREQUENCY, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_FREQUENCY, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_QUERY, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_QUERY, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_ACOUSTIC_AXIS_VELOCITY_FORMAT, self._build_enter_log_display_acoustic_axis_velocity_format_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES, self._build_enter_log_display_acoustic_axis_velocities_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_FRACTIONAL_SECOND, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_TIME, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_MONITOR, self._build_enter_monitor_command)
        self._add_build_handler(InstrumentCmds.SET_MONITOR, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_VELOCITY_FRAME, self._build_enter_velocity_frame_command)
        self._add_build_handler(InstrumentCmds.SET_VELOCITY_FRAME, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_NOTE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_NOTE, self._build_set_note_command)
        self._add_build_handler(InstrumentCmds.ENTER_TIME, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_TIME, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_PASSWORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_EXIT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CALIBRATION_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_GO, self._build_simple_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SET_TIME, self._parse_time_response)
        self._add_response_handler(InstrumentCmds.DEPLOY_MENU, self._parse_deploy_menu_response)
        self._add_response_handler(InstrumentCmds.SYSTEM_CONFIGURATION_PASSWORD, self._parse_system_configuration_menu_response)
        self._add_response_handler(InstrumentCmds.VELOCITY_OFFSETS_SET, self._parse_velocity_offset_set_response)
        self._add_response_handler(InstrumentCmds.COMPASS_OFFSETS_SET, self._parse_compass_offset_set_response)
        self._add_response_handler(InstrumentCmds.COMPASS_SCALE_FACTORS_SET, self._parse_compass_scale_factors_set_response)
        self._add_response_handler(InstrumentCmds.TILT_OFFSETS_SET, self._parse_tilt_offset_set_response)
   
    def _parse_time_response(self, response, prompt, **kwargs):
        """
        Parse handler for time command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.GET_TIME in response:
            raise InstrumentProtocolException('get time command not recognized by instrument: %s.' % response)
        
        log.debug("_parse_time_response: response=%s" %response)

        if not self._param_dict.update(InstrumentParameters.SYS_CLOCK, response.splitlines()[-1]):
            log.debug('_parse_time_response: Failed to parse %s' %InstrumentParameters.SYS_CLOCK)
        return None
              
    def _parse_deploy_menu_response(self, response, prompt, **kwargs):
        """
        Parse handler for deploy menu command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.DEPLOY_MENU in response:
            raise InstrumentProtocolException('deploy menu command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in DeployMenuParameters.list():
            #log.debug('_parse_deploy_menu_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_deploy_menu_response: Failed to parse %s' %parameter)
        return None
              
    def _parse_system_configuration_menu_response(self, response, prompt, **kwargs):
        """
        Parse handler for system configuration menu command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.SYSTEM_CONFIGURATION_MENU in response:
            raise InstrumentProtocolException('system configuration menu command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in SystemConfigurationMenuParameters.list():
            #log.debug('_parse_system_configuration_menu_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_system_configuration_menu_response: Failed to parse %s' %parameter)
        return None
              
    def _parse_velocity_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for velocity offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.VELOCITY_OFFSETS_SET in response:
            raise InstrumentProtocolException('velocity offset set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in VelocityOffsetParameters.list():
            #log.debug('_parse_velocity_offset_set_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_velocity_offset_set_response: Failed to parse %s' %parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_compass_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for compass offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.COMPASS_OFFSETS_SET in response:
            raise InstrumentProtocolException('compass offset set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in CompassOffsetParameters.list():
            #log.debug('_parse_compass_offset_set_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_compass_offset_set_response: Failed to parse %s' %parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_compass_scale_factors_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for compass scale factors set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.COMPASS_SCALE_FACTORS_SET in response:
            raise InstrumentProtocolException('compass scale factors set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in CompassScaleFactorsParameters.list():
            #log.debug('_parse_compass_scale_factors_set_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_compass_scale_factors_set_response: Failed to parse %s' %parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_tilt_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for tilt offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.TILT_OFFSETS_SET in response:
            raise InstrumentProtocolException('tilt offset set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in TiltOffsetParameters.list():
            #log.debug('_parse_tilt_offset_set_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_tilt_offset_set_response: Failed to parse %s' %parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def  _get_prompt(self, timeout=8, delay=4):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  There is no 
        'wakeup' for this instrument when it is in 'deployed' mode,
        so the best that can be done is to see if it responds or not.
        
        Clear buffers and send some CRs to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Grab time for timeout.
        starttime = time.time()
        
        # get longest prompt to match by sorting the prompts longest to shortest
        prompts = self._sorted_longest_to_shortest(self._prompts.list())
        log.debug("prompts=%s" %prompts)
        
        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''
        
            # Send a line return and wait a 4 sec.
            log.debug('Sending newline to get a response from the instrument.')
            self._connection.send(INSTRUMENT_NEWLINE)
            time.sleep(delay)
            
            for item in prompts:
                if item in self._promptbuf:
                    log.debug('_get_prompt got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

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
        
        deploy_menu_prameters_parsed = False
        system_configuration_menu_prameters_parsed = False
        velocity_offset_set_prameters_parsed = False
        compass_offset_set_prameters_parsed = False
        compass_scale_factors_set_prameters_parsed = False
        tilt_offset_set_prameters_parsed = False
        
        # sort the list so that the solid_state_tilt parameter will be updated and accurate before the tilt_offset
        # parameters are updated, so that the check of the solid_state_tilt param value reflects what's on the instrument
        for key in sorted(InstrumentParameters.list()):
            if key == InstrumentParameters.ALL:
                # this is not the name of any parameter
                continue
            dest_submenu = self._param_dict.get_menu_path_read(key)
            command = self._param_dict.get_submenu_read(key)

            if key in DeployMenuParameters.list():
                # only screen scrape the deploy menu once for efficiency
                if deploy_menu_prameters_parsed == True:
                    continue
                else:
                    deploy_menu_prameters_parsed = True
                    # set name to ALL so _parse_deploy_menu_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in SystemConfigurationMenuParameters.list():
                # only screen scrape the system configuration menu once for efficiency
                if system_configuration_menu_prameters_parsed == True:
                    continue
                else:
                    system_configuration_menu_prameters_parsed = True
                    # set name to ALL so _parse_system_configuration_menu_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in VelocityOffsetParameters.list():
                # only screen scrape the velocity offset set response once for efficiency
                if velocity_offset_set_prameters_parsed == True:
                    continue
                else:
                    velocity_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_velocity_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in CompassOffsetParameters.list():
                # only screen scrape the compass offset set response once for efficiency
                if compass_offset_set_prameters_parsed == True:
                    continue
                else:
                    compass_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_compass_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            elif key in CompassScaleFactorsParameters.list():
                # only screen scrape the compass scale factors set response once for efficiency
                if compass_scale_factors_set_prameters_parsed == True:
                    continue
                else:
                    compass_scale_factors_set_prameters_parsed = True
                    # set name to ALL so _parse_compass_scale_factors_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            elif key in TiltOffsetParameters.list():
                # only screen scrape the tilt offset set response once for efficiency
                if tilt_offset_set_prameters_parsed == True:
                    continue
                elif self._param_dict.get(InstrumentParameters.SOLID_STATE_TILT) == 'n':
                    # don't get the tilt offset parameters if the solid state tilt is disabled
                    self._param_dict.set(InstrumentParameters.TILT_PITCH_OFFSET, -1)
                    self._param_dict.set(InstrumentParameters.TILT_ROLL_OFFSET, -1)
                    tilt_offset_set_prameters_parsed = True               
                    continue
                else:
                    tilt_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_tilt_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            self._navigate_and_execute(command, name=key, dest_submenu=dest_submenu, timeout=10)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            
    def _sorted_longest_to_shortest(self, list):
        sorted_list = sorted(list, key=len, reverse=True)
        #log.debug("list=%s \nsorted=%s" %(list, sorted_list))
        return sorted_list
