"""
@package mi.dataset.driver.mflm.phsen.driver
@file marine-integrations/mi/dataset/driver/mflm/phsen/driver.py
@author Emily Hahn
@brief Driver for the mflm_phsen
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
from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.phsen import PhsenParser, PhsenParserDataParticle, PhsenControlDataParticle

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    PHSEN_ABCDEF_SIO_MULE = 'phsen_abcdef_sio_mule'
    PHSEN_ABCDEF = 'phsen_abcdef'

class MflmPHSENDataSetDriver(SioMuleDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [PhsenParserDataParticle.type(),
                PhsenControlDataParticle.type()]
    
    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.PHSEN_ABCDEF_SIO_MULE, DataSourceKey.PHSEN_ABCDEF]
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.PHSEN_ABCDEF_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataSourceKey.PHSEN_ABCDEF: HarvesterType.SINGLE_DIRECTORY}
        super(MflmPHSENDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.PHSEN_ABCDEF_SIO_MULE:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.PHSEN_ABCDEF:
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
        config = self._parser_config.get(DataSourceKey.PHSEN_ABCDEF_SIO_MULE)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.phsen',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['PhsenParserDataParticle',
                                                     'PhsenControlDataParticle']
        })
        log.debug("My Config: %s", config)
        parser = PhsenParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.PHSEN_ABCDEF_SIO_MULE),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_recovered_parser(self, parser_state, stream_in):
        """
        Build and return the parser
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
        if DataSourceKey.PHSEN_ABCDEF_SIO_MULE in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.PHSEN_ABCDEF_SIO_MULE),
                driver_state[DataSourceKey.PHSEN_ABCDEF_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.PHSEN_ABCDEF_SIO_MULE),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.PHSEN_ABCDEF_SIO_MULE)

        # Need to add recovered harvester when adding recovered parser here

        return harvesters