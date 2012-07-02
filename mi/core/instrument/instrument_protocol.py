#!/usr/bin/env python

"""
@package ion.services.mi.instrument_protocol Base instrument protocol structure
@file ion/services/mi/instrument_protocol.py
@author Steve Foley, 
        Bill Bollenbacher
@brief Instrument protocol classes that provide structure towards the
nitty-gritty interaction with individual instruments in the system.
@todo Figure out what gets thrown on errors
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import logging
import time
import os
import signal
import re

from mi.core.common import BaseEnum, InstErrorCode
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import get_logger ; log = get_logger()

class InterfaceType(BaseEnum):
    """The methods of connecting to a device"""
    ETHERNET = 'ethernet'
    SERIAL = 'serial'

class InstrumentProtocol(object):
    """
    Base instrument protocol class.
    """    
    def __init__(self, driver_event):
        """
        Base constructor.
        @param driver_event The callback for asynchronous driver events.
        """
        # Event callback to send asynchronous events to the agent.
        self._driver_event = driver_event

        # The connection used to talk to the device.
        self._connection = None
        
        # The protocol state machine.
        self._protocol_fsm = None
        
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

    ########################################################################
    # Helper methods
    ########################################################################
    def got_data(self, data):
        """
        Called by the instrument connection when data is available.
         Defined in subclasses.
        """
        pass
    
    def get_current_state(self):
        """
        Return current state of the protocol FSM.
        """
        return self._protocol_fsm.get_current_state()

    ########################################################################
    # Command build and response parse handlers.
    ########################################################################            
    def _add_response_handler(self, cmd, func, state=None):
        """
        Insert a handler class responsible for handling the response to a
        command sent to the instrument, optionally available only in a
        specific state.
        
        @param cmd The high level key of the command to respond to.
        @param func The function that handles the response
        @param state The state to pair with the command for which the function
        should be used
        """
        if state == None:
            self._response_handlers[cmd] = func
        else:            
            self._response_handlers[(state, cmd)] = func

    def _add_build_handler(self, cmd, func):
        """
        Add a command building function.
        @param cmd The device command to build.
        @param func The function that constructs the command.
        """
        self._build_handlers[cmd] = func
        
    ########################################################################
    # Static helpers to build commands.
    ########################################################################
    def _build_simple_command(self, cmd, *args):
        """
        Builder for simple commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument        
        """
        return "%s%s" % (cmd, self.eoln)
    
    def _build_keypress_command(self, cmd, *args):
        """
        Builder for simple, non-EOLN-terminated commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument        
        """
        return "%s" % (cmd)
    
    def _build_multi_keypress_command(self, cmd, *args):
        """
        Builder for simple, non-EOLN-terminated commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument        
        """
        return "%s%s%s%s%s%s" % (cmd, cmd, cmd, cmd, cmd, cmd)

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific
        formatting.
        
        @param v a boolean value.
        @retval A yes/no string formatted as a Python boolean for set operations.
        @throws InstrumentParameterException if value not a bool.
        """
        
        if not isinstance(v,bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        return str(v)

    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific
        formatting.
        
        @param v An int val.
        @retval an int string formatted for generic set operations.
        @throws InstrumentParameterException if value not an int.
        """
        
        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific
        formatting.
        
        @param v A float val.
        @retval a float string formatted for "generic" set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

class CommandResponseInstrumentProtocol(InstrumentProtocol):
    """
    Base class for text-based command-response instruments.
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        Constructor.
        @param prompts Enum class containing possible device prompts used for
        command response logic.
        @param newline The device newline.
        @driver_event The callback for asynchronous driver events.
        """
        
        # Construct superclass.
        InstrumentProtocol.__init__(self, driver_event)

        # The end of line delimiter.                
        self._newline = newline
    
        # Class of prompts used by device.
        self._prompts = prompts
    
        # Line buffer for input from device.
        self._linebuf = ''
        
        # Short buffer to look for prompts from device in command-response
        # mode.
        self._promptbuf = ''
        
        # Lines of data awaiting further processing.
        self._datalines = []

        # Handlers to build commands.
        self._build_handlers = {}

        # Handlers to parse responses.
        self._response_handlers = {}

        self._last_data_receive_timestamp = None
        
    def _get_response(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument
        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()
                
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            assert isinstance(expected_prompt, str)
            prompt_list = [expected_prompt]            
        while True:
            for item in prompt_list:
                if self._promptbuf.endswith(item):
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)
            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
               
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
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', 0)
        retval = None
        
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
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, expected_prompt=%s,' %
                        (repr(cmd_line), timeout, write_delay, expected_prompt))
        if (write_delay == 0):
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
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
        timeout = kwargs.get('timeout', 10)
        write_delay = kwargs.get('write_delay', 0)

        
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
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
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
                time.sleep(write_delay)
    
    def _do_cmd_direct(self, cmd):
        """
        Issue an untranslated command to the instrument. No response is handled 
        as a result of the command.
        
        @param cmd The high level command to issue
        """

        # Send command.
        log.debug('_do_cmd_direct: <%s>' % cmd)
        self._connection.send(cmd)
 
    ########################################################################
    # Incomming data callback.
    ########################################################################            
    def got_data(self, data):
        """
       Called by the instrument connection when data is available.
       Append line and prompt buffers. Extended by device specific
       subclasses.
        """
        # Update the line and prompt buffers.
        self._linebuf += data        
        self._promptbuf += data
        self._last_data_timestamp = time.time()

    ########################################################################
    # Wakeup helpers.
    ########################################################################            
    
    def _send_wakeup(self):
        """
        Send a wakeup to the device. Overridden by device specific
        subclasses.
        """
        pass
        
    def  _wakeup(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
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
                if self._promptbuf.endswith(item):
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _wakeup_until(self, timeout, desired_prompt, delay=1, no_tries=5):
        """
        Continue waking device until a specific prompt appears or a number
        of tries has occurred.
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
                    
                    
class MenuInstrumentProtocol(CommandResponseInstrumentProtocol):
    """
    Base class for menu-based instrument interfaces that can use a cmd/response approach to
    walking down the menu from its root.
    """
    
    class MenuTree(object):
        # nodes is a dictionary of menu tree nodes that each contain directions, which are lists of cmd/response 
        # pairs that need to be executed in the specified order to get from the root node to the sub-menu node
        # example;
        # nodes = {sub_menu1: [["1", "menu1_prompt"],
        #          sub_menu2: [["1", "menu1_prompt"], ["1", "menu2_prompt"]]
        #         }
        _nodes = {}
        
        def __init__(self, nodes):
            self._nodes = nodes
            
        def get_directions(self, node):
            return self._nodes[node]
           
    def __init__(self, menu, prompts, newline, driver_event):
        """
        Constructor.
        @param prompts Enum class containing possible device prompts used for
        menu system.
        @param newline The device newline.
        @driver_event The callback for asynchronous driver events.
        """
        
        # Construct superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        self._menu = menu

        # The end of line delimiter.                
        self._newline = newline
    
        # Class of prompts used by device.
        self._prompts = prompts
    
        # Linebuffer for input from device.
        self._linebuf = ''
        
        # Short buffer to look for prompts from device in command-response
        # mode.
        self._promptbuf = ''
        
        # Lines of data awaiting further processing.
        self._datalines = []

        # Handlers to build commands.
        self._build_handlers = {}

        # Handlers to parse responses.
        self._response_handlers = {}

        self._last_data_receive_timestamp = None
        
    # DHE Added
    def _get_response(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument
        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()
                
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            assert isinstance(expected_prompt, str)
            prompt_list = [expected_prompt]            
        while True:
            for item in prompt_list:
                if self._promptbuf.endswith(item):
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)
            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
               
    # DHE Added
    def _navigate_and_execute(self, cmd, *args, **kwargs):
        """
        Navigate to a sub-menu and execute a command.  
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the reponse did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', 0)
        retval = None
        
        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)
        
        cmd_line = build_handler(cmd, *args)
        
        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        log.debug('_navigate_and_execute: %s, timeout=%s, write_delay=%s, expected_prompt=%s,' %
                        (repr(cmd_line), timeout, write_delay, expected_prompt))

        #
        # iterate through the path, reading results until we get to the end of the path, 
        # at which point we should be at the submenu we need.
        #
        dict_element = self._param_dict.get_menu_path_read('BAUDRATE')
        for (command, response) in dict_element:
            log.debug('_navigate_and_execute: intermediate command: %s, expected response: %s' % 
                (command, response))
            self._do_cmd_resp(command, expected_prompt = response)

        (final_command, response) = self._param_dict.get_submenu_read('BAUDRATE')
        print "final_command is: " + final_command
        resp_result = self._do_cmd_resp(final_command)
 
        return resp_result

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the reponse did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', 0)
        retval = None

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, expected_prompt=%s,' %
                        (repr(cmd_line), timeout, write_delay, expected_prompt))
        if (write_delay == 0):
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
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

    def got_data(self, data):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers. Extended by device specific
        subclasses.
        """
        self._linebuf += data        
        self._promptbuf += data
        self._last_data_timestamp = time.time()    

