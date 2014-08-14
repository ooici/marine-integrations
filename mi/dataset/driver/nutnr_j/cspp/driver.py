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
from mi.dataset.parser.cspp_base import METADATA_PARTICLE_CLASS_KEY, \
                                        DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppParser, \
                                           NutnrJCsppTelemeteredDataParticle, \
                                           NutnrJCsppRecoveredDataParticle, \
                                           NutnrJCsppMetadataTelemeteredDataParticle, \
                                           NutnrJCsppMetadataRecoveredDataParticle


class DataSourceKey(BaseEnum):
    """
    Define the parser / harvester combinations for this driver
    """
    # Replace keys below with parser harvester named keys
    NUTNR_J_CSPP_TELEMETERED = "nutnr_j_cspp_telemetered"
    NUTNR_J_CSPP_RECOVERED = "nutnr_j_cspp_recovered"


class NutnrJCsppDataSetDriver(MultipleHarvesterDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [NutnrJCsppTelemeteredDataParticle.type(),
                NutnrJCsppRecoveredDataParticle.type(),
                NutnrJCsppMetadataTelemeteredDataParticle.type(),
                NutnrJCsppMetadataRecoveredDataParticle.type()]

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
        if data_key == DataSourceKey.NUTNR_J_CSPP_TELEMETERED:
            config = self._parser_config.get(DataSourceKey.NUTNR_J_CSPP_TELEMETERED)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: NutnrJCsppTelemeteredDataParticle
                }
            })

        elif data_key == DataSourceKey.NUTNR_J_CSPP_RECOVERED:
            config = self._parser_config.get(DataSourceKey.NUTNR_J_CSPP_RECOVERED)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: NutnrJCsppRecoveredDataParticle
                }
            })

        else:
            log.warn("Cannot build parser for unknown data source key %s", data_key)
            raise ConfigurationException("Cannot build parser for unknown data source key %s" % \
                                         data_key)
        
        parser = NutnrJCsppParser(
            config,
            parser_state,
            stream_in,
            lambda state, ingested: self._save_parser_state(state, data_key,
                                                            ingested),
            self._data_callback,
            self._sample_exception_callback
        )

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.NUTNR_J_CSPP_TELEMETERED in self._harvester_config:
            harvesters.append(self.build_single_dir_harvester(driver_state,
                                                              DataSourceKey.NUTNR_J_CSPP_TELEMETERED))
        else:
            log.warn('No configuration for %s harvester, not building',
                     DataSourceKey.NUTNR_J_CSPP_TELEMETERED)

        if DataSourceKey.NUTNR_J_CSPP_RECOVERED in self._harvester_config:
            harvesters.append(self.build_single_dir_harvester(driver_state,
                                                              DataSourceKey.NUTNR_J_CSPP_RECOVERED))
        else:
            log.warn('No configuration for %s harvester, not building',
                     DataSourceKey.NUTNR_J_CSPP_RECOVERED)

        return harvesters
    
    def build_single_dir_harvester(self, driver_state, data_key):
        """
        Build a single directory harvester for the given data source key
        @param driver_state - the starting driver state
        @param data_key - the data source key to build the harvester for
        """
        return SingleDirectoryHarvester(
            self._harvester_config.get(data_key),
            driver_state[data_key],
            lambda filename: self._new_file_callback(filename, data_key),
            lambda modified: self._modified_file_callback(modified, data_key),
            self._exception_callback
        )