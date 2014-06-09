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
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.parser.flortd import FlortdParser, FlortdParserDataParticle

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    FLORT_DJ_SIO_TELEMETERED = 'flort_dj_sio_telemetered'
    FLORT_DJ_SIO_RECOVERED = 'flort_dj_sio_recovered'

class MflmFLORTDDataSetDriver(SioMuleDataSetDriver):
    
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

    def _build_telemetered_parser(self, parser_state, stream_in):
        """
        Build and return the telemetered parser
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flortd',
            'particle_class': 'FlortdParserDataParticle'
        })
        log.debug("My Config: %s", config)
        parser = FlortdParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_recovered_parser(self, parser_state, stream_in):
        """
        Build and return the recovered parser
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        """
        # recovered parser is not written yet
        parser = None
        return parser

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

        #if DataSourceKey.FLORT_DJ_SIO_RECOVERED in self._harvester_config:
        #    recov_harvester = SingleDirectoryHarvester(
        #        self._harvester_config.get(DataSourceKey.FLORT_DJ_SIO_RECOVERED),
        #        driver_state[DataSourceKey.FLORT_DJ_SIO_RECOVERED],
        #        lambda file_state, file_ingested: self._file_changed_callback(file_state,
        #                                                                      DataSourceKey.FLORT_DJ_SIO_RECOVERED,
        #                                                                      file_ingested),
        #        self._exception_callback
        #    )
        #    harvesters.append(recov_harvester)
        #else:
        #    log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORT_DJ_SIO_RECOVERED)
        return harvesters

