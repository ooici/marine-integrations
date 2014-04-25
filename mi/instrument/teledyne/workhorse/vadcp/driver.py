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
from mi.core.common import BaseEnum, InstErrorCode

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

from mi.instrument.teledyne.driver import  TeledyneProtocol



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

        # Line buffer for input from device.
        self._linebuf2 = ''

        # Short buffer to look for prompts from device in command-response
        # mode.
        self._promptbuf2 = ''

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

            self._connections['5thBeam'].init_comms(self._protocol.got_data2, # Sung
                                      self._protocol.got_raw2,  # Sung
                                      self._got_exception,
                                      self._lost_connection_callback)
            self._protocol._connection_5thBeam = self.connections['5thBeam']

        except InstrumentConnectionException as e:
            log.error("Connection Exception: %s", e)
            log.error("Instrument Driver remaining in disconnected state.")
            # Re-raise the exception
            raise
        log.debug('_handler_disconnected_connect exit')
        return next_state, result

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
            self._connections['4Beam'].init_comms(self._protocol.got_data, # Sung
                                      self._protocol.got_raw,  # Sung
                                      self._got_exception,
                                      self._lost_connection_callback)
            self._protocol._connection_4Beam = self.connections['4Beam']

            self._connections['5thBeam'].init_comms(self._protocol.got_data2, # Sung
                                      self._protocol.got_raw2,  # Sung
                                      self._got_exception,
                                      self._lost_connection_callback)
            self._protocol._connection_5thBeam = self.connections['5thBeam']

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

        _connection_4beam = None
        _connection_5thBean = None

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
                    index = self._promptbuf.find(item)
                    if index >= 0:
                        result = self._promptbuf[0:index+len(item)]
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
                if self._promptbuf.rstrip(strip_chars).endswith(item.rstrip(strip_chars)):
                    return (item, self._linebuf2)
                else:
                    time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_raw_response()")


    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param write_delay kwarg for the amount of delay in seconds to pause
        between each character. If none supplied, the DEFAULT_WRITE_DELAY
        value will be used.
        @param timeout optional wakeup and command timeout via kwargs.
        @param expected_prompt kwarg offering a specific prompt to look for
        other than the ones in the protocol class itself.
        @param response_regex kwarg with a compiled regex for the response to
        match. Groups that match will be returned as a string.
        Cannot be supplied with expected_prompt. May be helpful for
        instruments that do not have a prompt.
        @retval resp_result The (possibly parsed) response result including the
        first instance of the prompt matched. If a regex was used, the prompt
        will be an empty string and the response will be the joined collection
        of matched groups.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', self.DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        response_regex = kwargs.get('response_regex', None)
        write_delay = kwargs.get('write_delay', self.DEFAULT_WRITE_DELAY)
        retval = None

        if response_regex and not isinstance(response_regex, self.RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        prompt = self._wakeup(timeout)

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, expected_prompt=%s, response_regex=%s',
                        repr(cmd_line), timeout, write_delay, expected_prompt, response_regex)

        if (write_delay == 0):
            #self._connection.send(cmd_line)
            self._connections['4Beam'].send(cmd_line)
            self._connections['5thBeam'].send(cmd_line)
        else:
            for char in cmd_line:
                self._connections['4Beam'].send(char)
                self._connections['5thBeam'].send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        if response_regex:
            prompt = ""
            result_tuple = self._get_response(timeout,
                                              response_regex=response_regex,
                                              expected_prompt=expected_prompt)
            result_tuple2 = self._get_response2(timeout,
                                              response_regex=response_regex,
                                              expected_prompt=expected_prompt)
            result = " \r\n From 5th beam: ".join(result_tuple, result_tuple2) #Sung -combine the two
            log.error("Sung printing join regex response %s", repr(result))
        else:
            (prompt, result1) = self._get_response(timeout,
                                                  expected_prompt=expected_prompt)
            (prompt2, result2) = self._get_response2(timeout,
                                                  expected_prompt=expected_prompt)

            result = " \r\n From 5th beam: ".join(result1, result2) #Sung -combine the two
            log.error("Sung printing join regex response %s", repr(result))

        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt) #Sung -combine the two

        return resp_result

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
            self._connection_5thBean.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection_4beam.send(char)
                self._connection_5thBean.send(char)
                time.sleep(write_delay)

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

            self._chunker.add_chunk(data, timestamp)
            (timestamp, chunk) = self._chunker.get_next_data()
            while(chunk):
                self._got_chunk2(chunk, timestamp)
                (timestamp, chunk) = self._chunker.get_next_data()


    def _got_chunk2(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample2(ADCP_COMPASS_CALIBRATION_DataParticle,
                                 ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk 2 - successful match for ADCP_COMPASS_CALIBRATION_DataParticle")

        if (self._extract_sample2(ADCP_PD0_PARSED_DataParticle,
                                 ADCP_PD0_PARSED_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk 2 - successful match for ADCP_PD0_PARSED_DataParticle")

        if (self._extract_sample2(ADCP_SYSTEM_CONFIGURATION_DataParticle,
                                 ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk 2 - successful match for ADCP_SYSTEM_CONFIGURATION_DataParticle")

    def _extract_sample2(self, particle_class, regex, line, timestamp, publish=True):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @param timestamp port agent timestamp to include with the particle
        @param publish boolean to publish samples (default True). If True,
               two different events are published: one to notify raw data and
               the other to notify parsed data.

        @retval dict of dicts {'parsed': parsed_sample, 'raw': raw_sample} if
                the line can be parsed for a sample. Otherwise, None.
        @todo Figure out how the agent wants the results for a single poll
            and return them that way from here
        """
        sample = None
        if regex.match(line):

            particle = particle_class(line, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = json.loads(parsed_sample)

        return sample

    def add_to_buffer2(self, data):
        '''
        Add a chunk of data to the internal data buffers
        @param data: bytes to add to the buffer
        '''
        # Update the line and prompt buffers.
        self._linebuf2 += data
        self._promptbuf2 += data
        self._last_data_timestamp2 = time.time()

        log.debug("LINE BUF: %s", self._linebuf2)
        log.debug("PROMPT BUF: %s", self._promptbuf2)

    ########################################################################
    # Incomming raw data callback.
    ########################################################################
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
        particle = RawDataParticle(port_agent_packet.get_as_dict(),
                                   port_timestamp=port_agent_packet.get_timestamp())

        if self._driver_event:
            self._driver_event(DriverAsyncEvent.SAMPLE, particle.generate())


    ########################################################################
    # Wakeup helpers.
    ########################################################################

    def _send_wakeup(self):
        """
        Send a wakeup to the device. Overridden by device specific
        subclasses.
        """
        pass

    def _wakeup(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        log.debug("clearing promptbuf: %s", self._promptbuf)
        self._promptbuf = ''

        # Grab time for timeout.
        starttime = time.time()

        while True:
            # Send a line return and wait a sec.
            log.trace('Sending wakeup. timeout=%s', timeout)
            self._send_wakeup()
            time.sleep(delay)

            log.debug("Prompts: %s", self._get_prompts())

            for item in self._get_prompts():
                log.debug("buffer: %s", self._promptbuf)
                log.debug("find prompt: %s", item)
                index = self._promptbuf.find(item)
                log.debug("Got prompt (index: %s): %s ", index, repr(self._promptbuf))
                if index >= 0:
                    log.trace('wakeup got prompt: %s', repr(item))
                    return item
            log.debug("Searched for all prompts")

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in _wakeup()")

    def _wakeup_until(self, timeout, desired_prompt, delay=1, no_tries=5):
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
            prompt = self._wakeup(timeout, delay)
            if prompt == desired_prompt:
                break
            else:
                time.sleep(delay)
                count += 1
                if count >= no_tries:
                    raise InstrumentProtocolException('Incorrect prompt.')

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


    def _do_cmd_direct(self, cmd):
        """
        Issue an untranslated command to the instrument. No response is handled
        as a result of the command.

        @param cmd The high level command to issue
        """

        # Send command.
        log.debug('_do_cmd_direct: <%s>' % cmd)
        #self._connection.send(cmd)
        self._connections['4Beam'].send(cmd)
        self._connections['5thBeam'].send(cmd)

    ############################



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
            default_value=8000)

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

        self._param_dict.add(Parameter.TIME,
            r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
            lambda match: str(match.group(1) + " UTC"),
            str,
            type=ParameterDictType.STRING,
            display_name="time",
            startup_param=True,
            expiration=86400, # expire once per day 60 * 60 * 24
            direct_access=True,
            visibility=ParameterDictVisibility.IMMUTABLE,
            default_value='2014/04/21,20:03:01')

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
            default_value=704)

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

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            r'WL (\d+,\d+) \-+ Water Reference Layer:  ',
            lambda match: str(match.group(1)),
            str,
            type=ParameterDictType.STRING,
            display_name="water reference layer",
            startup_param=True,
            direct_access=True,
            default_value='001,005')

        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            r'WM (\d+) \-+ Profiling Mode ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="water profiling mode",
            visibility=ParameterDictVisibility.IMMUTABLE,
            startup_param=True,
            direct_access=True,
            default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            type=ParameterDictType.INT,
            display_name="number of depth cells",
            startup_param=True,
            direct_access=True,
            default_value=100)

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
            default_value=800)

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


