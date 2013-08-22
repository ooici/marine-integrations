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
from pyon.agent.agent import ResourceAgentState
from ion.agents.instrument.exceptions import InstrumentStateException
from mi.core.instrument.instrument_driver import DriverEvent


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
    def __init__(self, config, data_callback, state_callback, exception_callback):
        self._config = config
        self._data_callback = data_callback
        self._state_callback = state_callback
        self._exception_callback = exception_callback

    def start_sampling(self, memento):
        pass

    def stop_sampling(self):
        pass

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
            raise InstrumentStateException("Unhandled resource command: %s", resource_cmd)


        
