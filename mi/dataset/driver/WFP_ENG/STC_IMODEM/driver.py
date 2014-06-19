"""
@package mi.dataset.driver.WFP_ENG.STC_IMODEM.driver
@file marine-integrations/mi/dataset/driver/WFP_ENG/STC_IMODEM/driver.py
@author Emily Hahn
@brief Driver for the WFP_ENG__STC_IMODEM
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.parser.wfp_eng__stc_imodem import WfpEngStcImodemParser
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringTelemeteredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    WFP_ENG_STC_IMODEM_RECOVERED = 'wfp_eng_stc_imodem_recovered'
    WFP_ENG_STC_IMODEM_TELEMETERED = 'wfp_eng_stc_imodem_telemetered'


class WFP_ENG__STC_IMODEM_DataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED]

        harvester_type = {
            DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED: HarvesterType.SINGLE_DIRECTORY
        }

        super(WFP_ENG__STC_IMODEM_DataSetDriver, self).__init__(
            config, memento, data_callback, state_callback, event_callback,
            exception_callback, data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [WfpEngStcImodemStatusRecoveredDataParticle.type(),
                WfpEngStcImodemStartRecoveredDataParticle.type(),
                WfpEngStcImodemEngineeringRecoveredDataParticle.type(),
                WfpEngStcImodemStatusTelemeteredDataParticle.type(),
                WfpEngStcImodemStartTelemeteredDataParticle.type(),
                WfpEngStcImodemEngineeringTelemeteredDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """
        # Default the parser to None
        parser = None

        config = self._parser_config.get(data_key)

        #
        # If the key is WFP_ENG_STC_IMODEM_RECOVERED, build the Wfp_eng__stc_imodemParser parser and
        # provide a config that includes the specific recovered particle types.
        #
        if data_key == DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'status_data_particle_class': WfpEngStcImodemStatusRecoveredDataParticle,
                    'start_data_particle_class': WfpEngStcImodemStartRecoveredDataParticle,
                    'engineering_data_particle_class': WfpEngStcImodemEngineeringRecoveredDataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = WfpEngStcImodemParser(
                config,
                parser_state,
                infile,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is WFP_ENG_STC_IMODEM_TELEMETERED, build the Wfp_eng__stc_imodemParser parser and
        # provide a config that includes the specific telemetered particle types.
        #
        elif data_key == DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'status_data_particle_class': WfpEngStcImodemStatusTelemeteredDataParticle,
                    'start_data_particle_class': WfpEngStcImodemStartTelemeteredDataParticle,
                    'engineering_data_particle_class': WfpEngStcImodemEngineeringTelemeteredDataParticle
                }
            })
            log.debug("My Config: %s", config)
            parser = WfpEngStcImodemParser(
                config,
                parser_state,
                infile,
                lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        else:
            raise ConfigurationException

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the WFP_ENG_STC_IMODEM_RECOVERED harvester has been configured.
        # If so, build the WFP_ENG_STC_IMODEM_RECOVERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED),
                driver_state[DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.debug('WFP_ENG_STC_IMODEM_RECOVERED HARVESTER NOT BUILT')

        #
        # Verify that the WFP_ENG_STC_IMODEM_TELEMETERED harvester has been configured.
        # If so, build the WFP_ENG_STC_IMODEM_TELEMETERED harvester and add it to the
        # list of harvesters.
        #
        if DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED),
                driver_state[DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED),
                self._exception_callback
            )

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.debug('WFP_ENG_STC_IMODEM_TELEMETERED HARVESTER NOT BUILT')

        return harvesters
