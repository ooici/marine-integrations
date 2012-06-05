#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/driver.py
@author Carlos Rueda
@brief VADCP driver implementation
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    EOLN, ClientException, TimeoutException
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import VadcpClient

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException

import logging
from mi.core.mi_logger import mi_logger as log

####################################################################
# Module-wide values
####################################################################

# TODO define Packet config for data granules.
PACKET_CONFIG = {}


class DriverState(BaseEnum):
    """
    driver states.
    """

    UNCONFIGURED = DriverConnectionState.UNCONFIGURED
    DISCONNECTED = DriverConnectionState.DISCONNECTED
    CONNECTED = DriverConnectionState.CONNECTED


####################################################################
# Static enumerations for this class
####################################################################

class Command(BaseEnum):
    SAVE = 'save'
    EXIT = 'exit'
    EXIT_AND_RESET = 'exit!'
    GET = 'show'
    SET = 'set'
    RESET = 0x12
    BREAK = 0x03
    STOP = 0x13
    AUTOSAMPLE = 0x01
    SAMPLE = 0x0D


class ProtocolState(BaseEnum):
    UNKNOWN = 'PROTOCOL_STATE_UNKNOWN'
    COMMAND_MODE = 'PROTOCOL_STATE_COMMAND_MODE'
    AUTOSAMPLE_MODE = 'PROTOCOL_STATE_AUTOSAMPLE_MODE'
    POLL_MODE = 'PROTOCOL_STATE_POLL_MODE'


class ProtocolEvent(BaseEnum):
    INITIALIZE = DriverEvent.INITIALIZE
    GET_LAST_ENSEMBLE = 'GET_LAST_ENSEMBLE'
    GET_METADATA = 'GET_METADATA'
    RUN_RECORDER_TESTS = 'RUN_RECORDER_TESTS'
    RUN_ALL_TESTS = 'RUN_ALL_TESTS'

    AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    BREAK = DriverEvent.BREAK

    STOP = DriverEvent.STOP_AUTOSAMPLE
    POLL = 'POLL_MODE'
    COMMAND = DriverEvent.EXECUTE
    GET = DriverEvent.GET
    SET = DriverEvent.SET


class Parameter(BaseEnum):
    pass


class Prompt(BaseEnum):
    COMMAND = '>'


####################################################################
# Protocol
####################################################################
class VadcpProtocol(CommandResponseInstrumentProtocol):
    """
    """

    def __init__(self, callback=None):
        CommandResponseInstrumentProtocol.__init__(self, Prompt, EOLN, callback)

        # TODO probably promote this convenience to super-class?
        self._timeout = 30
        """Default timeout value for operations accepting an optional timeout
        argument."""

        self._last_data_timestamp = None
        self.eoln = EOLN

        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           None, None)

        # UNKNOWN
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN,
                                       ProtocolEvent.INITIALIZE,
                                       self._handler_initialize)

        # COMMAND_MODE
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.GET_LAST_ENSEMBLE,
                                       self._handler_command_get_latest_ensemble)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.GET_METADATA,
                                       self._handler_command_get_metadata)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.RUN_RECORDER_TESTS,
                                       self._handler_command_run_recorder_tests)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.RUN_ALL_TESTS,
                                       self._handler_command_run_all_tests)

        self._protocol_fsm.start(ProtocolState.UNKNOWN)

    def execute_init_protocol(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.INITIALIZE,
                                           *args, **kwargs)

    def execute_get_latest_ensemble(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.GET_LAST_ENSEMBLE,
                                           *args, **kwargs)

    def execute_get_metadata(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.GET_METADATA,
                                           *args, **kwargs)

    def execute_run_recorder_tests(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.RUN_RECORDER_TESTS,
                                           *args, **kwargs)

    def execute_run_all_tests(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.RUN_ALL_TESTS,
                                           *args, **kwargs)

    def execute_break(self, *args, **kwargs):
        """ Execute the break command

        @retval None if nothing was done, otherwise result of FSM event handle
        @throws InstrumentProtocolException On invalid command or missing
        """
        return self._protocol_fsm.on_event(ProtocolEvent.BREAK,
                                           *args, **kwargs)

    ################
    # State handlers
    ################

    def _handler_initialize(self, *args, **kwargs):
        """
        Determines initial protocol state according to instrument's state
        """
        next_state = None
        result = None

        # TODO determine the state. For now, assume command mode

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        next_state = ProtocolState.COMMAND_MODE

        return (next_state, result)

    def _handler_command_get_latest_ensemble(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = self._protocol_fsm.get_current_state()
        result = None

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._connection.get_latest_ensemble(timeout)
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while get_latest_ensemble: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    def _handler_command_get_metadata(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = self._protocol_fsm.get_current_state()
        result = None

        timeout = kwargs.get('timeout', self._timeout)
        sections = kwargs.get('sections', None)

        try:
            result = self._connection.get_metadata(sections, timeout)
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while get_metadata: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    def _handler_command_run_recorder_tests(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = self._protocol_fsm.get_current_state()
        result = None

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._connection.run_recorder_tests(timeout)
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while run_recorder_tests: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    def _handler_command_run_all_tests(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = self._protocol_fsm.get_current_state()
        result = None

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._connection.run_all_tests(timeout)
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while run_all_tests: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    ###################################################################
    # Helpers
    ###################################################################

    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
        pass

    def _send_break(self, timeout=10):
        """
        """
        pass


class VadcpDriver(SingleConnectionInstrumentDriver):
    """
    """

    def __init__(self, evt_callback):
        """
        """
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    def _build_connection(self, config):
        """
        Constructs and returns a Connection object according to the given
        configuration.

        @param config configuration dict

        @retval a Connection instance

        @throws InstrumentParameterException Invalid configuration.
        """
        log.info('_build_connection: config=%s' % config)

        outfile = file('vadcp_output.txt', 'w')

        log.info("setting VadcpClient with config: %s" % config)
        try:
            client = VadcpClient(config, outfile, True)
        except (TypeError, KeyError):
            raise InstrumentParameterException('Invalid comms config dict.'
                                               ' config=%s' % config)
        def _data_listener(sample):
            log.info("_data_listener: sample = %s" % str(sample))

        client.set_data_listener(_data_listener)
        return client

    def _build_protocol(self):
        """ Construct driver protocol"""
        self._protocol = VadcpProtocol(self._driver_event)

    def execute_init_protocol(self, *args, **kwargs):
        return self._protocol.execute_init_protocol(*args, **kwargs)

    def execute_get_latest_ensemble(self, *args, **kwargs):
        return self._protocol.execute_get_latest_ensemble(*args, **kwargs)

    def execute_get_metadata(self, *args, **kwargs):
        return self._protocol.execute_get_metadata(*args, **kwargs)

    def execute_run_recorder_tests(self, *args, **kwargs):
        return self._protocol.execute_run_recorder_tests(*args, **kwargs)

    def execute_run_all_tests(self, *args, **kwargs):
        return self._protocol.execute_run_all_tests(*args, **kwargs)

    def execute_break(self, *args, **kwargs):
        return self._protocol.execute_break(*args, **kwargs)
