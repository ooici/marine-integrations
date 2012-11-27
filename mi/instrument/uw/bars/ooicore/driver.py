"""
@package mi.instrument.uw.bars.ooicore.driver
@file mi/instrument/uw/bars/ooicore/driver.py
@author Steve Foley
@brief Driver for the ooicore
Release notes:
This supports the UW BARS instrument from the Marv Tilley lab

"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, ParameterDictVisibility

from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol

from mi.core.log import get_logger ; log = get_logger()

Directions = MenuInstrumentProtocol.MenuTree.Directions

SAMPLE_PATTERN = r'(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\s+(\d+.\d+)\r\n'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

# newline.
NEWLINE = '\r'

# default timeout.
TIMEOUT = 10

# Packet config
PACKET_CONFIG = {
    'parsed' : None,
    'raw' : None,
    'eng' : None
}

class Command(BaseEnum):
    DIRECT_SET = "SET"
    BACK_MENU = "BACK_MENU"
    BLANK = "BLANK"
    BREAK = "BREAK"
    START_AUTOSAMPLE = "START_AUTOSAMPLE"
    CHANGE_PARAM = "CHANGE_PARAM"
    SHOW_PARAM = "SHOW_PARAM"
    SENSOR_POWER = "SENSOR_POWER"
    CHANGE_CYCLE_TIME = "CHANGE_CYCLE_TIME"
    CHANGE_VERBOSE = "CHANGE_VERBOSE"
    CHANGE_METADATA_POWERUP = "CHANGE_METADATA_POWERUP"
    CHANGE_METADATA_RESTART = "CHANGE_METADATA_RESTART"
    CHANGE_RES_SENSOR_POWER = "CHANGE_RES_SENSOR_POWER"
    CHANGE_INST_AMP_POWER = "CHANGE_INST_AMP_POWER"
    CHANGE_EH_ISOLATION_AMP_POWER = "CHANGE_EH_ISOLATION_AMP_POWER"
    CHANGE_HYDROGEN_POWER = "CHANGE_HYDROGEN_POWER"
    CHANGE_REFERENCE_TEMP_POWER = "CHANGE_REFERENCE_TEMP_POWER"

# Strings should line up with Command class
COMMAND_CHAR = {
    'BACK_MENU' : '9',
    'BLANK' : '\r',
    'BREAK' : 0x13, # Ctrl-S
    'START_AUTOSAMPLE' : '1',
    'CHANGE_PARAM' : '2',
    'SHOW_PARAM' : '6',
    'SENSOR_POWER' : '4',
    'CHANGE_CYCLE_TIME': '1',
    'CHANGE_VERBOSE' : '2',
    'CHANGE_METADATA_POWERUP' : '3',
    'CHANGE_METADATA_RESTART' : '4',
    'CHANGE_RES_SENSOR_POWER' : '1',
    'CHANGE_INST_AMP_POWER' : '2',
    'CHANGE_EH_ISOLATION_AMP_POWER' : '3',
    'CHANGE_HYDROGEN_POWER' : '4',
    'CHANGE_REFERENCE_TEMP_POWER' : '5',
}
    
class SubMenu(BaseEnum):
    MAIN = "SUBMENU_MAIN"
    CHANGE_PARAM = "SUBMENU_CHANGE_PARAM"
    SHOW_PARAM = "SUBMENU_SHOW_PARAM"
    SENSOR_POWER = "SUBMENU_SENSOR_POWER"
    CYCLE_TIME = "SUBMENU_CYCLE_TIME"
    VERBOSE = "SUBMENU_VERBOSE"
    METADATA_POWERUP = "SUBMENU_METADATA_POWERUP"
    METADATA_RESTART = "SUBMENU_METADATA_RESTART"
    RES_SENSOR_POWER = "SUBMENU_RES_SENSOR_POWER"
    INST_AMP_POWER = "SUBMENU_INST_AMP_POWER"
    EH_ISOLATION_AMP_POWER = "SUBMENU_EH_ISOLATION_AMP_POWER"
    HYDROGEN_POWER = "SUBMENU_HYDROGEN_POWER"
    REFERENCE_TEMP_POWER = "SUBMENU_REFERENCE_TEMP_POWER"
        
class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    EXECUTE_ACQUIRE_STATUS = "BARS_GET_STATUS"

class Capability(BaseEnum):
    """
    Capabilities exposed to user
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = ProtocolEvent.EXECUTE_DIRECT
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT
    
# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """
    CYCLE_TIME = "CYCLE_TIME"
    VERBOSE = "VERBOSE"
    METADATA_POWERUP = "METADATA_POWERUP"
    METADATA_RESTART = "METADATA_RESTART"
    RES_SENSOR_POWER = "RES_SENSOR_POWER"
    INST_AMP_POWER = "INST_AMP_POWER"
    EH_ISOLATION_AMP_POWER = "EH_ISOLATION_AMP_POWER"
    HYDROGEN_POWER = "HYDROGEN_POWER"
    REFERENCE_TEMP_POWER = "REFERENCE_TEMP_POWER"

class VisibleParameters(DriverParameter):
    """
    Just the parameters that can be edited by the user
    """
    CYCLE_TIME = "CYCLE_TIME"

# Device prompts.
class Prompt(BaseEnum):
    """
    io prompts.
    """
    CMD_PROMPT = "-->"
    BREAK_ACK = "\r\n"
    NONE = ""
    
    DEAD_END_PROMPT = "Press Enter to return to the Main Menu. -->"
    CONTINUE_PROMPT = "Press ENTER to continue."

    MAIN_MENU = "Enter 0, 1, 2, 3, 4, 5, or 6 here  -->"
    CHANGE_PARAM_MENU = "Enter 0 through 9 here  -->"
    SENSOR_POWER_MENU = "Enter 0 through 9 here  -->"

    CYCLE_TIME_PROMPT = "Enter 1 for Seconds, 2 for Minutes -->"
    CYCLE_TIME_VALUE_PROMPT = "Enter a new value between 15 and 59 here -->"
    VERBOSE_PROMPT = "Enter 2 for Verbose, 1 for just Data. -->"
    METADATA_PROMPT = "Enter 2 for Yes, 1 for No. -->"
    
MENU_PROMPTS = [Prompt.MAIN_MENU, Prompt.CHANGE_PARAM_MENU,
                Prompt.SENSOR_POWER_MENU, Prompt.CYCLE_TIME_PROMPT,
                Prompt.DEAD_END_PROMPT, Prompt.CONTINUE_PROMPT]
    
