#!/usr/bin/env python

"""
@package mi.dataset.driver Base class for data set driver
@file mi/dataset/driver.py
@author Steve Foley
@brief A generic data set driver package
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import gevent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import DataSourceLocationException
from mi.core.exceptions import ConfigurationException
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import NotImplementedException
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import Parameter
from mi.core.common import BaseEnum

class DataSourceConfigKey(BaseEnum):
    HARVESTER = 'harvester'
    PARSER = 'parser'
    DRIVER = 'driver'

# Driver parameters.
class DriverParameter(BaseEnum):
    ALL = 'ALL'
    RECORDS_PER_SECOND = 'records_per_second'
    PUBLISHER_POLLING_INTERVAL = 'publisher_polling_interval'
    BATCHED_PARTICLE_COUNT = 'batched_particle_count'

class DataSourceLocation(object):
    """
    A structure that keeps track of where data was last accessed. This will
    track both the file/stream position used by a harvester, as well as the
    position inside that stream needed by a parser. The structure can be
    derived off and modified to handle a given file/stream.
    """
    def __init__(self, harvester_position=None, parser_position=None):
        self.harvester_position = harvester_position
        self.parser_position = parser_position

    def update(self, parser_position=None, harvester_position=None):
        """
        Update the DataSourceLocation with a new harvester and/or parser
        position. Update should either update both harvester and parser
        positions at the same time (opened a new file and went somewhere),
        or update the parser alone (updating the file location, but in the
        same file). Updating just the harvester shouldnt make sense...unless
        it involves zeroing out the parser_position, but in that case, supply
        both in the call.

        @param parser_position The structure representing the position the
        parser needs to keep
        @param harvester_position The structure representing the position the
        harvester needs to keep
        @throws DataSourceLocationException when a parser position is missing
        """
        if (parser_position == None):
            raise DataSourceLocationException("Missing parser position!")
        if (harvester_position and parser_position):
            self.harvester_position = harvester_position
            self.parser_position = parser_position
            return
        if (harvester_position == None):
            self.parser_position = parser_position
            return

class DataSetDriverConfigKeys(BaseEnum):
    PARTICLE_MODULE = "particle_module"
    PARTICLE_CLASS = "particle_class"
    DIRECTORY = "directory"
    PATTERN = "pattern"
    FREQUENCY = "frequency"
    HARVESTER = "harvester"
    PARSER = "parser"
    MODULE = "module"
    CLASS = "class"
    URI = "uri"
    CLASS_ARGS = "class_args"

class DataSetDriver(object):
    """
    Base class for data set drivers.  Provides:
    - an interface via callback to publish data
    - an interface via callback to persist driver state
    - an interface via callback to handle exceptions
    - an start and stop sampling
    - a client interface for execute resource

    Subclasses need to include harvesters and parsers and
    be specialized to handle the interaction between the two.
    
    Configurations should contain keys from the DataSetDriverConfigKey class
    and should look something like this example (more full documentation in the
    "Dataset Agent Architecture" page on the OOI wiki):
    {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.txt',
            'frequency': 1,
        },
        'parser': {}
        'driver': {
            'records_per_second'
            'harvester_polling_interval'
            'batched_particle_count'
        }
    }
    """
    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        self._config = config
        self._data_callback = data_callback
        self._state_callback = state_callback
        self._exception_callback = exception_callback
        self._memento = memento
        self._publisher_thread = None

        self._verify_config()
        self._param_dict = ProtocolParameterDict()

        # Updated my set_resource, defaults defined in build_param_dict
        self._polling_interval = None
        self._generate_particle_count = None
        self._particle_count_per_second = None

        self._build_param_dict()

    def shutdown(self):
        self.stop_sampling()

    def start_sampling(self):
        """
        Start a new thread to monitor for data
        """
        self._start_sampling()
        self._start_publisher_thread()

    def stop_sampling(self):
        """
        Stop the sampling thread
        """
        log.debug("Stopping driver now")

        self._stop_sampling()
        self._stop_publisher_thread()

    def _start_sampling(self):
        raise NotImplementedException('virtual method needs to be specialized')

    def _stop_sampling(self):
        raise NotImplementedException('virtual method needs to be specialized')

    def _is_sampling(self):
        """
        Currently the drivers only have two states, command and streaming and
        all resource commands are common, either start or stop autosample.
        Therefore we didn't implement an enitre state machine to manage states
        and commands.  If it does get more complex than this we should take the
        time to implement a state machine to add some flexibility
        """
        raise NotImplementedException('virtual method needs to be specialized')

    def cmd_dvr(self, cmd, *args, **kwargs):
        log.warn("DRIVER: cmd_dvr %s", cmd)

        resource_cmd = args[0]

        if cmd == 'execute_resource':
            if resource_cmd == DriverEvent.START_AUTOSAMPLE:
                return (ResourceAgentState.STREAMING, None)

            elif resource_cmd == DriverEvent.STOP_AUTOSAMPLE:
                self.stop_sampling()
                return (ResourceAgentState.COMMAND, None)

            else:
                log.error("Unhandled resource command: %s", resource_cmd)
                raise

        elif cmd == 'get_resource_capabilities':
            return self.get_resource_capabilities()

        elif cmd == 'set_resource':
            return self.set_resource(*args, **kwargs)

        elif cmd == 'get_resource':
            return self.get_resource(*args, **kwargs)

        elif cmd == 'disconnect':
            pass

        else:
            log.error("Unhandled command: %s", cmd)
            raise InstrumentStateException("Unhandled command: %s" % cmd)

    def get_resource_capabilities(self, current_state=True, *args, **kwargs):
        """
        Return driver commands and parameters.
        @param current_state True to retrieve commands available in current
        state, otherwise reutrn all commands.
        @retval list of AgentCapability objects representing the drivers
        capabilities.
        @raises NotImplementedException if not implemented by subclass.
        """
        res_params = self._param_dict.get_keys()
        res_cmds = [DriverEvent.STOP_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE]

        if current_state and self._is_sampling():
            res_cmds = [DriverEvent.STOP_AUTOSAMPLE]
        elif current_state and not self._is_sampling():
            res_cmds = [DriverEvent.START_AUTOSAMPLE]

        return [res_cmds, res_params]

    def set_resource(self, *args, **kwargs):
        """
        Set the driver parameter
        """
        log.trace("start set_resource")
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        log.trace("set_resource: iterate through params: %s", params)
        for (key, val) in params.iteritems():
            if key in [DriverParameter.BATCHED_PARTICLE_COUNT, DriverParameter.RECORDS_PER_SECOND]:
                if not isinstance(val, int): raise InstrumentParameterException("%s must be an integer" % key)
            if key in [DriverParameter.PUBLISHER_POLLING_INTERVAL]:
                if not isinstance(val, (int, float)): raise InstrumentParameterException("%s must be an float" % key)

            if val <= 0:
                raise InstrumentParameterException("%s must be > 0" % key)

            self._param_dict.set_value(key, val)

        # Set the driver parameters
        self._generate_particle_count = self._param_dict.get(DriverParameter.BATCHED_PARTICLE_COUNT)
        self._particle_count_per_second = self._param_dict.get(DriverParameter.RECORDS_PER_SECOND)
        self._polling_interval = self._param_dict.get(DriverParameter.PUBLISHER_POLLING_INTERVAL)
        log.trace("Driver Parameters: %s, %s, %s", self._polling_interval, self._particle_count_per_second, self._generate_particle_count)

    def get_resource(self, *args, **kwargs):
        """
        Get driver parameter
        """
        result = {}

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter list.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retrieve each key in the list, raise if any are invalid.
        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                try:
                    val = self._param_dict.get(key)
                    result[key] = val

                except KeyError:
                    raise InstrumentParameterException(('%s is not a valid parameter.' % key))

        return result

    def _verify_config(self):
        """
        virtual method to verify the supplied driver configuration is value.  Must
        be overloaded in sub classes.

        raises an ConfigurationException when a configuration error is detected.
        """
        raise NotImplementedException('virtual methond needs to be specialized')

    def _build_param_dict(self):
        """
        Setup three common driver parameters
        """
        self._param_dict.add_parameter(
            Parameter(
                DriverParameter.RECORDS_PER_SECOND,
                int,
                value=60,
                type=ParameterDictType.INT,
                display_name="Records Per Second",
                description="Number of records to process per second")
        )

        self._param_dict.add_parameter(
            Parameter(
                DriverParameter.PUBLISHER_POLLING_INTERVAL,
                float,
                value=1,
                type=ParameterDictType.FLOAT,
                display_name="Harvester Polling Interval",
                description="Duration in minutes to wait before checking for new files.")
        )

        self._param_dict.add_parameter(
            Parameter(
                DriverParameter.BATCHED_PARTICLE_COUNT,
                int,
                value=1,
                type=ParameterDictType.INT,
                display_name="Batched Particle Count",
                description="Number of particles to batch before sending to the agent")
        )

        config = self._config.get(DataSourceConfigKey.DRIVER, {})
        log.debug("set_resource on startup with: %s", config)
        self.set_resource(config)

    def _start_publisher_thread(self):
        self._publisher_thread = gevent.spawn(self._publisher_loop)
        self._publisher_shutdown = False

    def _stop_publisher_thread(self):
        log.debug("Signal shutdown")
        self._publisher_shutdown = True
        if self._publisher_thread:
            self._publisher_thread.kill(block=False)
        log.debug("shutdown complete")

    def _publisher_loop(self):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        """
        log.info("Starting main publishing loop")

        try:
            while(not self._publisher_shutdown):
                self._poll()
                gevent.sleep(self._polling_interval)
        except Exception as e:
            log.error("Exception in publisher thread: %s", e)
            self._exception_callback(e)

        log.debug("publisher thread detected shutdown request")

    def _poll(self):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _new_file_exception(self):
        raise NotImplementedException('virtual methond needs to be specialized')


