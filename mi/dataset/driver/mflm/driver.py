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


class SioMuleDataSetDriver(SingleFileDataSetDriver):

    @classmethod
    def stream_config(cls):
        raise NotImplementedException("Must write stream_config()!")

    def _build_parser(self, parser_state, infile):
        raise NotImplementedException("Must write _build_parser()!")

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

    def pre_parse(self):
        """
        Check if the file has grown larger, if it has update the unprocessed data to add the additional section of the file
        """
        parser_state = None
        if self._filename in self._driver_state and DriverStateKey.PARSER_STATE in self._driver_state[self._filename]:
            parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE)
        # See if the last unprocessed index is less than the new file size
        if parser_state != None and \
            DriverStateKey.FILE_SIZE in self._next_driver_state[self._filename] and \
            DriverStateKey.FILE_SIZE in self._driver_state[self._filename] and \
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



