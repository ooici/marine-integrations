"""
@package mi.dataset.driver.ctdpf_ckl.wfp.driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp/driver.py
@author cgoodrich
@brief Driver for the ctdpf_ckl_wfp
Release notes:

initial release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import os

from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException
from mi.core.common import BaseEnum
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.parser.ctdpf_ckl_wfp import CtdpfCklWfpParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.ctdpf_ckl_wfp_particles import CtdpfCklWfpRecoveredDataParticle,\
    CtdpfCklWfpRecoveredMetadataParticle
from mi.dataset.parser.ctdpf_ckl_wfp_particles import CtdpfCklWfpTelemeteredDataParticle,\
    CtdpfCklWfpTelemeteredMetadataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    CTDPF_CKL_WFP_RECOVERED = 'ctdpf_ckl_wfp_recovered'
    CTDPF_CKL_WFP_TELEMETERED = 'ctdpf_ckl_wfp_telemetered'


class CtdpfCklWfpDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self,
                 config,
                 memento,
                 data_callback,
                 state_callback,
                 event_callback,
                 exception_callback):

        data_keys = [DataTypeKey.CTDPF_CKL_WFP_RECOVERED, DataTypeKey.CTDPF_CKL_WFP_TELEMETERED]

        super(CtdpfCklWfpDataSetDriver, self).__init__(config,
                                                       memento,
                                                       data_callback,
                                                       state_callback,
                                                       event_callback,
                                                       exception_callback,
                                                       data_keys)

    @classmethod
    def stream_config(cls):
        return [CtdpfCklWfpRecoveredDataParticle.type(),
                CtdpfCklWfpRecoveredMetadataParticle.type(),
                CtdpfCklWfpTelemeteredDataParticle.type(),
                CtdpfCklWfpTelemeteredMetadataParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):
        """
        Build and return the parser
        """
        # Default the parser to None
        parser = None

        config = self._parser_config.get(data_key)

        #
        # If the key is CTDPF_CKL_WFP_RECOVERED, build the ctdpf_ckl_wfp parser and
        # provide a config that includes the specific recovered particle types.
        #
        if data_key == DataTypeKey.CTDPF_CKL_WFP_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_ckl_wfp_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'instrument_data_particle_class': CtdpfCklWfpRecoveredDataParticle,
                    'metadata_particle_class': CtdpfCklWfpRecoveredMetadataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = CtdpfCklWfpParser(
                config,
                parser_state,
                file_handle,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback,
                os.path.getsize(file_handle.name))
        #
        # If the key is CTDPF_CKL_WFP_TELEMETERED, build the ctdpf_ckl_wfp parser and
        # provide a config that includes the specific telemetered particle types.
        #
        elif data_key == DataTypeKey.CTDPF_CKL_WFP_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_ckl_wfp_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'instrument_data_particle_class': CtdpfCklWfpTelemeteredDataParticle,
                    'metadata_particle_class': CtdpfCklWfpTelemeteredMetadataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = CtdpfCklWfpParser(
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
        # Verify that the CTDPF_CKL_WFP_RECOVERED harvester has been configured.
        # If so, build the CTDPF_CKL_WFP_RECOVERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.CTDPF_CKL_WFP_RECOVERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.CTDPF_CKL_WFP_RECOVERED),
                driver_state[DataTypeKey.CTDPF_CKL_WFP_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.CTDPF_CKL_WFP_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.CTDPF_CKL_WFP_RECOVERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warning('CTDPF_CKL_WFP_RECOVERED HARVESTER NOT BUILT')
        #
        # Verify that the CTDPF_CKL_WFP_TELEMETERED harvester has been configured.
        # If so, build the CTDPF_CKL_WFP_TELEMETERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.CTDPF_CKL_WFP_TELEMETERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.CTDPF_CKL_WFP_TELEMETERED),
                driver_state[DataTypeKey.CTDPF_CKL_WFP_TELEMETERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.CTDPF_CKL_WFP_TELEMETERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.CTDPF_CKL_WFP_TELEMETERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warning('CTDPF_CKL_WFP_TELEMETERED HARVESTER NOT BUILT')

        return harvesters
