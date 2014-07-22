"""
@package mi.dataset.driver.parad_j.cspp.driver
@file marine-integrations/mi/dataset/driver/parad_j/cspp/driver.py
@author Joe Padula
@brief Driver for the parad_j_cspp
Release notes:

initial release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType, DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import METADATA_PARTICLE_CLASS_KEY, DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.parad_j_cspp import ParadJCsppParser, \
    ParadJCsppInstrumentRecoveredDataParticle, ParadJCsppInstrumentTelemeteredDataParticle, \
    ParadJCsppMetadataRecoveredDataParticle, ParadJCsppMetadataTelemeteredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    PARAD_J_CSPP_RECOVERED = 'parad_j_cspp_recovered'
    PARAD_J_CSPP_TELEMETERED = 'parad_j_cspp_telemetered'


class ParadJCsppDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.PARAD_J_CSPP_RECOVERED,
                     DataTypeKey.PARAD_J_CSPP_TELEMETERED]

        harvester_type = {
            DataTypeKey.PARAD_J_CSPP_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.PARAD_J_CSPP_TELEMETERED: HarvesterType.SINGLE_DIRECTORY
        }

        super(ParadJCsppDataSetDriver, self).__init__(config, memento, data_callback,
                                                      state_callback, event_callback,
                                                      exception_callback,
                                                      data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [ParadJCsppInstrumentRecoveredDataParticle.type(),
                ParadJCsppInstrumentTelemeteredDataParticle.type(),
                ParadJCsppMetadataRecoveredDataParticle.type(),
                ParadJCsppMetadataTelemeteredDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """
        config = self._parser_config.get(data_key)

        #
        # If the key is RECOVERED, build the recovered parser.
        #
        if data_key == DataTypeKey.PARAD_J_CSPP_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.parad_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: ParadJCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: ParadJCsppInstrumentRecoveredDataParticle
                }
            })

        #
        # If the key is TELEMETERED, build the telemetered parser.
        #
        elif data_key == DataTypeKey.PARAD_J_CSPP_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.parad_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: ParadJCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: ParadJCsppInstrumentTelemeteredDataParticle
                }
            })

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException("Invalid data_key supplied to build parser")

        parser = ParadJCsppParser(
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

        harvesters = []     # list of harvesters to be returned

        #
        # Verify that the PARAD_J_CSPP_RECOVERED harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.PARAD_J_CSPP_RECOVERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.PARAD_J_CSPP_RECOVERED),
                driver_state[DataTypeKey.PARAD_J_CSPP_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.PARAD_J_CSPP_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.PARAD_J_CSPP_RECOVERED),
                self._exception_callback)

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warn('PARAD_J_CSPP_RECOVERED HARVESTER NOT BUILT')

        #
        # Verify that the PARAD_J_CSPP_TELEMETERED harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.PARAD_J_CSPP_TELEMETERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.PARAD_J_CSPP_TELEMETERED),
                driver_state[DataTypeKey.PARAD_J_CSPP_TELEMETERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.PARAD_J_CSPP_TELEMETERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.PARAD_J_CSPP_TELEMETERED),
                self._exception_callback)

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warn('PARAD_J_CSPP_TELEMETERED HARVESTER NOT BUILT')

        return harvester
