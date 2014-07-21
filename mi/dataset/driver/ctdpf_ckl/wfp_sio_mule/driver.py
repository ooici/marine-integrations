"""
@package mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/driver.py
@author cgoodrich
@brief Driver for the ctdpf_ckl_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import os

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.harvester import SingleFileHarvester, SingleDirectoryHarvester
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.ctdpf_ckl_wfp_particles import CtdpfCklWfpRecoveredDataParticle,\
    CtdpfCklWfpRecoveredMetadataParticle
from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import CtdpfCklWfpSioMuleParser, \
    CtdpfCklWfpSioMuleDataParticle, \
    CtdpfCklWfpSioMuleMetadataParticle
from mi.dataset.parser.ctdpf_ckl_wfp import CtdpfCklWfpParser


class DataTypeKey(BaseEnum):
    CTDPF_CKL_WFP = 'ctdpf_ckl_wfp'
    CTDPF_CKL_WFP_SIO_MULE = 'ctdpf_ckl_wfp_sio_mule'


INSTRUMENT_DATA_PARTICLE_CLASS = 'instrument_data_particle_class'
METADATA_PARTICLE_CLASS = 'metadata_particle_class'


class CtdpfCklWfpDataSetDriver(SioMuleDataSetDriver):

    def __init__(self,
                 config,
                 memento,
                 data_callback,
                 state_callback,
                 event_callback,
                 exception_callback):

        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataTypeKey.CTDPF_CKL_WFP, DataTypeKey.CTDPF_CKL_WFP_SIO_MULE]

        # link the data keys to the harvester type, single or multiple file harvester
        harvester_type = {DataTypeKey.CTDPF_CKL_WFP: HarvesterType.SINGLE_DIRECTORY,
                          DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: HarvesterType.SINGLE_FILE}

        super(CtdpfCklWfpDataSetDriver, self).__init__(config,
                                                       memento,
                                                       data_callback,
                                                       state_callback,
                                                       event_callback,
                                                       exception_callback,
                                                       data_keys,
                                                       harvester_type)

    @classmethod
    def stream_config(cls):
        return [CtdpfCklWfpRecoveredDataParticle.type(),
                CtdpfCklWfpRecoveredMetadataParticle.type(),
                CtdpfCklWfpSioMuleMetadataParticle.type(),
                CtdpfCklWfpSioMuleDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """
        # Default the parser to None
        parser = None

        config = self._parser_config.get(data_key)

        #
        # If the key is CTDPF_CKL_WFP, build the ctdpf_ckl_wfp parser and
        # provide a config that includes the specific recovered particle types.
        #
        if data_key == DataTypeKey.CTDPF_CKL_WFP:
            log.debug('CAG DRIVER - build parser for %s. State is %s', data_key, parser_state)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_ckl_wfp_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    INSTRUMENT_DATA_PARTICLE_CLASS: CtdpfCklWfpRecoveredDataParticle,
                    METADATA_PARTICLE_CLASS: CtdpfCklWfpRecoveredMetadataParticle
                }
            })

            parser = CtdpfCklWfpParser(
                config,
                parser_state,
                infile,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback,
                os.path.getsize(infile.name))
        #
        # If the key is CTDPF_CKL_WFP_SIO_MULE, build the ctdpf_ckl_wfp_sio_mule parser and
        # provide a config that includes the specific telemetered particle types.
        #
        elif data_key == DataTypeKey.CTDPF_CKL_WFP_SIO_MULE:
            log.debug('CAG DRIVER - build parser for %s. State is %s', data_key, parser_state)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_ckl_wfp_sio_mule',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    INSTRUMENT_DATA_PARTICLE_CLASS: CtdpfCklWfpSioMuleDataParticle,
                    METADATA_PARTICLE_CLASS: CtdpfCklWfpSioMuleMetadataParticle
                }
            })

            parser = CtdpfCklWfpSioMuleParser(
                config,
                parser_state,
                infile,
                lambda state: self._save_parser_state(state, DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
                self._data_callback,
                self._sample_exception_callback
            )
        else:
            raise ConfigurationException('Bad Configuration: %s - Failed to build ctdpf_ckl_wfp parser', config)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """
        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the CTDPF_CKL_WFP harvester has been configured.
        # If so, build the CTDPF_CKL_WFP harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.CTDPF_CKL_WFP in self._harvester_config:
            log.debug('CAG DRIVER - build harvester for %s', driver_state[DataTypeKey.CTDPF_CKL_WFP])
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.CTDPF_CKL_WFP),
                driver_state[DataTypeKey.CTDPF_CKL_WFP],
                lambda filename: self._new_file_callback(filename, DataTypeKey.CTDPF_CKL_WFP),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.CTDPF_CKL_WFP),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warning('CTDPF_CKL_WFP HARVESTER NOT BUILT')
        #
        # Verify that the CTDPF_CKL_WFP_SIO_MULE harvester has been configured.
        # If so, build the CTDPF_CKL_WFP_SIO_MULE harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.CTDPF_CKL_WFP_SIO_MULE in self._harvester_config:
            log.debug('CAG DRIVER - build harvester for %s', driver_state[DataTypeKey.CTDPF_CKL_WFP_SIO_MULE])
            harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
                driver_state[DataTypeKey.CTDPF_CKL_WFP_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataTypeKey.CTDPF_CKL_WFP_SIO_MULE),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warning('CTDPF_CKL_WFP_SIO_MULE HARVESTER NOT BUILT')

        return harvesters
