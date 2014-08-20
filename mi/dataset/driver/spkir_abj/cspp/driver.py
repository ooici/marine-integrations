"""
@package mi.dataset.driver.spkir_abj.cspp.driver
@file marine-integrations/mi/dataset/driver/spkir_abj/cspp/driver.py
@author Jeff Roy
@brief Driver for the spkir_abj_cspp
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.harvester import SingleDirectoryHarvester

from mi.dataset.parser.cspp_base import \
    METADATA_PARTICLE_CLASS_KEY, \
    DATA_PARTICLE_CLASS_KEY

from mi.dataset.parser.spkir_abj_cspp import \
    SpkirAbjCsppParser, \
    SpkirAbjCsppMetadataTelemeteredDataParticle, \
    SpkirAbjCsppMetadataRecoveredDataParticle, \
    SpkirAbjCsppInstrumentTelemeteredDataParticle, \
    SpkirAbjCsppInstrumentRecoveredDataParticle


class DataTypeKey(BaseEnum):
    SPKIR_ABJ_CSPP_TELEMETERED = 'spkir_abj_cspp_telemetered'
    SPKIR_ABJ_CSPP_RECOVERED = 'spkir_abj_cspp_recovered'


class SpkirAbjCsppDataSetDriver(MultipleHarvesterDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [SpkirAbjCsppMetadataTelemeteredDataParticle.type(),
                SpkirAbjCsppMetadataRecoveredDataParticle.type(),
                SpkirAbjCsppInstrumentTelemeteredDataParticle.type(),
                SpkirAbjCsppInstrumentRecoveredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        log.debug("data keys in driver constructor are %s", data_keys)

        super(SpkirAbjCsppDataSetDriver, self).__init__(config, memento,
                                                        data_callback,
                                                        state_callback,
                                                        event_callback,
                                                        exception_callback,
                                                        data_keys)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build and return the parser
        """

        config = self._parser_config.get(data_key)

        if config is None:
            log.warn('Parser config does not exist for key = %s.  Not building parser', data_key)
            raise ConfigurationException

        if data_key == DataTypeKey.SPKIR_ABJ_CSPP_TELEMETERED:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.spkir_abj_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: SpkirAbjCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: SpkirAbjCsppInstrumentTelemeteredDataParticle,
                }
            })
        elif data_key == DataTypeKey.SPKIR_ABJ_CSPP_RECOVERED:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.spkir_abj_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: SpkirAbjCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: SpkirAbjCsppInstrumentRecoveredDataParticle,
                }
            })
        else:
            log.warn('Invalid Data_Key %s.  Not building parser', data_key)
            raise ConfigurationException

        log.debug("_build_parser  Config: %s", config)

        parser = SpkirAbjCsppParser(
            config,
            parser_state,
            stream_in,
            lambda state, ingested:
            self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback
        )

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """

        harvesters = []

        if DataTypeKey.SPKIR_ABJ_CSPP_TELEMETERED in self._harvester_config:
            telemetered_harvester = self.build_single_harvester(
                driver_state,
                DataTypeKey.SPKIR_ABJ_CSPP_TELEMETERED)

            if telemetered_harvester is not None:
                harvesters.append(telemetered_harvester)
            else:
                log.warn('Creation of spkir_abj_cspp telemetered harvester failed')
        else:
            log.warn('No configuration for spkir_abj_cspp telemetered harvester, not building')

        if DataTypeKey.SPKIR_ABJ_CSPP_TELEMETERED in self._harvester_config:
            recovered_harvester = self.build_single_harvester(
                driver_state,
                DataTypeKey.SPKIR_ABJ_CSPP_RECOVERED)

            if recovered_harvester is not None:
                harvesters.append(recovered_harvester)
            else:
                log.warn('Creation of spkir_abj_cspp recovered harvester failed')
        else:
            log.warn('No configuration for spkir_abj_cspp recovered harvester, not building')

        return harvesters

    def build_single_harvester(self, driver_state, key):

        harvester = SingleDirectoryHarvester(
            self._harvester_config.get(key),
            driver_state[key],
            lambda filename: self._new_file_callback(filename, key),
            lambda modified: self._modified_file_callback(modified, key),
            self._exception_callback)

        return harvester