MENU = MenuInstrumentProtocol.MenuTree({
    SubMenu.MAIN:[],
    SubMenu.CHANGE_PARAM:[Directions(command=Command.CHANGE_PARAM,
                                     response=Prompt.CHANGE_PARAM_MENU)],
    SubMenu.SHOW_PARAM:[Directions(SubMenu.CHANGE_PARAM),
                        Directions(command=Command.SHOW_PARAM,
                                   response=Prompt.CONTINUE_PROMPT)],
    SubMenu.SENSOR_POWER:[Directions(command=Command.SENSOR_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
    SubMenu.CYCLE_TIME:[Directions(SubMenu.CHANGE_PARAM),
                        Directions(command=Command.CHANGE_CYCLE_TIME,
                                     response=Prompt.CYCLE_TIME_PROMPT)],
    SubMenu.VERBOSE:[Directions(SubMenu.CHANGE_PARAM),
                        Directions(command=Command.CHANGE_VERBOSE,
                                     response=Prompt.VERBOSE_PROMPT)],
    SubMenu.METADATA_POWERUP:[Directions(SubMenu.CHANGE_PARAM),
                        Directions(command=Command.CHANGE_METADATA_POWERUP,
                                     response=Prompt.METADATA_PROMPT)],
    SubMenu.METADATA_RESTART:[Directions(SubMenu.CHANGE_PARAM),
                        Directions(command=Command.CHANGE_METADATA_RESTART,
                                     response=Prompt.METADATA_PROMPT)],
    SubMenu.RES_SENSOR_POWER:[Directions(SubMenu.SENSOR_POWER),
                        Directions(command=Command.CHANGE_RES_SENSOR_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
    SubMenu.INST_AMP_POWER:[Directions(SubMenu.SENSOR_POWER),
                        Directions(command=Command.CHANGE_INST_AMP_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
    SubMenu.EH_ISOLATION_AMP_POWER:[Directions(SubMenu.SENSOR_POWER),
                        Directions(command=Command.CHANGE_EH_ISOLATION_AMP_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
    SubMenu.HYDROGEN_POWER:[Directions(SubMenu.SENSOR_POWER),
                        Directions(command=Command.CHANGE_HYDROGEN_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
    SubMenu.REFERENCE_TEMP_POWER:[Directions(SubMenu.SENSOR_POWER),
                        Directions(command=Command.CHANGE_REFERENCE_TEMP_POWER,
                                     response=Prompt.SENSOR_POWER_MENU)],
})



class BarsDataParticleKey(BaseEnum):
    RESISTIVITY_5 = "Resistivity5"
    RESISTIVITY_X1 = "ResistivityX1"
    RESISTIVITY_X5 = "ResistivityX5"
    HYDROGEN_5 = "Hydrogen5"
    HYDROGEN_X1 = "HydrogenX1"
    HYDROGEN_X5 = "HydrogenX5"
    EH_SENSOR = "EhSensor"
    REFERENCE_TEMP_VOLTS = "RefTempVolts"
    REFERENCE_TEMP_DEG_C = "RefTempDegC"
    RESISTIVITY_TEMP_VOLTS = "ResistivityTempVolts"
    RESISTIVITY_TEMP_DEG_C = "ResistivityTempDegC"
    BATTERY_VOLTAGE = "BatteryVoltage"

class BarsDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure for the
    Satlantic PAR sensor. Overrides the building of values, and the rest comes
    along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the sample format and split it into
        a PAR values (with an appropriate tag)
        
        @throw SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)
            
        log.trace("Matching sample [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s]",
                  match.group(1),match.group(2),match.group(3),match.group(4),match.group(5),
                  match.group(6),match.group(7),match.group(8),match.group(9),match.group(10),
                  match.group(11),match.group(12))
        res_5 = float(match.group(1))
        res_x1 = float(match.group(2))
        res_x5 = float(match.group(3))
        h_5 = float(match.group(4))
        h_x1 = float(match.group(5))
        h_x5 = float(match.group(6))
        eh = float(match.group(7))
        ref_temp_v = float(match.group(8))
        ref_temp_c = float(match.group(9))
        res_temp_v = float(match.group(10))
        res_temp_c = float(match.group(11))
        batt_v = float(match.group(12))
        
        
        result = [{DataParticleKey.VALUE_ID: BarsDataParticleKey.RESISTIVITY_5,
                   DataParticleKey.VALUE: res_5},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.RESISTIVITY_X1,
                   DataParticleKey.VALUE: res_x1},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.RESISTIVITY_X5,
                   DataParticleKey.VALUE: res_x5},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.HYDROGEN_5,
                   DataParticleKey.VALUE: h_5},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.HYDROGEN_X1,
                   DataParticleKey.VALUE: h_x1},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.HYDROGEN_X5,
                   DataParticleKey.VALUE: h_x5},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.EH_SENSOR,
                   DataParticleKey.VALUE: eh},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.REFERENCE_TEMP_VOLTS,
                   DataParticleKey.VALUE: ref_temp_v},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.REFERENCE_TEMP_DEG_C,
                   DataParticleKey.VALUE: ref_temp_c},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.RESISTIVITY_TEMP_VOLTS,
                   DataParticleKey.VALUE: res_temp_v},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.RESISTIVITY_TEMP_DEG_C,
                   DataParticleKey.VALUE: res_temp_c},
                  {DataParticleKey.VALUE_ID: BarsDataParticleKey.BATTERY_VOLTAGE,
                   DataParticleKey.VALUE: batt_v}
                  ]
        
        return result
    
###############################################################################
# Driver
###############################################################################

