"""
@package mi.dataset.driver.mflm.ctd.driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Driver for the mflm_ctd
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import HarvesterType, MultipleHarvesterDataSetDriver
from mi.dataset.dataset_driver import DriverStateKey
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.parser.sio_mule_common import StateKey

class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    CTDMO_GHQR_SIO_MULE = 'ctdmo_ghqr_sio_mule'
    CTDMO_GHQR = 'ctdmo_ghqr'

class MflmCTDMODataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        # Once the recovered parser exists, particles should be added here
        return [CtdmoParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataTypeKey.CTDMO_GHQR_SIO_MULE, DataTypeKey.CTDMO_GHQR]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataTypeKey.CTDMO_GHQR_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataTypeKey.CTDMO_GHQR: HarvesterType.SINGLE_DIRECTORY}
        super(MflmCTDMODataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param file_in Filename string to pass to parser
        @param data_key Key to determine which parser type is built
        """
        parser = None
        if data_key == DataTypeKey.CTDMO_GHQR_SIO_MULE:
            parser = self._build_ctdmo_ghqr_sio_mule_parser(parser_state, stream_in)
        elif data_key == DataTypeKey.CTDMO_GHQR:
            parser = self._build_ctdmo_ghqr_parser(parser_state, stream_in)
        return parser

    def _build_ctdmo_ghqr_sio_mule_parser(self, parser_state, stream_in):
        """
        Build and return the ctdmo ghqr sio mule parser (telemetered)
        @param parser_state starting parser state 
        @param stream_in Handle of open file 
        @param file_in Filename string
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdmo',
            'particle_class': 'CtdmoParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._ctdmo_ghqr_sio_mule_parser = CtdmoParser(
            config,
            parser_state,
            stream_in,
            self._save_ctdmo_ghqr_sio_mule_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._ctdmo_ghqr_sio_mule_parser

    def _build_ctdmo_ghqr_parser(self, parser_state, stream_in, file_in):
        """
        Build and return the ctdmo ghqr parser (recovered)
        This is just a placeholder until this parser is built
        @param parser_state starting parser state 
        @param stream_in Handle of open file 
        @param file_in Filename string
        """
        config = self._parser_config
        # recovered parser doesn't exist yet
        self._ctdmo_ghqr_parser = None

        return self._ctdmo_ghqr_parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        self._harvester = []
        if DataTypeKey.CTDMO_GHQR_SIO_MULE in self._harvester_config:
            self._ctdmo_ghqr_sio_mule_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.CTDMO_GHQR_SIO_MULE),
                driver_state[DataTypeKey.CTDMO_GHQR_SIO_MULE],
                self._ctdmo_ghqr_sio_mule_file_changed_callback,
                self._exception_callback
            )
            self._harvester.append(self._ctdmo_ghqr_sio_mule_harvester)
        else:
            log.warn('No configuration for ctdmo_ghqr_sio_mule harvester, not building')

        #if DataTypeKey.CTDMO_GHQR in self._harvester_config:
            #self._ctdmo_ghqr_harvester = SingleDirectoryHarvester(
            #    self._harvester_config.get(DataTypeKey.CTDMO_GHQR),
            #    driver_state,
            #    self._new_ctdmo_ghqr_file_callback,
            #    self._modified_file_callback,
            #    self._exception_callback
            #)
        #    self._harvester.append(self._ctdmo_ghqr_harvester)
        #else:
        #    log.warn('No configuration for ctdmo_ghqr harvester, not building')
        return self._harvester

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

    def _ctdmo_ghqr_sio_mule_file_changed_callback(self, new_state):
        """
        Callback used by the ctdmo ghqr sio mule single file harvester called when a file change is detected.  
        Store the new state in a queue.
        @param new_state: state of the changed file
        """
        self._file_changed_callback(new_state, DataTypeKey.CTDMO_GHQR_SIO_MULE)

    def _new_ctdmo_ghqr_file_callback(self, file_name):
        """
        Callback used by the ctdmo ghqr single directory harvester called when a new file is detected.  Store the
        filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.CTDMO_GHQR)

    def _save_ctdmo_ghqr_sio_mule_parser_state(self, state):
        """
        Callback used by ctdmo ghqr sio mule parser to save the parser state
        """
        self._save_parser_state(state, DataTypeKey.CTDMO_GHQR_SIO_MULE)

    def _save_ctdmo_ghqr_parser_state(self, state):
        """
        Callback used by ctdmo ghqr parser to save the parser state
        """
        self._save_parser_state(state, DataTypeKey.CTDMO_GHQR)
