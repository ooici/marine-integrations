"""
@package mi.instrument.harvard.massp.ooicore.driver
@file marine-integrations/mi/instrument/harvard/massp/ooicore/driver.py
@author Peter Cable
@brief Driver for the ooicore
Release notes:

Driver for the MASSP in-situ mass spectrometer
"""

import functools
import time

import mi.core.log
from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.port_agent_client import PortAgentClient
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.instrument_protocol import InstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.common import BaseEnum, Units
from mi.core.exceptions import InstrumentParameterException, InstrumentProtocolException
from mi.core.exceptions import InstrumentConnectionException
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.instrument.harvard.massp.common import MASSP_STATE_ERROR, MASSP_CLEAR_ERROR
import mi.instrument.harvard.massp.mcu.driver as mcu
import mi.instrument.harvard.massp.rga.driver as rga
import mi.instrument.harvard.massp.turbo.driver as turbo


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = mi.core.log.get_logger()
META_LOGGER = mi.core.log.get_logging_metaclass()


###
#    Driver Constant Definitions
###
NEWLINE = '\r'
MASTER = 'massp'
RGA = 'rga'
TURBO = 'turbo'
MCU = 'mcu'
DA_COMMAND_DELIMITER = ':'
DA_EXIT_MAX_RETRIES = 3


class DataParticleType(mcu.DataParticleType, turbo.DataParticleType, rga.DataParticleType):
    """
    Data particle types produced by this driver
    """


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    POLL = DriverProtocolState.POLL
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    CALIBRATE = DriverProtocolState.CALIBRATE
    REGEN = 'PROTOCOL_STATE_REGEN'
    ERROR = MASSP_STATE_ERROR
    MANUAL_OVERRIDE = 'PROTOCOL_STATE_MANUAL_OVERRIDE'


class ProtocolEvent(mcu.ProtocolEvent, turbo.ProtocolEvent, rga.ProtocolEvent):
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
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CALIBRATE = DriverEvent.CALIBRATE
    STOP = 'PROTOCOL_EVENT_STOP'
    START_NAFION = 'PROTOCOL_EVENT_START_NAFION_REGEN'
    START_ION = 'PROTOCOL_EVENT_START_ION_REGEN'
    ERROR = 'PROTOCOL_EVENT_ERROR'
    CLEAR = MASSP_CLEAR_ERROR
    POWEROFF = 'PROTOCOL_EVENT_POWEROFF'
    STOP_REGEN = 'PROTOCOL_EVENT_STOP_REGEN'
    START_MANUAL = 'PROTOCOL_EVENT_START_MANUAL_OVERRIDE'
    STOP_MANUAL = 'PROTOCOL_EVENT_STOP_MANUAL_OVERRIDE'
    GET_SLAVE_STATES = 'PROTOCOL_EVENT_GET_SLAVE_STATES'
    REGEN_COMPLETE = 'PROTOCOL_EVENT_REGEN_COMPLETE'


class Capability(mcu.Capability, turbo.Capability, rga.Capability):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CALIBRATE = ProtocolEvent.CALIBRATE
    START_NAFION = ProtocolEvent.START_NAFION
    START_ION = ProtocolEvent.START_ION
    CLEAR = ProtocolEvent.CLEAR
    POWEROFF = ProtocolEvent.POWEROFF
    STOP_REGEN = ProtocolEvent.STOP_REGEN
    START_MANUAL = ProtocolEvent.START_MANUAL
    STOP_MANUAL = ProtocolEvent.STOP_MANUAL
    GET_SLAVE_STATES = ProtocolEvent.GET_SLAVE_STATES


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    SAMPLE_INTERVAL = 'massp_sample_interval'


class SlaveProtocol(BaseEnum):
    """
    Names for the slave protocols
    """
    TURBO = TURBO
    RGA = RGA
    MCU = MCU


