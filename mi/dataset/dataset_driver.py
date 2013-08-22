#!/usr/bin/env python

"""
@package mi.dataset.driver Base class for data set driver
@file mi/dataset/driver.py
@author Steve Foley
@brief A generic data set driver package
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import DataSourceLocationException
from mi.core.exceptions import ConfigurationException
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import NotImplementedException
from mi.core.common import BaseEnum

class DataSourceConfigKey(BaseEnum):
    HARVESTER = 'harvester'
    PARSER = 'parser'

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
    """
    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        self._config = config
        self._data_callback = data_callback
        self._state_callback = state_callback
        self._exception_callback = exception_callback
        self._initial_memento = memento

        self._verify_config()

    def start_sampling(self, memento):
        raise NotImplementedException('virtual methond needs to be specialized')

    def stop_sampling(self):
        raise NotImplementedException('virtual methond needs to be specialized')

    def cmd_dvr(self, cmd, *args, **kwargs):
        log.warn("DRIVER: cmd_dvr %s", cmd)

        if cmd != 'execute_resource':
            raise InstrumentStateException("Unhandled command: %s", cmd)

        resource_cmd = args[0]

        if resource_cmd == DriverEvent.START_AUTOSAMPLE:
            log.debug("start autosample")
            #self.start_sampling()
            return (ResourceAgentState.STREAMING, None)

        elif resource_cmd == DriverEvent.STOP_AUTOSAMPLE:
            log.debug("stop autosample")
            #self.stop_sampling()
            return (ResourceAgentState.COMMAND, None)

        else:
            raise

    def _verify_config(self):
        """
        virtual method to verify the supplied driver configuration is value.  Must
        be overloaded in sub classes.

        raises an ConfigurationException when a configuration error is detected.
        """
        raise NotImplementedException('virtual methond needs to be specialized')


class SimpleDataSetDriver(DataSetDriver):
    """
    Simple data set driver handles cases where we are watching a single file and pushing the
    content into a single parser.  The hope is this class can be used for 80% of the drivers
    we implement.
    """
    _harvester = None
    _parser = None

    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        super(SimpleDataSetDriver, self).__init__(config, memento, data_callback, state_callback, exception_callback)

        self._harvester = self._build_harvester(self._initial_memento)

    def start_sampling(self, memento):
        log.debug("start sampling: %r", self._harvester)
        self._harvester.start()

    def stop_sampling(self):
        self._harvester.stop()

    ####
    ##    Helpers
    ####
    def _build_parser(self, memento):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _build_harvester(self, memento):
        raise NotImplementedException('virtual methond needs to be specialized')

    def _verify_config(self):
        """
        Verify we have good configurations for the parser and harvester.
        @raise: ConfigurationException if configuration is invalid
        """
        errors = []

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

    def _new_file_callback(self):
        pass
