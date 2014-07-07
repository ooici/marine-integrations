"""
@package mi.dataset.driver.dofst_k.wfp.driver
@file marine-integrations/mi/dataset/driver/dofst_k/wfp/driver.py
@author Emily Hahn
@brief Driver for the dofst_k_wfp
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import os
from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.parser.dofst_k_wfp import DofstKWfpParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.dofst_k_wfp_particles import DofstKWfpRecoveredDataParticle,\
    DofstKWfpRecoveredMetadataParticle
from mi.dataset.parser.dofst_k_wfp_particles import DofstKWfpTelemeteredDataParticle,\
    DofstKWfpTelemeteredMetadataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    DOFST_K_WFP_TELEMETERED = 'dofst_k_wfp_telemetered'
    DOFST_K_WFP_RECOVERED = 'dofst_k_wfp_recovered'


class DofstKWfpDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self,
                 config,
                 memento,
                 data_callback,
                 state_callback,
                 event_callback,
                 exception_callback):

        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataTypeKey.DOFST_K_WFP_TELEMETERED, DataTypeKey.DOFST_K_WFP_RECOVERED]

        super(DofstKWfpDataSetDriver, self).__init__(config,
                                                     memento,
                                                     data_callback,
                                                     state_callback,
                                                     event_callback,
                                                     exception_callback,
                                                     data_keys)
    @classmethod
    def stream_config(cls):
        return [DofstKWfpRecoveredDataParticle.type(),
                DofstKWfpRecoveredMetadataParticle.type(),
                DofstKWfpTelemeteredDataParticle.type(),
                DofstKWfpTelemeteredMetadataParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):
        """
        Build and return the parser
        """
        # Default the parser to None
        parser = None
        
        config = self._parser_config.get(data_key)
        
        #
        # If the key is DOFST_K_WFP_RECOVERED, build the dofst_k_wfp parser and
        # provide a config that includes the specific recovered particle types.
        #
        if data_key == DataTypeKey.DOFST_K_WFP_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dofst_k_wfp_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'instrument_data_particle_class': DofstKWfpRecoveredDataParticle,
                    'metadata_particle_class': DofstKWfpRecoveredMetadataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = DofstKWfpParser(
                config,
                parser_state,
                file_handle,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback,
                os.path.getsize(file_handle.name))
        #
        # If the key is DOFST_K_WFP_TELEMETERED, build the dofst_k_wfp parser and
        # provide a config that includes the specific telemetered particle types.
        #
        elif data_key == DataTypeKey.DOFST_K_WFP_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dofst_k_wfp_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'instrument_data_particle_class': DofstKWfpTelemeteredDataParticle,
                    'metadata_particle_class': DofstKWfpTelemeteredMetadataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = DofstKWfpParser(
                config,
                parser_state,
                file_handle,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback,
                os.path.getsize(file_handle.name))
        else:
            raise ConfigurationException\
                ('Bad Configuration: %s - Failed to build ctdpf_ckl_wfp parser',config)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the DOFST_K_WFP_RECOVERED harvester has been configured.
        # If so, build the DOFST_K_WFP_RECOVERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.DOFST_K_WFP_RECOVERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.DOFST_K_WFP_RECOVERED),
                driver_state[DataTypeKey.DOFST_K_WFP_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.DOFST_K_WFP_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.DOFST_K_WFP_RECOVERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.debug('DOFST_K_WFP_RECOVERED HARVESTER NOT BUILT')
        #
        # Verify that the DOFST_K_WFP_TELEMETERED harvester has been configured.
        # If so, build the DOFST_K_WFP_TELEMETERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.DOFST_K_WFP_TELEMETERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.DOFST_K_WFP_TELEMETERED),
                driver_state[DataTypeKey.DOFST_K_WFP_TELEMETERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.DOFST_K_WFP_TELEMETERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.DOFST_K_WFP_TELEMETERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.debug('DOFST_K_WFP_TELEMETERED HARVESTER NOT BUILT')

        return harvesters