class ScheduledJob(BaseEnum):
    """
    Scheduled jobs in this driver
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE


###############################################################################
# Driver
###############################################################################

# noinspection PyProtectedMember,PyMethodMayBeStatic
class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    __metaclass__ = META_LOGGER

    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
        self._slave_protocols = {}

    ########################################################################
    # Disconnected handlers.
    ########################################################################

    def _handler_disconnected_connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger and
        construct and initialize a protocol FSM for device interaction.
        @return (next_state, result) tuple, (DriverConnectionState.CONNECTED, None) if successful.
        @raises InstrumentConnectionException if the attempt to connect failed.
        """
        self._build_protocol()
        try:
            for name, connection in self._connection.items():
                connection.init_comms(self._slave_protocols[name].got_data,
                                      self._slave_protocols[name].got_raw,
                                      self._got_exception,
                                      self._lost_connection_callback)
                self._slave_protocols[name]._connection = connection
        except InstrumentConnectionException as e:
            log.error("Connection Exception: %s", e)
            log.error("Instrument Driver remaining in disconnected state.")
            # Re-raise the exception
            raise
        log.debug('_handler_disconnected_connect exit')
        return DriverConnectionState.CONNECTED, None

    ########################################################################
    # Connected handlers.
    ########################################################################

    def _handler_connected_disconnect(self, *args, **kwargs):
        """
        Disconnect to the device via port agent / logger and destroy the protocol FSM.
        @returns: (next_state, result) tuple, (DriverConnectionState.DISCONNECTED, None) if successful.
        """
        for connection in self._connection.values():
            connection.stop_comms()
        self._protocol = None
        self._slave_protocols = {}
        return DriverConnectionState.DISCONNECTED, None

    def _handler_connected_connection_lost(self, *args, **kwargs):
        """
        The device connection was lost. Stop comms, destroy protocol FSM and revert to disconnected state.
        @returns: (next_state, result) tuple, (DriverConnectionState.DISCONNECTED, None).
        """
        for connection in self._connection.values():
            connection.stop_comms()
        self._protocol = None
        self._slave_protocols = {}

        # Send async agent state change event.
        log.info("_handler_connected_connection_lost: sending LOST_CONNECTION "
                 "event, moving to DISCONNECTED state.")
        self._driver_event(DriverAsyncEvent.AGENT_EVENT,
                           ResourceAgentEvent.LOST_CONNECTION)

        return DriverConnectionState.DISCONNECTED, None

    ########################################################################
    # Helpers.
    ########################################################################

    def _build_connection(self, all_configs):
        """
        Constructs and returns a Connection object according to the given
        configuration. The connection object is a LoggerClient instance in
        this base class. Subclasses can overwrite this operation as needed.
        The value returned by this operation is assigned to self._connections
        and also to self._protocol._connection upon entering in the
        DriverConnectionState.CONNECTED state.

        @param all_configs configuration dict
        @returns a dictionary of Connection instances, which will be assigned to self._connection
        @throws InstrumentParameterException Invalid configuration.
        """
        connections = {}
        for name, config in all_configs.items():
            if not isinstance(config, dict):
                continue
            if 'mock_port_agent' in config:
                mock_port_agent = config['mock_port_agent']
                # check for validity here...
                if mock_port_agent is not None:
                    connections[name] = mock_port_agent
            else:
                try:
                    addr = config['addr']
                    port = config['port']
                    cmd_port = config.get('cmd_port')

                    if isinstance(addr, str) and isinstance(port, int) and len(addr) > 0:
                        connections[name] = PortAgentClient(addr, port, cmd_port)
                    else:
                        raise InstrumentParameterException('Invalid comms config dict.')

                except (TypeError, KeyError):
                    raise InstrumentParameterException('Invalid comms config dict.')
        return connections

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(self._driver_event)
        callbacks = {}
        for name in SlaveProtocol.list():
            callbacks[name] = functools.partial(self._protocol._slave_protocol_event, name=name)

        self._slave_protocols[MCU] = mcu.Protocol(mcu.Prompt, NEWLINE, callbacks[MCU])
        self._slave_protocols[RGA] = rga.Protocol(rga.Prompt, NEWLINE, callbacks[RGA])
        self._slave_protocols[TURBO] = turbo.Protocol(turbo.Prompt, NEWLINE, callbacks[TURBO])

        for name in SlaveProtocol.list():
            self._protocol.register_slave_protocol(name, self._slave_protocols[name])

        # build the dynamic event handlers for manual override
        self._protocol._add_manual_override_handlers()


