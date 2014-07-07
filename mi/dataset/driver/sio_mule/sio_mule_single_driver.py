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

from mi.core.log import get_logger ; log = get_logger()
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
        # confirm the current file is in the driver state and the file size is present,
        # and confirm we have a parser state with unprocessed data
        if self._filename in self._driver_state and \
            DriverStateKey.FILE_SIZE in self._next_driver_state[self._filename] and \
            DriverStateKey.PARSER_STATE in self._driver_state[self._filename] and \
            self._driver_state[self._filename][DriverStateKey.PARSER_STATE] is not None and \
            StateKey.UNPROCESSED_DATA in self._driver_state[self._filename][DriverStateKey.PARSER_STATE] and \
            StateKey.FILE_SIZE in self._driver_state[self._filename][DriverStateKey.PARSER_STATE]:

            # shorten names of long state variables
            parser_state = self._driver_state[self._filename].get(DriverStateKey.PARSER_STATE)
            last_size = parser_state[DriverStateKey.FILE_SIZE]
            next_size = self._next_driver_state[self._filename][DriverStateKey.FILE_SIZE]

            # Check for cases where we need to change the last unprocessed index
            if parser_state[StateKey.UNPROCESSED_DATA] == [] and last_size < next_size:
                # we have processed up to the last file size, append a
                # new block that goes from the last file size to the new file size
                log.debug('Appending new unprocessed parser %d,%d', last_size, next_size)
                parser_state[StateKey.UNPROCESSED_DATA].append([last_size, next_size])
                parser_state[StateKey.FILE_SIZE] = next_size
                self._save_parser_state(parser_state)

            elif parser_state[StateKey.UNPROCESSED_DATA] != [] and \
                parser_state[StateKey.UNPROCESSED_DATA][-1][1] < next_size:

                if last_size > parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # the previous file size is greater than the last unprocessed index so
                    # we have processed up to the last file size, append a
                    # new block that goes from the last file size to the new file size
                    log.debug('Appending new unprocessed parser %d,%d', last_size, next_size)
                    parser_state[StateKey.UNPROCESSED_DATA].append([last_size, next_size])
                    parser_state[StateKey.FILE_SIZE] = next_size
                    self._save_parser_state(parser_state)

                elif last_size == parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # if the last unprocessed is the last file size, increase the last index
                    log.debug('Replacing last unprocessed parser with %d', next_size)
                    parser_state[StateKey.UNPROCESSED_DATA][-1][1] = next_size
                    parser_state[StateKey.FILE_SIZE] = next_size
                    self._save_parser_state(parser_state)
