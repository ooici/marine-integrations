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
#from mi.instrument_connection import SerialInstrumentConnection
#from mi.instrument_driver import InstrumentDriver
#from mi.instrument_driver import DriverChannel
#from mi.exceptions import InstrumentProtocolException
#from mi.exceptions import InstrumentTimeoutException
#from mi.exceptions import InstrumentStateException
#from mi.exceptions import InstrumentConnectionException
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

###
#   Module wide values
###
log = logging.getLogger('mi_logger')
INSTRUMENT_NEWLINE = '\n'
WRITE_DELAY = 0
RESET_DELAY = 25
EOLN = "\r\n"

# @todo May need some regex(s) for data format returned...at least to confirm
# that it is data.

###
#   Static Enumerations
###
class State(BaseEnum):
    """
    Enumerated driver states.  Your driver will likly only support a subset of these.
    """
    UNCONFIGURED_MODE = DriverProtocolState.UNKNOWN
    BENCHTOP_MODE = "ISUS_STATE_BENCHTOP"
    TRIGGERED_MODE =  DriverProtocolState.POLL
    CONTINUOUS_MODE =  "ISUS_STATE_CONTINUOUS"
    FIXEDTIME_MODE = "ISUS_STATE_FIXEDTIME"
    SCHEDULED_MODE = "ISUS_STATE_SCHEDULED"
    MENU_MODE =  DriverProtocolState.COMMAND
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
    #TEST = DriverEvent.TEST
    #STOP_TEST = DriverEvent.STOP_TEST
    #CALIBRATE = DriverEvent.CALIBRATE
    #RESET = DriverEvent.RESET
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    #UPDATE_PARAMS = DriverEvent.UPDATE_PARAMS
    
    
    # Menu and operation commands
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

class Command(BaseEnum):
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
    
class Prompt(BaseEnum):
    ROOT_MENU = "ISUS> [H] ?"
    CONFIG_MENU = "ISUS_CONFIG> [H] ?"
    SETUP_MENU = "ISUS_SETUP> [H] ?"
    SETUP_OUTPUT_MENU = "ISUS_SETUP_OUTPUT> [H] ?"
    SETUP_DEPLOY_MENU = "ISUS_SETUP_DEPLOY> [H] ?"
    SETUP_SPEC_MENU = "ISUS_SETUP_SPEC> [H] ?"
    SETUP_LAMP_MENU = "ISUS_SETUP_LAMP> [H] ?"
    FILE_MENU = "ISUS_FILE> [H] ?"
    INFO_MENU = "ISUS_INFO> [H] ?"
    SAVE_SETTINGS = "Save current settings? (Otherwise changes are lost at next power-down) [Y] ?"
    REPLACE_SETTINGS = "Replace existing setting by current? [N] ?"
    MODIFY = "Modify? [N] ?"
    ENTER_CHOICE = "Enter number to assign new value [5] ?"

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

###
#   Protocol for ooicore
###
class ooicoreInstrumentProtocol(MenuInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    def __init__(self, callback=None, prompt=Prompt(), newline=INSTRUMENT_NEWLINE):
        """
        """
        MenuInstrumentProtocol.__init__(self, callback, prompt, newline)
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = EOLN
        
        ##### Setup the state machine
        self._protocol_fsm = InstrumentFSM(State, Event, Event.ENTER, Event.EXIT)
        
        self._protocol_fsm.add_handler(State.UNCONFIGURED_MODE, Event.INITIALIZE,
                              self._handler_initialize) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.MENU_CMD,
                              self._handler_continuous_menu) 
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.GO_CMD,
                              self._handler_continuous_go)
        self._protocol_fsm.add_handler(State.CONTINUOUS_MODE, Event.STOP_CMD,
                              self._handler_continuous_stop) 
        
        # ... and so on with the operation handler listings...
        # In general, naming is _handler_currentstate_eventreceived

        self._protocol_fsm.add_handler(State.ROOT_MENU, Event.CONFIG_MENU,
                              self._handler_root_config) 
        self._protocol_fsm.add_handler(State.ROOT_MENU, Event.SETUP_MENU,
                              self._handler_root_setup) 
        self._protocol_fsm.add_handler(State.ROOT_MENU, Event.FILE_MENU,
                              self._handler_root_file) 
        
        # @todo ... and so on with the menu handler listings...

        ##### Setup the parameter dictionary
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


        # State state machine in UNCONFIGURED state.
        self._protocol_fsm.start(State.UNCONFIGURED_MODE)

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
    def _wakeup(self, timeout):
        """Send a wakeup to this instrument...one that wont hurt if it is awake
        already."""
        self._connection.send(Event.ANY_KEY)

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
        self.get_config()
        new_config = self._param_dict.get_config()            
        if (new_config != old_config) and (None not in old_config.values()):
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)            
            
    #
    # DHE ADDED herehere
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

        print "DHE ------------------> <--------------------DHE"
        if len(data)>0:
            # Call the superclass to update line and prompt buffers.
            MenuInstrumentProtocol.got_data(self, data)

            # If in streaming mode, process the buffer for samples to publish.
            #cur_state = self.get_current_state()
            #if cur_state == SBE37ProtocolState.AUTOSAMPLE:
            #    if SBE37_NEWLINE in self._linebuf:
            #        lines = self._linebuf.split(SBE37_NEWLINE)
            #        self._linebuf = lines[-1]
            #        for line in lines:
            #            self._extract_sample(line)


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
        self._protocol = ooicoreInstrumentProtocol(evt_callback)
    
    def driver_echo(self, msg):
        """
        @brief Sample driver command. 
        """
        echo = 'driver_echo: %s' % msg
        return echo

