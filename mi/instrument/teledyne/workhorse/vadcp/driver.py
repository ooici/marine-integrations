"""
@package mi.instrument.teledyne.workhorse.adcp.driver
@file marine-integrations/mi/instrument/teledyne/workhorse/adcp/driver.py
@author Sung Ahn
@brief Driver for the ADCP
Release notes:

Generic Driver for ADCPS-K, ADCPS-I, ADCPT-B and ADCPT-DE
"""
from mi.instrument.teledyne.workhorse.driver import WorkhorseInstrumentDriver
from mi.instrument.teledyne.workhorse.driver import WorkhorseProtocol

from mi.instrument.teledyne.driver import TeledyneScheduledJob
from mi.instrument.teledyne.driver import TeledyneCapability
from mi.instrument.teledyne.driver import TeledyneInstrumentCmds
from mi.instrument.teledyne.driver import TeledyneProtocolState
from mi.instrument.teledyne.driver import TeledynePrompt

from mi.instrument.teledyne.workhorse.driver import NEWLINE
from mi.core.log import get_logger ; log = get_logger()

import json
import socket
from mi.core.util import dict_equal

from mi.core.time import get_timestamp_delayed
from mi.core.common import BaseEnum, InstErrorCode

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.driver_dict import DriverDict

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.instrument.teledyne.workhorse.driver import WorkhorseParameter
from mi.instrument.teledyne.driver import TeledyneProtocolEvent
from mi.core.instrument.port_agent_client import PortAgentClient
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.exceptions import InstrumentConnectionException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.data_particle import RawDataParticle
from mi.instrument.teledyne.particles import *

from mi.core.instrument.instrument_protocol import InitializationType

from mi.instrument.teledyne.driver import  TeledyneProtocol
from mi.core.exceptions import InstrumentParameterExpirationException

from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.instrument.teledyne.driver import TeledyneParameter

from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.chunker import StringChunker

import re
import base64


class SlaveProtocol(BaseEnum):
    FOURBEAM = '4Beam'
    FIFTHBEAM = '5thBeam'

class Prompt(TeledynePrompt):
    """
    Device i/o prompts..
    """