class SimpleDataSetDriver(DataSetDriver):
    """
    Simple data set driver handles cases where we are watching a single file and pushing the
    content into a single parser.  The hope is this class can be used for 80% of the drivers
    we implement.
    """
    _harvester = None
    _new_file_queue = []
    _harvester_state = None
    _parser_state = None

    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        super(SimpleDataSetDriver, self).__init__(config, memento, data_callback, state_callback, exception_callback)

        self._init_state(memento)

    def _is_sampling(self):
        """
        Are we currently sampling?
        """
        if self._harvester:
            return True
        else:
            return False

    def _start_sampling(self):
        # just a little nap before we start working.  Giving the agent time
        # to respond.
        try:
            self._harvester = self._build_harvester(self._harvester_state)
            self._harvester.start()
        except Exception as e:
            log.debug("Exception detected when starting sampling: %s", e, exc_info=True)
            self._exception_callback(e)

    def _stop_sampling(self):
        log.debug("Shutting down harvester")
        if self._harvester and self._harvester.is_alive():
            log.debug("Stopping harvester thread")
            self._harvester.shutdown()
            self._harvester = None
        else:
            log.debug("poller not running. not need to shutdown")

    ####
    ##    Helpers
    ####
    def _build_parser(self, memento, infile):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _build_harvester(self, memento):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _verify_config(self):
        """
        Verify we have good configurations for the parser and harvester.
        @raise: ConfigurationException if configuration is invalid
        """
        errors = []
        log.debug("Driver Config: %s", self._config)

        harvester_config = self._config.get(DataSourceConfigKey.HARVESTER)

        if harvester_config:
            if not harvester_config.get('directory'): errors.append("harvester config missing 'directory")
            if not harvester_config.get('pattern'): errors.append("harvester config missing 'pattern")
        else:
            errors.append("missing 'harvester' config")

        if errors:
            log.error("Driver configuration error: %r", errors)
            raise ConfigurationException("driver configuration errors: %r", errors)

        def _nextfile_callback(self):
            pass

        self._harvester_config = harvester_config
        self._parser_config = self._config.get(DataSourceConfigKey.PARSER)

    def _poll(self):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        """
        # If we have files, grab the first and process it.
        count = len(self._new_file_queue)
        log.trace("Checking for new files in queue, count: %d", count)
        if(count > 0):
            self._got_file(self._new_file_queue.pop(0))

    def _got_file(self, file_tuple):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_tuple: (file_handle, file_name) tuple returned by the harvester
        """
        handle, name = file_tuple
        log.info("Detected new file, handle: %r, name: %s", handle, name)
        count = 1
        delay = None

        # Calulate the delay between grabbing records to publish.
        if self._generate_particle_count:
            delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)

        if self._generate_particle_count:
            count = self._generate_particle_count

        # For some reason when adding the handle to the _new_file_queue the file
        # handle is closed.  Haven't had a chance to investigate, but this hack
        # re-opens the file.
        handle = open(handle.name, handle.mode)

        parser = self._build_parser(self._parser_state, handle)

        while(True):
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break

        # Once we have successfully imported the file reset the parser state
        # and store the harvester state.
        self._save_harvester_state(name)

    def _save_driver_state(self):
        """
        Build a memento object from the harvester and parser state and tell the
        agent, via callback, to persist the state.
        """
        state = self._get_memento()
        self._state_callback(state)

    def _save_parser_state(self, state):
        """
        Callback to store the parser state in the driver object.
        @param state: Object used by the parser to indicate position
        """
        log.trace("saving parser state: %r", state)
        self._parser_state = state
        self._save_driver_state()

    def _save_harvester_state(self, state):
        """
        Store the harvester state in the driver when a file is successfully parsed.
        We reset the parser state because we will need to start from the beginning
        of the next file.
        @param filename: file name we successfully parsed and imported.
        """
        log.debug("saving harvester state: %r", state)
        self._parser_state = None
        self._harvester_state = state
        self._save_driver_state()

    def _get_memento(self):
        """
        Build a memento object from internal driver states.
        @return: driver state stucture.
        """
        return {
            DataSourceConfigKey.HARVESTER: self._harvester_state,
            DataSourceConfigKey.PARSER: self._parser_state
        }

    def _init_state(self, memento):
        """
        Break apart a memento into parser and harvester state
        @param memento: agent persisted memento containing both parser and harvester state
        """
        if memento != None:
            if not isinstance(memento, dict): raise TypeError("memento must be a dict.")

            self._harvester_state = memento.get(DataSourceConfigKey.HARVESTER)
            self._parser_state = memento.get(DataSourceConfigKey.PARSER)

    def _new_file_callback(self, file_handle, file_name):
        """
        Callback used by the harvester called when a new file is detected.  Store the
        file handle and filename in a queue.
        @param file_handle: file handle to the new found file.
        @param file_name: file name of the found file.
        """
        index = len(self._new_file_queue)

        log.trace("Add new file to the new file queue: handle: %r, name: %s", file_handle, file_name)
        self._new_file_queue.append((file_handle, file_name))

        count = len(self._new_file_queue)
        log.trace("Current new file queue length: %d", count)
