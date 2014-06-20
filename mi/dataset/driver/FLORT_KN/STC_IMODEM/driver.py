"""
@package mi.dataset.driver.FLORT_KN.STC_IMODEM.driver
@file marine-integrations/mi/dataset/driver/FLORT_KN/STC_IMODEM/driver.py
@author Emily Hahn
@brief Driver for the FLORT_KN__STC_IMODEM
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string
from mi.core.log import get_logger; log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.flort_kn__stc_imodem import Flort_kn_stc_imodemParser,\
                                                   Flort_kn_stc_imodemParserDataParticleTelemetered,\
                                                   Flort_kn_stc_imodemParserDataParticleRecovered, \
                                                   DataParticleType
from mi.dataset.harvester import SingleDirectoryHarvester


class FLORT_KN_STC_IMODEM_DataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataParticleType.list()

        super(FLORT_KN_STC_IMODEM_DataSetDriver, self).__init__(config, memento, data_callback,
                                                                 state_callback, event_callback,
                                                                 exception_callback, data_keys)
    @classmethod
    def stream_config(cls):
        return [Flort_kn_stc_imodemParserDataParticleTelemetered.type(),
                Flort_kn_stc_imodemParserDataParticleRecovered.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """

        if data_key == DataParticleType.FLORT_KN_INSTRUMENT_TELEMETERED:
            config = self._parser_config.get(DataParticleType.FLORT_KN_INSTRUMENT_TELEMETERED)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flort_kn__stc_imodem',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'Flort_kn_stc_imodemParserDataParticleTelemetered'
            })

        elif data_key == DataParticleType.FLORT_KN_INSTRUMENT_RECOVERED:
            config = self._parser_config.get(DataParticleType.FLORT_KN_INSTRUMENT_RECOVERED)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flort_kn__stc_imodem',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'Flort_kn_stc_imodemParserDataParticleRecovered'
            })

        else:
            return None

        log.debug("My Config: %s", config)
        parser = Flort_kn_stc_imodemParser(
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
                                    driver_state,
                                    DataParticleType.FLORT_KN_INSTRUMENT_TELEMETERED)
        if instrument_harvester is not None:
            harvesters.append(instrument_harvester)

        recovered_harvester = self.build_single_harvester(
                                   driver_state,
                                   DataParticleType.FLORT_KN_INSTRUMENT_RECOVERED)
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
            raise ConfigurationException('FLORT KN recovered harvester not built because missing config')
        return harvester
