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

import os
import glob
import hashlib
import time
import re

from threading import Thread
from gevent.event import Event

from mi.core.log import get_logger ; log = get_logger()
from mi.core.poller import DirectoryPoller, ConditionPoller
from mi.core.common import BaseEnum
from mi.dataset.dataset_driver import DriverStateKey


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

# used to determine if we should do integer sorting of the files
NUMBER_UNDERSCORE_MATCHER = re.compile(r'_\d')

class SingleDirectoryPoller(ConditionPoller):
    """
    Monitor a single directory to see if new files have appeared or if files have changed.
    When a change is found this information will be returned through the callback.
    @param config - harvester configuration dictionary
    @param file_mod_wait - integer time to wait after files have been modified
    @param memento - previous harvester state dictionary
    @param callback - function to callback when a change in files has occured
    @param exception_callback - function to callback when an exception occurs
    @param interval - polling interval for checking this directory
    """
    def __init__(self, config, memento, callback, exception_callback=None, interval=1, file_mod_wait=30):
        log.debug("Initialize harvester with config: %s", config)
        directory = config.get('directory')
        wildcard = config.get('pattern')
        if not os.path.isdir(directory):
            raise ValueError('%s is not a directory'%directory)
        self.file_mod_wait = file_mod_wait
        if not isinstance(self.file_mod_wait, int) or self.file_mod_wait < 0:
            raise TypeError("File modification wait time must be an integer 0 or greater")
        log.debug("Start directory poller path: %s, pattern: %s", directory, wildcard)
        self._found_file_state = memento
        # driver state is not a new instance of memento, it is the same here as in the driver
        self._path = directory + '/' + wildcard
        log.debug("Starting harvester with directory pattern: %s", self._path)

        # this queue holds the names of the files that have been sent to the driver.  Each time the harvester
        # restarts, the queue is emptied so all files that have not been ingested can be added and sent again,
        # but this keeps the harvester from sending the same files over and over to not be put in the driver queue
        self.sent_to_driver_queue = []
        super(SingleDirectoryPoller,self).__init__(self._check_for_files, callback,
                                                   exception_callback, interval)

    def _check_for_files(self):
        """
        Find any new or modified files and update the harvester state
        """
        filenames = []

        if os.path.exists(os.path.dirname(self._path)):
            filenames = glob.glob(self._path)

        # if there are underscores in the filename, sort by ascii rather than 
        if len(filenames) > 0:
            if NUMBER_UNDERSCORE_MATCHER.search(filenames[0]):
                filenames = self.sort_files(filenames)
            else:
                filenames.sort()

        new_files = []
        modified_state = {}
        # loop over all files in the directory and compare their state to that in the harvester state dictionary
        for i_file in filenames:
            mod_time = os.path.getmtime(i_file)
            # check if the file has not been modified in the last X seconds
            if (mod_time + self.file_mod_wait) < time.time():
                file_name = os.path.basename(i_file)
                # find if this file already exists in the found files
                if file_name in self._found_file_state and self._found_file_state[file_name][DriverStateKey.INGESTED]:
                    # this file has been ingested (file size and date will only be available for ingested files)
                    file_size = os.path.getsize(i_file)
                    if self._found_file_state[file_name][DriverStateKey.FILE_SIZE] != file_size or \
                    self._found_file_state[file_name][DriverStateKey.FILE_MOD_DATE] != mod_time:
                       # this file has been ingested, but the file size and times don't match, confirm that
                       # the checksum is different
                        with open(i_file, 'rb') as filehandle:
                            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
                        if self._found_file_state[file_name][DriverStateKey.FILE_CHECKSUM] != md5_checksum:
                            # ingested file has been modified!
                            if DriverStateKey.MODIFIED_STATE in self._found_file_state[file_name]:
                                # this file has been modified before
                                old_state = self._found_file_state[file_name][DriverStateKey.MODIFIED_STATE]
                                if old_state[DriverStateKey.FILE_SIZE] != file_size or \
                                old_state[DriverStateKey.FILE_MOD_DATE] != mod_time or \
                                old_state[DriverStateKey.FILE_CHECKSUM] != md5_checksum:
                                    # this file has changed since its previous modification, update the
                                    # modified state
                                    modified_state[filename] = {
                                        DriverStateKey.FILE_SIZE: file_size,
                                        DriverStateKey.FILE_MOD_DATE: mod_time,
                                        DriverStateKey.FILE_CHECKSUM: md5_checksum,
                                    }
                            else:
                                # this is the first time this file has been modified
                                modified_state[filename] = {
                                    DriverStateKey.FILE_SIZE: file_size,
                                    DriverStateKey.FILE_MOD_DATE: mod_time,
                                    DriverStateKey.FILE_CHECKSUM: md5_checksum,
                                }
                else:
                    # send all files that have not been ingested yet, but keep track in a queue so
                    # duplicates are not sent
                    if file_name not in self.sent_to_driver_queue:
                        # only send this file once
                        self.sent_to_driver_queue.append(file_name)
                        new_files.append(file_name)

        log.debug('found new files: %r, modified_files: %r', new_files, modified_state)
        return (new_files, modified_state)

    def sort_files(self, filenames):
        """
        Sorts files which have multiple indices separated by underscores in a file name.
        Ascii sorting will sort '16' less than '6', so separate by underscores, turn into
        integers, then sort
        """
        # no sorting needed if 0 or 1 files
        if not filenames or len(filenames) < 2:
            return filenames

        # this assumes all files have the same extension
        file_extension = filenames[0].split('.')
        split_names = ()
        for fn in filenames:
            split_name = self.ascii_to_int_list(fn)
            # append this split up name as a tuple
            split_names = split_names + (split_name, ) 
        # now sort all the int formatted names
        sorted_tuple = sorted(split_names)
        # put the filenames back to string format
        sorted_filenames = []
        
        for fn in sorted_tuple:
            # Retrieve original name from end of sorted component list
            sorted_filenames.append(fn[len(fn) - 1])

        return sorted_filenames

    @staticmethod
    def ascii_to_int_list(filename):
        # remove file extension and split by underscores
        file_extension = filename.split('.')
        split_name = filename.replace('.' + file_extension[1], '').split('_')
        for i in range(0, len(split_name)):
            # if this part of the filename can be turned into an int, do it
            try:
                int_val = int(split_name[i])
                split_name[i] = int_val
            except ValueError:
                # ignore error
                pass
        # append the full filename to the end where it shouldn't interfere with the sorting
        split_name.append(filename)
        return split_name

