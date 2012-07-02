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
from mi.core.exceptions import InstrumentTimeoutException

import logging
from mi.core.mi_logger import mi_logger as log

# init log configuration
from mi.core.log import LoggerManager
LoggerManager().init()


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

    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

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
        # _timeout: Default timeout value for operations accepting an
        # optional timeout argument
        self._timeout = 30

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
                                       self._handler_command_get_latest_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.GET_METADATA,
                                       self._handler_command_get_metadata)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.RUN_RECORDER_TESTS,
                                       self._handler_command_run_recorder_tests)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.RUN_ALL_TESTS,
                                       self._handler_command_run_all_tests)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND_MODE,
                                       ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_autosample)

        # AUTOSAMPLE_MODE
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE_MODE,
                                       ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop)

        self._protocol_fsm.start(ProtocolState.UNKNOWN)

    def execute_init_protocol(self, *args, **kwargs):
        """
        """
        return self._protocol_fsm.on_event(ProtocolEvent.INITIALIZE,
                                           *args, **kwargs)

    def execute_get_latest_sample(self, *args, **kwargs):
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

    def _handler_command_get_latest_sample(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = self._protocol_fsm.get_current_state()
        result = None

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._connection.get_latest_sample(timeout)
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while get_latest_sample: %s" %
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

    def _handler_autosample_stop(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = None
        result = None

        duration = int(kwargs.get('duration', 1000))

        try:
            result = self._connection.send_break(duration)
            next_state = ProtocolState.COMMAND_MODE
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while send_break: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    def _handler_command_autosample(self, *args, **kwargs):
        """
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        next_state = None
        result = None

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._connection.start_autosample(timeout=timeout)
            next_state = ProtocolState.AUTOSAMPLE_MODE
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while start_autosample: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

        return (next_state, result)

    ########################################################################
    # Incomming data callback.
    ########################################################################
    def got_data(self, data):
        CommandResponseInstrumentProtocol.got_data(self, data)
        log.info("!!!!!!!!!!!!!!!!!!!got_data: data = %s" % str(data))

    ###################################################################
    # Helpers
    ###################################################################

    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
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
        configuration. The object returned here is a VadcpClient instance.

        @param config configuration dict

        @retval a VadcpClient instance

        @throws InstrumentParameterException Invalid configuration.
        """
        log.info('_build_connection: config=%s' % config)

        c4 = config['four_beam']
        outfilename = 'vadcp_output_%s_%s.txt' % (c4.host, c4.port)
        u4_outfile = file(outfilename, 'w')
        c5 = config['fifth_beam']
        outfilename = 'vadcp_output_%s_%s.txt' % (c5.host, c5.port)
        u5_outfile = file(outfilename, 'w')

        log.info("setting VadcpClient with config: %s" % config)
        try:
            client = VadcpClient(config, u4_outfile, u5_outfile)
        except (TypeError, KeyError):
            raise InstrumentParameterException('Invalid comms config dict.'
                                               ' config=%s' % config)

        # set data_listener to the client so we can notify corresponding
        # DriverAsyncEvent.SAMPLE events:
        def _data_listener(sample):
            log.info("_data_listener: sample = %s" % str(sample))
            self._driver_event(DriverAsyncEvent.SAMPLE, val=sample)

        client.set_data_listener(_data_listener)
        return client

    def _build_protocol(self):
        """ Construct driver protocol"""
        self._protocol = VadcpProtocol(self._driver_event)

    def execute_init_protocol(self, *args, **kwargs):
        return self._protocol.execute_init_protocol(*args, **kwargs)

    def execute_get_latest_sample(self, *args, **kwargs):
        return self._protocol.execute_get_latest_sample(*args, **kwargs)

    def execute_get_metadata(self, *args, **kwargs):
        return self._protocol.execute_get_metadata(*args, **kwargs)

    def execute_run_recorder_tests(self, *args, **kwargs):
        return self._protocol.execute_run_recorder_tests(*args, **kwargs)

    def execute_run_all_tests(self, *args, **kwargs):
        return self._protocol.execute_run_all_tests(*args, **kwargs)

    def execute_break(self, *args, **kwargs):
        return self._protocol.execute_break(*args, **kwargs)
