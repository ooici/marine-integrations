#!/usr/bin/env python

"""
@package mi.dataset.driver Base class for data set driver
@file mi/dataset/driver.py
@author Steve Foley
@brief A generic data set driver package
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import os
import gevent
import shutil
import hashlib
import copy
import traceback

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import DataSourceLocationException
from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import SampleException
from mi.core.exceptions import DatasetHarvesterException
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import NotImplementedException
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.driver_dict import DriverDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import Parameter
from mi.core.common import BaseEnum

class DataSourceConfigKey(BaseEnum):
    HARVESTER = 'harvester'
    PARSER = 'parser'
    DRIVER = 'driver'
    RESOURCE_ID = 'resource_id'

class DriverStateKey(BaseEnum):
    VERSION = 'version'
    FILE_NAME = 'file_name'
    FILE_SIZE = 'file_size'
    FILE_MOD_DATE = 'file_mod_date'
    FILE_CHECKSUM = 'file_checksum'
    INGESTED = 'ingested'
    PARSER_STATE = 'parser_state'
    MODIFIED_STATE = 'modified_state'

# Driver parameters.
class DriverParameter(BaseEnum):
    ALL = 'ALL'
    RECORDS_PER_SECOND = 'records_per_second'
    PUBLISHER_POLLING_INTERVAL = 'publisher_polling_interval'
    BATCHED_PARTICLE_COUNT = 'batched_particle_count'

class HarvesterType(BaseEnum):
    SINGLE_DIRECTORY = 'single_directory'
    SINGLE_FILE = 'single_file'

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
    STORAGE_DIRECTORY = "storage_directory"
    PATTERN = "pattern"
    FREQUENCY = "frequency"
    FILE_MOD_WAIT_TIME = "file_mod_wait_time"
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
            'storage_directory': '/tmp/stored_dsatest',
            'pattern': '*.txt',
            'frequency': 1,
            'file_mod_wait_time': 30,
        },
        'parser': {}
        'driver': {
            'records_per_second'
            'harvester_polling_interval'
            'batched_particle_count'
        }
    }
    """
    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        self._config = copy.deepcopy(config)
        self._data_callback = data_callback
        self._state_callback = state_callback
        self._event_callback = event_callback
        self._exception_callback = exception_callback
        self._memento = memento
        self._publisher_thread = None

        self._verify_config()

        # Updated my set_resource, defaults defined in build_param_dict
        self._polling_interval = None
        self._generate_particle_count = None
        self._particle_count_per_second = None
        self._resource_id = None

        self._param_dict = ProtocolParameterDict()
        self._cmd_dict = ProtocolCommandDict()
        self._driver_dict = DriverDict()

        self._build_command_dict()
        self._build_driver_dict()
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
        log.debug("Stopping sampling and publisher now")

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

        if cmd == 'execute_resource':
            resource_cmd = args[0]

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

        elif cmd == 'get_config_metadata':
            return self.get_config_metadata(*args, **kwargs)

        elif cmd == 'disconnect':
            pass

        elif cmd == 'initialize':
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
        log.trace("Driver Parameters: %s, %s, %s", self._polling_interval, self._particle_count_per_second,
                  self._generate_particle_count)


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

    def get_config_metadata(self):
        """
        Return the configuration metadata object in JSON format
        @retval The description of the parameters, commands, and driver info
        in a JSON string
        @see https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+SV+Instrument+Driver-Agent+parameter+and+command+metadata+exchange
        """
        log.debug("Getting metadata from driver...")
        log.debug("Getting metadata dict from protocol...")
        return_dict = {}
        return_dict[ConfigMetadataKey.DRIVER] = self._driver_dict.generate_dict()
        return_dict[ConfigMetadataKey.COMMANDS] = self._cmd_dict.generate_dict()
        return_dict[ConfigMetadataKey.PARAMETERS] = self._param_dict.generate_dict()

        return return_dict

    def _verify_config(self):
        """
        virtual method to verify the supplied driver configuration is value.  Must
        be overloaded in sub classes.

        raises an ConfigurationException when a configuration error is detected.
        """
        raise NotImplementedException('virtual methond needs to be specialized')

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        pass

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(DriverEvent.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(DriverEvent.STOP_AUTOSAMPLE, display_name="stop autosample")

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
                visibility=ParameterDictVisibility.IMMUTABLE,
                display_name="Records Per Second",
                description="Number of records to process per second")
        )

        self._param_dict.add_parameter(
            Parameter(
                DriverParameter.PUBLISHER_POLLING_INTERVAL,
                float,
                value=1,
                type=ParameterDictType.FLOAT,
                visibility=ParameterDictVisibility.IMMUTABLE,
                display_name="Harvester Polling Interval",
                description="Duration in minutes to wait before checking for new files.")
        )

        self._param_dict.add_parameter(
            Parameter(
                DriverParameter.BATCHED_PARTICLE_COUNT,
                int,
                value=1,
                type=ParameterDictType.INT,
                visibility=ParameterDictVisibility.IMMUTABLE,
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
            log.error("Exception in publisher thread (resource id: %s): %s", self._resource_id, traceback.format_exc(e))
            self._exception_callback(e)

        log.debug("publisher thread detected shutdown request")

    def _poll(self):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _new_file_exception(self):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _sample_exception_callback(self, exception):
        """
        Publish an event when a sample exception is detected
        """
        self._event_callback(event_type="ResourceAgentErrorEvent", error_msg = "%s" % exception)


    def _raise_new_file_event(self, name):
        """
        Raise a ResourceAgentIOEvent when a new file is detected.  Add file stats
        to the payload of the event.
        """
        s = os.stat(name)
        checksum = ""
        with open(name, 'rb') as filehandle:
            checksum = hashlib.md5(filehandle.read()).hexdigest()

        stats = {
            'name': name,
            'size': s.st_size,
            'mod': s.st_mtime,
            'md5_checksum': checksum
        }

        self._event_callback(event_type="ResourceAgentIOEvent", source_type="new file", stats=stats)


class SimpleDataSetDriver(DataSetDriver):
    """
    Simple data set driver handles cases where we are watching a single directory and pushing the
    content into a single parser.  The hope is this class can be used for 80% of the drivers
    we implement.
    """
    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        self._new_file_queue = []

        super(SimpleDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback, exception_callback)
        self._harvester = None
        self._driver_state = None

        self._init_state(memento)

        self._ingest_directory = self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)

        self._resource_id = self._config.get(DataSourceConfigKey.RESOURCE_ID)
        log.debug("Resource ID: %s", self._resource_id)

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
            self._harvester = self._build_harvester(self._driver_state)
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
            log.debug("poller not running. no need to shutdown")

    ####
    ##    Helpers
    ####
    def _build_parser(self, memento, infile):
        raise NotImplementedException('virtual method needs to be specialized')

    def _build_harvester(self, memento):
        raise NotImplementedException('virtual method needs to be specialized')

    def _verify_config(self):
        """
        Verify we have good configurations for the parser and harvester.
        @raise: ConfigurationException if configuration is invalid
        """
        errors = []
        log.debug("Driver Config: %s", self._config)

        self._harvester_config = self._config.get(DataSourceConfigKey.HARVESTER)
        if self._harvester_config:
            if not self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY):
                errors.append("harvester config missing 'directory")
            #if not harvester_config.get(DataSetDriverConfigKeys.STORAGE_DIRECTORY):
            #    errors.append("harvester config missing 'storage_directory")
            if not self._harvester_config.get(DataSetDriverConfigKeys.PATTERN):
                errors.append("harvester config missing 'pattern")
        else:
            errors.append("missing 'harvester' config")

        if errors:
            log.error("Driver configuration error: %r", errors)
            raise ConfigurationException("driver configuration errors: %r", errors)

        self._parser_config = self._config.get(DataSourceConfigKey.PARSER)


    def _poll(self):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        """
        # If we have files, grab the first and process it.
        count = len(self._new_file_queue)
        log.trace("Checking for new files in queue, count: %d", count)
        if(count > 0):
            log.debug("New file detected, resource_id: %s, array addr: %s", self._resource_id, id(self._new_file_queue))
            self._got_file(self._new_file_queue.pop(0))

    def _stage_input_file(self, path):
        """
        Store a file from the input directory in storage directory
        """
        storage_directory = self._harvester_config.get(DataSetDriverConfigKeys.STORAGE_DIRECTORY)
        log.debug("Storage Dir: %s", storage_directory)

        filename = os.path.basename(path)
        basedir = os.path.dirname(path)
        log.debug("Filename: %s", filename)

        destdir = os.path.join(storage_directory, basedir.lstrip('/'))
        log.debug("DestDir: %s", destdir)

        destpath = os.path.join(destdir, "%s.%s" % (filename, self._resource_id))
        log.debug("DestPath: %s", destpath)

        if os.path.isdir(destdir):
            log.debug("path exists, '%s'", destdir)
        else:
            if os.path.exists(destdir):
                log.error("storage directory exists and is not a directory. '%s'", destdir)

            log.debug("storage path doesn't exist, creating '%s'", destdir)
            try:
                os.makedirs(destdir)
            except Exception as e:
                log.error("Failed to create stage directory '%s': %s", destdir, str(e))
                return

        if os.path.exists(destpath):
            log.error("'%s' exists, not overwriting", destpath)
        else:
            log.debug("Copy file %s from %s to %s" % (filename, path, destpath))
            try:
                shutil.copy2(path, destpath)
            except Exception as e:
                log.error("failed to copy datafile to storage, (%s) dest: '%s'", (str(e), destpath))

    def _got_file(self, file_name):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_name: name of the file to parse
        """
        try:
            log.debug('got file, resource_id: %s, driver state %s', self._resource_id, self._driver_state)

            directory = self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)

            if directory != self._ingest_directory:
                log.error("Detected harvester configuration change. Resource ID: %s Original: %s, new: %s",
                          self._resource_id,
                          self._ingest_directory,
                          directory
                )

            # Removed this for the time being to get new driver code out.  May bring this back in the future
            #self._stage_input_file(os.path.join(directory, file_name))

            count = 1
            delay = None

            if self._generate_particle_count:
                # Calculate the delay between grabbing records to publish.
                delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
                count = self._generate_particle_count

            self._file_in_process = file_name

            # Open the copied file in the storage directory so we know the file won't be
            # changed while we are reading it
            path = os.path.join(directory, file_name)

            self._raise_new_file_event(path)
            log.debug("Open new data source file: %s", path)
            handle = open(path)

            # the file directory is initialized in the harvester, so it will exist by this point
            parser = self._build_parser(self._driver_state[file_name][DriverStateKey.PARSER_STATE], handle)

            while(True):
                result = parser.get_records(count)
                if result:
                    log.trace("Record parsed: %r delay: %f", result, delay)
                    if delay:
                        gevent.sleep(delay)
                else:
                    break

        except SampleException as e:
            # need to mark the bad file as ingested so we don't re-ingest it
            self._save_parser_state_after_error()
            self._sample_exception_callback(e)

        finally:
            self._file_in_process = None

    def _save_parser_state(self, state, file_ingested):
        """
        Callback to store the parser state in the driver object.
        @param state: Object used by the parser to indicate position
        """
        log.trace("saving parser state: %r", state)
        # this is for the directory harvester which uses file name keys
        self._driver_state[self._file_in_process][DriverStateKey.PARSER_STATE] = state
        # check if file has been completely parsed by comparing the parsed position and file size
        if file_ingested:
            log.debug("File %s fully parsed", self._file_in_process)
            self._driver_state[self._file_in_process][DriverStateKey.INGESTED] = True
        self._state_callback(self._driver_state)

    def _save_parser_state_after_error(self):
        """
        If a file has a sample exception that has made it to the driver, this file is done,
        mark it as ingested and save the state
        """
        log.debug("File %s fully parsed", self._file_in_process)
        self._driver_state[self._file_in_process][DriverStateKey.INGESTED] = True
        self._state_callback(self._driver_state)

    def _init_state(self, memento):
        """
        Initialize driver state
        @param memento: agent persisted memento containing driver state
        """
        if memento != None:
            if not isinstance(memento, dict): raise TypeError("memento must be a dict.")

            self._driver_state = memento
            if not self._driver_state:
                # if the state is empty, add a version
                self._driver_state = {DriverStateKey.VERSION: 0.1}
        else:
            # initialize the state since none was specified
            self._driver_state = {DriverStateKey.VERSION: 0.1}
        log.debug('initial driver state %s', self._driver_state)

    def _new_file_callback(self, file_name):
        """
        Callback used by the single directory harvester called when a new file is detected.  Store the
        filename in a queue.
        @param file_name: file name of the found file.
        """
        log.debug('got new file callback, resource_id, %s, driver state %s', self._resource_id, self._driver_state)
        if file_name not in self._driver_state:
            # initialize the driver state for this file
            full_file_path = os.path.join(self._harvester_config[DataSetDriverConfigKeys.DIRECTORY], file_name)
            mod_time = os.path.getmtime(full_file_path)
            file_size = os.path.getsize(full_file_path)
            with open(full_file_path, 'rb') as filehandle:
                md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
            self._driver_state[file_name] = {
                DriverStateKey.FILE_SIZE: file_size,
                DriverStateKey.FILE_MOD_DATE: mod_time,
                DriverStateKey.FILE_CHECKSUM: md5_checksum,
                DriverStateKey.INGESTED: False,
                DriverStateKey.PARSER_STATE: None
            }
        # check for duplicates, don't add it if it is already there
        if file_name not in self._new_file_queue:
            log.debug("Add new file to the new file queue: resource_id: %s, queue addr: %s, name: %s", self._resource_id, id(self._new_file_queue), file_name)
            self._new_file_queue.append(file_name)

            count = len(self._new_file_queue)
            log.trace("Current new file queue length: %d", count)
        # the harvester updates the driver state, make sure we save the newly found file state info
        self._state_callback(self._driver_state)

    def _modified_file_callback(self, modified_state):
        """
        Callback for the single directory harvester when an ingested file has been modified.
        Update the modified state for these ingested files.
        """
        log.debug('got modified file callback, modified state %s', modified_state)
        for filename in modified_state:
            self._driver_state[filename][DriverStateKey.MODIFIED_STATE] = modified_state[filename]
        self._state_callback(self._driver_state)