class Parameter(WorkhorseParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    SYNC_PING_ENSEMBLE = 'SA'
    RDS3_MODE_SEL = 'SM'  # 0=off, 1=master, 2=slave
    SLAVE_TIMEOUT = 'ST'
    SYNCH_DELAY = 'SW'



class ProtocolEvent(TeledyneProtocolEvent):
    """
    Protocol events
    """


class Capability(TeledyneCapability):
    """
    Protocol events that should be exposed to users (subset of above).
    """


class ScheduledJob(TeledyneScheduledJob):
    """
    Complete this last.
    """


class InstrumentCmds(TeledyneInstrumentCmds):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """
    GET2 = '  '

class RawDataParticle_5thbeam(RawDataParticle):
    _data_particle_type = "raw_5thbeam"

class VADCP_COMPASS_CALIBRATION_DataParticle(ADCP_COMPASS_CALIBRATION_DataParticle):
    _data_particle_type = "vadcp_5thbeam_compass_calibration"

class VADCP_SYSTEM_CONFIGURATION_DataParticle(ADCP_SYSTEM_CONFIGURATION_DataParticle):
    _data_particle_type = "adcp_5thbean_system_configuration"

class VADCP_PD0_PARSED_DataParticle(ADCP_PD0_PARSED_DataParticle):
    _data_particle_type = "VADCP"
    _slave = True


class ProtocolState(TeledyneProtocolState):
    """
    Instrument protocol states
    """


class InstrumentDriver(WorkhorseInstrumentDriver):
    """
    Specialization for this version of the workhorse ADCP driver
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        WorkhorseInstrumentDriver.__init__(self, evt_callback)

        #multiple portAgentClient
        self._connections = {}





    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(TeledynePrompt, NEWLINE, self._driver_event)

    ########################################################################
    # Unconfigured handlers.
    ########################################################################

    def _handler_unconfigured_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communications config dictionary.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful, (None, None) otherwise.
        @raises InstrumentParameterException if missing or invalid param dict.
        """
        result = None
        log.debug('_handler_unconfigured_configure args: %r kwargs: %r', args, kwargs)
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
        self._connections = self._build_connections(config)
        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result

    ########################################################################
    # Disconnected handlers.
    ########################################################################

    def _handler_disconnected_initialize(self, *args, **kwargs):
        """
        Initialize device communications. Causes the connection parameters to
        be reset.
        @retval (next_state, result) tuple, (DriverConnectionState.UNCONFIGURED,
        None).
        """
        result = None
        self._connections = None
        next_state = DriverConnectionState.UNCONFIGURED

        return next_state, result

    def _handler_disconnected_configure(self, *args, **kwargs):
        """
        Configure driver for device comms.
        @param args[0] Communications config dictionary.
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
        self._connections = self._build_connections(config)

        return next_state, result

    def _handler_disconnected_connect(self, *args, **kwargs):
        """
        Establish communications with the device via port agent / logger and
        construct and initialize a protocol FSM for device interaction.
        @retval (next_state, result) tuple, (DriverConnectionState.CONNECTED,
        None) if successful.
        @raises InstrumentConnectionException if the attempt to connect failed.
        """
        log.debug('_handler_disconnected_connect enter')
        next_state = DriverConnectionState.CONNECTED
        result = None
        self._build_protocol()
        try:
            self._connections['4Beam'].init_comms(self._protocol.got_data, # Sung
                                      self._protocol.got_raw,  # Sung
                                      self._got_exception,
                                      self._lost_connection_callback)
            self._protocol._connection_4Beam = self.connections['4Beam']

        except InstrumentConnectionException as e:
            log.error("4 beam Connection Exception: %s", e)
            log.error("Instrument Driver remaining in disconnected state.")
            # Re-raise the exception
            raise

        try:
            self._connections['5thBeam'].init_comms(self._protocol.got_data2, # Sung
                                      self._protocol.got_raw2,  # Sung
                                      self._got_exception,
                                      self._lost_connection_callback)
            self._protocol._connection_5thBeam = self.connections['5thBeam']

        except InstrumentConnectionException as e:
            log.error("5th beam Connection Exception: %s", e)
            log.error("Instrument Driver remaining in disconnected state.")
            # we don't need to roll back the connection on 4 beam
            # Just don't change the state to 'CONNECTED'
            # Re-raise the exception
            raise
        log.debug('_handler_disconnected_connect exit')
        return next_state, result

    ########################################################################
    # Connected handlers.
    ########################################################################

    def _handler_connected_disconnect(self, *args, **kwargs):
        """
        Disconnect to the device via port agent / logger and destroy the
        protocol FSM.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None) if successful.
        """
        result = None

        log.info("_handler_connected_disconnect: invoking stop_comms().")
        for connection in self._connections.values():
            connection.stop_comms()
        self._protocol = None
        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result

    def _handler_connected_connection_lost(self, *args, **kwargs):
        """
        The device connection was lost. Stop comms, destroy protocol FSM and
        revert to disconnected state.
        @retval (next_state, result) tuple, (DriverConnectionState.DISCONNECTED,
        None).
        """
        result = None

        log.info("_handler_connected_connection_lost: invoking stop_comms().")
        for connection in self._connections.values():
            connection.stop_comms()
        self._protocol = None

        # Send async agent state change event.
        log.info("_handler_connected_connection_lost: sending LOST_CONNECTION "
                 "event, moving to DISCONNECTED state.")
        self._driver_event(DriverAsyncEvent.AGENT_EVENT,
                           ResourceAgentEvent.LOST_CONNECTION)

        next_state = DriverConnectionState.DISCONNECTED

        return next_state, result


    def _build_connections(self, all_configs):
        """
        Constructs and returns a Connection object according to the given
        configuration. The connection object is a LoggerClient instance in
        this base class. Subclasses can overwrite this operation as needed.
        The value returned by this operation is assigned to self._connections
        and also to self._protocol._connection upon entering in the
        DriverConnectionState.CONNECTED state.

        @param all_configs configuration dict

        @retval a Connection instance, which will be assigned to
                  self._connections

        @throws InstrumentParameterException Invalid configuration.
        """
        log.debug('all_configs: %r', all_configs)
        connections = {}
        for name, config in all_configs.items():
            if not isinstance(config, dict):
                continue
            log.debug('_build_connections: config received: %r', config)
            if 'mock_port_agent' in config:
                mock_port_agent = config['mock_port_agent']
                # check for validity here...
                if mock_port_agent is not None:
                    connections[name] = mock_port_agent
            else:
                try:
                    addr = config['port_agent_addr']
                    port = config['data_port']
                    cmd_port = config.get('command_port')

                    if isinstance(addr, str) and isinstance(port, int) and len(addr) > 0:
                        connections[name] = PortAgentClient(addr, port, cmd_port)
                    else:
                        raise InstrumentParameterException('Invalid comms config dict.')

                except (TypeError, KeyError):
                    raise InstrumentParameterException('Invalid comms config dict.')
        return connections


class Protocol(WorkhorseProtocol):

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        log.debug("IN WorkhorseProtocol.__init__")
        # Construct protocol superclass.
        TeledyneProtocol.__init__(self, prompts, newline, driver_event)

        self._add_response_handler(InstrumentCmds.GET2, self._parse_get_response2)

        self._connection_4beam = None
        self._connection_5thBean = None

        # Line buffer for input from device.
        self._linebuf2 = ''

        # Short buffer to look for prompts from device in command-response
        # mode.
        self._promptbuf2 = ''

        # The parameter, comamnd, and driver dictionaries.
        self._param_dict2 = ProtocolParameterDict()
        self._cmd_dict2 = ProtocolCommandDict()
        self._driver_dict2 = DriverDict()
        self._build_param_dict2()

        self._chunker2 = StringChunker(WorkhorseProtocol.sieve_function)

    def _parse_get_response2(self, response, prompt):
        log.trace("GET RESPONSE2 = " + repr(response))
        if prompt == TeledynePrompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        while (not response.endswith('\r\n>\r\n>')) or ('?' not in response):
            (prompt, response) = self._get_raw_response2(30, TeledynePrompt.COMMAND)
            time.sleep(.05) # was 1

        self._param_dict2.update(response)

        for line in response.split(NEWLINE):
            self._param_dict2.update(line)
            if not "?" in line and ">" != line:
                response = line

        if self.get_param not in response:
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param)

        self.get_count = 0
        return response


    """
    Specialization for this version of the workhorse driver
    """

    ##########################

    def _get_response2(self, timeout=10, expected_prompt=None, response_regex=None):
        """
        Get a response from the instrument, but be a bit loose with what we
        find. Leave some room for white space around prompts and not try to
        match that just in case we are off by a little whitespace or not quite
        at the end of a line.

        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @param response_regex Look for a resposne value that matches the
        supplied compiled regex pattern. Groups that match will be returned as a
        string. Cannot be used with expected prompt. None
        will be returned as a prompt with this match. If a regex is supplied,
        internal the prompt list will be ignored.
        @retval Regex search result tuple (as MatchObject.groups() would return
        if a response_regex is supplied. A tuple of (prompt, response) if a
        prompt is looked for.
        @throw InstrumentProtocolException if both regex and expected prompt are
        passed in or regex is not a compiled pattern.
        @throw InstrumentTimeoutExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()

        if response_regex and not isinstance(response_regex, self.RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')

        if response_regex:
            prompt_list = []

        if expected_prompt == None:
            prompt_list = self._get_prompts()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        log.debug('_get_response: timeout=%s, prompt_list=%s, expected_prompt=%s, response_regex=%s, promptbuf=%s',
                  timeout, prompt_list, expected_prompt, response_regex, self._promptbuf2)
        while True:
            if response_regex:
                match = response_regex.search(self._linebuf2)
                if match:
                    return match.groups()
                else:
                    time.sleep(.1)
            else:
                for item in prompt_list:
                    index = self._promptbuf2.find(item)
                    if index >= 0:
                        result = self._promptbuf2[0:index+len(item)]
                        return (item, result)
                    else:
                        time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def _get_raw_response2(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument, but dont trim whitespace. Used in
        times when the whitespace is what we are looking for.

        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        strip_chars = "\t "

        starttime = time.time()
        if expected_prompt == None:
            prompt_list = self._get_prompts()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        while True:
            for item in prompt_list:
                if self._promptbuf2.rstrip(strip_chars).endswith(item.rstrip(strip_chars)):
                    return (item, self._linebuf2)
                else:
                    time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_raw_response()")

    def _do_cmd_direct(self, cmd):
        """
        Issue an untranslated command to the instrument. No response is handled
        as a result of the command.

        @param cmd The high level command to issue
        """

        # Send command.
        log.debug('_do_cmd_direct: <%s>' % cmd)
        #self._connection.send(cmd)
        self._connection_4beam.send(cmd)
        self._connection_5thBean.send(cmd)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', self.DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', self.DEFAULT_WRITE_DELAY)
        retval = None

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        if (self.last_wakeup + 30) > time.time():
            self.last_wakeup = time.time()
        else:
            prompt = self._wakeup(timeout=3)
        # Clear line and prompt buffers for result.


        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s' % repr(cmd_line))

        if (write_delay == 0):
            self._connection_4beam.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection_4beam.send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout,
                                              expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        return resp_result

    def _do_cmd_resp2(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', self.DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', self.EFAULT_WRITE_DELAY)
        retval = None

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        if (self.last_wakeup2 + 30) > time.time():
            self.last_wakeup2 = time.time()
        else:
            prompt = self._wakeup2(timeout=3)
        # Clear line and prompt buffers for result.


        self._linebuf2 = ''
        self._promptbuf2 = ''

        # Send command.
        log.debug('_do_cmd_resp2: %s' % repr(cmd_line))

        if (write_delay == 0):
            self._connection_5thBean.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection_5thBean.send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response2(timeout,
                                              expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        return resp_result

    def _get_response2(self, timeout=10, expected_prompt=None, response_regex=None):
        """
        Get a response from the instrument, but be a bit loose with what we
        find. Leave some room for white space around prompts and not try to
        match that just in case we are off by a little whitespace or not quite
        at the end of a line.

        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @param response_regex Look for a resposne value that matches the
        supplied compiled regex pattern. Groups that match will be returned as a
        string. Cannot be used with expected prompt. None
        will be returned as a prompt with this match. If a regex is supplied,
        internal the prompt list will be ignored.
        @retval Regex search result tuple (as MatchObject.groups() would return
        if a response_regex is supplied. A tuple of (prompt, response) if a
        prompt is looked for.
        @throw InstrumentProtocolException if both regex and expected prompt are
        passed in or regex is not a compiled pattern.
        @throw InstrumentTimeoutExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()

        if response_regex and not isinstance(response_regex, self.RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')

        if response_regex:
            prompt_list = []

        if expected_prompt == None:
            prompt_list = self._get_prompts()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        log.debug('_get_response: timeout=%s, prompt_list=%s, expected_prompt=%s, response_regex=%s, promptbuf=%s',
                  timeout, prompt_list, expected_prompt, response_regex, self._promptbuf)
        while True:
            if response_regex:
                match = response_regex.search(self._linebuf2)
                if match:
                    return match.groups()
                else:
                    time.sleep(.1)
            else:
                for item in prompt_list:
                    index = self._promptbuf2.find(item)
                    if index >= 0:
                        result = self._promptbuf2[0:index+len(item)]
                        return (item, result)
                    else:
                        time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def _do_cmd_no_resp(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after a wake up and clearing of
        buffers. No response is handled as a result of the command.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup timeout.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built.
        """

        timeout = kwargs.get('timeout', self.DEFAULT_CMD_TIMEOUT)
        write_delay = kwargs.get('write_delay', self.DEFAULT_WRITE_DELAY)

        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            log.error('_do_cmd_no_resp: no handler for command: %s' % (cmd))
            raise InstrumentProtocolException(error_code=InstErrorCode.BAD_DRIVER_COMMAND)
        cmd_line = build_handler(cmd, *args)

        # Wakeup the device, timeout exception as needed
        prompt = self._wakeup(timeout)

        # Clear line and prompt buffers for result.

        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_no_resp: %s, timeout=%s' % (repr(cmd_line), timeout))
        if (write_delay == 0):
            self._connection_4beam.send(cmd_line)
            #self._connection_5thBean.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection_4beam.send(char)
                #self._connection_5thBean.send(char)
                time.sleep(write_delay)

    def _do_cmd_no_resp2(self, cmd, *args, **kwargs):
        """
        Issue a command to the instrument after a wake up and clearing of
        buffers. No response is handled as a result of the command.

        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup timeout.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built.
        """

        timeout = kwargs.get('timeout', self.DEFAULT_CMD_TIMEOUT)
        write_delay = kwargs.get('write_delay', self.DEFAULT_WRITE_DELAY)

        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            log.error('_do_cmd_no_resp: no handler for command: %s' % (cmd))
            raise InstrumentProtocolException(error_code=InstErrorCode.BAD_DRIVER_COMMAND)
        cmd_line = build_handler(cmd, *args)

        # Wakeup the device, timeout exception as needed
        prompt = self._wakeup2(timeout)

        # Clear line and prompt buffers for result.

        self._linebuf2 = ''
        self._promptbuf2 = ''

        # Send command.
        log.debug('_do_cmd_no_resp2: %s, timeout=%s' % (repr(cmd_line), timeout))
        if (write_delay == 0):
            #self._connection_4beam.send(cmd_line)
            self._connection_5thBean.send(cmd_line)
        else:
            for char in cmd_line:
                #self._connection_4beam.send(char)
                self._connection_5thBean.send(char)
                time.sleep(write_delay)


    ########################################################################
    # Incomming data 2 (for parsing) callback.
    ########################################################################
    def got_data2(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """

        data_length = port_agent_packet.get_data_length()
        data = port_agent_packet.get_data()
        timestamp = port_agent_packet.get_timestamp()

        log.debug("Got Data 2: %s" % data)
        log.debug("Add Port Agent Timestamp 2: %s" % timestamp)

        if data_length > 0:
            if self.get_current_state() == DriverProtocolState.DIRECT_ACCESS:
                self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)

            self.add_to_buffer2(data)

            self._chunker2.add_chunk(data, timestamp)
            (timestamp, chunk) = self._chunker2.get_next_data()
            while(chunk):
                self._got_chunk2(chunk, timestamp)
                (timestamp, chunk) = self._chunker.get_next_data()

    def _got_chunk2(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample(VADCP_COMPASS_CALIBRATION_DataParticle,
                                 ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_COMPASS_CALIBRATION_DataParticle")

        if (self._extract_sample(VADCP_PD0_PARSED_DataParticle,
                                 ADCP_PD0_PARSED_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_PD0_PARSED_DataParticle")

        if (self._extract_sample(VADCP_SYSTEM_CONFIGURATION_DataParticle,
                                 ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_SYSTEM_CONFIGURATION_DataParticle")

    def got_raw2(self, port_agent_packet):
        """
        Called by the port agent client when raw data is available, such as data
        sent by the driver to the instrument, the instrument responses,etc.
        """
        self.publish_raw2(port_agent_packet)

    def publish_raw2(self, port_agent_packet):
        """
        Publish raw data
        @param: port_agent_packet port agent packet containing raw
        """
        particle = RawDataParticle_5thbeam(port_agent_packet.get_as_dict(),
                                   port_timestamp=port_agent_packet.get_timestamp())

        if self._driver_event:
            self._driver_event(DriverAsyncEvent.SAMPLE, particle.generate())

    def add_to_buffer2(self, data):
        '''
        Add a chunk of data to the internal data buffers
        @param data: bytes to add to the buffer
        '''
        # Update the line and prompt buffers.
        self._linebuf2 += data
        self._promptbuf2 += data
        self._last_data_timestamp2 = time.time()

        log.debug("LINE BUF2: %s", self._linebuf2)
        log.debug("PROMPT BUF2: %s", self._promptbuf2)



    ########################################################################
    # Wakeup helpers.
    ########################################################################

    def _wakeup2(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        log.debug("clearing promptbuf: %s", self._promptbuf2)
        self._promptbuf2 = ''

        # Grab time for timeout.
        starttime = time.time()

        while True:
            # Send a line return and wait a sec.
            log.trace('Sending wakeup. timeout=%s', timeout)
            self._send_wakeup2()
            time.sleep(delay)

            log.debug("Prompts: %s", self._get_prompts())

            for item in self._get_prompts():
                log.debug("buffer: %s", self._promptbuf2)
                log.debug("find prompt: %s", item)
                index = self._promptbuf2.find(item)
                log.debug("Got prompt (index: %s): %s ", index, repr(self._promptbuf2))
                if index >= 0:
                    log.trace('wakeup got prompt: %s', repr(item))
                    return item
            log.debug("Searched for all prompts")

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in _wakeup()")

    def _wakeup_until2(self, timeout, desired_prompt, delay=1, no_tries=5):
        """
        Continue waking device until a specific prompt appears or a number
        of tries has occurred. Desired prompt must be in the instrument's
        prompt list.
        @param timeout The timeout to wake the device.
        @desired_prompt Continue waking until this prompt is seen.
        @delay Time to wake between consecutive wakeups.
        @no_tries Maximum number of wakeup tries to see desired prompt.
        @raises InstrumentTimeoutException if device could not be woken.
        @raises InstrumentProtocolException if the desired prompt is not seen in the
        maximum number of attempts.
        """

        count = 0
        while True:
            prompt = self._wakeup2(timeout, delay)
            if prompt == desired_prompt:
                break
            else:
                time.sleep(delay)
                count += 1
                if count >= no_tries:
                    raise InstrumentProtocolException('Incorrect prompt.')


    ####

    def _send_break(self, duration=500):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("IN _send_break, clearing buffer.")
        self._promptbuf = ''
        self._linebuf = ''
        self._send_break_cmd_4beam(duration)
        break_confirmation = []
        log.trace("self._linebuf = " + self._linebuf)

        break_confirmation.append("[BREAK Wakeup A]" + NEWLINE + \
        "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
        "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
        "All Rights Reserved.")

        break_confirmation.append("[BREAK Wakeup A]")
        found = False
        timeout = 30
        count = 0
        while (not found):
            count += 1
            for break_message in break_confirmation:
                if break_message in self._linebuf:
                    log.error("GOT A BREAK MATCH ==> " + str(break_message))
                    found = True
            if count > (timeout * 10):
                if True != found:
                    raise InstrumentTimeoutException("NO BREAK RESPONSE.")
            time.sleep(0.1)
        self._chunker._clean_buffer(len(self._chunker.raw_chunk_list))
        self._promptbuf = ''
        self._linebuf = ''
        log.trace("leaving send_break")
        return True

    def _send_break2(self, duration=500):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("IN _send_break, clearing buffer.")
        self._promptbuf2 = ''
        self._linebuf2 = ''
        self._send_break_cmd_5thBeam(duration)
        break_confirmation = []
        log.trace("self._linebuf2 = " + self._linebuf2)

        break_confirmation.append("[BREAK Wakeup A]" + NEWLINE + \
        "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
        "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
        "All Rights Reserved.")

        break_confirmation.append("[BREAK Wakeup A]")
        found = False
        timeout = 30
        count = 0
        while (not found):
            count += 1
            for break_message in break_confirmation:
                if break_message in self._linebuf2:
                    log.error("GOT A BREAK MATCH ==> " + str(break_message))
                    found = True
            if count > (timeout * 10):
                if True != found:
                    raise InstrumentTimeoutException("NO BREAK RESPONSE.")
            time.sleep(0.1)
        self._chunker2._clean_buffer(len(self._chunker2.raw_chunk_list))
        self._promptbuf2 = ''
        self._linebuf2 = ''
        log.trace("leaving send_break")
        return True

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the device.
        """
        log.trace("IN _send_wakeup")

        self._connection_4beam.send(NEWLINE)

    def _send_wakeup2(self):
        """
        Send a newline to attempt to wake the device.
        """
        log.trace("IN _send_wakeup")

        self._connection_5thBean.send(NEWLINE)

    def _wakeup2(self, timeout=3, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """

        self.last_wakeup2 = time.time()
        # Clear the prompt buffer.
        self._promptbuf2 = ''

        # Grab time for timeout.
        starttime = time.time()
        endtime = starttime + float(timeout)

        # Send a line return and wait a sec.
        log.debug('Sending wakeup2. timeout=%s' % timeout)
        self._send_wakeup2()

        while time.time() < endtime:
            time.sleep(0.05)
            for item in self._get_prompts():
                index = self._promptbuf2.find(item)
                if index >= 0:
                    log.debug('wakeup2 got prompt: %s' % repr(item))
                    return item
        return None

    ####

    # This will over-write _send_break_cmd in teledyne/driver.py
    def _send_break_cmd_4beam(self, delay):
        """
        Send a BREAK to attempt to wake the device.
        """
        # NOTE!!!
        # Once the port agent can handle BREAK, please enable the following line
        #self._connection.send_break(delay)
        # Then remove below lines

        log.trace("IN _send_break_cmd")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            log.trace("WHOOPS! 1")

        try:
            sock.connect(('10.180.80.178', 2102))
        except socket.error, msg:
            log.trace("WHOOPS! 2")
        sock.send("break " + str(delay) + "\r\n")
        sock.close()

    # This will over-write _send_break_cmd in teledyne/driver.py
    def _send_break_cmd_5thBeam(self, delay):
        """
        Send a BREAK to attempt to wake the device.
        """
        # NOTE!!!
        # Once the port agent can handle BREAK, please enable the following line
        #self._connection.send_break(delay)
        # Then remove below lines

        log.trace("IN _send_break_cmd")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            log.trace("WHOOPS! 1")

        try:
            sock.connect(('10.180.80.177', 2102))
        except socket.error, msg:
            log.trace("WHOOPS! 2")
        sock.send("break " + str(delay) + "\r\n")
        sock.close()

    ############################


    def _sync_clock(self, command, date_time_param, timeout=TIMEOUT, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to syncronize the clock
        @param date_time_param: date time parameter that we want to set
        @param prompts: expected prompt
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        @return: true if the command is successful
        @throws: InstrumentProtocolException if command fails
        """
        prompt = self._wakeup2(timeout=3, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        self._linebuf2 = ''
        self._promptbuf2 = ''


        prompt = self._wakeup(timeout=3, delay=delay)
        prompt = self._wakeup2(timeout=3, delay=delay)
        str_val = get_timestamp_delayed(time_format)
        reply = self._do_cmd_direct(date_time_param + str_val)
        time.sleep(1)
        reply = self._get_response(TIMEOUT)
        reply = self._get_response2(TIMEOUT)



    def _instrument_config_dirty2(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @throws: InstrumentParameterException
        """
        log.trace("in _instrument_config_dirty2")
        # Refresh the param dict cache
        #self._update_params()

        #startup_params = self._param_dict.get_startup_list()
        startup_params2 = self._param_dict2.get_startup_list()
        #log.trace("Startup Parameters 4 beam: %s" % startup_params)
        log.trace("Startup Parameters 5th beam: %s" % startup_params2)

        for param in startup_params2:
            if not self._has_parameter(param):
                raise InstrumentParameterException("in _instrument_config_dirty2")

            if (self._param_dict2.get(param) != self._param_dict2.get_config_value(param)):
                log.trace("DIRTY: %s %s != %s" % (param, self._param_dict2.get(param), self._param_dict2.get_config_value(param)))
                return True

        log.trace("Clean instrument config")
        return False

    def _update_params2(self, *args, **kwargs):
        """
        Update the parameter dictionary.
        """
        log.debug("in _update_params2")
        error = None
        logging = self._is_logging2()

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging2()


            ###
            # Get old param dict config.
            old_config = self._param_dict2.get_config()
            kwargs['expected_prompt'] = TeledynePrompt.COMMAND

            cmds = self._get_params()
            results = ""
            for attr in sorted(cmds):
                if attr not in ['dict', 'has', 'list', 'ALL']:
                    if not attr.startswith("_"):
                        key = self._getattr_key(attr)
                        result = self._do_cmd_resp2(TeledyneInstrumentCmds.GET, key, **kwargs)
                        results += result + NEWLINE

            new_config = self._param_dict2.get_config()

            del old_config['TT']
            del new_config['TT']

            if not dict_equal(new_config, old_config):
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            ####

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                log.debug("GOING BACK INTO LOGGING")
                my_state = self._protocol_fsm.get_current_state()
                log.debug("current_state = %s calling start_logging", my_state)
                self._start_logging2()

        if(error):
            raise error

        return results

    def _set_params2(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.trace("in _set_params2")
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        result = None
        startup = False
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass
        log.trace("_set_params 2 calling _verify_not_readonly ARGS = " + repr(args))
        self._verify_not_readonly2(*args, **kwargs)
        for (key, val) in params.iteritems():
            result = self._do_cmd_resp2(TeledyneInstrumentCmds.SET, key, val, **kwargs)
        log.trace("_set_params 2 calling _update_params")
        self._update_params2()
        return result

    def _init_params2(self):
        """
        Initialize parameters based on initialization type.  If we actually
        do some initialization (either startup or DA) after we are done
        set the init type to None so we don't initialize again.
        @raises InstrumentProtocolException if the init_type isn't set or it
                                            is unknown
        """
        if(self._init_type == InitializationType.STARTUP):
            log.debug("_init_params: Apply Startup Config")
            self.apply_startup_params2()
            self._init_type = InitializationType.NONE
        elif(self._init_type == InitializationType.DIRECTACCESS):
            log.debug("_init_params: Apply DA Config")
            self.apply_direct_access_params2()
            self._init_type = InitializationType.NONE
            pass
        elif(self._init_type == InitializationType.NONE):
            log.debug("_init_params: No initialization required")
            pass
        elif(self._init_type == None):
            raise InstrumentProtocolException("initialization type not set")
        else:
            raise InstrumentProtocolException("Unknown initialization type: %s" % self._init_type)

    def apply_startup_params2(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @throws: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("in apply_startup_params")
        if (self.get_current_state() != TeledyneProtocolState.COMMAND and
            self.get_current_state() != TeledyneProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        logging = self._is_logging2()
        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.

        if(not self._instrument_config_dirty2()):
            log.trace("in apply_startup_params returning True")
            return True

        error = None

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging2()

            self._apply_params2()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                log.debug("GOING BACK INTO LOGGING")
                my_state = self._protocol_fsm.get_current_state()
                log.trace("current_state = %s", my_state)
                self._start_logging2()

        if(error):
            raise error

    def _apply_params2(self):
        """
        apply startup parameters to the instrument.
        @throws: InstrumentProtocolException if in wrong mode.
        """
        log.debug("IN _apply_params")
        config = self.get_startup_config2()
        # Pass true to _set_params so we know these are startup values
        self._set_params2(config, True)

    def get_startup_config2(self):
        """
        Gets the startup configuration for the instrument. The parameters
        returned are marked as startup, and the values are the best as chosen
        from the initialization, default, and current parameters.

        @retval The dict of parameter_name/values (override this method if it
            is more involved for a specific instrument) that should be set at
            a higher level.

        @raise InstrumentProtocolException if a startup parameter doesn't
               have a init or default value
        """
        return_dict = {}
        start_list = self._param_dict2.get_keys()
        log.trace("Startup list 2: %s", start_list)
        assert isinstance(start_list, list)

        for param in start_list:
            result = self._param_dict2.get_config_value(param)
            if(result != None):
                return_dict[param] = result
            elif(self._param_dict2.is_startup_param(param)):
                raise InstrumentProtocolException("Required startup value not specified: %s" % param)

        log.debug("Applying startup config: %s", return_dict)
        return return_dict

    ########################################################################
    # Helper methods
    ########################################################################
    def _init_params2(self):
        """
        Initialize parameters based on initialization type.  If we actually
        do some initialization (either startup or DA) after we are done
        set the init type to None so we don't initialize again.
        @raises InstrumentProtocolException if the init_type isn't set or it
                                            is unknown
        """
        if(self._init_type == InitializationType.STARTUP):
            log.debug("_init_params2: Apply Startup Config")
            self.apply_startup_params2()
            self._init_type = InitializationType.NONE
        elif(self._init_type == InitializationType.DIRECTACCESS):
            log.debug("_init_params2: Apply DA Config")
            self.apply_direct_access_params2()
            self._init_type = InitializationType.NONE
            pass
        elif(self._init_type == InitializationType.NONE):
            log.debug("_init_params2: No initialization required")
            pass
        elif(self._init_type == None):
            raise InstrumentProtocolException("initialization type not set")
        else:
            raise InstrumentProtocolException("Unknown initialization type: %s" % self._init_type)


    def _is_logging2(self, timeout=TIMEOUT):
        """
        Poll the instrument to see if we are in logging mode.  Return True
        if we are, False if not.
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging
        """
        log.debug("in _is_logging2")

        self._linebuf2 = ""
        self._promptbuf2 = ""

        prompt = self._wakeup2(timeout=3)
        #log.debug("********** GOT PROMPT" + repr(prompt))
        if TeledynePrompt.COMMAND == prompt:
            logging = False
            log.trace("COMMAND MODE!")
        else:
            logging = True
            log.trace("AUTOSAMPLE MODE!")

        return logging

    def _start_logging2(self, timeout=TIMEOUT):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @throws: InstrumentProtocolException if failed to start logging
        """
        log.debug("in _start_logging2 - are we logging? ")
        if (self._is_logging2()):
            log.debug("ALREADY LOGGING2")
            return True
        log.debug("SENDING START LOGGING2")
        self._do_cmd_no_resp2(TeledyneInstrumentCmds.START_LOGGING, timeout=timeout)

        return True

    def _stop_logging2(self, timeout=TIMEOUT):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @throws: InstrumentTimeoutException if prompt isn't seen
        @throws: InstrumentProtocolException failed to stop logging
        """
        log.debug("in Stop Logging2!")
        # Issue the stop command.


        # Send break twice, as sometimes the driver ack's the first one then
        # forgets to actually break.
        self._send_break2(duration=500)
        time.sleep(2)
        self._send_break2(duration=500)
        time.sleep(2)
        # Prompt device until command prompt is seen.
        timeout = 3
        self._wakeup_until2(timeout, TeledynePrompt.COMMAND)

        # set logging to false, as we just got a prompt after a break
        logging = False

        if self._is_logging2(timeout):
            log.debug("FAILED TO STOP LOGGING")
            raise InstrumentProtocolException("failed to stop logging")

        return True


    def _verify_not_readonly2(self, params_to_set, startup=False):
        """
        Verify that the parameters we are attempting to set in upstream methods
        are not readonly.  A parameter is considered read only if it is characterized
        as read-only or immutable.  However, if the startup flag is passed in as true
        then immutable will be considered settable.
        @param params_to_set: dictionary containing parameters to set
        @param startup: startup flag, if set don't verify visibility
        @return: True if we aren't violating visibility
        @raise: InstrumentParameterException if we violate visibility
        """
        log.debug("Verify parameters are not read only, startup: %s", startup)
        if not isinstance(params_to_set, dict):
            raise InstrumentParameterException('parameters not a dict.')

        readonly_params = self._param_dict2.get_visibility_list(ParameterDictVisibility.READ_ONLY)
        if not startup:
            readonly_params += self._param_dict2.get_visibility_list(ParameterDictVisibility.IMMUTABLE)

        log.debug("Read only params 2: %s", readonly_params)

        not_settable = []
        for (key, val) in params_to_set.iteritems():
            if key in readonly_params:
                not_settable.append(key)
        if len(not_settable) > 0:
            raise InstrumentParameterException("Attempt to set read only parameter(s) (%s)" %not_settable)

        return True

    def _get_param_list2(self, *args, **kwargs):
        """
        returns a list of parameters based on the list passed in.  If the
        list contains and ALL parameters request then the list will contain
        all parameters.  Otherwise the original list will be returned. Also
        check the list for unknown parameters
        @param args[0] list of parameters to inspect
        @return: list of parameters.
        @raises: InstrumentParameterException when the wrong param type is passed
        in or an unknown parameter is in the list
        """
        try:
            param_list = args[0]
        except IndexError:
            raise InstrumentParameterException('Parameter required, none specified')

        if(isinstance(param_list, str)):
            param_list = [param_list]
        elif(not isinstance(param_list, (list, tuple))):
            raise InstrumentParameterException("Expected a list, tuple or a string")

        # Verify all parameters are known parameters
        bad_params = []
        known_params = self._param_dict2.get_keys() + [DriverParameter.ALL]
        for param in param_list:
            if(param not in known_params):
                bad_params.append(param)

        if(len(bad_params)):
            raise InstrumentParameterException("Unknown parameters: %s" % bad_params)

        if(DriverParameter.ALL in param_list):
            return self._param_dict2.get_keys()
        else:
            return param_list


    def _get_param_result2(self, param_list, expire_time):
        """
        return a dictionary of the parameters and values
        @param expire_time: baseline time for expiration calculation
        @return: dictionary of values
        @throws InstrumentParameterException if missing or invalid parameter
        @throws InstrumentParameterExpirationException if value is expired.
        """
        result = {}

        for param in param_list:
            val = self._param_dict2.get(param, expire_time)
            result["_".join(param, "5th")] = val

        return result

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with ADCP parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial data out",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='000 000 000')

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial flow control",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='11110')

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match:  bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="banner",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=0)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="instrument id",
            direct_access=True,
            startup_param=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=0)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="sleep enable",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=False)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="save nvram to recorder",
            startup_param=True,
            default_value=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode ',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="polled mode",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=False)

        self._param_dict.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="xmit power",
            startup_param=True,
            direct_access=True,
            default_value=255)

        self._param_dict.add(Parameter.LATENCY_TRIGGER,
            r'CX = (\d) \-+ Trigger Enable ',
            lambda match: int(match.group(1), base=10),
            self._bool_to_int,
            type=ParameterDictType.INT,
            display_name="latency trigger",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=False)

        self._param_dict.add(Parameter.HEADING_ALIGNMENT,
            r'EA = ([\+\-\d]+) \-+ Heading Alignment',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Heading alignment",
            visibility=ParameterDictVisibility.IMMUTABLE,
            direct_access=True,
            startup_param=True,
            default_value='+00000')

        self._param_dict.add(Parameter.HEADING_BIAS,
            r'EB = ([\+\-\d]+) \-+ Heading Bias',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Heading Bias",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='+00000')

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="speed of sound",
            startup_param=True,
            direct_access=True,
            default_value=1485)

        self._param_dict.add(Parameter.TRANSDUCER_DEPTH,
            r'ED = (\d+) \-+ Transducer Depth ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Transducer Depth",
            startup_param=True,
            direct_access=True,
            default_value=2000)

        self._param_dict.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pitch",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="roll",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="salinity",
            startup_param=True,
            direct_access=True,
            default_value=35)

        self._param_dict.add(Parameter.COORDINATE_TRANSFORMATION,
            r'EX = (\d+) \-+ Coord Transform ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="coordinate transformation",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='00111')

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="sensor source",
            startup_param=True,
            direct_access=True,
            default_value='1111101')

        self._param_dict.add(Parameter.DATA_STREAM_SELECTION,
            r'PD = (\d+) \-+ Data Stream Select',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Data Stream Selection",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.SYNC_PING_ENSEMBLE,
            r'SA = (\d+) \-+ Synch Before',
            lambda match: int(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Synch ping ensemble",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='001')

        self._param_dict.add(Parameter.RDS3_MODE_SEL,
            r'SM = (\d+) \-+ Mode Select',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="RDS3 mode selection",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=1)

        # Not used for Master
        #self._param_dict.add(Parameter.SLAVE_TIMEOUT,
        #    r'ST = (\d+) \-+ Slave Timeout',
        #    lambda match: int(match.group(1), base=10),
        #    self._int_to_string,
        #    type=ParameterDictType.INT,
        #    display_name="Slave timeout",
        #    visibility=ParameterDictVisibility.IMMUTABLE,
        #    startup_param=True,
        #    direct_access=True,
        #    default_value=0)

        self._param_dict.add(Parameter.SYNCH_DELAY,
            r'SW = (\d+) \-+ Synch Delay',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Synch delay",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=100)


        self._param_dict.add(Parameter.ENSEMBLE_PER_BURST,
            r'TC (\d+) \-+ Ensembles Per Burst',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Ensemble per burst",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time per ensemble",
            startup_param=True,
            direct_access=True,
            default_value='00:00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time of first ping",
            startup_param=False,
            direct_access=False,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.TIME_PER_PING,
            r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time per ping",
            startup_param=True,
            direct_access=True,
            default_value='00:01.00')

        #self._param_dict.add(Parameter.TIME,
        #    r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
        #    lambda match: str(match.group(1) + " UTC"),
        #    str,
        #    type=ParameterDictType.STRING,
        #    display_name="time",
        #    startup_param=True,
        #    expiration=86400, # expire once per day 60 * 60 * 24
        #    direct_access=True,
        #    visibility=ParameterDictVisibility.IMMUTABLE,
        #    default_value='2014/04/21,20:03:01')

        self._param_dict.add(Parameter.BUFFERED_OUTPUT_PERIOD,
            r'TX (\d\d:\d\d:\d\d) \-+ Buffer Output Period:',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Buffered output period",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='00:00:00')

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD,
            r'WA (\d+,\d+) \-+ False Target Threshold ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="false target threshold",
            startup_param=True,
            direct_access=True,
            default_value='050,001')

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
            r'WB (\d) \-+ Bandwidth Control ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="bandwidth control",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="correlation threshold",
            startup_param=True,
            direct_access=True,
            default_value=64)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD ([\d ]+) \-+ Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial out fw switches",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='111100000')

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="error velocity threshold",
            startup_param=True,
            direct_access=True,
            default_value=2000)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="blank after transmit",
            startup_param=True,
            direct_access=True,
            default_value=88)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="clip data past bottom",
            startup_param=True,
            direct_access=True,
            default_value=False)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="receiver gain select",
            startup_param=True,
            direct_access=True,
            default_value=1)

        #self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
        #    r'WL (\d+,\d+) \-+ Water Reference Layer:  ',
        #    lambda match: str(match.group(1)),
        #    str,
        #    type=ParameterDictType.STRING,
        #    display_name="water reference layer",
        #    startup_param=True,
        #    direct_access=True,
        #    default_value='001,005')

        #self._param_dict.add(Parameter.WATER_PROFILING_MODE,
        #    r'WM (\d+) \-+ Profiling Mode ',
        #    lambda match: int(match.group(1), base=10),
        #    self._int_to_string,
        #    type=ParameterDictType.INT,
        #    display_name="water profiling mode",
        #    visibility=ParameterDictVisibility.IMMUTABLE,
        #    startup_param=True,
        #    direct_access=True,
        #    default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="number of depth cells",
            startup_param=True,
            direct_access=True,
            default_value=22)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pings per ensemble",
            startup_param=True,
            direct_access=True,
            default_value=1)

        self._param_dict.add(Parameter.SAMPLE_AMBIENT_SOUND,
            r'WQ (\d) \-+ Sample Ambient Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Sample ambient sound",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="depth cell size",
            startup_param=True,
            direct_access=True,
            default_value=100)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="transmit length",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ping weight",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d+) \-+ Mode 1 Ambiguity Vel ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ambiguity velocity",
            startup_param=True,
            direct_access=True,
            default_value=175)

    def _build_param_dict2(self):
        """
        Populate the parameter dictionary with ADCP parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict2.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial data out",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='000 000 000')

        self._param_dict2.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial flow control",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='11110')

        self._param_dict2.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match:  bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="banner",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=0)

        self._param_dict2.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="instrument id",
            direct_access=True,
            startup_param=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=0)

        self._param_dict2.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="sleep enable",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=False)

        self._param_dict2.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="save nvram to recorder",
            startup_param=True,
            default_value=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict2.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode ',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="polled mode",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value=False)

        self._param_dict2.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="xmit power",
            startup_param=True,
            direct_access=True,
            default_value=255)

        self._param_dict2.add(Parameter.LATENCY_TRIGGER,
            r'CX = (\d) \-+ Trigger Enable ',
            lambda match: int(match.group(1), base=10),
            self._bool_to_int,
            type=ParameterDictType.INT,
            display_name="latency trigger",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=False)

        self._param_dict2.add(Parameter.HEADING_ALIGNMENT,
            r'EA = ([\+\-\d]+) \-+ Heading Alignment',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Heading alignment",
            visibility=ParameterDictVisibility.IMMUTABLE,
            direct_access=True,
            startup_param=True,
            default_value='+00000')

        self._param_dict2.add(Parameter.HEADING_BIAS,
            r'EB = ([\+\-\d]+) \-+ Heading Bias',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Heading Bias",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='+00000')

        self._param_dict2.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="speed of sound",
            startup_param=True,
            direct_access=True,
            default_value=1485)

        self._param_dict2.add(Parameter.TRANSDUCER_DEPTH,
            r'ED = (\d+) \-+ Transducer Depth ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Transducer Depth",
            startup_param=True,
            direct_access=True,
            default_value=2000)

        self._param_dict2.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pitch",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="roll",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="salinity",
            startup_param=True,
            direct_access=True,
            default_value=35)

        self._param_dict2.add(Parameter.COORDINATE_TRANSFORMATION,
            r'EX = (\d+) \-+ Coord Transform ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="coordinate transformation",
            startup_param=True,
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='00111')

        self._param_dict2.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="sensor source",
            startup_param=True,
            direct_access=True,
            default_value='1111101')

        self._param_dict2.add(Parameter.DATA_STREAM_SELECTION,
            r'PD = (\d+) \-+ Data Stream Select',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Data Stream Selection",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.SYNC_PING_ENSEMBLE,
            r'SA = (\d+) \-+ Synch Before',
            lambda match: int(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Synch ping ensemble",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='001')

        self._param_dict.add(Parameter.RDS3_MODE_SEL,
            r'SM = (\d+) \-+ Mode Select',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="RDS3 mode selection",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=2)

        self._param_dict.add(Parameter.SLAVE_TIMEOUT,
            r'ST = (\d+) \-+ Slave Timeout',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Slave timeout",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict.add(Parameter.SYNCH_DELAY,
            r'SW = (\d+) \-+ Synch Delay',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Synch delay",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)


        self._param_dict2.add(Parameter.ENSEMBLE_PER_BURST,
            r'TC (\d+) \-+ Ensembles Per Burst',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Ensemble per burst",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time per ensemble",
            startup_param=True,
            direct_access=True,
            default_value='00:00:00.00')

        self._param_dict2.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="time of first ping",
            startup_param=False,
            direct_access=False,
            visibility=ParameterDictVisibility.READ_ONLY)

        #self._param_dict2.add(Parameter.TIME_PER_PING,
        #    r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
        #    lambda match: str(match.group(1)),
        #    str,
        #    type=ParameterDictType.STRING,
        #    display_name="time per ping",
        #    startup_param=True,
        #    direct_access=True,
        #    default_value='00:01.00')

        #self._param_dict2.add(Parameter.TIME,
        #    r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
        #    lambda match: str(match.group(1) + " UTC"),
        #    str,
        #    type=ParameterDictType.STRING,
        #    display_name="time",
        #    startup_param=True,
        #    expiration=86400, # expire once per day 60 * 60 * 24
        #    direct_access=True,
        #    visibility=ParameterDictVisibility.IMMUTABLE,
        #    default_value='2014/04/21,20:03:01')

        self._param_dict2.add(Parameter.BUFFERED_OUTPUT_PERIOD,
            r'TX (\d\d:\d\d:\d\d) \-+ Buffer Output Period:',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="Buffered output period",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='00:00:00')

        self._param_dict2.add(Parameter.FALSE_TARGET_THRESHOLD,
            r'WA (\d+,\d+) \-+ False Target Threshold ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="false target threshold",
            startup_param=True,
            direct_access=True,
            default_value='050,001')

        self._param_dict2.add(Parameter.BANDWIDTH_CONTROL,
            r'WB (\d) \-+ Bandwidth Control ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="bandwidth control",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="correlation threshold",
            startup_param=True,
            direct_access=True,
            default_value=64)

        self._param_dict2.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD ([\d ]+) \-+ Data Out ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="serial out fw switches",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value='111100000')

        self._param_dict2.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="error velocity threshold",
            startup_param=True,
            direct_access=True,
            default_value=2000)

        self._param_dict2.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="blank after transmit",
            startup_param=True,
            direct_access=True,
            default_value=83)

        self._param_dict2.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            type=ParameterDictType.BOOL,
            display_name="clip data past bottom",
            startup_param=True,
            direct_access=True,
            default_value=False)

        self._param_dict2.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="receiver gain select",
            startup_param=True,
            direct_access=True,
            default_value=1)

        #self._param_dict2.add(Parameter.WATER_REFERENCE_LAYER,
        #    r'WL (\d+,\d+) \-+ Water Reference Layer:  ',
        #    lambda match: str(match.group(1)),
        #    str,
        #    type=ParameterDictType.STRING,
        #    display_name="water reference layer",
        #    startup_param=True,
        #    direct_access=True,
        #    default_value='001,005')

        #self._param_dict2.add(Parameter.WATER_PROFILING_MODE,
        #    r'WM (\d+) \-+ Profiling Mode ',
        #    lambda match: int(match.group(1), base=10),
        #    self._int_to_string,
        #    type=ParameterDictType.INT,
        #    display_name="water profiling mode",
        #    visibility=ParameterDictVisibility.IMMUTABLE,
        #    startup_param=True,
        #    direct_access=True,
        #   default_value=1)

        self._param_dict2.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="number of depth cells",
            startup_param=True,
            direct_access=True,
            default_value=22)

        self._param_dict2.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="pings per ensemble",
            startup_param=True,
            direct_access=True,
            default_value=1)

        self._param_dict2.add(Parameter.SAMPLE_AMBIENT_SOUND,
            r'WQ (\d) \-+ Sample Ambient Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="Sample ambient sound",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="depth cell size",
            startup_param=True,
            direct_access=True,
            default_value=94)

        self._param_dict2.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="transmit length",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ping weight",
            startup_param=True,
            direct_access=True,
            default_value=0)

        self._param_dict2.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d+) \-+ Mode 1 Ambiguity Vel ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="ambiguity velocity",
            startup_param=True,
            direct_access=True,
            default_value=175)

    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None

        self._init_params()
        self._init_params2()
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        result = None
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        kwargs['timeout'] = 30

        log.info("SYNCING TIME WITH SENSOR.")
        resp = self._do_cmd_resp(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)
        resp = self._do_cmd_resp2(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)

        # Save setup to nvram and switch to autosample if successful.
        resp = self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)
        resp = self._do_cmd_resp2(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        # Issue start command and switch to autosample if successful.
        self._start_logging()
        self._start_logging2()

        next_state = TeledyneProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        log.trace("in _handler_command_get")
        next_state = None
        result = None
        error = None

        # Grab a baseline time for calculating expiration time.  It is assumed
        # that all data if valid if acquired after this time.
        expire_time = self._param_dict.get_current_timestamp()
        log.trace("expire_time = " + str(expire_time))
        # build a list of parameters we need to get
        param_list = self._get_param_list(*args, **kwargs)
        param_list2 = self._get_param_list2(*args, **kwargs)

        try:
            # Take a first pass at getting parameters.  If they are
            # expired an exception will be raised.
            result = self._get_param_result(param_list, expire_time)
        except InstrumentParameterExpirationException as e:
            # In the second pass we need to update parameters, it is assumed
            # that _update_params does everything required to refresh all
            # parameters or at least those that would expire.

            log.trace("in _handler_command_get Parameter expired, refreshing, %s", e)

            if self._is_logging():
                log.trace("I am logging")
                try:
                    # Switch to command mode,
                    self._stop_logging()

                    self._update_params()
                    # Take a second pass at getting values, this time is should
                    # have all fresh values.
                    log.trace("Fetching parameters for the second time")
                    result = self._get_param_result(param_list, expire_time)
                # Catch all error so we can put ourself back into
                # streaming.  Then rethrow the error
                except Exception as e:
                    error = e

                finally:
                    # Switch back to streaming
                    self._start_logging()

                if(error):
                    raise error
            else:
                log.trace("I am not logging")
                self._update_params()
                # Take a second pass at getting values, this time is should
                # have all fresh values.
                log.trace("Fetching parameters for the second time")
                result = self._get_param_result(param_list, expire_time)

        try:
            # Take a first pass at getting parameters.  If they are
            # expired an exception will be raised.
            result2 = self._get_param_result2(param_list2, expire_time)
        except InstrumentParameterExpirationException as e:
            # In the second pass we need to update parameters, it is assumed
            # that _update_params does everything required to refresh all
            # parameters or at least those that would expire.

            log.trace("in _handler_command_get Parameter expired, refreshing, %s", e)

            if self._is_logging2():
                log.trace("I am logging")
                try:
                    # Switch to command mode,
                    self._stop_logging2()

                    self._update_params2()
                    # Take a second pass at getting values, this time is should
                    # have all fresh values.
                    log.trace("Fetching parameters for the second time")
                    result2 = self._get_param_result2(param_list, expire_time)
                # Catch all error so we can put ourself back into
                # streaming.  Then rethrow the error
                except Exception as e:
                    error = e

                finally:
                    # Switch back to streaming
                    self._start_logging2()

                if(error):
                    raise error
            else:
                log.trace("I am not logging")
                self._update_params2()
                # Take a second pass at getting values, this time is should
                # have all fresh values.
                log.trace("Fetching parameters for the second time")
                result2 = self._get_param_result2(param_list2, expire_time)

        #combine the two results
        result.update(result2)
        #result_combined = ",".join(result, result2)
        return (next_state, result)

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
        log.trace("IN _handler_command_set")
        next_state = None
        result = None
        startup = False

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            result = self._set_params(params, startup)
            result2 = self._set_params2(params, startup)

        return (next_state, result)

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @retval (next_state, result) tuple, (None, (None, )) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._wakeup(timeout=3)
        prompt = self._wakeup2(timeout=3)
        self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")
        return (next_state, (next_agent_state, result))

    def _handler_command_get_calibration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.trace("IN _handler_command_get_calibration")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120

        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        output2 = self._do_cmd_resp2(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        result2 = self._sanitize(base64.b64decode(output2))

        result_combined = ",".join(result, result2)
        return (next_state, (next_agent_state, result_combined))

    def _handler_command_save_setup_to_ram(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)
        result = self._do_cmd_resp2(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)


        return (next_state, result)

    def _handler_command_send_last_sample(self, *args, **kwargs):
        log.debug("IN _handler_command_send_last_sample")

        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = '>\r\n>' # special one off prompt.
        prompt = self._wakeup(timeout=3)
        prompt = self._wakeup2(timeout=3)

        # Disable autosample recover, so it isnt faked out....
        self.disable_autosample_recover = True
        (result, last_sample) = self._do_cmd_resp(TeledyneInstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)
        (result2, last_sample2) = self._do_cmd_resp2(TeledyneInstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)
        # re-enable it.
        self.disable_autosample_recover = False

        last_sample_combined = ",".join(last_sample, last_sample2)
        decoded_last_sample = base64.b64decode(last_sample_combined)

        return (next_state, (next_agent_state, decoded_last_sample))

    def _handler_command_get_instrument_transform_matrix(self, *args, **kwargs):
        """
        get instrument transform matrix.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120  # long time to get params.
        log.debug("in _handler_command_get_configuration")
        output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        output2 = self._do_cmd_resp2(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        result2 = self._sanitize(base64.b64decode(output2))
        result_combined = ",".join(result, result2)
        return (next_state, (next_agent_state, {'result': result_combined}))

    def _handler_command_run_test_200(self, *args, **kwargs):
        """
        run test PT200
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.RUN_TEST_200, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.RUN_TEST_200, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_factory_sets(self, *args, **kwargs):
        """
        run Factory set
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.FACTORY_SETS, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.FACTORY_SETS, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_user_sets(self, *args, **kwargs):
        """
        run user set
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.USER_SETS, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.USER_SETS, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_clear_error_status_word(self, *args, **kwargs):
        """
        clear the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_acquire_error_status_word(self, *args, **kwargs):
        """
        read the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_display_fault_log(self, *args, **kwargs):
        """
        display the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_command_clear_fault_log(self, *args, **kwargs):
        """
        clear the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, *args, **kwargs)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, *args, **kwargs)
        result_combined = ",".join(result, result2)
        return (next_state, result_combined)

    def _handler_autosample_init_params(self, *args, **kwargs):
        """
        initialize parameters.  For this instrument we need to
        put the instrument into command mode, apply the changes
        then put it back.
        """
        log.debug("in _handler_autosample_init_params")
        next_state = None
        result = None
        error = None

        try:
            log.debug("stopping logging without checking")
            self._stop_logging()
            self._init_params()

        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            log.debug("starting logging")
            self._start_logging()

        if (error):
            log.error("Error in apply_startup_params: %s", error)
            raise error

        try:
            log.debug("stopping logging without checking")
            self._stop_logging2()
            self._init_params2()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            log.debug("starting logging")
            self._start_logging2()

        if (error):
            log.error("Error in apply_startup_params2: %s", error)
            raise error

        return (next_state, result)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)

        #if (self._is_logging(timeout)):
        self._stop_logging(timeout)
        self._stop_logging2(timeout)

        next_state = TeledyneProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))


    def _handler_autosample_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change from
        autosample mode.  For this command we have to move the instrument
        into command mode, do the clock sync, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None
        error = None

        logging = False

        self._promptbuf = ""
        self._linebuf = ""

        self._promptbuf2 = ""
        self._linebuf2 = ""

        if self._is_logging():
            logging = True
            # Switch to command mode,
            self._stop_logging()

        if self._is_logging2():
            logging2 = True
            # Switch to command mode,
            self._stop_logging2()

        log.debug("in _handler_autosample_clock_sync")
        try:
            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)

            self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if logging:
                self._start_logging()
            if logging2:
                self._start_logging2()

        if(error):
            raise error

        return (next_state, (next_agent_state, result))


    def _handler_autosample_get_calibration(self, *args, **kwargs):
        """
        execute a get calibration from autosample mode.
        For this command we have to move the instrument
        into command mode, get calibration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)
            self._stop_logging2(*args, **kwargs)

            kwargs['timeout'] = 120
            output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
            output2 = self._do_cmd_resp2(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()
            self._start_logging2()

        if(error):
            raise error

        result = self._sanitize(base64.b64decode(output))
        result2 = self._sanitize(base64.b64decode(output2))
        result_combined = ",".join(result, result2)
        return (next_state, (next_agent_state, result_combined))
        #return (next_state, (next_agent_state, {'result': result}))

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        execute a get configuration from autosample mode.
        For this command we have to move the instrument
        into command mode, get configuration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)
            self._stop_logging2(*args, **kwargs)

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)
            output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
            output2 = self._do_cmd_resp2(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()
            self._start_logging2()

        if(error):
            raise error

        result = self._sanitize(base64.b64decode(output))
        result2 = self._sanitize(base64.b64decode(output2))
        result_combined = ",".join(result, result2)

        return (next_state, (next_agent_state, result_combined))

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        log.debug("IN _handler_direct_access_exit")
        self._send_break()
        self._send_break2()

        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET, TeledyneParameter.TIME_OF_FIRST_PING)
        result2 = self._do_cmd_resp2(TeledyneInstrumentCmds.GET, TeledyneParameter.TIME_OF_FIRST_PING)
        if "****/**/**,**:**:**" not in result:
            log.error("TG not allowed to be set. sending a break to clear it.")

            self._send_break()

        if "****/**/**,**:**:**" not in result2:
            log.error("TG not allowed to be set. sending a break2 to clear it.")

            self._send_break2()

    def _handler_command_acquire_status(self,*args, **kwargs ): # Sung to do
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND

        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA,*args, **kwargs)
        result_AC = self._sanitize(base64.b64decode(output))
        time.sleep(.05)
        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_PT2, *args, **kwargs)
        result_PT2 = self._sanitize(base64.b64decode(output))
        time.sleep(.05)
        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_PT4, *args, **kwargs)
        result_PT4 = self._sanitize(base64.b64decode(output))
        time.sleep(.05)

        output = self._do_cmd_resp2(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA,*args, **kwargs)
        result2_AC = self._sanitize(base64.b64decode(output))
        time.sleep(.05)
        output = self._do_cmd_resp2(TeledyneInstrumentCmds.OUTPUT_PT2, *args, **kwargs)
        result2_PT2 = self._sanitize(base64.b64decode(output))
        time.sleep(.05)
        output = self._do_cmd_resp2(TeledyneInstrumentCmds.OUTPUT_PT4, *args, **kwargs)
        result2_PT4 = self._sanitize(base64.b64decode(output))
        time.sleep(.05)

        result_start = "4 beam status outputs:".join(result_AC)
        result2_start = "5th beam status outputs".join(result2_AC)

        result_4beam = ", ".join([result_start,result_PT2,result_PT4])
        result_5thBeam = ", ".join([result2_start,result2_PT2,result2_PT4])

        result = " ".join(result_4beam, result_5thBeam)
        return (next_state, result)

