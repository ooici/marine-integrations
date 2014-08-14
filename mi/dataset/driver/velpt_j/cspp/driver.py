"""
@package mi.dataset.driver.velpt_j.cspp.driver
@file marine-integrations/mi/dataset/driver/velpt_j/cspp/driver.py
@author Jeremy Amundson
@brief Driver for the velpt_j_cspp
Release notes:

Initial Release
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger 
log = get_logger()

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import METADATA_PARTICLE_CLASS_KEY, DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.velpt_j_cspp import VelptJCsppParser, \
    VelptJCsppInstrumentTelemeteredDataParticle, VelptJCsppInstrumentRecoveredDataParticle,\
    VelptJCsppMetadataRecoveredDataParticle, VelptJCsppMetadataTelemeteredDataParticle
from mi.core.common import BaseEnum
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.core.exceptions import ConfigurationException


class DataTypeKey(BaseEnum):

    VELPT_J_CSPP_RECOVERED = 'velpt_j_cspp_recovered'
    VELPT_J_CSPP_TELEMETERED = 'velpt_j_cspp_telemetered'


class VelptJCsppDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        super(VelptJCsppDataSetDriver, self).__init__(config, memento, data_callback,
                                                       state_callback, event_callback,
                                                       exception_callback, data_keys)

    @classmethod
    def stream_config(cls):
        return [VelptJCsppInstrumentTelemeteredDataParticle.type(), VelptJCsppInstrumentRecoveredDataParticle.type(),
                VelptJCsppMetadataRecoveredDataParticle.type(), VelptJCsppMetadataTelemeteredDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """

        if data_key == DataTypeKey.VELPT_J_CSPP_RECOVERED:
            config = self._parser_config.get(DataTypeKey.VELPT_J_CSPP_RECOVERED)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.velpt_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: VelptJCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: VelptJCsppInstrumentRecoveredDataParticle
                }
            })
        elif data_key == DataTypeKey.VELPT_J_CSPP_TELEMETERED:

            config = self._parser_config.get(DataTypeKey.VELPT_J_CSPP_TELEMETERED)
            config.update(
            {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.velpt_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: VelptJCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: VelptJCsppInstrumentTelemeteredDataParticle
                }
            })

        else:
            raise ConfigurationException('Parser not built due to missing particle type')

        parser = VelptJCsppParser(
            config,
            parser_state,
            infile,
            lambda state, ingested:
            self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_harvester(self, driver_state):

        harvesters = []

        instrument_harvester = self.build_single_harvester(
            driver_state, DataTypeKey.VELPT_J_CSPP_TELEMETERED)
        if instrument_harvester is not None:
            harvesters.append(instrument_harvester)

        recovered_harvester = self.build_single_harvester(
            driver_state, DataTypeKey.VELPT_J_CSPP_RECOVERED)

        if recovered_harvester is not None:
            harvesters.append(recovered_harvester)

        return harvesters

    def build_single_harvester(self, driver_state, key):
        """
        Build and return the harvester
        """
        if key in self._harvester_config:
            harvester = SingleDirectoryHarvester(
            self._harvester_config.get(key),
            driver_state[key],
            lambda filename: self._new_file_callback(filename, key),
            lambda modified: self._modified_file_callback(modified, key),
            self._exception_callback)
        else:
            harvester = None
            log.warn('build_single_harvester did not receive a particle type, harvester instantiation failed')
        return harvester
