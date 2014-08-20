"""
@package mi.dataset.driver.dosta_ln.wfp_sio_mule.driver
@file marine-integrations/mi/dataset/driver/dosta_ln/wfp_sio_mule/driver.py
@author Christopher Fortin, Emily Hahn
@brief Driver for the dosta_ln_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'Christopher Fortin, Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException

from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.dosta_ln_wfp_sio_mule import DostaLnWfpSioMuleParser, \
                                                    DostaLnWfpSioMuleParserDataParticle
from mi.dataset.parser.dosta_ln_wfp import DostaLnWfpParser, \
                                           DostaLnWfpInstrumentParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester, SingleFileHarvester
from mi.dataset.dataset_driver import DataSetDriverConfigKeys, HarvesterType

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    DOSTA_LN_WFP_SIO_MULE = 'dosta_ln_wfp_sio_mule'
    DOSTA_LN_WFP = 'dosta_ln_wfp'

class DostaLnWfpSioMuleDataSetDriver(SioMuleDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [DostaLnWfpSioMuleParserDataParticle.type(),
                DostaLnWfpInstrumentParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = DataSourceKey.list()

        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.DOSTA_LN_WFP_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataSourceKey.DOSTA_LN_WFP: HarvesterType.SINGLE_DIRECTORY}

        super(DostaLnWfpSioMuleDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.DOSTA_LN_WFP_SIO_MULE:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.DOSTA_LN_WFP:
            parser = self._build_recovered_parser(parser_state, stream_in)
        else:
            raise ConfigurationException("Invalid data source key %s" % data_key)
        return parser

    def _build_telemetered_parser(self, parser_state, stream_in):
        """
        Build and return the telemetered parser
        @param parser_state starting parser state to pass to parser
        @param infile Handle of open file to pass to parser
        """
        config = self._parser_config.get(DataSourceKey.DOSTA_LN_WFP_SIO_MULE)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_ln_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaLnWfpSioMuleParserDataParticle'
        })
        log.debug("My Config: %s", config)
        parser = DostaLnWfpSioMuleParser(
            config,
            parser_state,
            stream_in,
            lambda state: self._save_parser_state(state, DataSourceKey.DOSTA_LN_WFP_SIO_MULE),
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
        config = self._parser_config.get(DataSourceKey.DOSTA_LN_WFP)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_ln_wfp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaLnWfpInstrumentParserDataParticle'
        })
        log.debug("My Config: %s", config)
        parser = DostaLnWfpParser(
            config,
            parser_state,
            stream_in,
            lambda state, ingested: self._save_parser_state(state, DataSourceKey.DOSTA_LN_WFP, ingested),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_harvester(self, driver_state):
        """
        Build the telemetered and recovered harvester if they are configured
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.DOSTA_LN_WFP_SIO_MULE in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.DOSTA_LN_WFP_SIO_MULE),
                driver_state[DataSourceKey.DOSTA_LN_WFP_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.DOSTA_LN_WFP_SIO_MULE),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for dosta ln wfp sio mule harvester, not building')

        if DataSourceKey.DOSTA_LN_WFP in self._harvester_config:
            recov_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.DOSTA_LN_WFP),
                driver_state[DataSourceKey.DOSTA_LN_WFP],
                lambda filename: self._new_file_callback(filename, DataSourceKey.DOSTA_LN_WFP),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.DOSTA_LN_WFP),
                self._exception_callback)

            harvesters.append(recov_harvester)
        else:
            log.warn('No configuration for dosta ln wfp harvester, not building')

        return harvesters

