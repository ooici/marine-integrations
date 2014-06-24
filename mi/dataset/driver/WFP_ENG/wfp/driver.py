"""
@package mi.dataset.driver.wfp_eng.wfp_sio_mule.driver
@file marine-integrations/mi/dataset/driver/wfp_eng/wfp_sio_mule/driver.py
@author Mark Worden
@brief Driver for the wfp_eng_wfp_sio_mule
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import \
    HarvesterType, DataSetDriverConfigKeys

from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver

from mi.dataset.harvester import \
    SingleDirectoryHarvester, \
    SingleFileHarvester

from mi.dataset.parser.wfp_eng__stc_imodem import WfpEngStcImodemParser
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusRecoveredDataParticle, \
    WfpEngStcImodemStartRecoveredDataParticle, WfpEngStcImodemEngineeringRecoveredDataParticle

from mi.dataset.parser.wfp_eng_wfp_sio_mule import WfpEngWfpSioMuleParser, \
    WfpEngWfpSioMuleParserDataStartTimeParticle, \
    WfpEngWfpSioMuleParserDataStatusParticle, \
    WfpEngWfpSioMuleParserDataEngineeringParticle


class DataTypeKey(BaseEnum):
    WFP_ENG_STC_IMODEM = 'wfp_eng_stc_imodem'
    WFP_ENG_WFP_SIO_MULE = 'wfp_eng_wfp_sio_mule'


class WfpEngWfp(SioMuleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.WFP_ENG_STC_IMODEM, DataTypeKey.WFP_ENG_WFP_SIO_MULE]

        harvester_type = {
            DataTypeKey.WFP_ENG_STC_IMODEM: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.WFP_ENG_WFP_SIO_MULE: HarvesterType.SINGLE_FILE
        }

        super(WfpEngWfp, self).__init__(config, memento, data_callback,
                                        state_callback, event_callback,
                                        exception_callback,
                                        data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [WfpEngStcImodemStatusRecoveredDataParticle.type(),
                WfpEngStcImodemStartRecoveredDataParticle.type(),
                WfpEngStcImodemEngineeringRecoveredDataParticle.type(),
                WfpEngWfpSioMuleParserDataStartTimeParticle.type(),
                WfpEngWfpSioMuleParserDataStatusParticle.type(),
                WfpEngWfpSioMuleParserDataEngineeringParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """

        config = self._parser_config.get(data_key)

        #
        # If the key is WFP_ENG_STC_IMODEM, build the WFP parser.
        #
        if data_key == DataTypeKey.WFP_ENG_STC_IMODEM:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'status_data_particle_class': WfpEngStcImodemStatusRecoveredDataParticle,
                    'start_data_particle_class': WfpEngStcImodemStartRecoveredDataParticle,
                    'engineering_data_particle_class': WfpEngStcImodemEngineeringRecoveredDataParticle
                }
            })

            parser = WfpEngStcImodemParser(
                config, parser_state, infile,
                lambda state, ingested:
                self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is WFP_ENG_WFP_SIO_MULE, build the WFP SIO Mule parser.
        #
        elif data_key == DataTypeKey.WFP_ENG_WFP_SIO_MULE:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng_wfp_sio_mule',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'start_time_data_particle_class': WfpEngWfpSioMuleParserDataStartTimeParticle,
                    'status_data_particle_class': WfpEngWfpSioMuleParserDataStatusParticle,
                    'engineering_data_particle_class': WfpEngWfpSioMuleParserDataEngineeringParticle
                }
            })

            parser = WfpEngWfpSioMuleParser(config, parser_state, infile,
                                            lambda state:
                                            self._save_parser_state(state, data_key),
                                            self._data_callback,
                                            self._sample_exception_callback)

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException("Invalid data_key supplied to build parser")

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the WFP_ENG_STC_IMODEM harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.WFP_ENG_STC_IMODEM in self._harvester_config:
            wfp_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.WFP_ENG_STC_IMODEM),
                driver_state[DataTypeKey.WFP_ENG_STC_IMODEM],
                lambda filename: self._new_file_callback(filename, DataTypeKey.WFP_ENG_STC_IMODEM),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.WFP_ENG_STC_IMODEM),
                self._exception_callback)

            if wfp_harvester is not None:
                harvesters.append(wfp_harvester)
            else:
                log.debug('WFP_ENG_STC_IMODEM HARVESTER NOT BUILT')

        #
        # Verify that the WFP_ENG_WFP_SIO_MULE harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.WFP_ENG_WFP_SIO_MULE in self._harvester_config:
            sio_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.WFP_ENG_WFP_SIO_MULE),
                driver_state[DataTypeKey.WFP_ENG_WFP_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataTypeKey.WFP_ENG_WFP_SIO_MULE),
                self._exception_callback)

            if sio_harvester is not None:
                harvesters.append(sio_harvester)
            else:
                log.debug('WFP_ENG_WFP_SIO_MULE HARVESTER NOT BUILT')

        return harvesters
