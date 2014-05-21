#!/usr/bin/env python

"""
@package ion.services.mi.instrument_driver Instrument driver structures
@file ion/services/mi/instrument_driver.py
@author Edward Hunter
@brief Instrument driver classes that provide structure towards interaction
with individual instruments in the system.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import time
import json

from threading import Thread

from mi.core.common import BaseEnum
from mi.core.exceptions import TestModeException
from mi.core.exceptions import NotImplementedException
from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentConnectionException
from mi.core.instrument.instrument_fsm import InstrumentFSM, ThreadSafeFSM
from mi.core.instrument.port_agent_client import PortAgentClient

from mi.core.log import get_logger,LoggerManager
log = get_logger()

class ConfigMetadataKey(BaseEnum):
    """
    Keys used in the metadata structure that describes the driver, commands,
    and parameters used in the driver and protocol.
    """
    DRIVER = 'driver'
    COMMANDS = 'commands'
    PARAMETERS = 'parameters'
    
class DriverConfigKey(BaseEnum):
    """
    Dictionary keys for driver config objects
    """
    PARAMETERS = 'parameters'
    SCHEDULER = 'scheduler'

# This is a copy since we can't import from pyon.
class ResourceAgentState(BaseEnum):
    """
    Resource agent common states.
    """
    POWERED_DOWN = 'RESOURCE_AGENT_STATE_POWERED_DOWN'
    UNINITIALIZED = 'RESOURCE_AGENT_STATE_UNINITIALIZED'
    INACTIVE = 'RESOURCE_AGENT_STATE_INACTIVE'
    IDLE = 'RESOURCE_AGENT_STATE_IDLE'
    STOPPED = 'RESOURCE_AGENT_STATE_STOPPED'
    COMMAND = 'RESOURCE_AGENT_STATE_COMMAND'
    STREAMING = 'RESOURCE_AGENT_STATE_STREAMING'
    TEST = 'RESOURCE_AGENT_STATE_TEST'
    CALIBRATE = 'RESOURCE_AGENT_STATE_CALIBRATE'
    DIRECT_ACCESS = 'RESOUCE_AGENT_STATE_DIRECT_ACCESS'
    BUSY = 'RESOURCE_AGENT_STATE_BUSY'
    LOST_CONNECTION = 'RESOURCE_AGENT_STATE_LOST_CONNECTION'
    ACTIVE_UNKNOWN = 'RESOURCE_AGENT_STATE_ACTIVE_UNKNOWN'
    
class ResourceAgentEvent(BaseEnum):
    """
    Resource agent common events.
    """
    ENTER = 'RESOURCE_AGENT_EVENT_ENTER'
    EXIT = 'RESOURCE_AGENT_EVENT_EXIT'
    POWER_UP = 'RESOURCE_AGENT_EVENT_POWER_UP'
    POWER_DOWN = 'RESOURCE_AGENT_EVENT_POWER_DOWN'
    INITIALIZE = 'RESOURCE_AGENT_EVENT_INITIALIZE'
    RESET = 'RESOURCE_AGENT_EVENT_RESET'
    GO_ACTIVE = 'RESOURCE_AGENT_EVENT_GO_ACTIVE'
    GO_INACTIVE = 'RESOURCE_AGENT_EVENT_GO_INACTIVE'
    RUN = 'RESOURCE_AGENT_EVENT_RUN'
    CLEAR = 'RESOURCE_AGENT_EVENT_CLEAR'
    PAUSE = 'RESOURCE_AGENT_EVENT_PAUSE'
    RESUME = 'RESOURCE_AGENT_EVENT_RESUME'
    GO_COMMAND = 'RESOURCE_AGENT_EVENT_GO_COMMAND'
    GO_DIRECT_ACCESS = 'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS'
    GET_RESOURCE = 'RESOURCE_AGENT_EVENT_GET_RESOURCE'
    SET_RESOURCE = 'RESOURCE_AGENT_EVENT_SET_RESOURCE'
    EXECUTE_RESOURCE = 'RESOURCE_AGENT_EVENT_EXECUTE_RESOURCE'
    GET_RESOURCE_STATE = 'RESOURCE_AGENT_EVENT_GET_RESOURCE_STATE'
    GET_RESOURCE_CAPABILITIES = 'RESOURCE_AGENT_EVENT_GET_RESOURCE_CAPABILITIES'
    DONE = 'RESOURCE_AGENT_EVENT_DONE'
    PING_RESOURCE = 'RESOURCE_AGENT_PING_RESOURCE'
    LOST_CONNECTION = 'RESOURCE_AGENT_EVENT_LOST_CONNECTION'
    AUTORECONNECT = 'RESOURCE_AGENT_EVENT_AUTORECONNECT'
    GET_RESOURCE_SCHEMA = 'RESOURCE_AGENT_EVENT_GET_RESOURCE_SCHEMA'
    CHANGE_STATE_ASYNC = 'RESOURCE_AGENT_EVENT_CHANGE_STATE_ASYNC'

class DriverState(BaseEnum):
    """Common driver state enum"""

    UNCONFIGURED = 'DRIVER_STATE_UNCONFIGURED'
    DISCONNECTED = 'DRIVER_STATE_DISCONNECTED'
    CONNECTING = 'DRIVER_STATE_CONNECTING'
    DISCONNECTING = 'DRIVER_STATE_DISCONNECTING'
    CONNECTED = 'DRIVER_STATE_CONNECTED'
    ACQUIRE_SAMPLE = 'DRIVER_STATE_ACQUIRE_SAMPLE'
    UPDATE_PARAMS = 'DRIVER_STATE_UPDATE_PARAMS'
    SET = 'DRIVER_STATE_SET'
    SLEEP = 'DRIVER_STATE_SLEEP'

class DriverProtocolState(BaseEnum):
    """
    Base states for driver protocols. Subclassed for specific driver
    protocols.
    """
    AUTOSAMPLE = 'DRIVER_STATE_AUTOSAMPLE'
    TEST = 'DRIVER_STATE_TEST'
    CALIBRATE = 'DRIVER_STATE_CALIBRATE'
    COMMAND = 'DRIVER_STATE_COMMAND'
    DIRECT_ACCESS = 'DRIVER_STATE_DIRECT_ACCESS'
    UNKNOWN = 'DRIVER_STATE_UNKNOWN'
    POLL = 'DRIVER_STATE_POLL'

class DriverConnectionState(BaseEnum):
    """
    Base states for driver connections.
    """
    UNCONFIGURED = 'DRIVER_STATE_UNCONFIGURED'
    DISCONNECTED = 'DRIVER_STATE_DISCONNECTED'
    CONNECTED = 'DRIVER_STATE_CONNECTED'
    
class DriverEvent(BaseEnum):
    """
    Base events for driver state machines. Commands and other events
    are transformed into state machine events for handling.
    """
    ENTER = 'DRIVER_EVENT_ENTER'
    EXIT = 'DRIVER_EVENT_EXIT'
    INITIALIZE = 'DRIVER_EVENT_INITIALIZE'
    CONFIGURE = 'DRIVER_EVENT_CONFIGURE'
    CONNECT = 'DRIVER_EVENT_CONNECT'
    CONNECTION_LOST = 'DRIVER_CONNECTION_LOST'
    DISCONNECT = 'DRIVER_EVENT_DISCONNECT'
    SET = 'DRIVER_EVENT_SET'
    GET = 'DRIVER_EVENT_GET'
    DISCOVER = 'DRIVER_EVENT_DISCOVER'
    EXECUTE = 'DRIVER_EVENT_EXECUTE'
    ACQUIRE_SAMPLE = 'DRIVER_EVENT_ACQUIRE_SAMPLE'
    START_AUTOSAMPLE = 'DRIVER_EVENT_START_AUTOSAMPLE'
    STOP_AUTOSAMPLE = 'DRIVER_EVENT_STOP_AUTOSAMPLE'
    TEST = 'DRIVER_EVENT_TEST'
    RUN_TEST = 'DRIVER_EVENT_RUN_TEST'
    STOP_TEST = 'DRIVER_EVENT_STOP_TEST'
    CALIBRATE = 'DRIVER_EVENT_CALIBRATE'
    RESET = 'DRIVER_EVENT_RESET'
    ENTER = 'DRIVER_EVENT_ENTER'
    EXIT = 'DRIVER_EVENT_EXIT'
    UPDATE_PARAMS = 'DRIVER_EVENT_UPDATE_PARAMS'
    BREAK = 'DRIVER_EVENT_BREAK'
    EXECUTE_DIRECT = 'EXECUTE_DIRECT'    
    START_DIRECT = 'DRIVER_EVENT_START_DIRECT'
    STOP_DIRECT = 'DRIVER_EVENT_STOP_DIRECT'
    PING_DRIVER = 'DRIVER_EVENT_PING_DRIVER'
    FORCE_STATE = 'DRIVER_FORCE_STATE'
    CLOCK_SYNC = 'DRIVER_EVENT_CLOCK_SYNC'
    SCHEDULED_CLOCK_SYNC = 'DRIVER_EVENT_SCHEDULED_CLOCK_SYNC'
    ACQUIRE_STATUS = 'DRIVER_EVENT_ACQUIRE_STATUS'
    INIT_PARAMS = 'DRIVER_EVENT_INIT_PARAMS'
    GAP_RECOVERY = 'DRIVER_EVENT_GAP_RECOVERY'
    GAP_RECOVERY_COMPLETE = 'DRIVER_EVENT_GAP_RECOVERY_COMPLETE'

class DriverAsyncEvent(BaseEnum):
    """
    Asynchronous driver event types.
    """
    STATE_CHANGE = 'DRIVER_ASYNC_EVENT_STATE_CHANGE'
    CONFIG_CHANGE = 'DRIVER_ASYNC_EVENT_CONFIG_CHANGE'
    SAMPLE = 'DRIVER_ASYNC_EVENT_SAMPLE'
    ERROR = 'DRIVER_ASYNC_EVENT_ERROR'
    RESULT = 'DRIVER_ASYNC_RESULT'
    DIRECT_ACCESS = 'DRIVER_ASYNC_EVENT_DIRECT_ACCESS'
    AGENT_EVENT = 'DRIVER_ASYNC_EVENT_AGENT_EVENT'

class DriverParameter(BaseEnum):
    """
    Base driver parameters. Subclassed by specific drivers with device
    specific parameters.
    """
    ALL = 'DRIVER_PARAMETER_ALL'

class InstrumentDriver(object):
    """
    Base class for instrument drivers.
    """
        
    def __init__(self, event_callback):
        """
        Constructor.
        @param event_callback The driver process callback used to send
        asynchrous driver events to the agent.
        """
        LoggerManager()
        self._send_event = event_callback
        self._test_mode = False


    #############################################################
    # Device connection interface.
    #############################################################

    def set_test_mode(self, mode):
        """
        Enable test mode for the driver.  If this mode is envoked
        then the user has access to test_ commands.
        @param mode: test mode state
        """
        self._test_mode = True if mode else False

    def initialize(self, *args, **kwargs):
        """
        Initialize driver connection, bringing communications parameters
        into unconfigured state (no connection object).
        @raises InstrumentStateException if command not allowed in current state        
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('initialize() not implemented.')
        
    def configure(self, *args, **kwargs):
        """
        Configure the driver for communications with the device via
        port agent / logger (valid but unconnected connection object).
        @param arg[0] comms config dict.
        @raises InstrumentStateException if command not allowed in current state        
        @throws InstrumentParameterException if missing comms or invalid config dict.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('configure() not implemented.')
        
    def connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger
        (connected connection object).
        @raises InstrumentStateException if command not allowed in current state
        @throws InstrumentConnectionException if the connection failed.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('connect() not implemented.')
    
    def disconnect(self, *args, **kwargs):
        """
        Disconnect from device via port agent / logger.
        @raises InstrumentStateException if command not allowed in current state
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('disconnect() not implemented.')


    #############################################################
    # Command and control interface.
    #############################################################

    def discover_state(self, *args, **kwargs):
        """
        Determine initial state upon establishing communications.
        @param timeout=timeout Optional command timeout.        
        @retval Current device state.
        @raises InstrumentTimeoutException if could not wake device.
        @raises InstrumentStateException if command not allowed in current state or if
        device state not recognized.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('discover_state() is not implemented.')

    def get_resource_capabilities(self, *args, **kwargs):
        """
        Return driver commands and parameters.
        @param current_state True to retrieve commands available in current
        state, otherwise reutrn all commands.
        @retval list of AgentCapability objects representing the drivers
        capabilities.
        @raises NotImplementedException if not implemented by subclass.        
        """
        raise NotImplementedException('get_resource_capabilities() is not implemented.')
        
    def get_resource_state(self, *args, **kwargs):
        """
        Return the current state of the driver.
        @retval str current driver state.
        @raises NotImplementedException if not implemented by subclass.        
        """
        raise NotImplementedException('get_resource_state() is not implemented.')        

    def get_resource(self, *args, **kwargs):
        """
        Retrieve device parameters.
        @param args[0] DriverParameter.ALL or a list of parameters to retrive.
        @retval parameter : value dict.
        @raises InstrumentParameterException if missing or invalid get parameters.
        @raises InstrumentStateException if command not allowed in current state
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('get_resource() is not implemented.')

    def set_resource(self, *args, **kwargs):
        """
        Set device parameters.
        @param args[0] parameter : value dict of parameters to set.
        @param timeout=timeout Optional command timeout.
        @raises InstrumentParameterException if missing or invalid set parameters.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if set command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('set_resource() not implemented.')

    def execute_resource(self, *args, **kwargs):
        """
        Execute a driver command.
        @param timeout=timeout Optional command timeout.
        @ retval Command specific.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('execute_resource() not implemented.')

    def start_direct(self, *args, **kwargs):
        """
        Start direct access mode
        @param timeout=timeout Optional command timeout.
        @ retval Command specific.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('execute_resource() not implemented.')

    def stop_direct(self, *args, **kwargs):
        """
        Stop direct access mode
        @param timeout=timeout Optional command timeout.        
        @ retval Command specific.
        @raises NotImplementedException if not implemented by subclass.
        """
        raise NotImplementedException('execute_resource() not implemented.')

    ########################################################################
    # Event interface.
    ########################################################################

    def _driver_event(self, type, val=None):
        """
        Construct and send an asynchronous driver event.
        @param type a DriverAsyncEvent type specifier.
        @param val event value for sample and test result events.
        """
        event = {
            'type' : type,
            'value' : None,
            'time' : time.time()
        }
        if type == DriverAsyncEvent.STATE_CHANGE:
            state = self.get_resource_state()
            event['value'] = state
            self._send_event(event)
            
        elif type == DriverAsyncEvent.CONFIG_CHANGE:
            config = self.get_resource(DriverParameter.ALL)
            event['value'] = config
            self._send_event(event)
        
        elif type == DriverAsyncEvent.SAMPLE:
            event['value'] = val
            self._send_event(event)
            
        elif type == DriverAsyncEvent.ERROR:
            event['value'] = val
            self._send_event(event)

        elif type == DriverAsyncEvent.RESULT:
            event['value'] = val
            self._send_event(event)

        elif type == DriverAsyncEvent.DIRECT_ACCESS:
            event['value'] = val
            self._send_event(event)

        elif type == DriverAsyncEvent.AGENT_EVENT:
            event['value'] = val
            self._send_event(event)


    ########################################################################
    # Test interface.
    ########################################################################

    def driver_ping(self, msg):
        """
        Echo a message.
        @param msg the message to prepend and echo back to the caller.
        """
        reply = 'driver_ping: '+msg
        return reply
    
    def test_exceptions(self, msg):
        """
        Test exception handling in the driver process.
        @param msg message string to put in a raised exception to be caught in
        a test.
        @raises InstrumentExeption always.
        """
        raise InstrumentException(msg)
        
class SingleConnectionInstrumentDriver(InstrumentDriver):
    """
    Base class for instrument drivers with a single device connection.
    Provides connenction state logic for single connection drivers. This is
    the base class for the majority of driver implementation classes.
    """
    
    def __init__(self, event_callback):
        """
        Constructor for singly connected instrument drivers.
        @param event_callback Callback to the driver process to send asynchronous
        driver events back to the agent.
        """
        InstrumentDriver.__init__(self, event_callback)
        
        # The only and only instrument connection.
        # Exists in the connected state.
        self._connection = None

        # The one and only instrument protocol.
        self._protocol = None
        
        # Build connection state machine.
        self._connection_fsm = ThreadSafeFSM(DriverConnectionState,
                                                DriverEvent,
                                                DriverEvent.ENTER,
                                                DriverEvent.EXIT)
        
        # Add handlers for all events.
        self._connection_fsm.add_handler(DriverConnectionState.UNCONFIGURED, DriverEvent.ENTER, self._handler_unconfigured_enter)
        self._connection_fsm.add_handler(DriverConnectionState.UNCONFIGURED, DriverEvent.EXIT, self._handler_unconfigured_exit)
        self._connection_fsm.add_handler(DriverConnectionState.UNCONFIGURED, DriverEvent.INITIALIZE, self._handler_unconfigured_initialize)
        self._connection_fsm.add_handler(DriverConnectionState.UNCONFIGURED, DriverEvent.CONFIGURE, self._handler_unconfigured_configure)
        self._connection_fsm.add_handler(DriverConnectionState.DISCONNECTED, DriverEvent.ENTER, self._handler_disconnected_enter)
        self._connection_fsm.add_handler(DriverConnectionState.DISCONNECTED, DriverEvent.EXIT, self._handler_disconnected_exit)
        self._connection_fsm.add_handler(DriverConnectionState.DISCONNECTED, DriverEvent.INITIALIZE, self._handler_disconnected_initialize)
        self._connection_fsm.add_handler(DriverConnectionState.DISCONNECTED, DriverEvent.CONFIGURE, self._handler_disconnected_configure)
        self._connection_fsm.add_handler(DriverConnectionState.DISCONNECTED, DriverEvent.CONNECT, self._handler_disconnected_connect)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.ENTER, self._handler_connected_enter)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.EXIT, self._handler_connected_exit)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.DISCONNECT, self._handler_connected_disconnect)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.CONNECTION_LOST, self._handler_connected_connection_lost)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.DISCOVER, self._handler_connected_protocol_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.GET, self._handler_connected_protocol_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.SET, self._handler_connected_protocol_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.EXECUTE, self._handler_connected_protocol_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.FORCE_STATE, self._handler_connected_protocol_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.START_DIRECT, self._handler_connected_start_direct_event)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, DriverEvent.STOP_DIRECT, self._handler_connected_stop_direct_event)
        
            
        # Start state machine.
        self._connection_fsm.start(DriverConnectionState.UNCONFIGURED)
        
        self._pre_da_config = {}
        self._startup_config = {}
        
        # Idempotency flag for lost connections.
        # This set to false when a connection is established to
        # allow for lost callback to become activated.
        self._connection_lost = True
        
    #############################################################
    # Device connection interface.
    #############################################################

    def initialize(self, *args, **kwargs):
        """
        Initialize driver connection, bringing communications parameters
        into unconfigured state (no connection object).
        @raises InstrumentStateException if command not allowed in current state        
        """
        # Forward event and argument to the connection FSM.
        return self._connection_fsm.on_event(DriverEvent.INITIALIZE, *args, **kwargs)
        
    def configure(self, *args, **kwargs):
        """
        Configure the driver for communications with the device via
        port agent / logger (valid but unconnected connection object).
        @param arg[0] comms config dict.
        @raises InstrumentStateException if command not allowed in current state        
        @throws InstrumentParameterException if missing comms or invalid config dict.
        """
        # Forward event and argument to the connection FSM.
        return self._connection_fsm.on_event(DriverEvent.CONFIGURE, *args, **kwargs)
        
    def connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger
        (connected connection object).
        @raises InstrumentStateException if command not allowed in current state
        @throws InstrumentConnectionException if the connection failed.
        """
        # Forward event and argument to the connection FSM.
        result = self._connection_fsm.on_event(DriverEvent.CONNECT, *args, **kwargs)
        init_config = {}
        if len(args) > 0 and isinstance(args[0], dict):
            init_config = args[0]

        self.set_init_params(init_config)
        return result
    
    def disconnect(self, *args, **kwargs):
        """
        Disconnect from device via port agent / logger.
        @raises InstrumentStateException if command not allowed in current state
        """
        # Forward event and argument to the connection FSM.
        return self._connection_fsm.on_event(DriverEvent.DISCONNECT, *args, **kwargs)

    #############################################################
    # Configuration logic
    #############################################################
    def get_init_params(self):
        """
        get the driver initialization parameters
        @return driver configuration dictionary
        """
        return self._startup_config

    def set_init_params(self, config):
        """
        Set the initialization parameters down in the protocol and store the
        driver configuration in the driver.

        If the protocol hasn't been setup yet cache the config.  Next time
        this method is called, if you call it with an empty config it will
        read from the cache.

        @param config This default configuration assumes a structure driver
        configuration dict with keys named in DriverConfigKey.
        Stranger parameters can be adjusted by over riding this method.
        @raise InstrumentParameterException If the config cannot be applied
        """
        if not isinstance(config, dict):
            raise InstrumentParameterException("Incompatible initialization parameters")

        if self._protocol:
            param_config = None
            if config:
                param_config = config
            elif self._startup_config:
                param_config = self._startup_config

            if param_config:
                self._protocol.set_init_params(param_config)
                self._protocol.initialize_scheduler()

        if config:
            self._startup_config = config
    
    def apply_startup_params(self):
        """
        Apply the startup values previously stored in the protocol to
        the running config of the live instrument. The startup values are the
        values that are (1) marked as startup parameters and are (2) the "best"
        value to use at startup. Preference is given to the previously-set init
        value, then the default value, then the currently used value.

        This default implementation simply pushes the logic down into the protocol
        for processing should the action be better accomplished down there.
        
        The driver writer can decide to overload this method in the derived
        driver class and apply startup parameters in the driver (likely calling
        some get and set methods for the resource). If the driver does not
        implement an apply_startup_params() method in the driver, this method
        will call into the protocol. Deriving protocol classes are expected to
        implement an apply_startup_params() method lest they get the exception
        from the base InstrumentProtocol implementation.
        """
        log.debug("Base driver applying startup params...")
        self._protocol.apply_startup_params()
        
    def get_cached_config(self):
        """
        Return the configuration object that shows the instrument's
        configuration as cached in the protocol parameter dictionary.
        @retval The running configuration in the instruments config format. By
        default, it is a dictionary of parameter names and values.
        """
        if self._protocol:
            return self._protocol.get_cached_config()
                
    def get_config_metadata(self):
        """
        Return the configuration metadata object in JSON format
        @retval The description of the parameters, commands, and driver info
        in a JSON string
        @see https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+SV+Instrument+Driver-Agent+parameter+and+command+metadata+exchange
        """
        log.debug("Getting metadata from driver...")
        protocol = self._protocol

        # Because the config requires information from the protocol param dict
        # we temporarily instantiate a protocol object to get at the static
        # information.
        if not protocol:
            self._build_protocol()

        log.debug("Getting metadata from protocol...")
        return json.dumps(self._protocol.get_config_metadata_dict(),
                          sort_keys=True)
            
    def restore_direct_access_params(self, config):
        """
        Restore the correct values out of the full config that is given when
        returning from direct access. By default, this takes a simple dict of
        param name and value. Override this class as needed as it makes some
        simple assumptions about how your instrument sets things.
        
        @param config The configuration that was previously saved (presumably
        to disk somewhere by the driver that is working with this protocol)
        """
        vals = {}
        # for each parameter that is read only, restore
        da_params = self._protocol.get_direct_access_params()        
        for param in da_params:
            vals[param] = config[param]

        log.debug("Restore DA Parameters: %s" % vals)
        self.set_resource(vals, True)
        
    #############################################################
    # Commande and control interface.
    #############################################################

    def discover_state(self, *args, **kwargs):
        """
        Determine initial state upon establishing communications.
        @param timeout=timeout Optional command timeout.        
        @retval Current device state.
        @raises InstrumentTimeoutException if could not wake device.
        @raises InstrumentStateException if command not allowed in current state or if
        device state not recognized.
        @raises NotImplementedException if not implemented by subclass.
        """
        # Forward event and argument to the protocol FSM.
        return self._connection_fsm.on_event(DriverEvent.DISCOVER, DriverEvent.DISCOVER, *args, **kwargs)

    def get_resource_capabilities(self, current_state=True, *args, **kwargs):
        """
        Return driver commands and parameters.
        @param current_state True to retrieve commands available in current
        state, otherwise reutrn all commands.
        @retval list of AgentCapability objects representing the drivers
        capabilities.
        @raises NotImplementedException if not implemented by subclass.        
        """

        if self._protocol:
            return self._protocol.get_resource_capabilities(current_state)
        
        else:
            return [['foobb'], ['fooaa']]

                
    def get_resource_state(self, *args, **kwargs):
        """
        Return the current state of the driver.
        @retval str current driver state.
        @raises NotImplementedException if not implemented by subclass.        
        """
        connection_state = self._connection_fsm.get_current_state()
        if connection_state == DriverConnectionState.CONNECTED:
            return self._protocol.get_current_state()
        else:
            return connection_state

    def get_resource(self, *args, **kwargs):
        """
        Retrieve device parameters.
        @param args[0] DriverParameter.ALL or a list of parameters to retrive.
        @retval parameter : value dict.
        @raises InstrumentParameterException if missing or invalid get parameters.
        @raises InstrumentStateException if command not allowed in current state
        @raises NotImplementedException if not implemented by subclass.                        
        """
        # Forward event and argument to the protocol FSM.
        return self._connection_fsm.on_event(DriverEvent.GET, DriverEvent.GET, *args, **kwargs)

    def set_resource(self, *args, **kwargs):
        """
        Set device parameters.
        @param args[0] parameter : value dict of parameters to set.
        @param timeout=timeout Optional command timeout.
        @raises InstrumentParameterException if missing or invalid set parameters.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if set command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.                        
        """
        # Forward event and argument to the protocol FSM.
        return self._connection_fsm.on_event(DriverEvent.SET, DriverEvent.SET, *args, **kwargs)

    def execute_resource(self, resource_cmd, *args, **kwargs):
        """
        Poll for a sample.
        @param timeout=timeout Optional command timeout.
        @ retval Device sample dict.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if acquire command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        # Forward event and argument to the protocol FSM.
        return self._connection_fsm.on_event(DriverEvent.EXECUTE, resource_cmd, *args, **kwargs)

    def start_direct(self, *args, **kwargs):
        """
        start direct access mode
        @param timeout=timeout Optional command timeout.
        @ retval Device sample dict.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if acquire command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        # Need to pass the event as a parameter because the event handler to capture the current
        # pre-da config requires it.
        return self._connection_fsm.on_event(DriverEvent.START_DIRECT, DriverEvent.START_DIRECT)

    def execute_direct(self, *args, **kwargs):
        """
        execute direct accesscommand
        @param timeout=timeout Optional command timeout.
        @ retval Device sample dict.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if acquire command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        return self.execute_resource(DriverEvent.EXECUTE_DIRECT, *args, **kwargs)

    def stop_direct(self, *args, **kwargs):
        """
        stop direct access mode
        @param timeout=timeout Optional command timeout.
        @ retval Device sample dict.
        @raises InstrumentTimeoutException if could not wake device or no response.
        @raises InstrumentProtocolException if acquire command not recognized.
        @raises InstrumentStateException if command not allowed in current state.
        @raises NotImplementedException if not implemented by subclass.
        """
        return self._connection_fsm.on_event(DriverEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

    def test_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing 
        @param state=desired_state Required desired state to change to.
        @raises InstrumentParameterException if no state parameter.
        @raises TestModeException if not in test mode
        """

        if(not self._test_mode):
            raise TestModeException();

       # Get the required param 
        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        # We are mucking with internal FSM parameters which may be bad.
        # The alternative was to raise an event to change the state.  Dont
        # know which is better.
        self._protocol._protocol_fsm.current_state = state

    ########################################################################
    # Unconfigured handlers.
    ########################################################################

    def _handler_unconfigured_enter(self, *args, **kwargs):
        """
        Enter unconfigured state.
        """
        # Send state change event to agent.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    
    def _handler_unconfigured_exit(self, *args, **kwargs):
        """
        Exit unconfigured state.
        """
        pass

    def _handler_unconfigured_initialize(self, *args, **kwargs):
        """
        Initialize handler. We are already in unconfigured state, do nothing.
        @retval (next_state, result) tuple, (None, None).
        """
        next_state = None
        result = None
        
        return (next_state, result)

    def _handler_unconfigured_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communiations config dictionary.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful, (None, None) otherwise.
        @raises InstrumentParameterException if missing or invalid param dict.
        """
        next_state = None
        result = None

        # Get the required param dict.
        config = kwargs.get('config', None)  # via kwargs
        # TODO use kwargs as the only mechanism
        if config is None:
            try:
                config = args[0]  # via first argument
            except IndexError:
                pass

        if config is None:
            raise InstrumentParameterException('Missing comms config parameter.')

        # Verify dict and construct connection client.
        self._connection = self._build_connection(config)
        next_state = DriverConnectionState.DISCONNECTED

        return (next_state, result)

    ########################################################################
    # Disconnected handlers.
    ########################################################################

    def _handler_disconnected_enter(self, *args, **kwargs):
        """
        Enter disconnected state.
        """
        # Send state change event to agent.
        self._connection_lost = True
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_disconnected_exit(self, *args, **kwargs):
        """
        Exit disconnected state.
        """
        pass

    def _handler_disconnected_initialize(self, *args, **kwargs):
        """
        Initialize device communications. Causes the connection parameters to
        be reset.
        @retval (next_state, result) tuple, (DriverConnectionState.UNCONFIGURED,
        None).
        """
        next_state = None
        result = None
        
        self._connection = None
        next_state = DriverConnectionState.UNCONFIGURED
        
        return (next_state, result)

    def _handler_disconnected_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communiations config dictionary.
        @retval (next_state, result) tuple, (None, None).
        @raises InstrumentParameterException if missing or invalid param dict.
        """
        next_state = None
        result = None

        # Get required config param dict.
        config = kwargs.get('config', None)  # via kwargs
        # TODO use kwargs as the only mechanism
        if config is None:
            try:
                config = args[0]  # via first argument
            except IndexError:
                pass

        if config is None:
            raise InstrumentParameterException('Missing comms config parameter.')

        # Verify configuration dict, and update connection if possible.
        self._connection = self._build_connection(config)

        return (next_state, result)

    def _handler_disconnected_connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger and
        construct and intialize a protocol FSM for device interaction.
        @retval (next_state, result) tuple, (DriverConnectionState.CONNECTED,
        None) if successful.
        @raises InstrumentConnectionException if the attempt to connect failed.
        """
        next_state = None
        result = None
        self._build_protocol()
        try:
            self._connection.init_comms(self._protocol.got_data, 
                                        self._protocol.got_raw,
                                        self._got_exception,
                                        self._lost_connection_callback)
            self._protocol._connection = self._connection
            next_state = DriverConnectionState.CONNECTED
        except InstrumentConnectionException as e:
            log.error("Connection Exception: %s", e)
            log.error("Instrument Driver remaining in disconnected state.")
            # Re-raise the exception
            raise
        
        return (next_state, result)

    ########################################################################
    # Connected handlers.
    ########################################################################

    def _handler_connected_enter(self, *args, **kwargs):
        """
        Enter connected state.
        """
        # Send state change event to agent.
        self._connection_lost = False
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_connected_exit(self, *args, **kwargs):
        """
        Exit connected state.
        """
        pass

    def _handler_connected_disconnect(self, *args, **kwargs):
        """
        Disconnect to the device via port agent / logger and destroy the
        protocol FSM.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful.
        """
        next_state = None
        result = None
        
        log.info("_handler_connected_disconnect: invoking stop_comms().")
        self._connection.stop_comms()
        self._protocol = None
        next_state = DriverConnectionState.DISCONNECTED
        
        return (next_state, result)

    def _handler_connected_connection_lost(self, *args, **kwargs):
        """
        The device connection was lost. Stop comms, destroy protocol FSM and
        revert to disconnected state.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None).
        """
        next_state = None
        result = None
        
        log.info("_handler_connected_connection_lost: invoking stop_comms().")
        self._connection.stop_comms()
        self._protocol = None
        
        # Send async agent state change event.
        log.info("_handler_connected_connection_lost: sending LOST_CONNECTION " \
                 "event, moving to DISCONNECTED state.")
        self._driver_event(DriverAsyncEvent.AGENT_EVENT,
                           ResourceAgentEvent.LOST_CONNECTION)
         
        next_state = DriverConnectionState.DISCONNECTED
        
        return (next_state, result)

    def _handler_connected_protocol_event(self, event, *args, **kwargs):
        """
        Forward a driver command event to the protocol FSM.
        @param args positional arguments to pass on.
        @param kwargs keyword arguments to pass on.
        @retval (next_state, result) tuple, (None, protocol result).
        """
        next_state = None
        result = self._protocol._protocol_fsm.on_event(event, *args, **kwargs)
        return (next_state, result)

    def _handler_connected_start_direct_event(self, event, *args, **kwargs):
        """
        Stash the current config first, then forward a driver command event
        to the protocol FSM.
        @param args positional arguments to pass on.
        @param kwargs keyword arguments to pass on.
        @retval (next_state, result) tuple, (None, protocol result).
        """
        next_state = None

        # Get the value for all direct access parameters and store them in the protocol
        self._pre_da_config = self.get_resource(self._protocol.get_direct_access_params())
        self._protocol.store_direct_access_config(self._pre_da_config)
        self._protocol.enable_da_initialization()
        log.debug("starting DA.  Storing DA parameters for restore: %s", self._pre_da_config)

        result = self._protocol._protocol_fsm.on_event(event, *args, **kwargs)
        return (next_state, result)
    
    def _handler_connected_stop_direct_event(self, event, *args, **kwargs):
        """
        Restore previous config first, then forward a driver command event
        to the protocol FSM.
        @param args positional arguments to pass on.
        @param kwargs keyword arguments to pass on.
        @retval (next_state, result) tuple, (None, protocol result).
        """
        next_state = None
        result = self._protocol._protocol_fsm.on_event(event, *args, **kwargs)

        # Moving the responsibility for applying DA parameters to the
        # protocol.
        #self.restore_direct_access_params(self._pre_da_config)

        return (next_state, result)

    ########################################################################
    # Helpers.
    ########################################################################
    
    def _build_connection(self, config):
        """
        Constructs and returns a Connection object according to the given
        configuration. The connection object is a LoggerClient instance in
        this base class. Subclasses can overwrite this operation as needed.
        The value returned by this operation is assigned to self._connection
        and also to self._protocol._connection upon entering in the
        DriverConnectionState.CONNECTED state.

        @param config configuration dict

        @retval a Connection instance, which will be assigned to
                  self._connection

        @throws InstrumentParameterException Invalid configuration.
        """
        if 'mock_port_agent' in config:
            mock_port_agent = config['mock_port_agent']
            # check for validity here...
            if (mock_port_agent is not None):
                return mock_port_agent
        try:
            addr = config['addr']
            port = config['port']
            cmd_port = config.get('cmd_port')

            if isinstance(addr, str) and isinstance(port, int) and len(addr)>0:
                return PortAgentClient(addr, port, cmd_port)
            else:
                raise InstrumentParameterException('Invalid comms config dict.')

        except (TypeError, KeyError):
            raise InstrumentParameterException('Invalid comms config dict.')

    def _got_exception(self, exception):
        """
        Callback for the client for exception handling with async data.  Exceptions
        are wrapped in an event and sent up to the agent.
        """
        try:
            log.error("ASYNC Data Exception Detected: %s (%s)", exception.__class__.__name__, str(exception))
        finally:
            self._driver_event(DriverAsyncEvent.ERROR, exception)

    def _lost_connection_callback(self, error_string):
        """
        A callback invoked by the port agent client when it looses
        connectivity to the port agent.
        """
        
        if not self._connection_lost:
            log.info("_lost_connection_callback: starting thread to send " \
                     "CONNECTION_LOST event to instrument driver.")
            self._connection_lost = True
            lost_comms_thread = Thread(
                target=self._connection_fsm.on_event,
                args=(DriverEvent.CONNECTION_LOST, ))
            lost_comms_thread.start()
        else:
            log.info("_lost_connection_callback: connection_lost flag true.")
            
            
    def _build_protocol(self):
        """
        Construct device specific single connection protocol FSM.
        Overridden in device specific subclasses.
        """
        pass
                
            
