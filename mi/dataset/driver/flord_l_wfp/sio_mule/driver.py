"""
@package mi.dataset.driver.flord_l_wfp.sio_mule.driver
@file marine-integrations/mi/dataset/driver/flord_l_wfp/sio_mule/driver.py
@author Maria Lutz
@brief Driver for the flord_l_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz, Joe Padula'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.harvester import SingleDirectoryHarvester, SingleFileHarvester
from mi.dataset.parser.global_wfp_e_file_parser import GlobalWfpEFileParser
from mi.dataset.parser.flord_l_wfp import FlordLWfpInstrumentParserDataParticle
from mi.dataset.parser.flord_l_wfp_sio_mule import FlordLWfpSioMuleParser, FlordLWfpSioMuleParserDataParticle


class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    FLORD_L_WFP_SIO_MULE = 'flord_l_wfp_sio_mule'
    FLORD_L_WFP = 'flord_l_wfp'


class FlordLWfpSioMuleDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlordLWfpSioMuleParserDataParticle.type(),
                FlordLWfpInstrumentParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = DataSourceKey.list()
        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.FLORD_L_WFP_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataSourceKey.FLORD_L_WFP: HarvesterType.SINGLE_DIRECTORY}
        super(FlordLWfpSioMuleDataSetDriver, self).__init__(config, memento, data_callback, state_callback,
                                                            event_callback, exception_callback, data_keys,
                                                            harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.FLORD_L_WFP_SIO_MULE:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.FLORD_L_WFP:
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
        config = self._parser_config.get(DataSourceKey.FLORD_L_WFP_SIO_MULE)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flord_l_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordLWfpSioMuleParserDataParticle'
        })
        log.debug("My Config: %s", config)
        parser = FlordLWfpSioMuleParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.FLORD_L_WFP_SIO_MULE),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_recovered_parser(self, parser_state, stream_in):
        """
        Build and return the parser
        """
        config = self._parser_config.get(DataSourceKey.FLORD_L_WFP)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flord_l_wfp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordLWfpInstrumentParserDataParticle'
        })

        parser = GlobalWfpEFileParser(
            config, parser_state, stream_in,
            lambda state, ingested:
            self._save_parser_state(state, DataSourceKey.FLORD_L_WFP, ingested),
            self._data_callback, self._sample_exception_callback
        )
        return parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.FLORD_L_WFP_SIO_MULE in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.FLORD_L_WFP_SIO_MULE),
                driver_state[DataSourceKey.FLORD_L_WFP_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.FLORD_L_WFP_SIO_MULE),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORD_L_WFP_SIO_MULE)

        if DataSourceKey.FLORD_L_WFP in self._harvester_config:

            recov_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.FLORD_L_WFP),
                driver_state[DataSourceKey.FLORD_L_WFP],
                lambda filename: self._new_file_callback(filename, DataSourceKey.FLORD_L_WFP),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.FLORD_L_WFP),
                self._exception_callback
            )
            harvesters.append(recov_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORD_L_WFP)

        return harvesters
