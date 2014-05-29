"""
@package mi.dataset.driver.sio_mule.sio_mule_driver
@file marine-integrations/mi/dataset/driver/sio_mule/sio_mule_driver.py
@author Emily Hahn
@brief Common driver for sio mule
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.dataset_driver import DriverStateKey, MultipleHarvesterDataSetDriver
from mi.dataset.parser.sio_mule_common import StateKey


class SioMuleDataSetDriver(MultipleHarvesterDataSetDriver):

    def pre_parse_single(self, filename, data_key):
        """
        Check if the file has grown larger, if it has update the unprocessed data to add
        the additional section of the file
        @param filename The filename for this file
        @param data_key The data key indicating which parser we are working with
        """
        # need to check if the file has grown larger, if it has update the last
        # unprocessed data index
<<<<<<< HEAD
        if data_key in self._new_file_queue and data_key in self._driver_state and \
            filename in self._new_file_queue[data_key] and \
            filename in self._driver_state[data_key] and \
            DriverStateKey.FILE_SIZE in self._new_file_queue[data_key][filename] and \
            DriverStateKey.FILE_SIZE in self._driver_state[data_key][filename] and \
            DriverStateKey.PARSER_STATE in self._driver_state[data_key][filename] and \
            StateKey.UNPROCESSED_DATA in self._driver_state[data_key][filename][DriverStateKey.PARSER_STATE]:

            # shorten names of long state variables
            parser_state = self._driver_state[data_key][filename].get(DriverStateKey.PARSER_STATE)
            last_size = self._driver_state[data_key][filename][DriverStateKey.FILE_SIZE]
            next_size = self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]

            if parser_state[StateKey.UNPROCESSED_DATA] == [] and last_size < next_size:
                # we have processed up to the last file size, append a
                # new block that goes from the last file size to the new file size
                log.debug('Appending new unprocessed parser %d,%d', last_size, next_size)
                parser_state[StateKey.UNPROCESSED_DATA].append([last_size, next_size])
                self._save_parser_state(parser_state, data_key)

            elif parser_state[StateKey.UNPROCESSED_DATA] != [] and \
                parser_state[StateKey.UNPROCESSED_DATA][-1][1] < next_size:

                if last_size > parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # the previous file size is greater than the last unprocessed index so
                    # we have processed up to the last file size, append a
                    # new block that goes from the last file size to the new file size
                    log.debug('Appending new unprocessed parser %d,%d', last_size, next_size)
                    parser_state[StateKey.UNPROCESSED_DATA].append([last_size, next_size])
                    self._save_parser_state(parser_state, data_key)

                elif last_size == parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                    # if the last unprocessed is the last file size, just increase the last index
                    log.debug('Replacing last unprocessed parser with %d', next_size)
                    parser_state[StateKey.UNPROCESSED_DATA][-1][1] = next_size
                    self._save_parser_state(parser_state, data_key)

=======
        parser_state = None
        if DriverStateKey.PARSER_STATE in self._driver_state[data_key][filename]:
            parser_state = self._driver_state[data_key][filename].get(DriverStateKey.PARSER_STATE)

        if parser_state != None and \
            data_key in self._new_file_queue and filename in self._new_file_queue[data_key] and \
            DriverStateKey.FILE_SIZE in self._new_file_queue[data_key][filename] and \
            filename in self._driver_state[data_key] and \
            DriverStateKey.FILE_SIZE in self._driver_state[data_key][filename] and \
            parser_state[StateKey.UNPROCESSED_DATA][-1][1] < \
            self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]:

            last_size = self._driver_state[data_key][filename][DriverStateKey.FILE_SIZE]
            new_parser_state = parser_state

            # the file is larger, need to update last unprocessed index
            # set the new parser unprocessed data state
            if last_size == new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if the last unprocessed is the last file size, just increase the last index
                log.debug('Replacing last unprocessed parser with %d',
                          self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE])
                new_parser_state[StateKey.UNPROCESSED_DATA][-1][1] = \
                self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]
            elif last_size  > new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if we processed past the last file size, append a new unprocessed block
                # that goes from the last file size to the new file size
                log.debug('Appending new unprocessed parser %d,%d', last_size,
                          self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE])
                new_parser_state[StateKey.UNPROCESSED_DATA].append([last_size,
                                                                    self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]])

            self._save_parser_state(new_parser_state, data_key)
>>>>>>> Upstream merge, including sio mule driver.
