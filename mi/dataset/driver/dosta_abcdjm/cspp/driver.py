"""
@package mi.dataset.driver.dosta_abcdjm.cspp.driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/cspp/driver.py
@author Mark Worden
@brief Driver for the dosta_abcdjm_cspp
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType, DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import METADATA_PARTICLE_CLASS_KEY, DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.dosta_abcdjm_cspp import DostaAbcdjmCsppParser, \
    DostaAbcdjmCsppInstrumentRecoveredDataParticle, DostaAbcdjmCsppInstrumentTelemeteredDataParticle, \
    DostaAbcdjmCsppMetadataRecoveredDataParticle, DostaAbcdjmCsppMetadataTelemeteredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    DOSTA_ABCDJM_CSPP_RECOVERED = 'dosta_abcdjm_cspp_recovered'
    DOSTA_ABCDJM_CSPP_TELEMETERED = 'dosta_abcdjm_cspp_telemetered'


class DostaAbcdjmCsppDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED,
                     DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED]

        harvester_type = {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED: HarvesterType.SINGLE_DIRECTORY
        }

        super(DostaAbcdjmCsppDataSetDriver, self).__init__(config, memento, data_callback,
                                                           state_callback, event_callback,
                                                           exception_callback,
                                                           data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [DostaAbcdjmCsppInstrumentRecoveredDataParticle.type(),
                DostaAbcdjmCsppInstrumentTelemeteredDataParticle.type(),
                DostaAbcdjmCsppMetadataRecoveredDataParticle.type(),
                DostaAbcdjmCsppMetadataTelemeteredDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """

        config = self._parser_config.get(data_key)

        #
        # If the key is DOSTA_ABCDJM_CSPP_RECOVERED, build the WFP parser.
        #
        if data_key == DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_abcdjm_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppInstrumentRecoveredDataParticle
                }
            })

        #
        # If the key is DOSTA_ABCDJM_CSPP_TELEMETERED, build the WFP SIO Mule parser.
        #
        elif data_key == DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_abcdjm_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppInstrumentTelemeteredDataParticle
                }
            })

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException("Invalid data_key supplied to build parser")

        parser = DostaAbcdjmCsppParser(
            config,
            parser_state,
            infile,
            lambda state, ingested: self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the DOSTA_ABCDJM_CSPP_RECOVERED harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                driver_state[DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                self._exception_callback)

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warn('DOSTA_ABCDJM_CSPP_RECOVERED harvester not built')
        else:
            log.warn('DOSTA_ABCDJM_CSPP_RECOVERED key missing from config harvester not built')
        #
        # Verify that the DOSTA_ABCDJM_CSPP_TELEMETERED harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED),
                driver_state[DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED],
                lambda filename: self._new_file_callback(filename, DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED),
                lambda modified: self._modified_file_callback(modified, DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED),
                self._exception_callback)

            if harvester is not None:
                harvesters.append(harvester)
            else:
                log.warn('DOSTA_ABCDJM_CSPP_TELEMETERED harvester not built')
        else:
            log.warn('DOSTA_ABCDJM_CSPP_TELEMETERED key missing from config harvester not built')

        return harvesters
