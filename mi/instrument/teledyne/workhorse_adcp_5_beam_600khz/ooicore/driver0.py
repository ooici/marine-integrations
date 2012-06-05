#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver0
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/driver0.py
@author Carlos Rueda
@brief VADCP driver implementation
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    ClientException, TimeoutException
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import VadcpClient

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import InstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverAsyncEvent

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentTimeoutException

import time

import logging
from mi.core.mi_logger import mi_logger as log

# TODO define Packet config for data granules.
PACKET_CONFIG = {}


class DriverState(BaseEnum):
    """
    driver states.
    """

    UNCONFIGURED = DriverConnectionState.UNCONFIGURED
    DISCONNECTED = DriverConnectionState.DISCONNECTED
    CONNECTED = DriverConnectionState.CONNECTED


class VadcpDriver(InstrumentDriver):
    """
    driver
    """
    def __init__(self, evt_callback):
        """
        Constructor.

        @param evt_callback Driver process event callback.
        """
        InstrumentDriver.__init__(self, evt_callback)

        # _client created in configure()
        self._client = None

        self._state = DriverState.UNCONFIGURED

        # TODO probably promote this convenience to super-class?
        self._timeout = 30
        """Default timeout value for operations accepting an optional timeout
        argument."""


    def _assert_state(self, obj):
        """
        Asserts that the current state is either the same as the one given (if
        not a list) or one of the elements of the given list.

        @raises InstrumentStateException if the assertion fails
        """
        cs = self.get_current_state()
        if isinstance(obj, list):
            if cs in obj:
                return  # OK
            else:
                raise InstrumentStateException(msg=
                        "current state=%s not one of %s" % (cs, str(obj)))
        state = obj
        if cs != state:
            raise InstrumentStateException(
                    "current state=%s, expected=%s" % (cs, state))

    #############################################################
    # Device connection interface.
    #############################################################

    def initialize(self, *args, **kwargs):
        """
        Initialize driver connection, bringing communications parameters
        into unconfigured state (no connection object).

        @raises InstrumentStateException if command not allowed in current
                 state
        """

        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        if self._state == DriverState.UNCONFIGURED:
            assert self._client is None
            return

        if self._client is not None:
            try:
                self._client.end()
            finally:
                self._client = None

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._state = DriverState.UNCONFIGURED

    def configure(self, *args, **kwargs):
        """
        Configure the driver for communications with the device via
        port agent / logger (valid but unconnected connection object).

        @param config comms config dict.

        @raises InstrumentStateException if command not allowed in current
                state
        @throws InstrumentParameterException if missing comms or invalid
                config dict.
        """

        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.UNCONFIGURED)

        config = kwargs.get('config', None)
        if config is None:
#            raise InstrumentParameterException(msg="'config' parameter required")
            config = args[0]

        outfile = file('vadcp_output.txt', 'w')

        # Verify dict and construct connection client.
        log.info("setting VadcpClient with config: %s" % config)
        try:
            self._client = VadcpClient(config, outfile, True)
        except (TypeError, KeyError):
            raise InstrumentParameterException('Invalid comms config dict.'
                                               ' config=%s' % config)
        def _data_listener(sample):
            log.info("_data_listener: sample = %s" % str(sample))

        self._client.set_data_listener(_data_listener)

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._state = DriverState.DISCONNECTED

    def connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger
        (connected connection object).

        @raises InstrumentStateException if command not allowed in current
                state
        @throws InstrumentConnectionException if the connection failed.
        """

        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.DISCONNECTED)

        self._client.connect()

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._state = DriverState.CONNECTED

    def disconnect(self, *args, **kwargs):
        """
        Disconnect from device via port agent / logger.
        @raises InstrumentStateException if command not allowed in current
                state
        """

        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        self._client.end()

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._state = DriverState.DISCONNECTED

    def execute_init_protocol(self, *args, **kwargs):
        # added here as part of the preparation using the general scheme
        # TODO
        pass

    def execute_get_latest_ensemble(self, *args, **kwargs):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._client.get_latest_ensemble(timeout)
            return result
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while get_latest_ensemble: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

    def execute_get_metadata(self, *args, **kwargs):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        timeout = kwargs.get('timeout', self._timeout)
        sections = kwargs.get('sections', None)

        try:
            result = self._client.get_metadata(sections, timeout)
            return result
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while get_metadata: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

    def execute_run_recorder_tests(self, *args, **kwargs):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._client.run_recorder_tests(timeout)
            return result
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while run_recorder_tests: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

    def execute_run_all_tests(self, *args, **kwargs):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._client.run_all_tests(timeout)
            return result
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while run_all_tests: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

    def execute_break(self, *args, **kwargs):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("args=%s kwargs=%s" % (str(args), str(kwargs)))

        self._assert_state(DriverState.CONNECTED)

        timeout = kwargs.get('timeout', self._timeout)

        try:
            result = self._client.send_break(timeout=timeout)
            return result
        except TimeoutException, e:
            raise InstrumentTimeoutException(msg=str(e))
        except ClientException, e:
            log.warn("ClientException while send_break: %s" %
                     str(e))
            raise InstrumentException('ClientException: %s' % str(e))

    ########################################################################
    # Resource query interface.
    ########################################################################
    def get_resource_commands(self):
        """
        Retrun list of device execute commands available.
        """
        return [cmd for cmd in dir(self) if cmd.startswith('execute_')]

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return self.get(DriverParameter.ALL)

    def get_current_state(self):
        """
        Return current device state. Implemented in connection specific
        subclasses.
        """
        return self._state

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
            'type': type,
            'value': None,
            'time': time.time()
        }
        if type == DriverAsyncEvent.STATE_CHANGE:
            state = self.get_current_state()
            event['value'] = state
            self._send_event(event)

        elif type == DriverAsyncEvent.CONFIG_CHANGE:
            config = self.get(DriverParameter.ALL)
            event['value'] = config
            self._send_event(event)

        elif type == DriverAsyncEvent.SAMPLE:
            event['value'] = val
            self._send_event(event)

        elif type == DriverAsyncEvent.ERROR:
            # Error caught at driver process level.
            pass

        elif type == DriverAsyncEvent.TEST_RESULT:
            event['value'] = val
            self._send_event(event)

    ########################################################################
    # Test interface.
    ########################################################################

    def driver_echo(self, msg):
        """
        Echo a message.
        @param msg the message to prepend and echo back to the caller.
        """
        reply = 'driver_echo: %s' % msg
        return reply

    def test_exceptions(self, msg):
        """
        Test exception handling in the driver process.
        @param msg message string to put in a raised exception to be caught in
        a test.
        @raises InstrumentExeption always.
        """
        raise InstrumentException(msg)