###########################################################################
# Protocol
###########################################################################

# noinspection PyMethodMayBeStatic,PyUnusedLocal,PyProtectedMember
class Protocol(InstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    __metaclass__ = META_LOGGER

    def __init__(self, driver_event):
        """
        Protocol constructor.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        InstrumentProtocol.__init__(self, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_start_poll),
                (ProtocolEvent.CALIBRATE, self._handler_command_start_calibrate),
                (ProtocolEvent.START_NAFION, self._handler_command_start_nafion_regen),
                (ProtocolEvent.START_ION, self._handler_command_start_ion_regen),
                (ProtocolEvent.ERROR, self._handler_error),
                (ProtocolEvent.POWEROFF, self._handler_command_poweroff),
                (ProtocolEvent.START_MANUAL, self._handler_command_start_manual),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.ACQUIRE_SAMPLE, self._handler_autosample_acquire_sample),
                (ProtocolEvent.STOP, self._handler_stop_generic),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_stop_generic),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.POLL: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP, self._handler_stop_generic),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.ERROR: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.CLEAR, self._handler_error_clear),
            ],
            ProtocolState.CALIBRATE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP, self._handler_stop_generic),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.REGEN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_REGEN, self._handler_stop_regen),
                (ProtocolEvent.REGEN_COMPLETE, self._handler_regen_complete),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            ],
            ProtocolState.MANUAL_OVERRIDE: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_MANUAL, self._handler_manual_override_stop),
                (ProtocolEvent.GET_SLAVE_STATES, self._handler_manual_get_slave_states),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._slave_protocols = {}
        self.initialize_scheduler()

    def _add_manual_override_handlers(self):
        for slave in self._slave_protocols:
            for event in self._slave_protocols[slave]._cmd_dict._cmd_dict:
                self._protocol_fsm.add_handler(ProtocolState.MANUAL_OVERRIDE,
                                               event, self._build_override_handler(slave, event))

    def _build_override_handler(self, slave, event):
        log.debug('Building event handler for protocol: %s event: %s', slave, event)

        def inner():
            return None, self._slave_protocols[slave]._protocol_fsm.on_event(event)
        return inner

    def register_slave_protocol(self, name, protocol):
        """
        @param name: slave protocol name
        @param protocol: slave protocol instance
        @return: None
        """
        self._slave_protocols[name] = protocol

    def _slave_protocol_event(self, event, *args, **kwargs):
        """
        Handle an event from a slave protocol.
        @param event: event to be processed
        """
        name = kwargs.get('name')
        if name is not None and name in self._slave_protocols:
            # only react to slave protocol events once we have transitioned out of unknown
            if self.get_current_state() != ProtocolState.UNKNOWN or event == DriverAsyncEvent.ERROR:
                if event == DriverAsyncEvent.STATE_CHANGE:
                    self._react()
                elif event == DriverAsyncEvent.CONFIG_CHANGE:
                    # do nothing, we handle this ourselves in set_param
                    pass
                else:
                    # pass the event up to the instrument agent
                    log.debug('Passing event up to the Instrument agent: %r %r %r', event, args, kwargs)
                    self._driver_event(event, *args)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        self._param_dict.add(Parameter.SAMPLE_INTERVAL, '', None, int,
                             type=ParameterDictType.INT,
                             display_name='Autosample Interval',
                             description='Interval between sample starts during autosample state',
                             units=Units.SECOND)

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.ACQUIRE_SAMPLE, display_name="Acquire one sample")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="Start autosample")
        self._cmd_dict.add(Capability.CALIBRATE, display_name="Acquire calibration samples")
        self._cmd_dict.add(Capability.START_ION, display_name="Start the ion chamber regeneration sequence")
        self._cmd_dict.add(Capability.START_NAFION, display_name="Start the nafion regeneration sequence")
        self._cmd_dict.add(Capability.STOP_REGEN, display_name="Stop the current regeneration sequence")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="Stop autosample")
        self._cmd_dict.add(Capability.POWEROFF, display_name='Issue the "Power Off" command to the instrument')
        self._cmd_dict.add(Capability.GET_SLAVE_STATES,
                           display_name='Report the states of the underlying slave protocols')

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _react(self):
        """
        Determine if an action is necessary based on the states of the slave protocols.

            (MCU STATE, TURBO STATE, RGA STATE) : (TARGET, EVENT)

        The specified event will be sent to the specified target.
        """
        state = self.get_current_state()
        slave_states = self._get_slave_states()

        if MASSP_STATE_ERROR in slave_states:
            return self._error()

        if state == ProtocolState.REGEN and slave_states[0] == ProtocolState.COMMAND:
            self._async_raise_fsm_event(ProtocolEvent.REGEN_COMPLETE)

        # these actions are only applicable in POLL, AUTOSAMPLE or CALIBRATE states
        if state not in [ProtocolState.POLL, ProtocolState.AUTOSAMPLE, ProtocolState.CALIBRATE]:
            return

        mps = mcu.ProtocolState
        tps = turbo.ProtocolState
        rps = rga.ProtocolState
        action_map = {
            # Waiting Turbo (RGA is off)
            (mps.WAITING_TURBO, tps.COMMAND, rps.COMMAND): (TURBO, turbo.Capability.START_TURBO),
            (mps.WAITING_TURBO, tps.AT_SPEED, rps.COMMAND): (MCU, mcu.Capability.START2),

            # Waiting RGA
            (mps.WAITING_RGA, tps.AT_SPEED, rps.SCAN): (MCU, mcu.Capability.SAMPLE),
            (mps.WAITING_RGA, tps.AT_SPEED, rps.COMMAND): (RGA, rga.Capability.START_SCAN),
            (mps.WAITING_RGA, tps.COMMAND, rps.SCAN): (RGA, rga.Capability.STOP_SCAN),  # this should never happen!
            (mps.WAITING_RGA, tps.COMMAND, rps.COMMAND): (MCU, mcu.Capability.STANDBY),  # this should never happen!

            # Stopping
            (mps.STOPPING, tps.AT_SPEED, rps.SCAN): (RGA, rga.Capability.STOP_SCAN),
            (mps.STOPPING, tps.AT_SPEED, rps.COMMAND): (TURBO, turbo.Capability.STOP_TURBO),
            (mps.STOPPING, tps.COMMAND, rps.SCAN): (RGA, rga.Capability.STOP_SCAN),  # this should never happen!
            (mps.STOPPING, tps.COMMAND, rps.COMMAND): (MCU, mcu.Capability.STANDBY),
        }

        action = action_map.get(self._get_slave_states())

        if action is not None:
            if not isinstance(action, list):
                action = [action]

            # iterate through the action list, sending the events to the targets
            # if we are in POLL or CALIBRATE and we see a STANDBY event, return this driver to COMMAND.
            for target, command in action:
                if command == mcu.Capability.SAMPLE and state == ProtocolState.CALIBRATE:
                    command = mcu.Capability.CALIBRATE
                if command == mcu.Capability.STANDBY and state in [ProtocolState.CALIBRATE, ProtocolState.POLL]:
                    self._send_event_to_slave(target, command)
                    self._async_raise_fsm_event(ProtocolEvent.STOP)
                else:
                    self._send_event_to_slave(target, command)
        return action

    def _error(self):
        """
        Handle error state in slave protocol
        """
        state = self.get_current_state()
        slave_states = self._get_slave_states()

        # if we are not currently in the error state, make the transition
        if state != ProtocolState.ERROR:
            self._async_raise_fsm_event(ProtocolEvent.ERROR)
        mcu_state, turbo_state, rga_state = slave_states

        # before we do anything else, the RGA must be stopped.
        if rga_state not in [rga.ProtocolState.COMMAND, rga.ProtocolState.ERROR]:
            self._send_event_to_slave(RGA, rga.ProtocolEvent.STOP_SCAN)
        # RGA must be in COMMAND or ERROR, the TURBO must be stopped.
        elif turbo_state not in [turbo.ProtocolState.COMMAND, turbo.ProtocolState.SPINNING_DOWN]:
            self._send_event_to_slave(TURBO, turbo.ProtocolEvent.STOP_TURBO)
        # Turbo and RGA must be in COMMAND or ERROR, stop the MCU
        elif mcu_state != mcu.ProtocolState.COMMAND:
            self._send_event_to_slave(MCU, mcu.ProtocolEvent.STANDBY)

    def _got_chunk(self, chunk):
        """
        This driver has no chunker...
        """

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        @param events: Events to be filtered
        @return: list of events which are also capabilities
        """
        return [x for x in events if Capability.has(x) or mcu.Capability.has(x)
                or turbo.Capability.has(x) or rga.Capability.has(x)]

    def _get_slave_states(self):
        """
        Retrieve the current protocol state from each of the slave protocols and return them as a tuple.
        """
        return (
            self._slave_protocols[MCU].get_current_state(),
            self._slave_protocols[TURBO].get_current_state(),
            self._slave_protocols[RGA].get_current_state(),
        )

    def _send_event_to_all(self, event):
        """
        Send the same event to all slave protocols.
        @return: List of (name, result) for a slave protocols
        """
        return [(name, slave._protocol_fsm.on_event(event)) for name, slave in self._slave_protocols.items()]

    def _send_event_to_slave(self, name, event):
        """
        Send an event to a specific protocol
        @param name: Name of slave protocol
        @param event: Event to be sent
        """
        slave_protocol = self._slave_protocols.get(name)
        if slave_protocol is None:
            raise InstrumentProtocolException('Attempted to send event to non-existent protocol: %s' % name)
        slave_protocol._async_raise_fsm_event(event)

    def _send_massp_direct_access(self, command):
        """
        Handle a direct access command.  Driver expects direct access commands to specify the target
        using the following format:

        target:command

        It then routes the command to the appropriate slave protocol.
        @param command: Direct access command received
        """
        err_string = 'Invalid command.  Command must be in the following format: "target:command' + NEWLINE + \
                     'Valid targets are: %r' % self._slave_protocols.keys()
        try:
            target, command = command.split(DA_COMMAND_DELIMITER, 1)
            target = target.lower()
        except ValueError:
            target = None

        log.debug('_do_cmd_direct - target: %s command: %r', target, command)

        if target not in self._slave_protocols:
            self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, err_string)
        else:
            self._slave_protocols[target]._protocol_fsm.on_event(ProtocolEvent.EXECUTE_DIRECT, command)

    def _set_params(self, *args, **kwargs):
        """
        Set one or more parameters.  This method will determine where the parameter actually resides and
        forward it to the appropriate parameter dictionary based on name.
        @param args: arglist which must contain a parameter dictionary
        @throws InstrumentParameterException
        """
        params = args[0]

        if not isinstance(params, dict):
            raise InstrumentParameterException('Attempted to set parameters with a non-dictionary argument')

        _, old_config = self._handler_command_get([Parameter.ALL])

        temp_dict = {}
        for key in params:
            split_key = key.split('_', 1)
            if len(split_key) == 1:
                raise InstrumentParameterException('Missing target in MASSP parameter: %s' % key)
            target = split_key[0]
            if not target in self._slave_protocols:
                # this is a master driver parameter, set it here
                if key in self._param_dict.get_keys():
                    log.debug("Setting value for %s to %s", key, params[key])
                    self._param_dict.set_value(key, params[key])
                else:
                    raise InstrumentParameterException('Invalid key in SET action: %s' % key)
            else:
                temp_dict.setdefault(target, {})[key] = params[key]

        # set parameters for slave protocols
        for name in temp_dict:
            if name in self._slave_protocols:
                self._slave_protocols[name]._set_params(temp_dict[name])
            else:
                # how did we get here?  This should never happen, but raise an exception if it does.
                raise InstrumentParameterException('Invalid key(s) in SET action: %r' % temp_dict[name])

        _, new_config = self._handler_command_get([Parameter.ALL])

        if not new_config == old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def set_init_params(self, config):
        """
        Set initial parameters.  Parameters are forwarded to the appropriate parameter dictionary based on name.
        @param config: Init param config to be handled
        """
        temp_dict = {}
        self._startup_config = config
        config = config.get(DriverConfigKey.PARAMETERS, {})
        for key in config:
            target, _ = key.split('_', 1)
            if not target in self._slave_protocols:
                # master driver parameter
                log.debug("Setting init value for %s to %s", key, config[key])
                self._param_dict.set_init_value(key, config[key])
            else:
                temp_dict.setdefault(target, {})[key] = config[key]

        for name in temp_dict:
            if name in self._slave_protocols:
                self._slave_protocols[name].set_init_params({DriverConfigKey.PARAMETERS: temp_dict[name]})
            else:
                # how did we get here?  This should never happen, but raise an exception if it does.
                raise InstrumentParameterException('Invalid key(s) in INIT PARAMS action: %r' % temp_dict[name])

    def get_config_metadata_dict(self):
        """
        See base class for full description.  This method is overridden to retrieve the parameter
        dictionary from each slave protocol and merge them.
        @return: dictionary containing driver metadata
        """
        log.debug("Getting metadata dict from protocol...")
        return_dict = {ConfigMetadataKey.DRIVER: self._driver_dict.generate_dict(),
                       ConfigMetadataKey.COMMANDS: self._cmd_dict.generate_dict(),
                       ConfigMetadataKey.PARAMETERS: self._param_dict.generate_dict()}

        for protocol in self._slave_protocols.values():
            return_dict[ConfigMetadataKey.PARAMETERS].update(protocol._param_dict.generate_dict())
            return_dict[ConfigMetadataKey.COMMANDS].update(protocol._cmd_dict.generate_dict())

        return return_dict

    def get_resource_capabilities(self, current_state=True):
        """
        Overrides base class to include slave protocol parameters
        @param current_state: Boolean indicating whether we should return only the current state events
        @return: (resource_commands, resource_parameters)
        """
        res_cmds = self._protocol_fsm.get_events(current_state)
        res_cmds = self._filter_capabilities(res_cmds)
        res_params = self._param_dict.get_keys()

        for protocol in self._slave_protocols.values():
            res_params.extend(protocol._param_dict.get_keys())

        return res_cmds, res_params

    def _build_scheduler(self):
        """
        Build a scheduler for periodic status updates
        """
        job_name = ScheduledJob.ACQUIRE_SAMPLE
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.SAMPLE_INTERVAL)
                    },
                }
            }
        }

        self.set_init_params(config)
        self._add_scheduler_event(ScheduledJob.ACQUIRE_SAMPLE, ProtocolEvent.ACQUIRE_SAMPLE)

    def _delete_scheduler(self):
        """
        Remove the autosample schedule.
        """
        try:
            self._remove_scheduler(ScheduledJob.ACQUIRE_SAMPLE)
        except KeyError:
            log.info('Failed to remove scheduled job for ACQUIRE_SAMPLE')

    ########################################################################
    # Generic handlers.
    ########################################################################
    def _handler_generic_enter(self, *args, **kwargs):
        """
        Generic enter handler, raise STATE CHANGE
        """
        if self.get_current_state() != ProtocolState.UNKNOWN:
            self._init_params()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_generic_exit(self, *args, **kwargs):
        """
        Generic exit handler, do nothing.
        """

    def _handler_stop_generic(self, *args, **kwargs):
        """
        Generic stop method to return to COMMAND (via POLL if appropriate)
        @return next_state, (next_agent_state, None)
        """
        self._delete_scheduler()

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        # check if we are in autosample AND currently taking a sample, if so, move to POLL
        # otherwise go back to COMMAND.
        if self.get_current_state() == ProtocolState.AUTOSAMPLE:
            if self._get_slave_states() != (ProtocolState.COMMAND, ProtocolState.COMMAND, ProtocolState.COMMAND):
                next_state = ProtocolState.POLL
                next_agent_state = ResourceAgentState.BUSY

        # notify the agent we have changed states
        self._async_agent_state_change(next_agent_state)
        return next_state, (next_agent_state, None)

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @return (next_state, next_agent_state)
        """
        result = self._send_event_to_all(ProtocolEvent.DISCOVER)
        log.debug('_handler_unknown_discover -- send DISCOVER to all: %r', result)
        target_state = (ProtocolState.COMMAND, ProtocolState.COMMAND, ProtocolState.COMMAND)
        success = False
        # wait for the slave protocols to discover
        for attempt in xrange(5):
            slave_states = self._get_slave_states()
            if slave_states == target_state:
                success = True
                break
            time.sleep(1)
        if not success:
            return ProtocolState.ERROR, ResourceAgentState.IDLE
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter.  Query this protocol plus all slave protocols.
        @param args: arglist which should contain a list of parameters to get
        @return None, results
        """
        params = args[0]

        if not isinstance(params, list):
            params = [params]

        temp_dict = {}
        result_dict = {}

        # request is for all parameters, send get(ALL) to each protocol then combine the results.
        if Parameter.ALL in params:
            params = [Parameter.ALL]
            _, result = self._handler_get(params, **kwargs)
            result_dict.update(result)
            for protocol in self._slave_protocols.values():
                _, result = protocol._handler_get(params, **kwargs)
                result_dict.update(result)

        # request is for specific parameters.  Determine which protocol should service each,
        # call the appropriate _handler_get and combine the results
        else:
            for key in params:
                log.debug('about to split: %s', key)
                target, _ = key.split('_', 1)
                temp_dict.setdefault(target, []).append(key)
            for key in temp_dict:
                if key == MASTER:
                    _, result = self._handler_get(params, **kwargs)
                else:
                    if key in self._slave_protocols:
                        _, result = self._slave_protocols[key]._handler_get(params, **kwargs)
                    else:
                        raise InstrumentParameterException('Invalid key(s) in GET action: %r' % temp_dict[key])
                result_dict.update(result)

        return None, result_dict

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter, just pass through to _set_params, which knows how to set the params
        in the slave protocols.
        """
        self._set_params(*args, **kwargs)
        return None, None

    def _handler_command_start_direct(self):
        """
        Start direct access
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_autosample(self):
        """
        Move my FSM to autosample and start the sample sequence by sending START1 to the MCU.
        Create the scheduler to automatically start the next sample sequence
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.START1)
        self._build_scheduler()
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_poll(self):
        """
        Move my FSM to poll and start the sample sequence by sending START1 to the MCU
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.START1)
        return ProtocolState.POLL, (ResourceAgentState.BUSY, None)

    def _handler_command_start_calibrate(self):
        """
        Move my FSM to calibrate and start the calibrate sequence by sending START1 to the MCU
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.START1)
        return ProtocolState.CALIBRATE, (ResourceAgentState.BUSY, None)

    def _handler_command_start_nafion_regen(self):
        """
        Move my FSM to NAFION_REGEN and send NAFION_REGEN to the MCU
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.NAFREG)
        return ProtocolState.REGEN, (ResourceAgentState.BUSY, None)

    def _handler_command_start_ion_regen(self):
        """
        Move my FSM to ION_REGEN and send ION_REGEN to the MCU
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.IONREG)
        return ProtocolState.REGEN, (ResourceAgentState.BUSY, None)

    def _handler_command_poweroff(self):
        """
        Send POWEROFF to the MCU
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.POWEROFF)
        return None, (None, None)

    def _handler_command_start_manual(self):
        """
        Move FSM to MANUAL OVERRIDE state
        @return next_state, (next_agent_state, result)
        """
        return ProtocolState.MANUAL_OVERRIDE, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Error handlers.
    ########################################################################

    def _handler_error(self):
        """
        @return next_state, next_agent_state
        """
        return ProtocolState.ERROR, ResourceAgentState.BUSY

    def _handler_error_clear(self):
        """
        Send the CLEAR event to any slave protocol in the error state and return this driver to COMMAND
        @return next_state, (next_agent_state, result)
        """
        for protocol in self._slave_protocols:
            state = protocol.get_current_state()
            if state == MASSP_STATE_ERROR:
                # do this synchronously, to allow each slave protocol to complete the CLEAR action
                # before transitioning states.
                protocol._protocol_fsm.on_event(ProtocolEvent.CLEAR)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_acquire_sample(self):
        """
        Fire off a sample sequence while in the autosample state.
        @return None, None
        @throws InstrumentProtocolException
        """
        slave_states = self._get_slave_states()
        # verify the MCU is not already in a sequence
        if slave_states[0] == ProtocolState.COMMAND:
            result = self._send_event_to_slave(MCU, mcu.Capability.START1)
        else:
            raise InstrumentProtocolException("Attempted to acquire sample while sampling")
        return None, None

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.  Forward to all slave protocols.
        """
        self._send_event_to_all(ProtocolEvent.START_DIRECT)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.  Check slave protocol states and verify they all
        return to COMMAND, otherwise raise InstrumentProtocolException.
        @throws InstrumentProtocolException
        """
        for attempt in range(DA_EXIT_MAX_RETRIES):
            slave_states = self._get_slave_states()
            if ProtocolState.DIRECT_ACCESS in slave_states:
                log.error('Slave protocol failed to return to command, attempt %d', attempt)
                time.sleep(1)
            else:
                return

        raise InstrumentProtocolException('Slave protocol never returned to command from DA.')

    def _handler_direct_access_execute_direct(self, data):
        """
        Execute a direct access command.  For MASSP, this means passing the actual command to the
        correct slave protocol.  This is handled by _send_massp_direct_access.
        @return next_state, (next_agent_state, result)
        """
        self._send_massp_direct_access(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_all(ProtocolEvent.STOP_DIRECT)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Regen handlers.
    ########################################################################

    def _handler_stop_regen(self):
        """
        Abort the current regeneration sequence, return to COMMAND
        @return next_state, (next_agent_state, result)
        """
        self._send_event_to_slave(MCU, mcu.Capability.STANDBY)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_regen_complete(self):
        """
        Regeneration sequence is complete, return to COMMAND
        @return next_state, (next_agent_state, result)
        """
        self._async_agent_state_change(ResourceAgentState.COMMAND)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_manual_override_stop(self):
        """
        Exit manual override.  Attempt to bring the slave drivers back to COMMAND.
        """
        mcu_state, turbo_state, rga_state = self._get_slave_states()
        if rga_state == rga.ProtocolState.SCAN:
            self._slave_protocols[RGA]._protocol_fsm.on_event(rga.Capability.STOP_SCAN)
        if turbo_state == turbo.ProtocolState.AT_SPEED:
            self._slave_protocols[TURBO]._protocol_fsm.on_event(turbo.Capability.STOP_TURBO)
        while rga_state not in [rga.ProtocolState.COMMAND, rga.ProtocolState.ERROR] or \
                turbo_state not in [turbo.ProtocolState.COMMAND, turbo.ProtocolState.ERROR]:
            time.sleep(.1)
            mcu_state, turbo_state, rga_state = self._get_slave_states()
        if mcu_state != mcu.ProtocolState.COMMAND:
            self._slave_protocols[MCU]._protocol_fsm.on_event(mcu.Capability.STANDBY)

        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    def _handler_manual_get_slave_states(self):
        """
        Get the slave states and return them to the user
        @return: next_state, (next_agent_state, result)
        """
        mcu_state, turbo_state, rga_state = self._get_slave_states()
        return None, (None, {MCU: mcu_state, RGA: rga_state, TURBO: turbo_state})
