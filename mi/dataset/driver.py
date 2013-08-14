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

class DatasetDriver(object):
    
    def __init__(self):
        self.parsers = []
        self.harvesters = []
        self.parser_callbacks = []
        self.parser_errbacks = []
        self.harvester_callbacks = []
        self.harvester_errbacks = []
        
    def start(self):
        """
        Start collecting data from the data source
        """
        pass
    
    def stop(self):
        """
        Stop collecting data from the data source
        """
        pass    
    
        
