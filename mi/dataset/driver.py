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
    
        
