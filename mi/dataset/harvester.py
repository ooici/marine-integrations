#!/usr/bin/env python

"""
@package mi.dataset.harvester A collection of polling routines that pull
data out of some source (an external file?) and put them into the ION system
via data set agents.
@file mi/dataset/harvester.py
@author Steve Foley
@brief Base classes for data set agent pollers
"""

__author__ = 'Christopher Mueller, Jonathan Newbrough, Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()
from ooi.poller import DirectoryPoller

from pyon.util.containers import get_safe


class Harvester(object):
    """ abstract class to show API needed for plugin poller objects """
    def __init__(self, config, memento, data_callback, exception_callback):  
        pass

    def start(self): 
        pass

    def shutdown(self): 
        pass
    
    def connect_to_source(self):
        """
        Trigger a connection to the data source using the configuration
        information for this stream. 
        """
        pass

## other pollers that check HTTP, FTP or other methods of finding data may be
## added here down the road

class AdditiveSequentialFileHarvester(DirectoryPoller, Harvester):
    """ polls directory for files that match wildcard, in order """
    def __init__(self, config, memento, file_callback, exception_callback):
        self.callback = file_callback
        self.last_file_completed = memento
        DirectoryPoller.__init__(self,
                                 config['directory'],
                                 config['pattern'],
                                 self.on_new_files,
                                 exception_callback,
                                 get_safe(config, 'frequency', 300))
    def on_new_files(self, files):
        for file in files:
            if file>self.last_file_completed:
                with open(file,'rb') as f:
                    self.callback(f, file)