class SingleFileDataSetDriver(SimpleDataSetDriver):
    """
    Simple data set driver handles cases where we are watching a single file and pushing the
    content into a single parser.
    """
    _in_process_state = None
    _next_driver_state = None

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        super(SingleFileDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback, exception_callback)

        if memento and not self._filename in memento:
            raise ConfigurationException("file name in configuration %s does not match state %s" % (memento, self._filename))

    def _poll(self):
        """
        Main loop to listen for if the file has changed to parse.  Parse them and move on.
        """
        # Check if the file has changed
        log.trace("Checking for file change")
        # if the parser keeps track of unprocessed data, that can be tried again if it is not empty
        if not self._in_process_state and self._next_driver_state != None:
            self._got_file()

    def _stop_sampling(self):
        log.debug("Shutting down harvester")
        if self._harvester and self._harvester.is_alive():
            log.debug("Stopping harvester thread")
            self._harvester.shutdown()
            self._harvester = None
        else:
            log.debug("poller not running. no need to shutdown")
        # stopping sampling interrupts _got_file, so need to reset these
        self._in_process_state = None
        self._next_driver_state = None

    def _init_state(self, memento):
        """
        Initialize driver state
        @param memento: agent persisted memento containing driver state
        """
        self._filename = self._harvester_config.get(DataSetDriverConfigKeys.PATTERN)
        if memento != None:
            if not isinstance(memento, dict): raise TypeError("memento must be a dict.")

            self._driver_state = memento
            if not self._driver_state:
                # if the state is empty, add a version
                self._driver_state = {DriverStateKey.VERSION: 0.1,
                                      self._filename:{DriverStateKey.PARSER_STATE: None}}
        else:
            # initialize the state since none was specified
            self._driver_state = {DriverStateKey.VERSION: 0.1,
                                  self._filename:{DriverStateKey.PARSER_STATE: None}}
        log.debug('initial driver state %s', self._driver_state)

    def _got_file(self):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_name: name of the file to parse
        """
        log.debug('in dataset driver got file, driver state %s, next state %s', self._driver_state, self._next_driver_state)
        try:
            self._in_process_state = self._next_driver_state
            directory = self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)

            # removed storage directory usage for now, may bring back in the future
            #storage_directory = self._harvester_config.get(DataSetDriverConfigKeys.STORAGE_DIRECTORY)
            #shutil.copy2(os.path.join(directory, self._filename), storage_directory)
            #log.info("Copied file %s from %s to %s" % (self._filename, directory, storage_directory))

            count = 1
            delay = None

            if self._generate_particle_count:
                # Calculate the delay between grabbing records to publish.
                delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
                count = self._generate_particle_count

            # Open the copied file in the storage directory so we know the file won't be
            # changed while we are reading it
            path = os.path.join(directory, self._filename)
            self._raise_new_file_event(path)
            handle = open(path)

            self.pre_parse()

            parser_state = None
            if self._filename in self._driver_state and \
               isinstance(self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE), dict):
                # make sure we are not linking
                parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE).copy()

            # the directory harvester uses file_name keys, the single file harvester does not
            # the file directory is initialized in the harvester, so it will exist by this point
            parser = self._build_parser(parser_state, handle)

            while(True):
                result = parser.get_records(count)
                if result:
                    log.trace("Record parsed: %r delay: %f", result, delay)
                    if delay:
                        gevent.sleep(delay)
                else:
                    break

            self._save_ingested_file_state()
        except SampleException as e:
            self._save_ingested_file_state()
            self._sample_exception_callback(e)

    def pre_parse(self):
        """
        This can be overloaded to do something prior to parsing
        """
        pass

    def _save_parser_state(self, state):
        """
        Callback to store the parser state in the driver object.
        @param state: Object used by the parser to indicate position
        """
        log.trace("saving parser state: %r", state)
        # this is for the single file harvester, which does not use file name keys
        self._driver_state[self._filename][DriverStateKey.PARSER_STATE] = state
        self._state_callback(self._driver_state)

    def _file_changed_callback(self, new_state):
        """
        Callback used by the single file harvester called when a file is changed in the
        single file harvester. Store the filename in a queue and the new state.
        @param new_state: new state of the file
        """
        log.debug('got file changed callback for file %s, next driver state %s', self._filename, new_state)
        self._next_driver_state = new_state

    def _save_ingested_file_state(self):
        """
        After the file has been ingested, update the file parameters to those that have been found in the 'next driver state'
        """
        if self._in_process_state != None:
            self._driver_state[self._filename][DriverStateKey.FILE_SIZE] = self._in_process_state[self._filename][DriverStateKey.FILE_SIZE]
            self._driver_state[self._filename][DriverStateKey.FILE_CHECKSUM] = self._in_process_state[self._filename][DriverStateKey.FILE_CHECKSUM]
            self._driver_state[self._filename][DriverStateKey.FILE_MOD_DATE] = self._in_process_state[self._filename][DriverStateKey.FILE_MOD_DATE]
            # next driver state may have changed while we are processing, if it hasn't clear the next driver state
            if self._driver_and_next_state_equal():
                self._next_driver_state = None
                log.debug('clearing next driver state')
            self._in_process_state = None
        log.debug('saving driver state %s', self._driver_state)
        self._state_callback(self._driver_state)

    def _driver_and_next_state_equal(self):
        if self._next_driver_state == None and self._driver_state == None:
            return True
        if self._next_driver_state != None and self._filename in self._next_driver_state and \
            DriverStateKey.FILE_SIZE in self._next_driver_state[self._filename] and \
            self._filename in self._next_driver_state and \
            DriverStateKey.FILE_SIZE in self._driver_state[self._filename] and \
            self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE] == self._driver_state[self._filename][DriverStateKey.FILE_SIZE] and \
            self._next_driver_state[self._filename][DriverStateKey.FILE_CHECKSUM] == self._driver_state[self._filename][DriverStateKey.FILE_CHECKSUM] and \
            self._next_driver_state[self._filename][DriverStateKey.FILE_MOD_DATE] == self._driver_state[self._filename][DriverStateKey.FILE_MOD_DATE]:
            return True
        return False

class MultipleHarvesterDataSetDriver(SimpleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback, data_keys, harvester_type=None):
        """
        Initialize the multiple harvster data set driver
        @param config Driver configuration
        @param memento Previous driver state
        @param data_callback Method to call when a data sample is available
        @param state_callback Method to call when the driver state changes
        @param event_callback Method to call when an event occurs
        @param exception_callback Method to call when an exception occurs
        @param data_keys A list of keys, one for each harvester/parser pair to start
        @param harvester_type Optional parameter defaults to None, a dictionary of data keys associated with a harvester type
        """
        self._data_keys = data_keys
        if harvester_type != None and not isinstance(harvester_type, dict):
            raise DatasetHarvesterException("Harvester type must be a dictionary, got harvester type %s" % harvester_type)
        self._harvester_type = harvester_type

        super(MultipleHarvesterDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                             exception_callback)
        self._publisher_thread = {}
        self._publisher_shutdown = {}
        self._init_queues()

    def _init_queues(self):
        """
        Initialize the queues which hold the either the newly found files (for single
        directory harvester) or the newly found file state (for the single file harvester).
        Need an additional queue for single file harvesters to keep track of the in
        process file state.
        """
        self._new_file_queue = {}
        self._file_in_process = {}
        for key in self._data_keys:
            self._new_file_queue[key] = []
            self._file_in_process[key] = None

        if self._harvester_type != None:
            # the in_process_queue is only used for single file harvesters,
            # which will only occur if the harvester type is specified
            self._in_process_queue = {}
            for key in self._data_keys:
                if key in self._harvester_type and \
                self._harvester_type[key] == HarvesterType.SINGLE_FILE:
                    self._in_process_queue[key] = None

    def _init_state(self, memento):
        """
        Initialize driver state
        @param memento: agent persisted memento containing driver state
        """
        if memento != None:
            if not isinstance(memento, dict): raise TypeError("memento must be a dict.")

            self._driver_state = memento
            if not self._driver_state:
                # if the state is empty, add a version
                self._driver_state = {DriverStateKey.VERSION: 0.1}
                # initialize each harvester key
                for key in self._data_keys:
                    self._driver_state[key] = {}
        else:
            # initialize the state since none was specified
            self._driver_state = {DriverStateKey.VERSION: 0.1}
            # initialize each harvester key
            for key in self._data_keys:
                self._driver_state[key] = {}
        log.debug('initial driver state %s', self._driver_state)

    def _start_publisher_thread(self):
        """
        Start however many publisher threads are needed, one for each data key
        """
        for key in self._data_keys:
            # no harvester type specified defaults to all single directory harvesters
            if self._harvester_type == None or \
                (key in self._harvester_type and self._harvester_type[key] == HarvesterType.SINGLE_DIRECTORY):
                # this is a multiple file harvester, poll for multiple files
                self._publisher_thread[key] = gevent.spawn(self._publisher_loop, key)
            elif key in self._harvester_type and self._harvester_type[key] == HarvesterType.SINGLE_FILE:
                # this is a single file harvester, poll for changes to a single file
                self._publisher_thread[key] = gevent.spawn(self._publisher_loop_single_file, key)
            self._publisher_shutdown[key] = False

    def _stop_publisher_thread(self):
        """
        Shutdown all the publisher threads
        """
        log.debug("Signal publisher threads shutdown")
        if self._publisher_thread != {}:
            for key in self._data_keys:
                self._publisher_shutdown[key] = True
                if self._publisher_thread[key]:
                    self._publisher_thread[key].kill(block=False)
        else:
            log.debug("publisher not running, no need to shutdown")
        # need to clear in_process queue for single file harvester if we
        # interrupt the publisher thread
        if self._harvester_type != None:
            for key in self._data_keys:
                if key in self._harvester_type and \
                   self._harvester_type[key] == HarvesterType.SINGLE_FILE:
                    log.debug('Clearing in process queue for key %s', key)
                    self._in_process_queue[key] = None
        log.debug("publisher threads shutdown complete")

    def _publisher_loop(self, data_key):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        @param data_key The data key to index into the queues
        """
        log.info("Starting main publishing loop for key %s", data_key)

        try:
            while(not self._publisher_shutdown[data_key]):
                self._poll(data_key)
                gevent.sleep(self._polling_interval)
        except Exception as e:
            log.error("Exception in publisher thread (resource id: %s): %s", self._resource_id, traceback.format_exc(e))
            self._exception_callback(e)

        log.debug("publisher thread detected shutdown request")

    def _publisher_loop_single_file(self, data_key):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        @param data_key The data key to index into the queues
        """
        log.info("Starting main publishing loop for key %s", data_key)

        try:
            filename = self._harvester_config[data_key].get(DataSetDriverConfigKeys.PATTERN)
            while(not self._publisher_shutdown[data_key]):
                self._poll_single_file(data_key, filename)
                gevent.sleep(self._polling_interval)
        except Exception as e:
            log.error("Exception in publisher thread (resource id: %s): %s", self._resource_id, traceback.format_exc(e))
            self._exception_callback(e)

        log.debug("publisher thread detected shutdown request")

    def _poll(self, data_key):
        """
        Main loop to listen for new files to parse.  Parse them and move on.
        @param data_key The data key to index into the queues
        """
        # If we have files, grab the first and process it.
        count = len(self._new_file_queue[data_key])
        log.trace("Checking for new files in %s queue, count: %d", data_key, count)
        if(count > 0):
            log.debug("New file detected, resource_id: %s, array addr: %s", self._resource_id,
                      id(self._new_file_queue[data_key]))
            self._got_file(self._new_file_queue[data_key].pop(0), data_key)

    def _poll_single_file(self, data_key, filename):
        """
        Main loop to listen for if the file has changed to parse.  Parse them and move on.
        @param data_key The data key to index into the queues
        @param filename The name of the file we are polling for changes for
        """
        # Check if the file has changed
        log.trace("Checking for file change")
        # if the parser keeps track of unprocessed data, that can be tried again if it is not empty
        # the _new_file_queue how the next driver state for this file
        if not self._in_process_queue[data_key] and self._new_file_queue[data_key] != []:
            self._got_single_file(filename, data_key)

    def _start_sampling(self):
        """
        Start sampling by building all the harvester and starting them
        """
        try:
            self._harvester = self._build_harvester(self._driver_state)
            for harvester in self._harvester:
                harvester.start()
        except Exception as e:
            log.debug("Exception detected when starting sampling: %s", e, exc_info=True)
            self._exception_callback(e)

    def _stop_sampling(self):
        """
        Stop sampling by shutting down the harvesters
        """
        log.debug("Shutting down harvester")
        if self._harvester:
            for harvester in self._harvester:
                if harvester and harvester.is_alive():
                    log.debug("Stopping harvester %s thread", harvester)
                    harvester.shutdown()
            self._harvester = None
        else:
            log.debug("poller not running. no need to shutdown")

    def _got_file(self, file_name, data_key):
        """
        We have a file from the single directory harvester that we want to parse.  Do any optional
        pre-parsing, then build the parser and get records
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
        """
        log.debug('got file, resource_id: %s, driver state %s', self._resource_id, self._driver_state)
        try:
            self._file_in_process[data_key] = file_name
            # pre_parse can be overloaded if there is anything needed to be done prior to parsing
            self.pre_parse(filename=file_name, data_key=data_key)
            self._get_parser_results(file_name, data_key)
        except SampleException as e:
            # need to mark the bad file as ingested so we don't re-ingest it
            log.debug("File %s fully parsed", file_name)
            self._driver_state[data_key][file_name][DriverStateKey.INGESTED] = True
            self._state_callback(self._driver_state)
            self._sample_exception_callback(e)
        finally:
            self._file_in_process[data_key] = None

    def _got_single_file(self, file_name, data_key):
        """
        We got a file from the single file harvester that we want to parse.  Initialize the
        in_process_queue for this data_key, copy the driver state, build the parser and
        get the records, then save the driver state
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
        """
        log.debug('got file, resource_id: %s, driver state %s', self._resource_id, self._driver_state)
        try:
            # hold on to the current state of the file.  The file state in new_file_queue may change
            # during processing, this makes sure we go through this iteration of got_single_file
            # with the same file parameters
            self._in_process_queue[data_key] = self._new_file_queue[data_key]
            self._file_in_process[data_key] = file_name
            # make sure we have initialized the file name dictionary with the parser state
            if file_name not in self._driver_state[data_key]:
                self._driver_state[data_key][file_name] = {DriverStateKey.PARSER_STATE: None}
                self._state_callback(self._driver_state)

            # pre_parse can be overloaded if there is anything needed to be done prior to parsing
            self.pre_parse_single(filename=file_name, data_key=data_key)

            self._get_parser_results(file_name, data_key)
            self._save_single_file_state(file_name, data_key)
        except SampleException as e:
            self._save_single_file_state(file_name, data_key)
            self._sample_exception_callback(e)
        finally:
            self._file_in_process[data_key] = None

    def _get_parser_results(self, file_name, data_key):
        """
        Build the parser and get all the records until there are no more available
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
        """
        count = 1
        delay = None

        directory = self._harvester_config[data_key].get(DataSetDriverConfigKeys.DIRECTORY)

        if self._generate_particle_count:
            # Calculate the delay between grabbing records to publish.
            delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
            count = self._generate_particle_count

        # Open the copied file in the storage directory so we know the file won't be
        # changed while we are reading it
        path = os.path.join(directory, file_name)

        self._raise_new_file_event(path)
        log.debug("Open new data source file: %s", path)
        handle = open(path)

        self._file_in_process[data_key] = file_name

        # the file directory is initialized in the harvester, so it will exist by this point
        parser = self._build_parser(self._driver_state[data_key][file_name][DriverStateKey.PARSER_STATE], handle, data_key)

        while(True):
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break

    def pre_parse(self, filename=None, data_key=None):
        """
        This can be overloaded if something needs to be done just before parsing
        a file found with the directory harvester
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
        """
        pass

    def pre_parse_single(self, filename=None, data_key=None):
        """
        This can be overloaded if something needs to be done just before parsing
        a single file
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
        """
        pass

    def _save_parser_state(self, state, data_key, file_ingested=None):
        """
        Callback to store the parser state in the driver object for both the single
        directory and single file harvesters.
        @param state: Object used by the parser to indicate position
        @param file_name: The name of the file to save the state for, which is the key into the driver state
        @param file_ingested: A true/false flag indicating if the file has been fully ingested, only input this
                              for multiple file harvester, for single file harvesters leave as None
        """
        file_name = self._file_in_process[data_key]
        log.trace("saving parser state: %r for file %s", state, file_name)
        # this is for the directory harvester which uses file name keys
        self._driver_state[data_key][file_name][DriverStateKey.PARSER_STATE] = state
        # check if file has been completely parsed by comparing the parsed position and file size
        if file_ingested:
            log.debug("File %s fully parsed", file_name)
            self._driver_state[data_key][file_name][DriverStateKey.INGESTED] = True
        self._state_callback(self._driver_state)

    def _file_changed_callback(self, new_state, data_key):
        """
        Callback used by the single file harvester called when a file is changed in the
        single file harvester. Store the next driver state in a queue and the new state.
        @param new_state: new state of the file
        @param data_key: data key to index into new file queue
        """
        log.debug('got file changed callback, next driver state %s, current state %s', new_state, self._driver_state)
        self._new_file_queue[data_key] = new_state

    def _new_file_callback(self, file_name, data_key):
        """
        Callback used by the single directory harvester called when a new file is detected.  
        Store the filename in a queue.
        @param file_name: file name of the found file
        @param data_key: data key to index into new file queue
        """
        log.debug('got new file callback, resource_id, %s, driver state %s', self._resource_id, self._driver_state)
        if data_key not in self._driver_state:
            self._driver_state[data_key] = {}
        if file_name not in self._driver_state[data_key]:
            # initialize the driver state for this file
            full_file_path = os.path.join(self._harvester_config[data_key][DataSetDriverConfigKeys.DIRECTORY], file_name)
            mod_time = os.path.getmtime(full_file_path)
            file_size = os.path.getsize(full_file_path)
            with open(full_file_path, 'rb') as filehandle:
                md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
            self._driver_state[data_key][file_name] = {
                DriverStateKey.FILE_SIZE: file_size,
                DriverStateKey.FILE_MOD_DATE: mod_time,
                DriverStateKey.FILE_CHECKSUM: md5_checksum,
                DriverStateKey.INGESTED: False,
                DriverStateKey.PARSER_STATE: None
            }
        # check for duplicates, don't add it if it is already there
        if file_name not in self._new_file_queue[data_key]:
            log.debug("Add new file to the new file queue: resource_id: %s, queue addr: %s, name: %s",
                      self._resource_id,
                      id(self._new_file_queue[data_key]), file_name)
            self._new_file_queue[data_key].append(file_name)

            count = len(self._new_file_queue[data_key])
            log.trace("Current new file queue length: %d", count)
        # the harvester updates the driver state, make sure we save the newly found file state info
        self._state_callback(self._driver_state)

    def _modified_file_callback(self, modified_state, data_key):
        """
        Callback for the single directory harvester when an ingested file has been modified.
        Update the modified state for these ingested files.
        """
        log.debug('got modified file callback, modified state %s', modified_state)
        for filename in modified_state:
            self._driver_state[data_key][filename][DriverStateKey.MODIFIED_STATE] = modified_state[filename]
        self._state_callback(self._driver_state)

    def _verify_config(self):
        """
        Verify we have good configurations for the parser and harvester.
        @raise: ConfigurationException if configuration is invalid
        """
        errors = []
        log.debug("Driver Config: %s", self._config)

        self._harvester_config = self._config.get(DataSourceConfigKey.HARVESTER)
        if self._harvester_config:
            # we are allowing partial configurations in case all instruments are not present
            # for all deployments
            for key in self._harvester_config:
                sub_config = self._harvester_config.get(key)
                log.debug('sub config is %s', sub_config)
                if not sub_config.get(DataSetDriverConfigKeys.DIRECTORY):
                    errors.append("harvester %s config missing 'directory" % key)
                if not sub_config.get(DataSetDriverConfigKeys.PATTERN):
                    errors.append("harvester %s config missing 'pattern" % key)
        else:
            errors.append("missing 'harvester' config")

        if errors:
            log.error("Driver configuration error: %r", errors)
            raise ConfigurationException("driver configuration errors: %r", errors)

        self._parser_config = self._config.get(DataSourceConfigKey.PARSER)

    def _save_single_file_state(self, file_name, data_key):
        """
        After the file has been ingested, update the file parameters to those that have been found in the
        next driver state, which is stored in the in_process_queue.  The in_process_queue is cleared at the
        end to indicate we are done processing the file in this state.  If the file parameters haven't changed
        during processing, the next driver state is cleared so we don't process it again.
        @param file_name: file name of the found file
        @param data_key: data key to index into new file queue
        """
        if self._in_process_queue[data_key] != None:
            in_process_file_state = self._in_process_queue[data_key][file_name]
            self._driver_state[data_key][file_name][DriverStateKey.FILE_SIZE] = in_process_file_state[DriverStateKey.FILE_SIZE]
            self._driver_state[data_key][file_name][DriverStateKey.FILE_CHECKSUM] = in_process_file_state[DriverStateKey.FILE_CHECKSUM]
            self._driver_state[data_key][file_name][DriverStateKey.FILE_MOD_DATE] = in_process_file_state[DriverStateKey.FILE_MOD_DATE]
            # next driver state in _new_file_queue may have changed while we are processing, if it hasn't clear the next driver state
            driver_file_state = self._driver_state[data_key][file_name]
            next_driver_state = self._new_file_queue[data_key][file_name]
            if self._new_file_queue[data_key] != [] and file_name in self._new_file_queue[data_key] and \
                DriverStateKey.FILE_SIZE in next_driver_state and \
                DriverStateKey.FILE_SIZE in driver_file_state and \
                next_driver_state[DriverStateKey.FILE_SIZE] == driver_file_state[DriverStateKey.FILE_SIZE] and \
                next_driver_state[DriverStateKey.FILE_CHECKSUM] == driver_file_state[DriverStateKey.FILE_CHECKSUM] and \
                next_driver_state[DriverStateKey.FILE_MOD_DATE] == driver_file_state[DriverStateKey.FILE_MOD_DATE]:
                self._new_file_queue[data_key] = []
                log.debug('clearing next driver state')

            self._in_process_queue[data_key] = None
        log.debug('saving driver state %s', self._driver_state)
        self._state_callback(self._driver_state)


