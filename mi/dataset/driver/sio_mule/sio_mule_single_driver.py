"""
@package mi.dataset.driver.sio_mule.sio_mule_single_driver
@file marine-integrations/mi/dataset/driver/sio_mule/sio_mule_single_driver.py
@author Emily Hahn
@brief Common Driver for the sio mule single file dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import DriverStateKey, SingleFileDataSetDriver
from mi.dataset.parser.sio_mule_common import StateKey


class SioMuleSingleDataSetDriver(SingleFileDataSetDriver):

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        @param driver_state the driver state to pass to the harvester
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
        Check if the file has grown larger, if it has update the unprocessed data to add
        the additional section of the file
        """
        if self._filename in self._driver_state and \
                DriverStateKey.PARSER_STATE in self._driver_state[self._filename]:

            parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE)

            if parser_state is not None:

                # Get the size of the last time we processed the file
                last_size = self._driver_state[self._filename][DriverStateKey.FILE_SIZE]

                # Get the new size of the file
                new_size = self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE]

                # If the parser's UNPROCESSED_DATA list is empty and the prior size of the file is less than
                # the new size, append a new UNPROCESSED_DATA block
                if parser_state[StateKey.UNPROCESSED_DATA] == [] and last_size < new_size:

                    # if the last unprocessed is the last file size, just increase the last index
                    log.debug('Appending new unprocessed data with size %d', new_size)
                    parser_state[StateKey.UNPROCESSED_DATA].append([last_size, new_size])

                # else if the size of the last unprocessed block (i.e. -1 indexed block) has range
                # (i.e. value at index 1) is less than the new size
                elif (parser_state[StateKey.UNPROCESSED_DATA] != [] and
                      parser_state[StateKey.UNPROCESSED_DATA][-1][1] < new_size):

                    # the previous file size is greater than the last unprocessed index so
                    # we have processed up to the last file size, append a
                    # new block that goes from the last file size to the new file size
                    log.debug('Appending new unprocessed parser %d,%d', last_size, new_size)
                    parser_state[StateKey.UNPROCESSED_DATA].append([last_size, new_size])

                elif last_size == parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # if the last unprocessed is the last file size, just increase the last index
                    log.debug('Replacing last unprocessed parser with %d', new_size)
                    parser_state[StateKey.UNPROCESSED_DATA][-1][1] = new_size

                self._save_parser_state(parser_state)
