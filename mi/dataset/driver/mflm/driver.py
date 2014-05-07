"""
@package mi.dataset.driver.mflm.driver
@file marine-integrations/mi/dataset/driver/mflm/driver.py
@author Emily Hahn
@brief Common Driver for the mflm
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import hashlib
import gevent
import shutil
import os

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import SingleFileDataSetDriver
from mi.dataset.dataset_driver import DriverStateKey, DataSetDriverConfigKeys
from mi.dataset.parser.sio_mule_common import StateKey


class MflmDataSetDriver(SingleFileDataSetDriver):

    @classmethod
    def stream_config(cls):
        raise NotImplementedException("Must write stream_config()!")

    def _build_parser(self, parser_state, infile):
        raise NotImplementedException("Must write build_parser()!")

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = SingleFileHarvester(
            self._harvester_config,
            driver_state,
            self._file_changed_callback,
            self._exception_callback
        )     
        return self._harvester

    def _got_file(self):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_tuple: (file_handle, file_size) tuple returned by the harvester
        """
        try:
            log.debug('in mflm got file, driver state %s, next state %s', self._driver_state, self._next_driver_state)
            self._in_process_state = self._next_driver_state
            directory = self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)
            count = 1
            delay = None
    
            # Calulate the delay between grabbing records to publish.
            if self._generate_particle_count:
                delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
                count = self._generate_particle_count
    
            # Open the copied file in the storage directory so we know the file won't be
            # changed while we are reading it
            handle = open(os.path.join(directory, self._filename), 'rb')
    
            # need to check if the file has grown larger, if it has update the last
            # unprocessed data index
            parser_state = None
            if self._filename in self._driver_state:
                parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE)
            if parser_state != None and \
                parser_state[StateKey.UNPROCESSED_DATA][-1][1] < self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE]:
                last_size = self._driver_state[self._filename][DriverStateKey.FILE_SIZE]
                new_parser_state = parser_state
                # the file is larger, need to update last unprocessed index
                # set the new parser unprocessed data state
                if last_size == new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # if the last unprocessed is the last file size, just increase the last index
                    log.debug('Replacing last unprocessed parser with %d',
                              self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE])
                    new_parser_state[StateKey.UNPROCESSED_DATA][-1][1] = self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE]
                elif last_size  > new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # if we processed past the last file size, append a new unprocessed block
                    # that goes from the last file size to the new file size
                    log.debug('Appending new unprocessed parser %d,%d', last_size,
                              self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE])
                    new_parser_state[StateKey.UNPROCESSED_DATA].append([last_size,
                                                                        self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE]])
                self._save_parser_state(new_parser_state)

            parser_state = None
            if self._filename in self._driver_state and \
               isinstance(self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE), dict):
                # make sure we are not linking
                parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE).copy()
            log.debug('Making parser with state %s', parser_state)
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
            # need to update the state then pass the exception
            self._save_ingested_file_state()
            self._sample_exception_callback(e)


