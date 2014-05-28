"""
@package mi.dataset.driver.mflm.flort.driver
@file marine-integrations/mi/dataset/driver/mflm/flort/driver.py
@author Emily Hahn
@brief Driver for the mflm_flort
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import HarvesterType, MultipleHarvesterDataSetDriver
from mi.dataset.dataset_driver import DriverStateKey
from mi.dataset.parser.flortd import FlortdParser, FlortdParserDataParticle
from mi.dataset.parser.sio_mule_common import StateKey

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    FLORT_DJ_SIO_TELEMETERED = 'flort_dj_sio_telemetered'
    FLORT_DJ_SIO_RECOVERED = 'flort_dj_sio_recovered'

class MflmFLORTDDataSetDriver(MultipleHarvesterDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlortdParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.FLORT_DJ_SIO_TELEMETERED, DataSourceKey.FLORT_DJ_SIO_RECOVERED]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.FLORT_DJ_SIO_TELEMETERED: HarvesterType.SINGLE_FILE,
                          DataSourceKey.FLORT_DJ_SIO_RECOVERED: HarvesterType.SINGLE_DIRECTORY}
        super(MflmFLORTDDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param file_in Filename string to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.FLORT_DJ_SIO_TELEMETERED:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.FLORT_DJ_SIO_RECOVERED:
            parser = self._build_recovered_parser(parser_state, stream_in)
        else:
            raise ConfigurationException('Tried to build parser for unknown data source key %s' % data_key)
        return parser

    def _build_telemetered_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flortd',
            'particle_class': 'FlortdParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = FlortdParser(
            config,
            parser_state,
            infile,
            lambda state: self._save_parser_state(state, DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
            self._data_callback,
            self._sample_exception_callback
        )
        return self._parser

    def _build_recovered_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flortd',
            'particle_class': 'FlortdParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = FlortdParser(
            config,
            parser_state,
            infile,
            lambda state: self._save_parser_state(state, DataSourceKey.FLORT_DJ_SIO_RECOVERED),
            self._data_callback,
            self._sample_exception_callback,
            recovered_flag=True
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.FLORT_DJ_SIO_TELEMETERED in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
                driver_state[DataSourceKey.FLORT_DJ_SIO_TELEMETERED],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORT_DJ_SIO_TELEMETERED)

        if DataSourceKey.FLORT_DJ_SIO_RECOVERED in self._harvester_config:
            recov_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.FLORT_DJ_SIO_RECOVERED),
                driver_state[DataSourceKey.FLORT_DJ_SIO_RECOVERED],
                lambda file_state, file_ingested: self._file_changed_callback(file_state,
                                                                              DataSourceKey.FLORT_DJ_SIO_RECOVERED,
                                                                              file_ingested),
                self._exception_callback
            )
            harvesters.append(recov_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORT_DJ_SIO_RECOVERED)
        return harvesters

    # once all mflm drivers are moved to multiple harvester drivers, this will be moved into the sio common driver
    def pre_parse_single(self, filename=None, data_key=None):
        """
        Check if the file has grown larger, if it has update the unprocessed data to add the additional section of the file
        @param filename The filename for this file
        @param data_key The data key indicating which parser we are working with
        """
        # need to check if the file has grown larger, if it has update the last
        # unprocessed data index
        parser_state = None
        if DriverStateKey.PARSER_STATE in self._driver_state[data_key][filename]:
            parser_state = self._driver_state[data_key][filename].get(DriverStateKey.PARSER_STATE)

        if parser_state != None and \
            data_key in self._new_file_queue and filename in self._new_file_queue[data_key] and \
            DriverStateKey.FILE_SIZE in self._new_file_queue[data_key][filename] and \
            filename in self._driver_state[data_key] and \
            DriverStateKey.FILE_SIZE in self._driver_state[data_key][filename] and \
            parser_state[StateKey.UNPROCESSED_DATA][-1][1] < self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]:

            last_size = self._driver_state[data_key][filename][DriverStateKey.FILE_SIZE]
            new_parser_state = parser_state

            # the file is larger, need to update last unprocessed index
            # set the new parser unprocessed data state
            if last_size == new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if the last unprocessed is the last file size, just increase the last index
                log.debug('Replacing last unprocessed parser with %d',
                          self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE])
                new_parser_state[StateKey.UNPROCESSED_DATA][-1][1] = self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]
            elif last_size  > new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if we processed past the last file size, append a new unprocessed block
                # that goes from the last file size to the new file size
                log.debug('Appending new unprocessed parser %d,%d', last_size,
                          self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE])
                new_parser_state[StateKey.UNPROCESSED_DATA].append([last_size,
                                                                    self._new_file_queue[data_key][filename][DriverStateKey.FILE_SIZE]])

            self._save_parser_state(new_parser_state, data_key)
