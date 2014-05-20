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

import re
import time
import json
from functools import partial

from mi.core.log import get_logger ; log = get_logger()

from threading import Thread

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.common import BaseEnum, InstErrorCode
from mi.core.instrument.data_particle import RawDataParticle
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverScheduler
from mi.core.driver_scheduler import DriverSchedulerConfigKey

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentEvent

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.driver_dict import DriverDict
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import NotImplementedException
from mi.core.exceptions import InstrumentParameterExpirationException

MAX_BUFFER_SIZE=32768
DEFAULT_CMD_TIMEOUT=20
DEFAULT_WRITE_DELAY=0
RE_PATTERN = type(re.compile(""))

class InterfaceType(BaseEnum):
    """The methods of connecting to a device"""
    ETHERNET = 'ethernet'
    SERIAL = 'serial'

class InitializationType(BaseEnum):
    NONE = 0,
    STARTUP = 1,
    DIRECTACCESS = 2

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
        
        # The parameter, comamnd, and driver dictionaries.
        self._param_dict = ProtocolParameterDict()
        self._cmd_dict = ProtocolCommandDict()
        self._driver_dict = DriverDict()
        
        # The spot to stash a configuration before going into direct access
        # mode
        self._pre_direct_access_config = None

        # Driver configuration passed from the user
        self._startup_config = {}

        # scheduler config is a bit redundant now, but if we ever want to
        # re-initialize a scheduler we will need it.
        self._scheduler = None
        self._scheduler_callback = {}
        self._scheduler_config = {}

        # Set the initialization type to startup so that startup parameters
        # are applied at the first opertunity.
        self._init_type = InitializationType.STARTUP

    ########################################################################
    # Common handlers
    ########################################################################
    def _handler_get(self, *args, **kwargs):
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
        log.debug("%%% IN base _handler_get")

        next_state = None
        result = None

        # Grab a baseline time for calculating expiration time.  It is assumed
        # that all data if valid if acquired after this time.
        expire_time = self._param_dict.get_current_timestamp()

        # build a list of parameters we need to get
        param_list = self._get_param_list(*args, **kwargs)

        try:
            # Take a first pass at getting parameters.  If they are
            # expired an exception will be raised.
            result = self._get_param_result(param_list, expire_time)
        except InstrumentParameterExpirationException as e:
            # In the second pass we need to update parameters, it is assumed
            # that _update_params does everything required to refresh all
            # parameters or at least those that would expire.
            log.debug("Parameter expired, refreshing, %s", e)
            self._update_params()

            # Take a second pass at getting values, this time is should
            # have all fresh values.
            log.debug("Fetching parameters for the second time")
            result = self._get_param_result(param_list, expire_time)

        return (next_state, result)

    ########################################################################
    # Helper methods
    ########################################################################
    def _init_params(self):
        """
        Initialize parameters based on initialization type.  If we actually
        do some initialization (either startup or DA) after we are done
        set the init type to None so we don't initialize again.
        @raises InstrumentProtocolException if the init_type isn't set or it
                                            is unknown
        """
        if(self._init_type == InitializationType.STARTUP):
            log.debug("_init_params: Apply Startup Config")
            self.apply_startup_params()
            self._init_type = InitializationType.NONE
        elif(self._init_type == InitializationType.DIRECTACCESS):
            log.debug("_init_params: Apply DA Config")
            self.apply_direct_access_params()
            self._init_type = InitializationType.NONE
            pass
        elif(self._init_type == InitializationType.NONE):
            log.debug("_init_params: No initialization required")
            pass
        elif(self._init_type == None):
            raise InstrumentProtocolException("initialization type not set")
        else:
            raise InstrumentProtocolException("Unknown initialization type: %s" % self._init_type)

    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
         Defined in subclasses.
        """
        log.error("base got_data.  Who called me?")
        pass

    def _get_param_result(self,param_list, expire_time):
        """
        return a dictionary of the parameters and values
        @param expire_time: baseline time for expiration calculation
        @return: dictionary of values
        @raise InstrumentParameterException if missing or invalid parameter
        @raise InstrumentParameterExpirationException if value is expired.
        """
        result = {}

        for param in param_list:
            val = self._param_dict.get(param, expire_time)
            result[param] = val

        return result

    def _verify_not_readonly(self, params_to_set, startup=False):
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

        readonly_params = self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)
        if not startup:
            readonly_params += self._param_dict.get_visibility_list(ParameterDictVisibility.IMMUTABLE)

        log.debug("Read only params: %s", readonly_params)

        not_settable = []
        for (key, val) in params_to_set.iteritems():
            if key in readonly_params:
                not_settable.append(key)
        if len(not_settable) > 0:
            raise InstrumentParameterException("Attempt to set read only parameter(s) (%s)" %not_settable)

        return True

    def _extract_sample(self, particle_class, regex, line, timestamp, publish=True):
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

    def get_current_state(self):
        """
        Return current state of the protocol FSM.
        """
        return self._protocol_fsm.get_current_state()

    def get_resource_capabilities(self, current_state=True):
        """
        """
        res_cmds = self._protocol_fsm.get_events(current_state)
        res_cmds = self._filter_capabilities(res_cmds)        
        res_params = self._param_dict.get_keys()
        
        return [res_cmds, res_params]

    def _filter_capabilities(self, events):
        """
        """
        return events

    def _async_agent_state_change(self, agent_state):
        """
        Used when we need to change the agent state from an asych
        process.

        @param agent_state: New agent state
        """
        val = {
            'event' : ResourceAgentEvent.CHANGE_STATE_ASYNC,
            'args' : [agent_state]
        }

        self._driver_event(DriverAsyncEvent.AGENT_EVENT, val)

    def _async_raise_fsm_event(self, event, *args, **kwargs):
        """
        Spawn a new thread and raise an FSM event.  This is intended to be used from the listener
        thread.  If not used the port agent client could be blocked when a FSM event is raised.
        @param event: event to raise
        @param args: args for the event
        @param kwargs: ignored
        """
        log.info("_async_raise_fsm_event: starting new thread to raise event")

        args = list(args)

        log.debug('_async_raise_fsm_event event: %s args: %r', event, args)

        args.insert(0, event)

        new_thread = Thread(
            target=self._protocol_fsm.on_event,
            args=args)
        new_thread.start()

        log.info("_async_raise_fsm_event: event complete. bub bye thread.")

    ########################################################################
    # Scheduler interface.
    ########################################################################
    def _remove_scheduler(self, name):
        """
        remove a scheduler in a driver.
        @param name the name of the job
        @raise KeyError if we try to remove a non-existent job 
        """
        if(not self._scheduler_callback.get(name)):
            raise KeyError("scheduler does not exist for '%s'" % name)

        log.debug("removing scheduler: %s" % name)
        callback = self._scheduler_callback.get(name)
        try:
            self._scheduler.remove_job(callback)
        except KeyError:
            log.warning('Unable to remove job from scheduler.')
        self._scheduler_callback.pop(name)
        self._scheduler_config.pop(name, None)
    
    def _add_scheduler(self, name, callback):
        """
        Stage a scheduler in a driver.  The job will actually be configured
        and started by initialize_scheduler

        @param name the name of the job
        @param callback the handler when the job is triggered
        @raise KeyError if we try to add a job twice
        """
        if(self._scheduler_callback.get(name)):
            raise KeyError("duplicate scheduler exists for '%s'" % name)

        log.debug("Add scheduler callback: %s" % name)
        self._scheduler_callback[name] = callback
        self._add_scheduler_job(name)

    def _add_scheduler_event(self, name, event):
        """
        Create a scheduler, but instead of passing a callback we pass in
        an event to raise.  A callback function is dynamically created
        to do this.
        @param name the name of the job
        @param event: event to raise when the scheduler is triggered
        @raise KeyError if we try to add a job twice
        """
        # Create a callback for the scheduler to raise an event
        def event_callback(self, event):
            log.info("driver job triggered, raise event: %s" % event)
            self._protocol_fsm.on_event(event)

        # Dynamically create the method and add it
        method = partial(event_callback, self, event)
        self._add_scheduler(name, method)

    def _add_scheduler_job(self, name):
        """
        Map the driver configuration to a scheduler configuration.  If
        the scheduler has been started then also add the job.
        @param name the name of the job
        @raise KeyError if job name does not exists in the callback config
        @raise KeyError if job is already configured
        """
        # Do nothing if the scheduler isn't initialized
        if(not self._scheduler):
            return

        callback = self._scheduler_callback.get(name)
        if(not callback):
            raise KeyError("callback not defined in driver for '%s'" % name)

        if(self._scheduler_config.get(name)):
            raise KeyError("scheduler job already configured '%s'" % name)

        scheduler_config = self._get_scheduler_config()
        log.debug("Scheduler config: %s" % scheduler_config)

        # No config?  Nothing to do then.
        if(scheduler_config == None):
            return

        job_config = scheduler_config.get(name)

        if(job_config):
            # Store the scheduler configuration
            self._scheduler_config[name] = {
                DriverSchedulerConfigKey.TRIGGER: job_config.get(DriverSchedulerConfigKey.TRIGGER),
                DriverSchedulerConfigKey.CALLBACK: callback
            }
            config = {name: self._scheduler_config[name]}
            log.debug("Scheduler job with config: %s" % config)

            # start the job.  Note, this lazily starts the scheduler too :)
            self._scheduler.add_config(config)

    def _get_scheduler_config(self):
        """
        Get the configuration dictionary to use for initializing jobs

        Returned dictionary structure:
        {
            'job_name': {
                DriverSchedulerConfigKey.TRIGGER: {}
            }
        }

        @return: scheduler configuration dictionary
        """
        # Currently the startup config is in the child class.
        # @TODO should the config code be promoted?
        config = self._startup_config
        return config.get(DriverConfigKey.SCHEDULER)

    def initialize_scheduler(self):
        """
        Activate all configured schedulers added using _add_scheduler.
        Timers start when the job is activated.
        """
        log.debug("Scheduler config: %s" % self._get_scheduler_config())
        log.debug("Scheduler callbacks: %s" % self._scheduler_callback)
        self._scheduler = DriverScheduler()
        for name in self._scheduler_callback.keys():
            log.debug("Add job for callback: %s" % name)
            self._add_scheduler_job(name)

    #############################################################
    # Gap recovery logic
    #############################################################
    def _start_gap_recovery(self, *args, **kwargs):
        """
        Currently this is just a mock implementation so the agent
        tests could be put in place.  Before this code goes into
        production it needs to be completed.

        Start a new gap recovery thread to publish samples.
        """
        raise NotImplementedException("Needs to be implemented")


    #############################################################
    # Configuration logic
    #############################################################

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
        # Let's give it a try in unknown state
        log.debug("apply_startup_params start")

        config = self.get_startup_config()
        log.debug("apply_startup_params: startup config: %s", config)

        readonly = self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)
        log.debug("apply_startup_params: Read only keys: %s", readonly)

        for (key, val) in config.iteritems():
            if key in readonly:
                raise InstrumentParameterException("Attempt to set read only parameter (%s)" % key)

        self._set_params(config, True)

    def apply_direct_access_params(self):
        """
        Apply the da params values previously stored in the protocol to
        the running config of the live instrument.
        @raise InstrumentParameterException If the config cannot be applied
        """
        # Let's give it a try in unknown state
        log.debug("apply_direct_access_params start")

        config = self.get_direct_access_config()
        log.debug("apply_direct_access_params: direct_access config: %s", config)

        self._set_params(config, True)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters.  If
        startup is set to true that means we are setting startup values
        and immutable parameters can be set.  Otherwise only READ_WRITE
        parameters can be set.

        must be overloaded in derived classes

        @param params dictionary containing parameter name and value
        @param startup bool try is we are initializing, false otherwise
        @raise NotImplementedException
        """
        raise NotImplementedException("_set_params must be overloaded")

        
    def set_init_params(self, config):
        """
        Set the initialization parameters to the given values in the protocol
        parameter dictionary. 
        @param config The parameter_name/value to set in the initialization
            fields of the parameter dictionary
        @raise InstrumentParameterException If the config cannot be set
        """
        if not isinstance(config, dict):
            raise InstrumentParameterException("Invalid init config format")

        self._startup_config = config
        
        param_config = config.get(DriverConfigKey.PARAMETERS)
        if(param_config):
            for name in param_config.keys():
                log.debug("Setting init value for %s to %s", name, param_config[name])
                self._param_dict.set_init_value(name, param_config[name])

    def enable_da_initialization(self):
        """
        Tell the protocol to initialize parameters using the stored direct access
        config when in a state that can set parameters
        """
        self._init_type = InitializationType.DIRECTACCESS

    def store_direct_access_config(self, config):
        """
        Save the direct access configuration in the object.  This is generally
        called from the driver because it is responsible for reading the config.
        @param config DA configuration to store.
        """
        self._pre_direct_access_config = config

    def get_direct_access_config(self):
        """
        Gets the direct access stored configuration for the instrument.
        @retval The dict of parameter_name/values (override this method if it
            is more involved for a specific instrument) that should be set at
            a higher level.
        """
        return self._pre_direct_access_config

    def get_startup_config(self):
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
        start_list = self._param_dict.get_keys()
        log.trace("Startup list: %s", start_list)
        assert isinstance(start_list, list)
        
        for param in start_list:
            result = self._param_dict.get_config_value(param)
            if(result != None):
                return_dict[param] = result
            elif(self._param_dict.is_startup_param(param)):
                raise InstrumentProtocolException("Required startup value not specified: %s" % param)

        log.debug("Applying startup config: %s", return_dict)
        return return_dict
        
    def get_direct_access_params(self):
        """
        Get the list of direct access parameters, useful for restoring direct
        access configurations up in the driver.
        
        @retval a list of direct access parameter names
        """
        return self._param_dict.get_direct_access_list()
        
    def get_cached_config(self):
        """
        Return the configuration object that shows the instrument's 
        configuration as cached in the parameter dictionary...usually in
        sync with the instrument, but accessible when offline...
        @retval The cached configuration in the instruments config format. By
        default, it is a dictionary of parameter names and values.
        """
        assert self._param_dict != None
        return self._param_dict.get_config()
        
    def get_config_metadata_dict(self):
        """
        Return a list of metadata about the protocol's driver support,
        command formats, and parameter formats. The format should be easily
        JSONifyable (as will happen in the driver on the way out to the agent)
        @retval A python dict that represents the metadata
        @see https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+SV+Instrument+Driver-Agent+parameter+and+command+metadata+exchange
        """
        log.debug("Getting metadata dict from protocol...")
        return_dict = {}
        return_dict[ConfigMetadataKey.DRIVER] = self._driver_dict.generate_dict()
        return_dict[ConfigMetadataKey.COMMANDS] = self._cmd_dict.generate_dict()
        return_dict[ConfigMetadataKey.PARAMETERS] = self._param_dict.generate_dict()
        
        return return_dict
        
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
    # Helpers to build commands.
    ########################################################################
    def _build_simple_command(self, cmd, *args):
        """
        Builder for simple commands

        @param cmd The command to build
        @param args Unused arguments
        @retval Returns string ready for sending to instrument        
        """

        return "%s%s" % (cmd, self._newline)
    
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

    def _get_param_list(self, *args, **kwargs):
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
        known_params = self._param_dict.get_keys() + [DriverParameter.ALL]
        for param in param_list:
            if(param not in known_params):
                bad_params.append(param)

        if(len(bad_params)):
            raise InstrumentParameterException("Unknown parameters: %s" % bad_params)

        if(DriverParameter.ALL in param_list):
            return self._param_dict.get_keys()
        else:
            return param_list

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

    def _get_prompts(self):
        """
        Return a list of prompts order from longest to shortest.  The
        assumption is the longer is more specific.
        @return: list of prompts orders by length.
        """
        if isinstance(self._prompts, list):
            prompts = self._prompts
        else:
            prompts = self._prompts.list()

        prompts.sort(lambda x, y: cmp(len(y), len(x)))

        return prompts

    def _get_response(self, timeout=10, expected_prompt=None, response_regex=None):
        """
        Get a response from the instrument, but be a bit loose with what we
        find. Leave some room for white space around prompts and not try to
        match that just in case we are off by a little whitespace or not quite
        at the end of a line.
        
        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @param response_regex Look for a response value that matches the
        supplied compiled regex pattern. Groups that match will be returned as a
        string. Cannot be used with expected prompt. None
        will be returned as a prompt with this match. If a regex is supplied,
        internal the prompt list will be ignored.
        @retval Regex search result tuple (as MatchObject.groups() would return
        if a response_regex is supplied. A tuple of (prompt, response) if a
        prompt is looked for.
        @throw InstrumentProtocolException if both regex and expected prompt are
        passed in or regex is not a compiled pattern.
        @throw InstrumentTimeoutException on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()
        
        if response_regex and not isinstance(response_regex, RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')
        
        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')
            
        if expected_prompt is None:
            prompt_list = self._get_prompts()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        if response_regex is None:
            pattern = None
        else:
            pattern = response_regex.pattern

        log.debug('_get_response: timeout=%s, prompt_list=%s, expected_prompt=%s, response_regex=%r, promptbuf=%s',
                  timeout, prompt_list, expected_prompt, pattern, self._promptbuf)
        while True:
            if response_regex:
                match = response_regex.search(self._linebuf)
                if match:
                    return match.groups()
            else:
                for item in prompt_list:
                    index = self._promptbuf.find(item)
                    if index >= 0:
                        result = self._promptbuf[0:index+len(item)]
                        return item, result

            time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def _get_raw_response(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument, but don't trim whitespace. Used in
        times when the whitespace is what we are looking for.
        
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolException on timeout
        """
        # Grab time for timeout and wait for prompt.
        strip_chars = "\t "

        starttime = time.time()
        if expected_prompt is None:
            prompt_list = self._get_prompts()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        while True:
            for item in prompt_list:
                if self._promptbuf.rstrip(strip_chars).endswith(item.rstrip(strip_chars)):
                    return (item, self._linebuf)
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
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        response_regex = kwargs.get('response_regex', None)
        write_delay = kwargs.get('write_delay', DEFAULT_WRITE_DELAY)

        if response_regex and not isinstance(response_regex, RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')
        
        if expected_prompt and response_regex:
            raise InstrumentProtocolException('Cannot supply both regex and expected prompt!')
        
        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        self._wakeup(timeout)
        
        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, expected_prompt=%s, response_regex=%s',
                        repr(cmd_line), timeout, write_delay, expected_prompt, response_regex)

        if (write_delay == 0):
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        if response_regex:
            prompt = ""
            result_tuple = self._get_response(timeout,
                                              response_regex=response_regex,
                                              expected_prompt=expected_prompt)
            result = "".join(result_tuple)
        else:
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

        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        write_delay = kwargs.get('write_delay', DEFAULT_WRITE_DELAY)
        
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
    # Incoming data (for parsing) callback.
    ########################################################################            
    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """

        data_length = port_agent_packet.get_data_length()
        data = port_agent_packet.get_data()
        timestamp = port_agent_packet.get_timestamp()

        log.debug("Got Data: %r" % data)
        log.debug("Add Port Agent Timestamp: %s" % timestamp)

        if data_length > 0:
            if self.get_current_state() == DriverProtocolState.DIRECT_ACCESS:
                self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)

            self.add_to_buffer(data)

            self._chunker.add_chunk(data, timestamp)
            (timestamp, chunk) = self._chunker.get_next_data()
            while(chunk):
                self._got_chunk(chunk, timestamp)
                (timestamp, chunk) = self._chunker.get_next_data()

    ########################################################################
    # Incoming raw data callback.
    ########################################################################            
    def got_raw(self, port_agent_packet):
        """
        Called by the port agent client when raw data is available, such as data 
        sent by the driver to the instrument, the instrument responses,etc.
        """
        self.publish_raw(port_agent_packet)

    def publish_raw(self, port_agent_packet):
        """
        Publish raw data
        @param: port_agent_packet port agent packet containing raw
        """
        particle = RawDataParticle(port_agent_packet.get_as_dict(),
                                   port_timestamp=port_agent_packet.get_timestamp())

        if self._driver_event:
            self._driver_event(DriverAsyncEvent.SAMPLE, particle.generate())

    def add_to_buffer(self, data):
        '''
        Add a chunk of data to the internal data buffers
        buffers implemented as lifo ring buffer
        @param data: bytes to add to the buffer
        '''
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._last_data_timestamp = time.time()

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        if(len(self._linebuf) > self._max_buffer_size()):
            self._linebuf = self._linebuf[self._max_buffer_size()*-1:]

        # If our buffer exceeds the max allowable size then drop the leading
        # characters on the floor.
        if(len(self._promptbuf) > self._max_buffer_size()):
            self._promptbuf = self._linebuf[self._max_buffer_size()*-1:]

        log.debug("LINE BUF: %s", self._linebuf)
        log.debug("PROMPT BUF: %s", self._promptbuf)

    def _max_buffer_size(self):
        return MAX_BUFFER_SIZE

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
                    
                
class MenuInstrumentProtocol(CommandResponseInstrumentProtocol):
    """
    Base class for menu-based instrument interfaces that can use a cmd/response approach to
    walking down the menu from its root.
    """
    
    class MenuTree(object):
        # The _node_directions variable is a dictionary of menu sub-menus keyed by the sub-menu's name.
        # Each sub-menu entry contains a list of directions, which are either cmd/response pairs or 
        # sub_menu names. These commands need to be executed in the specified order to get from the root menu
        # to the sub-menu.
        # example:
        #
        # for these enumerations:
        #
        # class SubMenues(BaseEnum):
        #     SUB_MENU1 = 'sub_menu1'
        #     SUB_MENU2 = 'sub_menu2'
        #     SUB_MENU3 = 'sub_menu3'
        #     SUB_MENU4 = 'sub_menu4'
        #
        # class InstrumentPrompts(BaseEnum):
        #     MAIN_MENU = '\a\b ? \a\b'
        #     SUB_MENU1  = '\a\b 1'
        #     SUB_MENU2  = '\a\b 2'
        #     SUB_MENU3  = '\a\b 3'
        #     SUB_MENU4  = '\a\b 4'
        #
        # the instance creation could look like:
        #
        # Directions = MenuInstrumentProtocol.MenuTree.Directions
        #
        # menu = MenuInstrumentProtocol.MenuTree({
        #    SubMenues.SUB_MENU1   : [Directions("1", InstrumentPrompts.SUB_MENU1)],
        #    SubMenues.SUB_MENU2   : [Directions("2", InstrumentPrompts.SUB_MENU2)],
        #    SubMenues.SUB_MENU3   : [Directions(SubMenues.SUB_MENU2),
        #                            Directions("2", InstrumentPrompts.SUB_MENU3, 20)],
        #    SubMenues.SUB_MENU4   : [Directions(SubMenues.SUB_MENU3),
        #                            Directions("d", InstrumentPrompts.SUB_MENU4)]
        #    })
        #
        # After passing the menu into the constructor via:
        # MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)
        #
        # directions can be retrieved for a sub-menu using:
        #
        # directions_list = self._menu.get_directions(SubMenues.SUB_MENU4)
        #
        # which should return a list of Directions objects which can be used to walk from
        # the root menu to the sub-menu as follows:
        #
        # for directions in directions_list:
        #     command = directions.get_command()
        #     response = directions.get_response()
        #     timeout = directions.get_timeout()
        #     do_cmd_reponse(command, expected_prompt = response, timeout = timeout)
        
        class Directions(object):
            def __init__(self, command = None, response = None, timeout = 10):
                if command == None:
                    raise InstrumentProtocolException('MenuTree.Directions(): command parameter missing')                
                self.command = command
                self.response = response
                self.timeout = timeout
                
            def __str__(self):
                return "command=%s, response=%s, timeout=%s" %(repr(self.command), 
                                                               repr(self.response), 
                                                               repr(self.timeout))
            
            def get_command(self):
                return self.command
            
            def get_response(self):
                return self.response
                
            def get_timeout(self):
                return self.timeout
                
        _node_directions = {}
        
        def __init__(self, node_directions):
            if not isinstance(node_directions, dict):
                raise InstrumentProtocolException('MenuTree.__init__(): node_directions parameter not a dictionary')                
            self._node_directions = node_directions
            
        def get_directions(self, node):
            try:
                directions_list = self._node_directions[node]
            except:
                raise InstrumentProtocolException('MenuTree.get_directions(): node %s not in _node_directions dictionary'
                                                  %str(node))                
            log.trace("MenuTree.get_directions(): _node_directions = %s, node = %s, d_list = %s" 
                      %(str(self._node_directions), str(node), str(directions_list)))
            directions = []
            for item in directions_list:
                if not isinstance(item, self.Directions):
                    raise InstrumentProtocolException('MenuTree.get_directions(): item %s in directions list not a Directions object'
                                                      %str(item))                
                if item.response != None:
                    directions.append(item)
                else:
                    directions += self.get_directions(item.command)
            return directions
        
           
    def __init__(self, menu, prompts, newline, driver_event, **kwargs):
        """
        Constructor.
        @param prompts Enum class containing possible device prompts used for
        menu system.
        @param newline The device newline.
        @param driver_event The callback for asynchronous driver events.
        @param read_delay optional kwarg specifying amount of time to delay before
               attempting to read response from instrument (in _get_response).

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
        
        # Initialize read_delay
        self._read_delay = kwargs.get('read_delay', None)
        

    def _get_response(self, timeout=10, expected_prompt=None, **kwargs):
        """
        Get a response from the instrument
        @todo Consider cases with no prompt
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """

        """
        Because the output of the instrument does not generate events, do_cmd_resp 
        jumps right in here looking for a response, and often it is before the 
        complete response has arrived, so we can miss it.  The read delay
        is to alleviate that problem.
        """

        if self._read_delay is not None:
            time.sleep(self._read_delay)
        
        return CommandResponseInstrumentProtocol._get_response(self,
                    timeout=timeout,
                    expected_prompt=expected_prompt)
                 
    def _navigate(self, menu, **kwargs):
        """
        Navigate to the given sub menu and then do nothing
        @param menu The enum for the menu to navigate to.
        @retval A tuple of result and parameter of the last menu encountered
        @throw InstrumentProtocolException When the destination cannot be reached.
        """
        # Get dest_submenu arg
        if menu == None:
            raise InstrumentProtocolException('Menu parameter missing')
        result = (None, None) # base case in case of empty directions list

        # iterate through the directions 
        directions_list = self._menu.get_directions(menu)
        for directions in directions_list:
            log.debug('_navigate: directions: %s' %(directions))
            command = directions.get_command()
            response = directions.get_response()
            timeout = directions.get_timeout()
            result = self._do_cmd_resp(command, expected_prompt=response,
                                       timeout=timeout, **kwargs)
        return result

    def _navigate_and_execute(self, cmd, expected_prompt=None, **kwargs):
        """
        Navigate to a sub-menu and execute a command.  
        @param cmd The command to execute.
        @param expected_prompt optional kwarg passed through to do_cmd_resp.
        @param timeout=timeout optional wakeup and command timeout.
        @param write_delay optional kwarg passed through to do_cmd_resp.
        @throws InstrumentTimeoutException if the response did not occur in time.
        @throws InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        
        self._navigate(kwargs['dest_submenu'], expected_prompt, **kwargs)
        self._do_cmd_resp(cmd, expected_prompt=expected_prompt, **kwargs)
        """
        DHE: this is a kludge; need a way to send a parameter as a "command."  We can't expect to look
        up all possible values in the build_handlers
        """
        value = kwargs.pop('value', None)
        if cmd is None:
            cmd_line = self._build_simple_command(value) 
            log.debug('_navigate_and_execute: sending value: %s to connection.send.' %(cmd_line))
            self._connection.send(cmd_line)
        else:
            log.debug('_navigate_and_execute: sending cmd: %s with kwargs: %s to _do_cmd_resp.' %(cmd, kwargs))
            resp_result = self._do_cmd_resp(cmd, **kwargs)
 
        return resp_result
    
    def _go_to_root_menu(self):
        """
        This method needs to be implemented for each instrument.  It performs the commands that 
        returns the instrument to its root menu
        """
        raise NotImplementedException('_go_to_root_menu() not implemented.')

    def got_data(self, data):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers. Extended by device specific
        subclasses.
        """
        CommandResponseInstrumentProtocol.got_data(self, data)