class SingleDirectoryHarvester(SingleDirectoryPoller, Harvester):
    """
    Poll a single directory looking for new files with the single directory poller.
    @param config - harvester configuration dictionary
    @param file_mod_wait - integer time to wait after files have been modified
    @param memento - previous harvester state dictionary
    @param file_callback - function to callback when a not ingested file has been found
    @param modified_callback - function to callback when a modified ingested file has been found
    @param exception_callback - function to callback when an exception occurs
    """
    def __init__(self, config, memento, file_callback, modified_callback, exception_callback):
        if not isinstance(config, dict):
            raise TypeError("Config object must be a dict")
        if memento is None:
            memento = {}
        if not isinstance(memento, dict):
            raise TypeError("memento object must be a dict")
        self.callback = file_callback
        self.modified_callback = modified_callback
        SingleDirectoryPoller.__init__(self,
                                    config,
                                    memento,
                                    self.on_new_files,
                                    exception_callback,
                                    config.get('frequency', 1),
                                    config.get('file_mod_wait_time', 30))

    def on_new_files(self, file_tuple):
        """
        New files or modified files have been found.  The new files includes all files that
        have not been ingested, so duplicates may be passed back.  Filter this in the
        dataset driver. 
        """
        (new_files, modified_state) = file_tuple
        if modified_state != {}:
            # if there are modified files, need to update the driver state
            self.modified_callback(modified_state)
        # update the new files    
        for this_file in new_files:
            self.callback(this_file)