class ooicoreInstrumentDriver(SingleConnectionInstrumentDriver):
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
        
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
                                         DriverEvent.DISCOVER,
                                         self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params
        # when we discover. Gotta get into command mode first though.
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
        self._protocol = Protocol(MENU, Prompt, NEWLINE, self._driver_event)

    def apply_startup_params(self):
        """
        Apply the startup values previously stored in the protocol to
        the running config of the live instrument. The startup values are the
        values that are (1) marked as startup parameters and are (2) the "best"
        value to use at startup. Preference is given to the previously-set init
        value, then the default value, then the currently used value.
        
        This default method assumes a dict of parameter name and value for
        the configuration.
        @raise InstrumentParameterException If the config cannot be applied
        """
        config = self._protocol.get_startup_config()
        
        if not isinstance(config, dict):
            raise InstrumentParameterException("Incompatible initialization parameters")
        
        self._protocol.set_readonly_values()
        self.set_resource(config)

###############################################################################
# Protocol
################################################################################

class Protocol(MenuInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses MenuInstrumentProtocol
    """
    def __init__(self, menu, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.DISCOVER, self._handler_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_autosample)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.DISCOVER, self._handler_discover)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(Command.BACK_MENU, self._build_menu_command)
        self._add_build_handler(Command.BLANK, self._build_solo_command)
        self._add_build_handler(Command.START_AUTOSAMPLE, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_PARAM, self._build_menu_command)
        self._add_build_handler(Command.SHOW_PARAM, self._build_menu_command)
        self._add_build_handler(Command.SENSOR_POWER, self._build_menu_command)
        self._add_build_handler(Command.DIRECT_SET, self._build_direct_command)
        self._add_build_handler(Command.CHANGE_CYCLE_TIME, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_VERBOSE, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_METADATA_RESTART, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_METADATA_POWERUP, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_RES_SENSOR_POWER, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_INST_AMP_POWER, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_EH_ISOLATION_AMP_POWER, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_HYDROGEN_POWER, self._build_menu_command)
        self._add_build_handler(Command.CHANGE_REFERENCE_TEMP_POWER, self._build_menu_command)

        # Add response handlers for device commands.
        #self._add_response_handler(Command.GET, self._parse_get_response)
        #self._add_response_handler(Command.SET, self._parse_get_response)
        self._add_response_handler(Command.BACK_MENU, self._parse_menu_change_response)
        self._add_response_handler(Command.BLANK, self._parse_menu_change_response)
        self._add_response_handler(Command.SHOW_PARAM, self._parse_show_param_response)
        self._add_response_handler(Command.CHANGE_CYCLE_TIME, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_VERBOSE, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_METADATA_RESTART, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_METADATA_POWERUP, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_RES_SENSOR_POWER, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_INST_AMP_POWER, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_EH_ISOLATION_AMP_POWER, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_HYDROGEN_POWER, self._parse_menu_change_response)
        self._add_response_handler(Command.CHANGE_REFERENCE_TEMP_POWER, self._parse_menu_change_response)
        self._add_response_handler(Command.DIRECT_SET, self._parse_menu_change_response)
        
        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(self.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        return_list = []
        
        for match in SAMPLE_REGEX.finditer(raw_data):
            return_list.append((match.start(), match.end()))

        return return_list

    def _go_to_root_menu(self):
        """ Get back to the root menu, assuming we are in COMMAND mode.
        Getting to command mode should be done before this method is called.
        A discover will get there.
        """
        log.debug("Returning to root menu...")
        # Issue an enter or two off the bat to get out of any display screens
        # and confirm command mode
        try:
            response = self._do_cmd_resp(Command.BLANK, expected_prompt=Prompt.CMD_PROMPT)
            while not str(response).lstrip().endswith(Prompt.CMD_PROMPT):
                response = self._do_cmd_resp(Command.BLANK,
                                             expected_prompt=Prompt.CMD_PROMPT)
                time.sleep(1)
        except InstrumentTimeoutException:
            raise InstrumentProtocolException("Not able to get valid command prompt. Is instrument in command mode?")
        
        # When you get a --> prompt, do 9's until you get back to the root
        response = self._do_cmd_resp(Command.BACK_MENU,
                                     expected_prompt=MENU_PROMPTS)
        while not str(response).lstrip().endswith(Prompt.MAIN_MENU):
            response = self._do_cmd_resp(Command.BACK_MENU,
                                         expected_prompt=MENU_PROMPTS)

            
    def _filter_capabilities(self, events):
        """ Define a small filter of the capabilities
        
        @param A list of events to consider as capabilities
        @retval A list of events that are actually capabilities
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def get_resource_capabilities(self, current_state=True):
        """
        """

        res_cmds = self._protocol_fsm.get_events(current_state)
        res_cmds = self._filter_capabilities(res_cmds)        
        res_params = VisibleParameters.list()
        
        return [res_cmds, res_params]
        
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

    def _handler_discover(self, *args, **kwargs):
        """
        Discover current state by going to the root menu 
        @retval (next_state, result)
        """
        next_state = None
        next_agent_state = None
        result = None
        
        # Try to break in case we are in auto sample
        self._send_break() 

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._go_to_root_menu()
      
        return (next_state, (next_agent_state, result))
                
    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throw InstrumentTimeoutException if the device cannot be woken.
        @throw InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, params=None, *args, **kwargs):
        """
        Get parameters while in the command state.
        @param params List of the parameters to pass to the state
        @retval returns (next_state, result) where result is a dict {}. No
            agent state changes happening with Get, so no next_agent_state
        @throw InstrumentParameterException for invalid parameter
        """
        next_state = None
        result = None
        result_vals = {}
        
        if (params == None):
            raise InstrumentParameterException("GET parameter list empty!")
            
        if (params == Parameter.ALL):
            params = [Parameter.CYCLE_TIME, Parameter.EH_ISOLATION_AMP_POWER,
                      Parameter.HYDROGEN_POWER, Parameter.INST_AMP_POWER,
                      Parameter.METADATA_POWERUP, Parameter.METADATA_RESTART,
                      Parameter.REFERENCE_TEMP_POWER, Parameter.RES_SENSOR_POWER,
                      Parameter.VERBOSE]
            
        if not isinstance(params, list):
            raise InstrumentParameterException("GET parameter list not a list!")

        # Do a bulk update from the instrument since they are all on one page
        self._update_params()
        
        # fill the return values from the update
        for param in params:
            if not Parameter.has(param):
                raise InstrumentParameterException("Invalid parameter!")
            result_vals[param] = self._param_dict.get(param) 
        result = result_vals

        log.debug("Get finished, next: %s, result: %s", next_state, result) 
        return (next_state, result)

    def _handler_command_set(self, params, *args, **kwargs):
        """Handle setting data from command mode
         
        @param params Dict of the parameters and values to pass to the state
        @retval return (next state, result)
        @throw InstrumentProtocolException For invalid parameter
        """
        next_state = None
        result = None
        result_vals = {}    

        if ((params == None) or (not isinstance(params, dict))):
            raise InstrumentParameterException()
        name_values = params
        for key in name_values.keys():
            if not Parameter.has(key):
                raise InstrumentParameterException()
            # ***SAF
            #try:
            #    str_val = self._param_dict.format(key, name_values[key])
            #except KeyError:
            #    raise InstrumentParameterException()
            
            # restrict operations to just the read/write parameters
            if (key == Parameter.CYCLE_TIME):
                self._navigate(SubMenu.CYCLE_TIME)
                (unit, value) = self._from_seconds(name_values[key])
                
                try:                
                    self._do_cmd_resp(Command.DIRECT_SET, unit,
                                      expected_prompt=Prompt.CYCLE_TIME_VALUE_PROMPT)
                    self._do_cmd_resp(Command.DIRECT_SET, value,
                                      expected_prompt=Prompt.CHANGE_PARAM_MENU)
                except InstrumentProtocolException:
                    self._go_to_root_menu()
                    raise InstrumentProtocolException("Could not set cycle time")
                
                # Populate with actual value set
                result_vals[key] = name_values[key]
                
        # re-sync with param dict?
        self._go_to_root_menu()
        self._update_params()
        
        result = result_vals
            
        log.debug("next: %s, result: %s", next_state, result) 
        return (next_state, result)

    def _handler_command_autosample(self, *args, **kwargs):
        """ Start autosample mode """
        next_state = None
        next_agent_state = None
        result = None
        
        self._navigate(SubMenu.MAIN)
        self._do_cmd_no_resp(Command.START_AUTOSAMPLE)
        
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

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

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        next_agent_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers
    ########################################################################
    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample mode
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_stop(self):
        """
        Stop autosample mode
        """
        next_state = None
        next_agent_state = None
        result = None

        if (self._send_break()):        
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        
        return (next_state, (next_agent_state, result))

    ########################################################################
    # Command builders
    ########################################################################    
    def _build_solo_command(self, cmd):
        """ Issue a simple command that does NOT require a newline at the end to
        execute. Likly used for control characters or special characters """
        return COMMAND_CHAR[cmd]
    
    def _build_menu_command(self, cmd):
        """ Pick the right character and add a newline """
        if COMMAND_CHAR[cmd]:
            return COMMAND_CHAR[cmd]+self._newline
        else:
            raise InstrumentProtocolException("Unknown command character for %s" % cmd)
            
    def _build_direct_command(self, cmd, arg):
        """ Build a command where we just send the argument to the instrument.
        Ignore the command part, we dont need it here as we are already in
        a submenu.
        """
        return "%s%s" % (arg, self._newline)
    
    ########################################################################
    # Command parsers
    ########################################################################
    def _parse_menu_change_response(self, response, prompt):
        """ Parse a response to a menu change
        
        @param response What was sent back from the command that was sent
        @param prompt The prompt that was returned from the device
        @retval The prompt that was encountered after the change
        """
        log.trace("Parsing menu change response with prompt: %s", prompt)
        return prompt

    def _parse_show_param_response(self, response, prompt):
        """ Parse the show parameter response screen """
        log.trace("Parsing show parameter screen")
        self._param_dict.update_many(response)
        
    ########################################################################
    # Utilities
    ########################################################################

    def _wakeup(self, timeout):
        # Always awake for this instrument!
        pass
    
    def _got_chunk(self, chunk):
        '''
        extract samples from a chunk of data
        @param chunk: bytes to parse into a sample.
        '''
        self._extract_sample(BarsDataParticle, SAMPLE_REGEX, chunk)
        
    def _update_params(self):
        """Fetch the parameters from the device, and update the param dict.
        
        @param args Unused
        @param kwargs Takes timeout value
        @throw InstrumentProtocolException
        @throw InstrumentTimeoutException
        """
        log.debug("Updating parameter dict")
        old_config = self._param_dict.get_config()
        self._get_config()
        new_config = self._param_dict.get_config()            
        if (new_config != old_config):
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)  
    
    def _get_config(self, *args, **kwargs):
        """ Get the entire configuration for the instrument
        
        @param params The parameters and values to set
        Should be a dict of parameters and values
        @throw InstrumentProtocolException On a deeper issue
        """
        # Just need to show the parameter screen...the parser for the command
        # does the update_many()
        self._go_to_root_menu()
        self._navigate(SubMenu.SHOW_PARAM)
        self._go_to_root_menu()
            
    def _send_break(self, timeout=4):
        """
        Execute an attempts to break out of auto sample (a few if things get garbled).
        For this instrument, it is done with a ^S, a wait for a \r\n, then
        another ^S within 1/2 a second
        @param timeout
        @retval True if 2 ^S chars were sent with a prompt in the middle, False
            if not.
        """
        log.debug("Sending break sequence to instrument...")
        # Timing is an issue, so keep it simple, work directly with the
        # couple chars instead of command/respose. Could be done that way
        # though. Just more steps, logic, and delay for such a simple
        # exchange
        
        for count in range(0, 3):
            self._promptbuf = ""
            try:
                self._connection.send("%c" % COMMAND_CHAR[Command.BREAK])
                (prompt, result) = self._get_raw_response(timeout, expected_prompt=[Prompt.BREAK_ACK,
                                                                              Prompt.CMD_PROMPT])
                if (prompt == Prompt.BREAK_ACK):
                    self._connection.send("%c" % COMMAND_CHAR[Command.BREAK])
                    (prompt, result) = self._get_response(timeout, expected_prompt=Prompt.CMD_PROMPT)
                    return True
                elif(prompt == Prompt.CMD_PROMPT):
                    return True
                
            except InstrumentTimeoutException:
                continue

        log.trace("_send_break failing after several attempts")
        return False   
 
    def set_readonly_values(self, *args, **kwargs):
        """Set read-only values to the instrument. This is usually (only?)
        done at initialization.
        
        @throw InstrumentProtocolException When in the wrong state or something
        really bad prevents the setting of all values.
        """
        # Let's give it a try in unknown state
        if (self.get_current_state() != ProtocolState.COMMAND):
            raise InstrumentProtocolException("Not in command state. Unable to set read-only params")

        self._go_to_root_menu()
        self._update_params()

        for param in self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY):
            if not Parameter.has(param):
                raise InstrumentParameterException()

            self._go_to_root_menu()
            # Only try to change them if they arent set right as it is
            log.trace("Setting read-only parameter: %s, current paramdict value: %s, init val: %s",
                      param, self._param_dict.get(param),
                      self._param_dict.get_init_value(param))
            if (self._param_dict.get(param) != self._param_dict.get_init_value(param)):
                if (param == Parameter.METADATA_POWERUP):
                    self._navigate(SubMenu.METADATA_POWERUP)
                    result = self._do_cmd_resp(Command.DIRECT_SET, (1+ int(self._param_dict.get_init_value(param))),
                                               expected_prompt=Prompt.CHANGE_PARAM_MENU)
                    if not result:
                        raise InstrumentParameterException("Could not set param %s" % param)
                    
                    self._go_to_root_menu()                
                
                elif (param == Parameter.METADATA_RESTART):
                    self._navigate(SubMenu.METADATA_RESTART)
                    result = self._do_cmd_resp(Command.DIRECT_SET, (1 + int(self._param_dict.get_init_value(param))),
                                               expected_prompt=Prompt.CHANGE_PARAM_MENU)
                    if not result:
                        raise InstrumentParameterException("Could not set param %s" % param)
                    
                    self._go_to_root_menu()
                    
                elif (param == Parameter.VERBOSE):
                    self._navigate(SubMenu.VERBOSE)
                    result = self._do_cmd_resp(Command.DIRECT_SET, self._param_dict.get_init_value(param),
                                               expected_prompt=Prompt.CHANGE_PARAM_MENU)
                    if not result:
                        raise InstrumentParameterException("Could not set param %s" % param)
                    
                    self._go_to_root_menu()    
                    
                elif (param == Parameter.EH_ISOLATION_AMP_POWER):
                    result = self._navigate(SubMenu.EH_ISOLATION_AMP_POWER)
                    while not result:
                        result = self._navigate(SubMenu.EH_ISOLATION_AMP_POWER)
                        
                elif (param == Parameter.HYDROGEN_POWER):
                    result = self._navigate(SubMenu.HYDROGEN_POWER)
                    while not result:
                        result = self._navigate(SubMenu.HYDROGEN_POWER)
        
                elif (param == Parameter.INST_AMP_POWER):
                    result = self._navigate(SubMenu.INST_AMP_POWER)
                    while not result:
                        result = self._navigate(SubMenu.INST_AMP_POWER)
                    
                elif (param == Parameter.REFERENCE_TEMP_POWER):
                    result = self._navigate(SubMenu.REFERENCE_TEMP_POWER)
                    while not result:
                        result = self._navigate(SubMenu.REFERENCE_TEMP_POWER)
                    
                elif (param == Parameter.RES_SENSOR_POWER):
                    result = self._navigate(SubMenu.RES_SENSOR_POWER)
                    while not result:
                        result = self._navigate(SubMenu.RES_SENSOR_POWER)
                
        # re-sync with param dict?
        self._go_to_root_menu()
        self._update_params()
        
        # Should be good by now, but let's double check just to be safe
        for param in self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY):
            if (param == Parameter.VERBOSE):
                continue
            if (self._param_dict.get(param) != self._param_dict.get_init_value(param)):
                raise InstrumentProtocolException("Could not set default values!")
                
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict = ProtocolParameterDict()
        
        self._param_dict.add(Parameter.CYCLE_TIME,
                             r'(\d+)\s+= Cycle Time \(.*\)\r\n(0|1)\s+= Minutes or Seconds Cycle Time',
                             lambda match : self._to_seconds(int(match.group(1)),
                                                             int(match.group(2))),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             startup_param=True,
                             direct_access=False,
                             default_value=20,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.CHANGE_PARAM,
                             submenu_write=[["1", Prompt.CYCLE_TIME_PROMPT]])
        
        self._param_dict.add(Parameter.VERBOSE,
                             r'', # Write-only, so does it really matter?
                             lambda match : None,
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=True,
                             init_value=1,
                             menu_path_write=SubMenu.CHANGE_PARAM,
                             submenu_write=[["2", Prompt.VERBOSE_PROMPT]])
 
        self._param_dict.add(Parameter.METADATA_POWERUP,
                             r'(0|1)\s+= Metadata Print Status on Power up',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=True,
                             init_value=0,
                             menu_path_write=SubMenu.CHANGE_PARAM,
                             submenu_write=[["3", Prompt.METADATA_PROMPT]])

        self._param_dict.add(Parameter.METADATA_RESTART,
                             r'(0|1)\s+= Metadata Print Status on Restart Data Collection',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=True,
                             init_value=0,
                             menu_path_write=SubMenu.CHANGE_PARAM,
                             submenu_write=[["4", Prompt.METADATA_PROMPT]])
        
        self._param_dict.add(Parameter.RES_SENSOR_POWER,
                             r'(0|1)\s+= Res Power Status',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=False,
                             init_value=1,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.SENSOR_POWER,
                             submenu_write=[["1"]])

        self._param_dict.add(Parameter.INST_AMP_POWER,
                             r'(0|1)\s+= Thermocouple & Hydrogen Amp Power Status',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=False,
                             init_value=1,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.SENSOR_POWER,
                             submenu_write=[["2"]])

        self._param_dict.add(Parameter.EH_ISOLATION_AMP_POWER,
                             r'(0|1)\s+= eh Amp Power Status',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=False,
                             init_value=1,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.SENSOR_POWER,
                             submenu_write=[["3"]])
        
        self._param_dict.add(Parameter.HYDROGEN_POWER,
                             r'(0|1)\s+= Hydrogen Sensor Power Status',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=False,
                             init_value=1,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.SENSOR_POWER,
                             submenu_write=[["4"]])
        
        self._param_dict.add(Parameter.REFERENCE_TEMP_POWER,
                             r'(0|1)\s+= Reference Temperature Power Status',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             startup_param=True,
                             direct_access=False,
                             init_value=1,
                             menu_path_read=SubMenu.SHOW_PARAM,
                             submenu_read=[],
                             menu_path_write=SubMenu.SENSOR_POWER,
                             submenu_write=[["5"]])
    
    @staticmethod
    def _to_seconds(value, unit):
        """
        Converts a number and a unit into seconds. Ie if "4" and "1"
        comes in, it spits out 240
        @param value The int value for some number of minutes or seconds
        @param unit int of 0 or 1 where 0 is seconds, 1 is minutes
        @return Number of seconds.
        """
        if (not isinstance(value, int)) or (not isinstance(unit, int)):
            raise InstrumentProtocolException("Invalid second arguments!")
        
        if unit == 1:
            return value * 60
        elif unit == 0:
            return value
        else:
            raise InstrumentProtocolException("Invalid Units!")
            
    @staticmethod
    def _from_seconds(value):
        """
        Converts a number of seconds into a (unit, value) tuple.
        
        @param value The number of seconds to convert
        @retval A tuple of unit and value where the unit is 1 for seconds and 2
            for minutes. If the value is 15-59, units should be returned in
            seconds. If the value is over 59, the units will be returned in
            a number of minutes where the seconds are rounded down to the
            nearest minute.
        """
        if (value < 15) or (value > 3600):
            raise InstrumentParameterException("Invalid seconds value: %s" % value)
        
        if (value < 60):
            return (1, value)
        else:
            return (2, value // 60)
        