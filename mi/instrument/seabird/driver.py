"""
@package mi.instrument.seabird.driver
@file mi/instrument/seabird/driver.py
@author Roger Unwin
@brief Base class for seabird instruments
Release notes:

None.
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import NotImplementedException

from mi.core.instrument.instrument_protocol import DriverProtocolState
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import NotImplementedException
from mi.core.exceptions import SampleException

from mi.core.time import get_timestamp_delayed

NEWLINE = '\r\n'

SBE_EPOCH = 946713600 # Unix time for SBE epoch 2000-01-01 00:00:00

# default timeout.
TIMEOUT = 20
DEFAULT_ENCODER_KEY = '__default__'

###############################################################################
# Particles
###############################################################################

class SeaBirdParticle(DataParticle):
    """
    Overload the base particle to add in some common parsing logic for SBE
    instruments.  Add regex methods to help identify and parse multiline
    strings.
    """
    @staticmethod
    def regex():
        '''
        Return a regex string to use in matching functions.  This can be used
        for parsing too if more complex parsing isn't needed.
        Static methods  because it is called outside this class.
        @return: uncompiled regex string
        '''
        NotImplementedException()

    @staticmethod
    def regex_compiled():
        '''
        Return a regex compiled regex of the regex
        Static methods  because it is called outside this class.
        @return: compiled regex
        '''
        NotImplementedException()

    def regex_multiline(self):
        '''
        return a dictionary containing uncompiled regex used to match patterns
        in SBE multiline results. includes an encoder method.
        @return: dictionary of uncompiled regexs
        '''
        NotImplementedException()

    def regex_multiline_compiled(self):
        '''
        return a dictionary containing compiled regex used to match patterns
        in SBE multiline results.
        @return: dictionary of compiled regexs
        '''
        result = {}
        for (key, regex) in self.regex_multiline().iteritems():
            result[key] = re.compile(regex, re.DOTALL)

        return result

    def encoders(self):
        '''
        return a dictionary containing encoder methods for parameters
        a special key 'default' can be used to name the default mechanism
        @return: dictionary containing encoder callbacks
        '''
        NotImplementedException()

    def _get_multiline_values(self, split_fun=None):
        '''
        return a dictionary containing keys and found values from a
        multiline sample using the multiline regex
        @param: split_fun - function to which splits sample into lines
        @return: dictionary of compiled regexs
        '''
        result = []

        if(split_fun == None):
            split_fun = self._split_on_newline

        log.debug("Let the parsing begin!")
        matchers = self.regex_multiline_compiled()
        regexs = self.regex_multiline()

        for line in split_fun(self.raw_data):
            log.trace("Line: %s" % line)
            for key in matchers.keys():
                log.trace("match: %s" % regexs.get(key))
                match = matchers[key].search(line)
                if(match):
                    encoder = self._get_encoder(key)
                    if(encoder):
                        log.debug("encoding value %s (%s)" % (key, match.group(1)))
                        value = encoder(match.group(1))
                    else:
                        value = match.group(1)

                    log.trace("multiline match %s = %s (%s)" % (key, match.group(1), value))
                    result.append({
                        DataParticleKey.VALUE_ID: key,
                        DataParticleKey.VALUE: value
                    })

        return result

    def _split_on_newline(self, value):
        '''
        default split method for multiline regex matches
        @param: value string to split
        @return: list of line split on NEWLINE
        '''
        return value.split(NEWLINE)

    def _get_encoder(self, key):
        '''
        Get an encoder for a key, if one isn't specified look for a default.
        Can return None for no encoder
        @param: key encoder we are looking for
        @return: dictionary of encoders.
        '''
        encoder = self.encoders().get(key)
        if(not encoder):
            encoder = self.encoders().get(DEFAULT_ENCODER_KEY)

        return encoder

    def _map_param_to_xml_tag(self, parameter_name):
        '''
        @return: a string containing the xml tag name for a parameter
        '''
        NotImplementedException()

    def _extract_xml_elements(self, node, tag, raise_exception_if_none_found=True):
        """
        extract elements with tag from an XML node
        @param: node - XML node to look in
        @param: tag - tag of elements to look for
        @param: raise_exception_if_none_found - raise an exception if no element is found
        @return: return list of elements found; empty list if none found
        """
        elements = node.getElementsByTagName(tag)
        if raise_exception_if_none_found and len(elements) == 0:
            raise SampleException("No %s in input data: [%s]" % (tag, self.raw_data))
        return elements

    def _extract_xml_element_value(self, node, tag, raise_exception_if_none_found=True):
        """
        extract element value that has tag from an XML node
        @param: node - XML node to look in
        @param: tag - tag of elements to look for
        @param: raise_exception_if_none_found - raise an exception if no value is found
        @return: return value of element
        """
        elements = self._extract_xml_elements(node, tag, raise_exception_if_none_found)
        children = elements[0].childNodes
        if raise_exception_if_none_found and len(children) == 0:
            raise SampleException("No value for %s in input data: [%s]" % (tag, self.raw_data))
        return children[0].nodeValue
    
    def _get_xml_parameter(self, xml_element, parameter_name, type=float):
        return {DataParticleKey.VALUE_ID: parameter_name,
                DataParticleKey.VALUE: type(self._extract_xml_element_value(xml_element, 
                                                                            self._map_param_to_xml_tag(parameter_name)))}
        
    ########################################################################
    # Static helpers.
    ########################################################################
    @staticmethod
    def hex2value(hex_value, divisor=None):
        """
        Convert a SBE hex value to a value.  Some hex values are converted
        from raw counts to volts using a divisor.  If passed the value
        will be calculated, otherwise return an int.
        @param hex_value: string to convert
        @param divisor: conversion value
        @return: int or float of the converted value
        """
        if not isinstance(hex_value, str):
            raise InstrumentParameterException("hex value not a string")

        if divisor != None and divisor == 0:
            raise InstrumentParameterException("divisor can not be 0")

        value = int(hex_value, 16)
        if(divisor != None):
            return float(value) / divisor
        else:
            return value

    @staticmethod
    def yesno2bool(value):
        """
        convert a yes no response to a bool
        @param value: string to convert
        @return: bool
        """
        if not isinstance(value, str):
            raise InstrumentParameterException("value not a string")

        if(value.lower() == 'no'):
            return False
        elif(value.lower() == 'yes'):
            return True
        else:
            raise InstrumentParameterException("Could not convert '%s' to bool" % value)

    @staticmethod
    def disabled2bool(value):
        """
        convert a disabled/enabled to bool
        @param value: string to convert
        @return: bool
        """
        if not isinstance(value, str):
            raise InstrumentParameterException("value not a string")

        if(value.lower() == 'disabled'):
            return False
        elif(value.lower() == 'enabled'):
            return True
        else:
            raise InstrumentParameterException("Could not convert '%s' to bool" % value)

    @staticmethod
    def sbetime2unixtime(value):
        """
        Convert an SBE integer time (epoch 1-1-2000) to unix time
        @param value: sbe integer time
        @return: unix time
        """
        if not isinstance(value, int):
            raise InstrumentParameterException("value not a int")

        return SBE_EPOCH + value


###############################################################################
# Driver
###############################################################################

class SeaBirdInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    Base class for all seabird instrument drivers.
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
        log.debug("in _handler_connected_discover")
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result


###############################################################################
# Protocol
###############################################################################

class SeaBirdProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for seabird driver.
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The sbe26plus newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

    ########################################################################
    # Common handlers
    ########################################################################
    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.  First we set a baseline timestamp
        that all data expirations will be calculated against.  Then we try to get parameter
        value.  If we catch an expired parameter then we will update all parameters and get
        values using the original baseline time that we set at the beginning of this method.
        Assuming our _update_params is updating all parameter values properly then we can
        ensure that all data will be fresh.  Nobody likes stale data!
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @raise InstrumentParameterException if missing or invalid parameter.
        @raise InstrumentParameterExpirationException If we fail to update a parameter
        on the second pass this exception will be raised on expired data
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @param args[1] parameter : startup parameters?
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
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
            self._set_params(params, startup)

        return (next_state, result)

    ########################################################################
    # Private helpers.
    ########################################################################

    def _sync_clock(self, command, date_time_param, timeout=TIMEOUT, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to syncronize the clock
        @param command: command to set6 date time
        @param date_time_param: date time parameter that we want to set
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        @raise: InstrumentProtocolException if command fails
        """
        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        log.debug("Set time format(%s) '%s''", time_format, date_time_param)
        str_val = get_timestamp_delayed(time_format)
        log.debug("Set time value == '%s'", str_val)
        self._do_cmd_resp(command, date_time_param, str_val)

    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @todo: This feels odd.  It feels like some of this logic should
               be handled by the state machine.  It's a pattern that we
               may want to review.  I say this because this command
               needs to be run from autosample or command mode.
        @raise: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("CURRENT STATE: %s", self.get_current_state())
        if (self.get_current_state() != DriverProtocolState.COMMAND and
                    self.get_current_state() != DriverProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        log.debug("sbe apply_startup_params, logging?")
        logging = self._is_logging()
        log.debug("sbe apply_startup_params, logging == %s", logging)

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if(not self._instrument_config_dirty()):
            log.debug("configuration not dirty.  Nothing to do here")
            return True

        error = None

        try:
            if(logging):
                # Switch to command mode,
                log.debug("stop logging")
                self._stop_logging()

            log.debug("sbe apply_startup_params now")
            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if(logging):
                log.debug("sbe apply_startup_params start logging again")
                self._start_logging()

        if(error):
            raise error

    def _start_logging(self):
        """
        Issue the instrument command to start logging data
        """
        raise NotImplementedException()

    def _stop_logging(self):
        """
        Issue the instrument command to stop logging data
        """
        raise NotImplementedException()

    def _is_logging(self):
        """
        Is the instrument in logging or command mode.
        @return: True if streaming, False if in command, None if we don't know
        """
        raise NotImplementedException()

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        startup = False
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        # Only check for readonly parameters if we are not setting them from startup
        if not startup:
            readonly = self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)

            log.debug("set param, but check visibility first")
            log.debug("Read only keys: %s", readonly)

            for (key, val) in params.iteritems():
                if key in readonly:
                    raise InstrumentParameterException("Attempt to set read only parameter (%s)" % key)

        # Make sure this method is overloaded because this just verifies, but doesn't
        # set a damn thing.

    def _update_params(self):
        """
        Send instrument commands to get data to refresh the param_dict cache
        """
        raise NotImplementedException()

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @raise: InstrumentProtocolException if in wrong mode.
        """
        config = self.get_startup_config()
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @raise: InstrumentParameterException
        """
        # Refresh the param dict cache

        self._update_params()

        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s", startup_params)

        for param in startup_params:
            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                log.debug("DIRTY: %s %s != %s", param, self._param_dict.get(param), self._param_dict.get_config_value(param))
                return True

        log.debug("Clean instrument config")
        return False
