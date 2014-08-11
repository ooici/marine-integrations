"""
@package mi.dataset.driver.optaa_dj.cspp.driver
@file marine-integrations/mi/dataset/driver/optaa_dj/cspp/driver.py
@author Joe Padula
@brief Driver for the optaa_dj_cspp
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import METADATA_PARTICLE_CLASS_KEY, DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.optaa_dj_cspp import OptaaDjCsppParser, \
    OptaaDjCsppInstrumentRecoveredDataParticle, OptaaDjCsppInstrumentTelemeteredDataParticle, \
    OptaaDjCsppMetadataRecoveredDataParticle, OptaaDjCsppMetadataTelemeteredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    OPTAA_DJ_CSPP_RECOVERED = 'optaa_dj_cspp_recovered'
    OPTAA_DJ_CSPP_TELEMETERED = 'optaa_dj_cspp_telemetered'


class OptaaDjCsppDataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [OptaaDjCsppInstrumentRecoveredDataParticle.type(),
                OptaaDjCsppInstrumentTelemeteredDataParticle.type(),
                OptaaDjCsppMetadataRecoveredDataParticle.type(),
                OptaaDjCsppMetadataTelemeteredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        super(OptaaDjCsppDataSetDriver, self).__init__(config, memento, data_callback,
                                                       state_callback, event_callback,
                                                       exception_callback,
                                                       data_keys)

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """
        config = self._parser_config.get(data_key)

        #
        # If the key is RECOVERED, build the recovered parser.
        #
        if data_key == DataTypeKey.OPTAA_DJ_CSPP_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: OptaaDjCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: OptaaDjCsppInstrumentRecoveredDataParticle
                }
            })

        #
        # If the key is TELEMETERED, build the telemetered parser.
        #
        elif data_key == DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: OptaaDjCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: OptaaDjCsppInstrumentTelemeteredDataParticle
                }
            })

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException("Invalid data_key (%s) supplied to build parser" % data_key)

        parser = OptaaDjCsppParser(
            config,
            parser_state,
            infile,
            lambda state, ingested: self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """

        harvesters = []

        if DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED in self._harvester_config:
            telemetered_harvester = self.build_single_harvester(
                driver_state,
                DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED)

            harvesters.append(telemetered_harvester)

        else:
            log.warn('No configuration for optaa_dj_cspp telemetered harvester, not building')

        if DataTypeKey.OPTAA_DJ_CSPP_RECOVERED in self._harvester_config:
            recovered_harvester = self.build_single_harvester(
                driver_state,
                DataTypeKey.OPTAA_DJ_CSPP_RECOVERED)

            harvesters.append(recovered_harvester)

        else:
            log.warn('No configuration for optaa_dj_cspp recovered harvester, not building')

        return harvesters

    def build_single_harvester(self, driver_state, key):

        harvester = SingleDirectoryHarvester(
            self._harvester_config.get(key),
            driver_state[key],
            lambda filename: self._new_file_callback(filename, key),
            lambda modified: self._modified_file_callback(modified, key),
            self._exception_callback)

        return harvester
