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
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.parser.ctdmo import CtdmoOffsetDataParticle

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    CTDMO_GHQR_SIO_MULE = 'ctdmo_ghqr_sio_mule'
    CTDMO_GHQR = 'ctdmo_ghqr'

class MflmCTDMODataSetDriver(SioMuleDataSetDriver):

    @classmethod
    def stream_config(cls):
        # Once the recovered parser exists, particles should be added here
        return [CtdmoParserDataParticle.type(),
                CtdmoOffsetDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.CTDMO_GHQR_SIO_MULE, DataSourceKey.CTDMO_GHQR]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.CTDMO_GHQR_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataSourceKey.CTDMO_GHQR: HarvesterType.SINGLE_DIRECTORY}
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
        if data_key == DataSourceKey.CTDMO_GHQR_SIO_MULE:
            parser = self._build_ctdmo_ghqr_sio_mule_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.CTDMO_GHQR:
            parser = self._build_ctdmo_ghqr_parser(parser_state, stream_in)
        return parser

    def _build_ctdmo_ghqr_sio_mule_parser(self, parser_state, stream_in):
        """
        Build and return the ctdmo ghqr sio mule parser (telemetered)
        @param parser_state starting parser state 
        @param stream_in Handle of open file 
        @param file_in Filename string
        """
        config = self._parser_config[DataSourceKey.CTDMO_GHQR_SIO_MULE]
        config.update({
            'particle_module': 'mi.dataset.parser.ctdmo',
            'particle_class': ['CtdmoParserDataParticle',
                               'CtdmoOffsetDataParticle']
        })
        log.debug("MYCONFIG: %s", config)
        ctdmo_ghqr_sio_mule_parser = CtdmoParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.CTDMO_GHQR_SIO_MULE),
            self._data_callback,
            self._sample_exception_callback
        )
        return ctdmo_ghqr_sio_mule_parser

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
        ctdmo_ghqr_parser = None

        return ctdmo_ghqr_parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.CTDMO_GHQR_SIO_MULE in self._harvester_config:
            ctdmo_ghqr_sio_mule_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.CTDMO_GHQR_SIO_MULE),
                driver_state[DataSourceKey.CTDMO_GHQR_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.CTDMO_GHQR_SIO_MULE),
                self._exception_callback
            )
            harvesters.append(ctdmo_ghqr_sio_mule_harvester)
        else:
            log.warn('No configuration for ctdmo_ghqr_sio_mule harvester, not building')

        #if DataSourceKey.CTDMO_GHQR in self._harvester_config:
            #ctdmo_ghqr_harvester = SingleDirectoryHarvester(
            #    self._harvester_config.get(DataSourceKey.CTDMO_GHQR),
            #    driver_state[DataSourceKey.CTDMO_GHQR],
            #    lambda filename:self._new_file_callback(filename, DataSourceKey.CTDMO_GHQR),
            #    lambda modified: self._modified_file_callback(modified, DataSourceKey.CTDMO_GHQR),
            #    self._exception_callback
            #)
        #    harvesters.append(ctdmo_ghqr_harvester)
        #else:
        #    log.warn('No configuration for ctdmo_ghqr harvester, not building')
        return harvesters


