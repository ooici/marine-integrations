"""
@package mi.dataset.driver.nutnr_j.cspp.driver
@file marine-integrations/mi/dataset/driver/nutnr_j/cspp/driver.py
@author Emily Hahn
@brief Driver for the nutnr_j_cspp
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, \
                                      DataSetDriverConfigKeys
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppParser, NutnrJCsppParserDataParticle

class DataSourceKey(BaseEnum):
    """
    Define the parser / harvester combinations for this driver
    """
    # Replace keys below with parser harvester named keys
    KEY_1 = "key_1"
    KEY_2 = "key_2"

class NutnrJCsppDataSetDriver(MultipleHarvesterSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [NutnrJCsppParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):
        # no harvester type argument defaults to all single directory harvesters
        super(NutnrJCsppDataSetDriver, self).__init__(config, memento, data_callback,
                                        state_callback, event_callback,
                                        exception_callback, DataSourceKey.list())

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build and return a parser for the data_key type parser
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        # build the parser based on which key is passed in 
        if data_key == DataSourceKey.KEY_1:
            config = self._parser_config.get(DataSourceKey.KEY_1)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'NutnrJCsppParserDataParticle'
            })

            parser = NutnrJCsppParser(
                config,
                parser_state,
                stream_in,
                lambda state,ingested: self._save_parser_state(state, DataSourceKey.KEY_1, ingested),
                self._data_callback,
                self._sample_exception_callback 
            )

        elif data_key == DataSourceKey.KEY_2:
            config = self._parser_config.get(DataSourceKey.KEY_2)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'NutnrJCsppParserDataParticle'
            })

            parser = NutnrJCsppParser(
                config,
                parser_state,
                stream_in,
                lambda state, ingested: self._save_parser_state(state, DataSourceKey.KEY_2, ingested),
                self._data_callback,
                self._sample_exception_callback
            )
        else:
            raise ConfigurationException("Cannot build parser for unknown data source key %s" % data_key)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.KEY_1 in self._harvester_config:
            harvester_1 = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.KEY_1),
                driver_state[DataSourceKey.KEY_1],
                lambda filename: self._new_file_callback(filename, DataSourceKey.KEY_1),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.KEY_1),
                self._exception_callback
            )
            harvesters.append(harvester_1)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.KEY_1)

        if DataSourceKey.KEY_2 in self._harvester_config:
            harvester_2 = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.KEY_2),
                driver_state[DataSourceKey.KEY_2],
                lambda filename: self._new_file_callback(filename, DataSourceKey.KEY_2),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.KEY_2),
                self._exception_callback
            )
            harvesters.append(harvester_2)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.KEY_2)

        return harvesters
