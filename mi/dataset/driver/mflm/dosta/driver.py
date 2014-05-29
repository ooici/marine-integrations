"""
@package mi.dataset.driver.mflm.dosta.driver
@file marine-integrations/mi/dataset/driver/mflm/dosta/driver.py
@author Emily Hahn
@brief Driver for the mflm_dosta
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.dostad import DostadParser, DostadParserDataParticle
from mi.dataset.parser.dostad import DostadMetadataDataParticle, StateKey

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    DOSTA_ABCDJM_SIO_TELEMETERED = 'dosta_abcdjm_sio_telemetered'
    DOSTA_ABCDJM_SIO_RECOVERED = 'dosta_abcdjm_sio_recovered'

class MflmDOSTADDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        # Fill in below with particle stream
        return [DostadParserDataParticle.type(), DostadMetadataDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED, DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED: HarvesterType.SINGLE_FILE,
                          DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED: HarvesterType.SINGLE_DIRECTORY}
        super(MflmDOSTADDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED:
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
        config = self._parser_config[DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED]
        # Fill in blanks with particle info
        config.update({
            'particle_module': 'mi.dataset.parser.dostad',
            'particle_class': ['DostadParserDataParticle',
                               'DostadMetadataDataParticle']
        })
        log.debug("My Config: %s", config)
        parser = DostadParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_recovered_parser(self, parser_state, stream_in):
        """
        Build and return the telemetered parser
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        """
        # no recovered parser defined yet
        parser = None
        return parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        self._harvester = []
        if DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED in self._harvester_config:
            telemetered_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED),
                driver_state[DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.DOSTA_ABCDJM_SIO_TELEMETERED),
                self._exception_callback
            )
            self._harvester.append(telemetered_harvester)
        else:
            log.warn('No configuration for telemetered harvester, not building')

        #if DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED in self._harvester_config:
            #recovered_harvester = SingleDirectoryHarvester(
            #    self._harvester_config.get(DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED),
            #    driver_state[DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED],
            #    lambda filename: self._new_file_callback(filename, DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED),
            #    lambda modified: self._modified_file_callback(modified, DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED),
            #    self._exception_callback
            #)
        #    self._harvester.append(recovered_harvester)
        #else:
        #    log.warn('No configuration for recovered harvester, not building')
        return self._harvester

