#!/usr/bin/env python

"""
@package mi.instrument.satlantic.isusv3.ooicore.driver
@file /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/satlantic/isusv3/ooicore/driver.py
@author Steve Foley
@brief Driver for the ooicore

Development notes/todo list:
* Menu handlers need to find the operating mode they will be returning to
when bumping off the end of the root menu and starting operations again.

Release notes:

Satlantic MBARI-ISUSv3 Nutrient sampler
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'


import logging
import time
import re
import datetime

from mi.core.common import BaseEnum

from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
#from mi.core.instrument.instrument_driver import InstrumentDriver
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentStateException
#from mi.instrument_connection import SerialInstrumentConnection
#from mi.instrument_driver import InstrumentDriver
#from mi.instrument_driver import DriverChannel
#from mi.exceptions import InstrumentConnectionException
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

from mi.core.log import get_logger
log = get_logger()

###
#   Module wide values
###
INSTRUMENT_NEWLINE = '\r\n'
WRITE_DELAY = 0
RESET_DELAY = 25
#EOLN = "\r\n"
EOLN = "\n"

# Packet config for ISUSV3 data granules.
STREAM_NAME_PARSED = 'parsed'
STREAM_NAME_RAW = 'raw'
PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]

# @todo May need some regex(s) for data format returned...at least to confirm
# that it is data.

###
#   Static Enumerations
###
class State(BaseEnum):
    """
    Enumerated driver states.  Your driver will likly only support a subset of these.
    """
    #UNCONFIGURED_MODE = DriverProtocolState.UNKNOWN
    UNKNOWN = DriverProtocolState.UNKNOWN
    #BENCHTOP_MODE = "ISUS_STATE_BENCHTOP"
    POLL =  DriverProtocolState.POLL
    #TRIGGERED_MODE =  DriverProtocolState.POLL
    CONTINUOUS_MODE =  "ISUS_STATE_CONTINUOUS"
    AUTOSAMPLE=  DriverProtocolState.AUTOSAMPLE
    #FIXEDTIME_MODE = "ISUS_STATE_FIXEDTIME"
    SCHEDULED_MODE = "ISUS_STATE_SCHEDULED"
    #MENU_MODE =  DriverProtocolState.COMMAND
    COMMAND =  DriverProtocolState.COMMAND
    FILE_UPLOADING = "ISUS_STATE_FILE_UPLOADING"
    ROOT_MENU = "ISUS_STATE_ROOT_MENU"
    CONFIG_MENU = "ISUS_STATE_CONFIG_MENU"
    SETUP_MENU = "ISUS_STATE_SETUP_MENU"
    OUTPUT_SETUP_MENU = "ISUS_STATE_OUTPUT_SETUP_MENU"
    DEPLOYMENT_SETUP_MENU = "ISUS_STATE_DEPLOYMENT_SETUP_MENU"
    SPECTROMETER_SETUP_MENU = "ISUS_STATE_SPECTROMETER_SETUP_MENU"
    LAMP_SETUP_MENU = "ISUS_STATE_LAMP_SETUP_MENU"
    FITTING_SETUP_MENU = "ISUS_STATE_FITTING_SETUP_MENU"
    FILE_MENU = "ISUS_STATE_FILE_MENU"
    INFO_MENU = "ISUS_STATE_INFO_MENU"
    
    #TEST =  DriverState.TEST
    #CALIBRATE =  DriverState.CALIBRATE

class Event(BaseEnum):
    """
    Enumerated driver events.  Your driver will likly only support a subset of these.
    """
    CONFIGURE = DriverEvent.CONFIGURE
    INITIALIZE = DriverEvent.INITIALIZE
    DISCOVER = DriverEvent.DISCOVER
    #PROMPTED = DriverEvent.PROMPTED
    #DATA_RECEIVED = DriverEvent.DATA_RECEIVED
    #COMMAND_RECEIVED = DriverEvent.COMMAND_RECEIVED
    #RESPONSE_TIMEOUT = DriverEvent.RESPONSE_TIMEOUT
    SET = DriverEvent.SET
    GET = DriverEvent.GET
    EXECUTE = DriverEvent.EXECUTE
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    FORCE_STATE = DriverEvent.FORCE_STATE
    #TEST = DriverEvent.TEST
    #STOP_TEST = DriverEvent.STOP_TEST
    #CALIBRATE = DriverEvent.CALIBRATE
    #RESET = DriverEvent.RESET
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    #UPDATE_PARAMS = DriverEvent.UPDATE_PARAMS
    
    """
    QUESTION FOR STEVE: What are these events doing here?  How would such an event
    get generated?  Should these be in class Event?
    """
    
    """
    DHE: this doesn't work; These commands collide (ex., several 'S' events/commands), and the 
    response handler is set up to use just the value.  Need a better way, like use a dict with
    a unique string as the key (for instance, "setup_menu_reponse", or "show_config_response" for
    two different keys for the that have the same command value.
    """

    # Menu and operation commands
    QUIT_CMD = 'Q'
    GO_CMD = 'G'
    STOP_CMD = 'S'
    MENU_CMD = 'M'
    ANY_KEY = 'Z'
    YES = 'Y'
    NO = 'N'
    ACCEPT = 0x0D

    # Main menu commands
    CONFIG_MENU = 'C'
    SETUP_MENU = 'S'
    FILE_MENU = 'F'
    INFO_MENU = 'I'
    UP_MENU_LEVEL = 'Q'
    OUTPUT_SETUP_MENU = 'O'
    DEPLOYMENT_SETUP_MENU = 'D'
    SPECTROMETER_SETUP_MENU = 'S'
    LAMP_SETUP_MENU = 'L'
    
    # Config menu parameters
    SHOW_CONFIG = 'S'
    BAUD_RATE = 'B'
    DEPLOYMENT_COUNTER = 'D'
    
    # Output setup menu
    STATUS_MESSAGES = 'S'
    LOGGING_FRAME_MODE = 'L'
    TRANSFER_FRAME_MODE = 'T'
    DAILY_LOG_TOGGLE = 'D'
    NITRATE_DAC_RANGE = 'N'
    AUX_DAC_RANGE = 'A'
    
    # Deployment setup menu
    OPERATIONAL_MODE = 'O'
    INITIAL_DELAY = 'D'
    FIXED_TIME_DURATION = 'F'
    START_COMMAND_TRIGGERED = 'T'
    STOP_COMMAND_TRIGGERED = 'S'
    
    # Spectrometer setup menu
    INTEGRATION_PERIOD = 'I'
    COLLECTION_RATE = 'C'
    LOAD_SPECTROMETER_COEFFICIENTS = 'L'
    
    # Lamp setup menu
    POWER_ON_WARM_UP_PERIOD = 'P'
    REFERENCE_DETECTOR = 'R'
    
    # Fitting setup menu
    FITTING_RANGE = 'F'
    BASELINE_ORDER = 'B'
    SEAWATER_DARK_SAMPLES = 'S'

    # File menu
    FILE_LIST_PROGRAM = "LP"
    FILE_LIST_COEFFICIENT = "LC"
    FILE_LIST_LOG = "LL"
    FILE_LIST_DATA = "LD"
    FILE_OUTPUT_EXTINCT = "OE"
    FILE_OUTPUT_WAVELENGTH = "OW"
    FILE_OUTPUT_SCHEDULE = "OS"
    FILE_OUTPUT_LOG = "OL"
    FILE_OUTPUT_DATA = "OD"
    FILE_UPLOAD_SCHEDULE = "US"
    FILE_UPLOAD_EXTINCT = "UE"
    FILE_UPLOAD_PROGRAM = "UP"
    FILE_ERASE_EXTINCT = "EE"
    FILE_ERASE_LOG = "EL"
    FILE_ERASE_DATA = "ED"
    FILE_ERASE_ALL_DATA = "EAD"

    # Info menu
    BUILD_INFO = 'B'
    DISK_INFO = 'D'
    CLOCK_INFO = 'C'
    PIXEL_TO_WAVELENGTH = 'P'
    FITTING_COEFFICIENTS = 'F'
    LAMP_ON_TIME = 'L'
    DAC_MENU = 'A'
    GENERATE_DUMP_FILE = 'G'
    
    REBOOT = "REBOOT"


#class Command(BaseEnum):
class Command(object):
    """
    DHE: Commenting these out for now..
    REBOOT = "REBOOT"
    GENERATE_DUMP_FILE = 'GENERATE_DUMP_FILE'
    FILE_LIST_PROGRAM = "LP"
    FILE_LIST_COEFFICIENT = "LC"
    FILE_LIST_LOG = "LL"
    FILE_LIST_DATA = "LD"
    FILE_OUTPUT_EXTINCT = "OE"
    FILE_OUTPUT_WAVELENGTH = "OW"
    FILE_OUTPUT_SCHEDULE = "OS"
    FILE_OUTPUT_LOG = "OL"
    FILE_OUTPUT_DATA = "OD"
    FILE_UPLOAD_SCHEDULE = "US"
    FILE_UPLOAD_EXTINCT = "UE"
    FILE_UPLOAD_PROGRAM = "UP"
    FILE_ERASE_EXTINCT = "EE"
    FILE_ERASE_LOG = "EL"
    FILE_ERASE_DATA = "ED"
    FILE_ERASE_ALL_DATA = "EAD"
    #SUBMIT_SCHEDULE = "SUBMIT_SCHEDULE"
    #SUBMIT_CALIBRATION = "SUBMIT_CALIBRATION"
    #GET_CALIBRATION = "GET_CALIBRATION"
    """

    # Main menu commands
    DEPLOYMENT_MODE_YES = ('deployment_mode_yes', 'Y')
    DEPLOYMENT_MODE_NO = ('deployment_mode_no', 'N')
    CONFIG_MENU_CMD = ('config_menu_cmd', 'C')
    SHOW_CONFIG_CMD = ('show_config_cmd', 'S')
    BAUD_RATE_CMD = ('baud_rate_cmd', 'B')
    SETUP_MENU_CMD = ('setup_menu_cmd', 'S')
    DEPLOYMENT_COUNTER_CMD = ('deployment_counter_cmd', 'D')
    DEPLOYMENT_MODE_CMD = ('deployment_mode_cmd', 'D')
    OPERATIONAL_MODE_CMD = ('operational_mode_cmd', 'O')


    #FILE_MENU_CMD = 'F'
    #INFO_MENU_CMD = 'I'
    #UP_MENU_LEVEL_CMD = 'Q'
    #OUTPUT_SETUP_MENU_CMD = 'O'
    #DEPLOYMENT_SETUP_MENU_CMD = 'D'
    #SPECTROMETER_SETUP_MENU_CMD = 'S'
    #LAMP_SETUP_MENU_CMD = 'L'
    
    
class Prompt(BaseEnum):
    ROOT_MENU = "ISUS> [H] ?"
    CONFIG_MENU_1 = "ISUS Configuration Menu (<H> for Help)"
    #CONFIG_MENU = "ISUS_CONFIG> [H] ?"
    # DHE This is bogus; seems to timeout looking for this sometimes.
    CONFIG_MENU = "ISUS_CONFIG>"
    SETUP_MENU = "ISUS_SETUP> [H]"
    SETUP_OUTPUT_MENU = "ISUS_SETUP_OUTPUT> [H] ?"
    SETUP_DEPLOY_MENU = "ISUS_SETUP_DEPLOY"
    SETUP_FIT_MENU = "ISUS_SETUP_FIT> [H] ?"
    SETUP_SPEC_MENU = "ISUS_SETUP_SPEC> [H] ?"
    SETUP_LAMP_MENU = "ISUS_SETUP_LAMP> [H] ?"
    FILE_MENU = "ISUS_FILE> [H] ?"
    INFO_MENU = "ISUS_INFO> [H] ?"
    #SAVE_SETTINGS = "Save current settings? (Otherwise changes are lost at next power-down) [Y] ?"
    SAVE_SETTINGS = "Save current settings? (Otherwise changes are lost at next power-down)"
    #REPLACE_SETTINGS = "Replace existing setting by current? [N] ?"
    REPLACE_SETTINGS = "Replace existing setting by current?"
    MODIFY = "Modify?  [N]" 
    ENTER_CHOICE = "Enter number to assign new value"
    ENTER_DEPLOYMENT_COUNTER = "Enter deployment counter. ?"

class Parameter(DriverParameter):
    """ The parameters that drive/control the operation and behavior of the device """
    BAUDRATE = "BAUDRATE"
    DEPLOYMENT_COUNTER = "DEPLOYMENT_COUNTER"
    STATUS_MESSAGES = "STATUS_MESSAGES"
    LOGGING_FRAME_MODE = "LOGGING_FRAME_MODE"
    TRANSFER_FRAME_MODE = "TRANSFER_FRAME_MODE"
    DAILY_LOG_TOGGLE = "DAILY_LOG_TOGGLE"
    NITRATE_DAC_RANGE_MIN = "NITRATE_DAC_RANGE_MIN"
    NITRATE_DAC_RANGE_MAX = "NITRATE_DAC_RANGE_MAX"
    AUX_DAC_RANGE_MIN = "AUX_DAC_RANGE_MIN"
    AUX_DAC_RANGE_MAX = "AUX_DAC_RANGE_MAX"
    DEPLOYMENT_MODE = "DEPLOYMENT_MODE"
    INITIAL_DELAY = "INITIAL_DELAY"
    FIXED_OP_TIME = "FIXED_OP_TIME"
    COLLECTION_RATE = "COLLECTION_RATE"
    BUILD_INFO = "BUILD_INFO"
    DISK_INFO = "DISK_INFO"
    CLOCK_INFO = "CLOCK_INFO"
    PIXEL = "PIXEL"
    DAC_MENU = "DAC_MENU"

    # Read-only
    SPEC_COEFF = "SPEC_COEFF" # R/O
    
    # Direct access only
    INTEGRATION_PERIOD = "INTEGRATION_PERIOD" # Direct Access
    WARM_UP_PERIOD = "WARM_UP_PERIOD" # DA
    REFERENCE_DIODE = "REFERENCE_DIODE" # DA
    FITTING_RANGE = "FITTING_RANGE" # DA
    BASELINE_ORDER = "BASELINE_ORDER" # DA
    SEAWATER_DARK_SAMPLES = "SEAWATER_DARK_SAMPLES" # DA
    
class Status(BaseEnum):
    """ Values that are real-time/transient/in-flux, read-only """
    TRANSFER_FRAME_MODE = "TRANSFER_FRAME_MODE"
    LAMP_ON_TIME = "LAMP_ON_TIME"
    
class MetadataParameter(BaseEnum):
    pass

class Error(BaseEnum):
    pass

class Status(BaseEnum):
    pass

class ooicoreParameter():
    """
    """
class SubMenues(BaseEnum):
    CONFIG_MENU = 'config_menu'
    SHOW_CONFIG_MENU = 'show_config_menu'
    SETUP_MENU = 'setup_menu'
    DEPLOYMENT_COUNTER_MENU = 'deployment_counter_menu'
    DEPLOYMENT_MODE_MENU = 'deployment_mode_menu'
    OPERATIONAL_MODE_MENU = 'operational_mode_menu'
    OPERATIONAL_MODE_SET= 'operational_mode_set'

class InstrumentPrompts(BaseEnum):
    MAIN_MENU = "ISUS> [H] ?"

###
#   Protocol for ooicore
###
class ooicoreInstrumentProtocol(MenuInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        directions = self.MenuTree.Directions

        # DHE NEW METHOD
        # It seems to me that the "command" or "intent" object should contain everything necessary for its
        # execution.  For now, the is no command object.  It was just a string (character).  
        # 
        menu = self.MenuTree({
            SubMenues.CONFIG_MENU: [directions(Command.CONFIG_MENU_CMD, Prompt.CONFIG_MENU)],
            SubMenues.SETUP_MENU: [directions(Command.SETUP_MENU_CMD, Prompt.SETUP_MENU)],
            SubMenues.SHOW_CONFIG_MENU: [directions(SubMenues.CONFIG_MENU)],
            SubMenues.DEPLOYMENT_COUNTER_MENU: [directions(SubMenues.CONFIG_MENU),
                                                directions(Command.DEPLOYMENT_COUNTER_CMD, Prompt.ENTER_DEPLOYMENT_COUNTER)],
            SubMenues.DEPLOYMENT_MODE_MENU: [directions(SubMenues.SETUP_MENU),
                                             directions(Command.DEPLOYMENT_MODE_CMD, Prompt.SETUP_DEPLOY_MENU)],
            SubMenues.OPERATIONAL_MODE_MENU: [directions(SubMenues.DEPLOYMENT_MODE_MENU),
                                             directions(Command.OPERATIONAL_MODE_CMD, Prompt.MODIFY)],
            SubMenues.OPERATIONAL_MODE_SET: [directions(SubMenues.OPERATIONAL_MODE_MENU),
                                             directions(Command.DEPLOYMENT_MODE_YES, Prompt.ENTER_CHOICE)]
        })

        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event) 
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = EOLN
        
        ##### Setup the state machine
        self._protocol_fsm = InstrumentFSM(State, Event, Event.ENTER, Event.EXIT)
        
        self._protocol_fsm.add_handler(State.UNKNOWN, Event.INITIALIZE,
                              self._handler_initialize) 
        self._protocol_fsm.add_handler(State.UNKNOWN, Event.DISCOVER,
                              self._handler_unknown_discover) 
        self._protocol_fsm.add_handler(State.UNKNOWN, Event.FORCE_STATE,
                              self._handler_unknown_force_state) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.MENU_CMD,
                              self._handler_continuous_menu) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.GO_CMD,
                              self._handler_continuous_go)
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.STOP_CMD,
                              self._handler_continuous_stop) 
        
        # ... and so on with the operation handler listings...
        # In general, naming is _handler_currentstate_eventreceived

        self._protocol_fsm.add_handler(State.COMMAND, Event.ENTER,
                              self._handler_root_menu_enter) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.CONFIG_MENU,
                              self._handler_root_config) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.SETUP_MENU,
                              self._handler_root_setup) 
        self._protocol_fsm.add_handler(State.COMMAND, Event.FILE_MENU,
                              self._handler_root_file) 
        #
        # DHE added
        #
        self._protocol_fsm.add_handler(State.COMMAND, Event.GET,
                              self._handler_command_get) 
        
        self._protocol_fsm.add_handler(State.COMMAND, Event.SET,
                              self._handler_command_set) 

        # Not handled right now; there is no single acquire sample for the ISUS
        # in "command mode."  It could be simulated by going into triggered mode
        # and starting and stopping, but the state machine needs triggered mode
        # which it doesn't have right now.
        #self._protocol_fsm.add_handler(State.COMMAND, Event.ACQUIRE_SAMPLE,
        #                      self._handler_command_acquire_sample) 
        
        self._protocol_fsm.add_handler(State.COMMAND, Event.START_AUTOSAMPLE,
                              self._handler_command_start_autosample) 
        
        # @todo ... and so on with the menu handler listings...
        # these build handlers will be called by the base class during the
        # navigate_and_execute sequence.        
        #self._add_build_handler(Event.CONFIG_MENU, self._build_simple_command)
        #self._add_build_handler(Event.SHOW_CONFIG, self._build_simple_command)
        #self._add_build_handler(Event.BAUD_RATE, self._build_simple_command)
        #self._add_build_handler(Event.DEPLOYMENT_COUNTER, self._build_simple_command)

        self._add_build_handler(Command.CONFIG_MENU_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.SHOW_CONFIG_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.BAUD_RATE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_COUNTER_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.SETUP_MENU_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.OPERATIONAL_MODE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_CMD[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_YES[0], self._build_simple_command)
        self._add_build_handler(Command.DEPLOYMENT_MODE_NO[0], self._build_simple_command)

        # Add response handlers for parsing command responses
        self._add_response_handler(Command.SHOW_CONFIG_CMD[0], self._parse_show_config_menu_response)
        #self._add_response_handler(Command.DEPLOYMENT_MODE_NO[0], self._parse_deployment_mode_response)
        #self._add_response_handler(Command.DEPLOYMENT_MODE_CMD[0], self._parse_deployment_mode_response)
        self._add_response_handler(Command.OPERATIONAL_MODE_CMD[0], self._parse_deployment_mode_response)
        
        # Add sample handlers.
        self._sample_pattern = r'^SAT(.{3}).{4},(.{4,7}),(.{,9})'
        #self._sample_pattern += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
        #self._sample_pattern += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'
        #self._sample_pattern += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'        
        self._sample_regex = re.compile(self._sample_pattern)


        # Construct the parameter dictionary
        self._build_param_dict()

        # State state machine in UNCONFIGURED state.
        #self._protocol_fsm.start(State.UNCONFIGURED_MODE)
        self._protocol_fsm.start(State.UNKNOWN)

        """
        @todo ... and so on, continuing with these additional parameters (and any that
        may have been left out...drive the list by the actual interface...
        
        INITIAL_DELAY = "INITIAL_DELAY"
        FIXED_OP_TIME = "FIXED_OP_TIME"
        COLLECTION_RATE = "COLLECTION_RATE"
        BUILD_INFO = "BUILD_INFO"
        DISK_INFO = "DISK_INFO"
        CLOCK_INFO = "CLOCK_INFO"
        PIXEL = "PIXEL"
        DAC_MENU = "DAC_MENU"
    
        # Read-only, so tag the visibility with READ_ONLY
        SPEC_COEFF = "SPEC_COEFF" # R/O
        
        # Direct access only, so tag the visibility with DIRECT_ACCESS
        INTEGRATION_PERIOD = "INTEGRATION_PERIOD" # Direct Access
        WARM_UP_PERIOD = "WARM_UP_PERIOD" # DA
        REFERENCE_DIODE = "REFERENCE_DIODE" # DA
        FITTING_RANGE = "FITTING_RANGE" # DA
        BASELINE_ORDER = "BASELINE_ORDER" # DA
        SEAWATER_DARK_SAMPLES = "SEAWATER_DARK_SAMPLES" # DA
        """
        
    ##############################
    # execute_* interface routines
    ##############################
    
    # @todo Add execute_* routines to expose. Should line up with commands
    # plus GET, SET, SAMPLE, POLL, RESET, and others of that ilk
    
    ################
    # State handlers
    ################
    def _handler_initialize(self, *args, **kwargs):
        """Handle transition from UNCONFIGURED state to a known one.
        
        This method determines what state the device is in or gets it to a
        known state so that the instrument and protocol are in sync.
        @param params Parameters to pass to the state
        @retval return (next state, result)
        @todo fix this to only do break when connected
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    #
    # DHE ADDED
    #
    def _handler_unknown_discover(self, *args, **kwargs):
        """
        """
        next_state = None
        result = None

        try:
            self._go_to_root_menu()
        except InstrumentTimeoutException:
            raise InstrumentProtocolException('Instrument timed out going to root menu.')
        else:
            next_state = State.COMMAND
            result = State.COMMAND
        
        return (next_state, result)

    #
    # DHE ADDED
    #
    def _handler_unknown_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing 
        @param state=desired_state Required desired state to transition to.
        @raises InstrumentParameterException if no state parameter.
        """

        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        next_state = state
        result = state
        
        return (next_state, result)

    def _handler_continuous_menu(self, *args, **kwargs):
        """Handle a menu command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_continuous_go(self, *args, **kwargs):
        """Handle a go command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_continuous_stop(self, *args, **kwargs):
        """Handle a stop command event from continuous mode operations.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
        
    # @todo ...carry on with the rest of the operation handlers and what they actually do...
    # include handling of MODIFY prompts properly

    #
    # DHE Added
    #
    def _handler_command_get(self, *args, **kwargs):
        """Handle a config menu command event from root menu.
        
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
            # DHE TEMPTEMP
            print "-----> DHE: result for get DriverParameter.ALL is: " + str(result) 
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
        
    #
    # DHE Added
    #
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

        # DHE TEMP
        print '-----> DHE in _handler_command_set'

        next_state = None
        result = None

        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:

            # DHE TEMP
            print '-----> DHE in _handler_command_set: params are: ' + str(params)

            #
            # There is a problem with the current build_handler scheme; it's keyed by
            # the command.  I need to pass the "final command" parameter as a value,
            # and there is no build handler for all of the possible values.   
            #
            for (key, val) in params.iteritems():
                dest_submenu = self._param_dict.get_menu_path_write(key)
                command = self._param_dict.get_submenu_write(key)
                self._navigate_and_execute(None, value=val, dest_submenu=dest_submenu, timeout=5)
            self._update_params()

        return (next_state, result)

    #
    # DHE Added
    #
    def _handler_command_start_autosample(self, *args, **kwargs):
        """Handle a start autosample command event from root menu.
        
        """

        #
        # DHE: We need to either put the instrument into continuous mode or triggered mode.  If
        # triggered mode, then we need our own scheduler to cause the periodic sampling that would
        # be simulate autosample.
        #
        #self._navigate_and_execute(Command.DEPLOYMENT_MODE_YES, dest_submenu=SubMenues.OPERATIONAL_MODE_MENU, 
        #    expected_prompt=Prompt.SETUP_DEPLOY_MENU, 
        #    timeout=5)
        self._go_to_root_menu()
        self._navigate_and_execute(None, value = '0', dest_submenu=SubMenues.OPERATIONAL_MODE_SET, 
            expected_prompt=Prompt.SETUP_DEPLOY_MENU,
            timeout=5)
        self._go_to_root_menu()
        #
        # DHE: NEED TO REBOOT HERE IN ORDER FOR THE CHANGE TO TAKE EFFECT!!!!

        next_state = State.AUTOSAMPLE 
        result = State.AUTOSAMPLE 

        return (next_state, result)
        
    def _handler_root_menu_enter(self, *args, **kwargs):
        """Entry event for the command state
        """

        self._update_params()

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_root_config(self, *args, **kwargs):
        """Handle a config menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_root_setup(self, *args, **kwargs):
        """Handle a setup menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)
        
    def _handler_root_file(self, *args, **kwargs):
        """Handle a file menu command event from root menu.
        
        """
        next_state = None
        result = None
        
        # handler logic goes here
        
        return (next_state, result)

    # @todo ...carry on with the rest of the menu system handlers and what they actually do...
    # include handling of MODIFY prompts properly

    ##########
    # Builders
    ##########
    
    # Add additional routines here that build commands to be sent in case
    # _build_simple_command, _build_keypress_command, and
    # _build_multi_keypress_command are insufficient
    
    ##################################################################
    # Response parsers
    ##################################################################
    
    # Add in some parsing routines to handle various types of output such as
    # parameter get, parameter set, exec, into and out of op modes, menu changes?
        
    # DHE Added
    def _parse_show_config_menu_response(self, response, prompt):
        """
        Parse handler for config menu response.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if config_menu command misunderstood.
        """

        print "------------> DHE: in _parse_show_config_menu_response: prompt is: " + \
            prompt + ". Response is: " + response

        if prompt != Prompt.CONFIG_MENU:
            raise InstrumentProtocolException('_parse__config_menu: command not recognized: %s.' % response)

        for line in response.split(self.eoln):
            print "------> DHE: passing line <" + line + "> to _param_dict.update()"
            self._param_dict.update(line)

    # DHE Added
    def _parse_deployment_mode_response(self, response, prompt):
        """
        Parse handler for config menu response.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if config_menu command misunderstood.
        """

        print "------------> DHE: in _parse_deployment_mode_response: prompt is: " + \
            prompt + ". Response is: " + response

        #if prompt != Prompt.DEPLOYMENT_MODE:
        #    raise InstrumentProtocolException('_parse_deployment_mode_response: command not recognized: %s.' % response)

        for line in response.split(self.eoln):
            print "------> DHE: parse_deployment_mode passing line <" + line + "> to _param_dict.update()"
            self._param_dict.update(line)


    ######################
    # Translation routines
    ######################
    def _enable_disable_to_bool(self):
        """ Translate ENABLE or DISABLE into a True/False for param dict
        ...or maybe a string is more appropriate?"""
        pass

    def _frametype_to_int(self):
        """ Translate frame type (NONE, FULL_ASCII, FULL_BINARY, CONCENTRATION)
        to the integer that matches it when setting the value
        (0-3 respectively)
        ...or maybe a string is more appropriate?
        """
        pass
    
    def _opmode_to_string(self):
        """ Translate opmode (SCHEDULED, CONTINUOUS, FIXEDTIME, FIXEDTIMEISUS,
        BENCHTOP, TRIGGERED) to matching int (0-5 respectively)
        """
        pass
    
    def _logtoggle_to_int(self):
        """ Translate log message toggling (DAILY, EACHEVENT) to matching int
        (0-1 respectively)
        """
        pass
    
    # @todo ...carry on with the rest of the translation routines as needed
    
    #########
    # Helpers
    #########
    def _send_wakeup(self):
        """Send a wakeup to this instrument...one that wont hurt if it is awake
        already."""
        self._connection.send(self.eoln)

    def _update_params(self, *args, **kwargs):
        """Fetch the parameters from the device, and update the param dict.
        May be used when transitioning into or out of an operational mode?
        
        @param args Unused
        @param kwargs Takes timeout value
        @throws InstrumentProtocolException
        @throws InstrumentTimeoutException
        """
        log.debug("Updating parameter dict")

        old_config = self._param_dict.get_config()

        # Not sure what this was for. 
        #self.get_config()

        self._go_to_root_menu()
        #self._navigate_and_execute(Event.SHOW_CONFIG, dest_submenu=SubMenues.SHOW_CONFIG_MENU, timeout=5)
        self._navigate_and_execute(Command.SHOW_CONFIG_CMD, dest_submenu=SubMenues.SHOW_CONFIG_MENU, timeout=5)
        # DHE Trying to get DEPLOYMENT_MODE
        print "--->>> DHE Trying to get DEPLOYMENT_MODE"
        self._go_to_root_menu()
        self._navigate_and_execute(Command.DEPLOYMENT_MODE_NO, dest_submenu=SubMenues.OPERATIONAL_MODE_MENU, 
            expected_prompt=Prompt.SETUP_DEPLOY_MENU, 
            timeout=5)
        self._go_to_root_menu()

        new_config = self._param_dict.get_config()            
        if (new_config != old_config) and (None not in old_config.values()):
            print "--------> DHE: publishing CONFIG_CHANGE event"
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)            

    def  _wakeup(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        #
        # DHE: This doesn't seem very efficient...seems like there should be an expected response optional
        # kwarg so that we don't have to iterate through all the prompts in self._prompts
        #
        # Clear the prompt buffer.
        self._promptbuf = ''

        # Grab time for timeout.
        starttime = time.time()

        while True:
            # Send a line return and wait a sec.
            log.debug('Sending wakeup.')
            self._send_wakeup()
            time.sleep(delay)

            for item in self._prompts.list():
                if item in self._promptbuf:
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()


            
    #
    # DHE ADDED 
    #
    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """
        #if self.get_current_state() == State.DIRECT_ACCESS:
        #    # direct access mode
        #    if len(data) > 0:
        #        #mi_logger.debug("ooicoreInstrumentProtocol.got_data(): <" + data + ">")
        #        # check for echoed commands from instrument (TODO: this should only be done for telnet?)
        #        if len(self._sent_cmds) > 0:
        #            # there are sent commands that need to have there echoes filtered out
        #            oldest_sent_cmd = self._sent_cmds[0]
        #            if string.count(data, oldest_sent_cmd) > 0:
        #                # found a command echo, so remove it from data and delete the command form list
        #                data = string.replace(data, oldest_sent_cmd, "", 1)
        #                self._sent_cmds.pop(0)
        #        if len(data) > 0 and self._driver_event:
        #            self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)
        #            # TODO: what about logging this as an event?
        #    return

        if len(data) > 0:
            # Call the superclass to update line and prompt buffers.
            MenuInstrumentProtocol.got_data(self, data)

            # If in streaming mode, process the buffer for samples to publish.
            cur_state = self.get_current_state()
            if cur_state == State.AUTOSAMPLE:
                if INSTRUMENT_NEWLINE in self._linebuf:
                    lines = self._linebuf.splitlines(1)
                    """
                    Make the _linebuf variable equal to the last item in the 
                    list created by the above split.  It will either be a 
                    null string or the beginning of a new fragment, which we
                    want to save.
                    """
                    self._linebuf = lines[-1]
                    for line in lines:
                        """
                        The above split can leave a zero-length line in list,
                        so only call extract_sample if len greater than zero.
                        Also, we could have the beginning fragment of a sample,
                        which we don't want to parse yet, so only extract_sample
                        if the line ends lith the instrument terminator.
                        """
                        if len(line) > 0 and line.endswith(INSTRUMENT_NEWLINE):
                            self._extract_sample(line)


    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish "raw" and
        "parsed" sample events to agent.

        @param line string to match for sample.
        @param publish boolean to publish samples (default True). If True,
               two different events are published: one to notify raw data and
               the other to notify parsed data.

        @retval dict of dicts {'parsed': parsed_sample, 'raw': raw_sample} if
                the line can be parsed for a sample. Otherwise, None.
        """
        sample = None
        match = self._sample_regex.match(line)
        """
        DHE TEMPTEMPTEMP
        """
        if match:

            # Driver timestamp.
            ts = time.time()

            # prepate "raw" sample dict
            raw_sample = dict(
                stream_name=STREAM_NAME_RAW,
                time=[ts],
                blob=[line]
            )

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, raw_sample)

            """
            DHE: Need to know what the parsed will look like.  So for now, 
            the following are commented out.
            """
            
            # prepare "parsed" sample dict
            parsed_sample = dict(
                stream_name=STREAM_NAME_PARSED,
                time=[ts],
                inst_frame_type=(match.group(1)),
                inst_samp_date=(match.group(2)),
                inst_samp_time=(match.group(3)),
            )

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = dict(parsed=parsed_sample, raw=raw_sample)

        return sample


    #
    # DHE ADDED
    #
    def _go_to_root_menu(self):
        """
        Determine if we're at home (root-menu); if not, iterate sending 'Q' (quit) until we get there.
        """
        """
        Clear buffers and send a wakeup command to the instrument
        @throw InstrumentTimeoutException if the device does not get to root.
        """
        #
        # DHE: This doesn't seem very efficient...seems like there should be an expected response optional
        # kwarg so that we don't have to iterate through all the prompts in self._prompts
        #

        timeout = 10
        delay = 1
        prompt = self._wakeup(timeout)

        # Grab time for timeout.
        starttime = time.time()

        while Prompt.ROOT_MENU not in self._promptbuf:
            # Clear the prompt buffer.
            self._promptbuf = ''

            # Send a quit  
            print '====== DHE: Sending quit.'

            self._connection.send(Event.QUIT_CMD + self.eoln)
            time.sleep(delay)

            if time.time() > starttime + timeout:
                print '====== DHE: Dude we timed out.'
                raise InstrumentTimeoutException()

            if Prompt.SAVE_SETTINGS in self._promptbuf:
                print '====== DHE: Save settings yes.'
                self._connection.send(Event.YES + self.eoln)
                time.sleep(delay)

            if Prompt.REPLACE_SETTINGS in self._promptbuf:
                print '====== DHE: Replace settings yes.'
                self._connection.send(Event.YES + self.eoln)
                time.sleep(delay)


    def _build_param_dict(self):
        """
        Populate the paramenter dictionary with the ISUS parameters.
        For each parameter (the key), add match string, match lambda
        function, value formatting function, visibility (READ or READ_WRITE),
        and the path to the submenu from the root menu.
        """
 
        """
        DHE Trying this new model with menu_path and then final submenu for
        both read and write operations
        """
        self._param_dict.add(Parameter.BAUDRATE,
                             r'Baudrate:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_read=[Event.SHOW_CONFIG, Prompt.CONFIG_MENU],
                             menu_path_write=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_write=[Event.BAUD_RATE, Event.YES])

        self._param_dict.add(Parameter.DEPLOYMENT_COUNTER,
                             r'Deployment Cntr:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             submenu_read=[Event.SHOW_CONFIG, Prompt.CONFIG_MENU],
                             #menu_path_write=[[Event.CONFIG_MENU, Prompt.CONFIG_MENU]],
                             menu_path_write=SubMenues.DEPLOYMENT_COUNTER_MENU,
                             submenu_write=[Event.DEPLOYMENT_COUNTER, Event.YES])

        self._param_dict.add(Parameter.DEPLOYMENT_MODE,
                             r'OpMode = (SCHEDULED|CONTINUOUS|FIXEDTIME|FIXEDTIMEISUS|BENCHTOP|TRIGGERED)',
                             lambda match : str(match.group(1)),
                             self._opmode_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=SubMenues.DEPLOYMENT_MODE_MENU,
                             #menu_path_read=[[Event.SETUP_MENU,
                             #                Event.DEPLOYMENT_SETUP_MENU]],
                             submenu_read=[Event.OPERATIONAL_MODE, Prompt.SETUP_DEPLOY_MENU],
                             menu_path_write=SubMenues.DEPLOYMENT_MODE_MENU,
                             submenu_write=[Event.OPERATIONAL_MODE, Event.YES])


        """
        DHE COMMENTED OUT
        This was Steve's original way
        self._param_dict.add(Parameter.BAUDRATE,
                             r'Baudrate:\s+(\d+) bps',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.CONFIG_MENU,
                                             Event.SHOW_CONFIG],
                             menu_path_write=[Event.CONFIG_MENU,
                                             Event.BAUD_RATE,
                                             Event.YES])
        self._param_dict.add(Parameter.DEPLOYMENT_COUNTER,
                             r'Deployment Cntr:\s+(\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.CONFIG_MENU,
                                             Event.SHOW_CONFIG],
                             menu_path_write=[Event.CONFIG_MENU,
                                              Event.DEPLOYMENT_COUNTER,
                                              Event.YES])
        self._param_dict.add(Parameter.STATUS_MESSAGES,
                             r'StatusMessages = (ENABLED|DISABLED)',
                             lambda match : int(match.group(1)),
                             self._enable_disable_to_bool,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.STATUS_MESSAGES],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.STATUS_MESSAGES,
                                              Event.YES])
        self._param_dict.add(Parameter.LOGGING_FRAME_MODE,
                             r'FrameLogging = (NONE|FULL_ASCII|FULL_BINARY|CONCENTRATION)',
                             lambda match : int(match.group(1)),
                             self._frametype_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.LOGGING_FRAME_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.LOGGING_FRAME_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.TRANSFER_FRAME_MODE,
                             r'FrameTransfer = (NONE|FULL_ASCII|FULL_BINARY|CONCENTRATION)',
                             lambda match : int(match.group(1)),
                             self._frametype_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.TRANSFER_FRAME_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.TRANSFER_FRAME_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.DAILY_LOG_TOGGLE,
                             r'SchFile = (DAILY|EACHEVENT)',
                             lambda match : int(match.group(1)),
                             self._logtoggle_to_int,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.DAILY_LOG_TOGGLE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.DAILY_LOG_TOGGLE,
                                              Event.YES])    
        self._param_dict.add(Parameter.NITRATE_DAC_RANGE_MIN,
                             r'NO3DacMin = ([-+]?\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.NITRATE_DAC_RANGE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.NITRATE_DAC_RANGE,
                                              Event.YES])
        self._param_dict.add(Parameter.NITRATE_DAC_RANGE_MAX,
                             r'NO3DacMax = (\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.NITRATE_DAC_RANGE,
                                             Event.NO],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.NITRATE_DAC_RANGE,
                                              Event.NO,
                                              Event.YES])
        self._param_dict.add(Parameter.AUX_DAC_RANGE_MIN,
                             r'AuxDacMin = ([-+]?\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.AUX_DAC_RANGE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.AUX_DAC_RANGE,
                                              Event.YES])
        self._param_dict.add(Parameter.AUX_DAC_RANGE_MAX,
                             r'AuxDacMax = (\d*\.?\d+)',
                             lambda match : int(match.group(1)),
                             self._float_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.OUTPUT_SETUP_MENU,
                                             Event.AUX_DAC_RANGE,
                                             Event.NO],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.OUTPUT_SETUP_MENU,
                                              Event.AUX_DAC_RANGE,
                                              Event.NO,
                                              Event.YES])
        self._param_dict.add(Parameter.DEPLOYMENT_MODE,
                             r'OpMode = (SCHEDULED|CONTINUOUS|FIXEDTIME|FIXEDTIMEISUS|BENCHTOP|TRIGGERED)',
                             lambda match : int(match.group(1)),
                             self._opmode_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.DEPLOYMENT_SETUP_MENU,
                                             Event.OPERATIONAL_MODE],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.DEPLOYMENT_SETUP_MENU,
                                              Event.OPERATIONAL_MODE,
                                              Event.YES])
        self._param_dict.add(Parameter.INITIAL_DELAY,
                             r'ContModeDelay = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             menu_path_read=[Event.SETUP_MENU,
                                             Event.DEPLOYMENT_SETUP_MENU,
                                             Event.INITIAL_DELAY],
                             menu_path_write=[Event.SETUP_MENU,
                                              Event.DEPLOYMENT_SETUP_MENU,
                                              Event.INITIAL_DELAY,
                                              Event.YES])

        """



    # @todo Add necessary helper routines as needed.
    # Maybe a stop/break/reset for leaving operating modes?
    #
    # Maybe some for confirming what state the instrument is in?
    
    
###
#   Driver for ooicore
###
#class ooicoreInstrumentDriver(InstrumentDriver):
class ooicoreInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    """
    def __init__(self, evt_callback):
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)


    # DHE Added
    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()


    # DHE Added
    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = ooicoreInstrumentProtocol(Prompt, INSTRUMENT_NEWLINE, self._driver_event) 