class SingleFilePoller(ConditionPoller):
    """
    Monitor a single file to see if it changes
    @param config - harvester configuration dictionary
    @param file_mod_wait - integer time to wait after files have been modified
    @param memento - previous harvester state dictionary
    @param callback - function to callback when a file change is found
    @param exception_callback - function to callback when an exception occurs
    @param interval - polling interval for checking this file
    """
    def __init__(self, config, memento, callback, exception_callback=None, interval=1, file_mod_wait=30):
        directory = config.get('directory')
        self._filename = config.get('pattern')
        if not os.path.isdir(directory):
            raise ValueError('%s is not a directory'%directory)
        self._path = directory + '/' + self._filename
        if os.path.exists(self._path) and not os.access(self._path, os.R_OK):
            raise ValueError('%s exists but is not readable'%self._path)
        self.file_mod_wait = file_mod_wait
        if not isinstance(self.file_mod_wait, int) or self.file_mod_wait < 0:
            raise TypeError("File modification wait time must be an integer 0 or greater")
        if self._filename in memento and DriverStateKey.FILE_SIZE in memento[self._filename]:
            # since _found_file_state is internal to harvester, don't need to match driver state
            # with indexing by filename
            self._found_file_state = {
                DriverStateKey.FILE_SIZE: memento[self._filename].get(DriverStateKey.FILE_SIZE),
                DriverStateKey.FILE_MOD_DATE: memento[self._filename].get(DriverStateKey.FILE_MOD_DATE),
                DriverStateKey.FILE_CHECKSUM: memento[self._filename].get(DriverStateKey.FILE_CHECKSUM)
            }
        else:
            self._found_file_state = {}
        log.debug("Start file poller path: %s, initial state: %s", self._path, self._found_file_state)
        super(SingleFilePoller,self).__init__(self._check_for_changes, callback,
                                                   exception_callback, interval)

    def _check_for_changes(self):
        """
        Find any new or modified files and update the harvester state
        """
        new_driver_state = None
        if os.path.exists(self._path):
            mod_time = os.path.getmtime(self._path)
            file_size = os.path.getsize(self._path)
            # check if the file has not been modified in the last X seconds
            if (mod_time + self.file_mod_wait) < time.time():
                if DriverStateKey.FILE_SIZE in self._found_file_state:
                    # this file has been found previously, compare the state
                    log.trace('Comparing driver state to %s', self._found_file_state)
                    if self._found_file_state[DriverStateKey.FILE_SIZE] != file_size or \
                        self._found_file_state[DriverStateKey.FILE_MOD_DATE] != mod_time:
                        # size or time is different, confirm with checksum
                        with open(self._path, 'rb') as filehandle:
                            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
                        if self._found_file_state[DriverStateKey.FILE_CHECKSUM] != md5_checksum:
                            # file is different, update the state
                            self._found_file_state[DriverStateKey.FILE_SIZE] = file_size
                            self._found_file_state[DriverStateKey.FILE_MOD_DATE] = mod_time
                            self._found_file_state[DriverStateKey.FILE_CHECKSUM] = md5_checksum

                            new_driver_state = {
                                self._filename: {
                                    DriverStateKey.FILE_SIZE: file_size,
                                    DriverStateKey.FILE_MOD_DATE: mod_time,
                                    DriverStateKey.FILE_CHECKSUM: md5_checksum
                                }
                            }
                else:
                    # no driver state yet, first time opening this file
                    with open(self._path, 'rb') as filehandle:
                        md5_checksum = hashlib.md5(filehandle.read()).hexdigest()

                    self._found_file_state[DriverStateKey.FILE_SIZE] = file_size
                    self._found_file_state[DriverStateKey.FILE_MOD_DATE] = mod_time
                    self._found_file_state[DriverStateKey.FILE_CHECKSUM] = md5_checksum

                    new_driver_state = {
                        self._filename: {
                            DriverStateKey.FILE_SIZE: file_size,
                            DriverStateKey.FILE_MOD_DATE: mod_time,
                            DriverStateKey.FILE_CHECKSUM: md5_checksum
                        }
                    }
        return new_driver_state
    
class SingleFileHarvester(SingleFilePoller, Harvester):
    """
    Poll a single file looking for changes to that file.
    @param config - harvester configuration dictionary
    @param file_mod_wait - integer time to wait after files have been modified
    @param memento - previous harvester state dictionary
    @param file_callback - function to callback when a file change is found
    @param exception_callback - function to callback when an exception occurs
    """
    def __init__(self, config, memento, file_callback, exception_callback):
        if not isinstance(config, dict):
            raise TypeError("Config object must be a dict")
        if memento is None:
            memento = {}
        if not isinstance(memento, dict):
            raise TypeError("memento object must be a dict")
        self.callback = file_callback
        SingleFilePoller.__init__(self,
                                config,
                                memento,
                                self.on_changed_file,
                                exception_callback,
                                config.get('frequency', 1),
                                config.get('file_mod_wait_time', 30))

    def on_changed_file(self, new_state):
        """
        The file has changed.  
        """
        if new_state:
            log.trace("File state changed to %s", new_state)
            self.callback(new_state)

