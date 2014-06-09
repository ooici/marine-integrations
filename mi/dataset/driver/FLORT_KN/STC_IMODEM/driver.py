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
from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.parser.flort_kn__stc_imodem import Flort_kn__stc_imodemParser, Flort_kn__stc_imodemParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    """
    Serves as an enumeration that determines whether the driver is parsing Instrument data
    or Recovered data
    """
    FLORT_KN_INSTRUMENT = 'FLORT_KN_instrument'
    FLORT_KN_RECOVERED = 'FLORT_KN_recovered'


class FLORT_KN__STC_IMODEN_DataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.FLORT_KN_INSTRUMENT, DataTypeKey.FLORT_KN_RECOVERED]
        super(FLORT_KN__STC_IMODEN_DataSetDriver, self).__init__(config, memento, data_callback,
                                                                 state_callback, event_callback,
                                                                 exception_callback, data_keys)
    @classmethod
    def stream_config(cls):
        return [Flort_kn__stc_imodemParserDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key = None):
        """
        Build and return the parser
        """

        if data_key == DataTypeKey.FLORT_KN_INSTRUMENT:
            config = self._parser_config
            config.update({
                'particle_module': 'mi.dataset.parser.flort_kn__stc_imodem',
                'particle_class': 'Flort_kn__stc_imodemParserDataParticle'
            })
        elif data_key == DataTypeKey.FLORT_KN_RECOVERED:
            config = self._parser_config
            config.update({
                'particle_module': 'mi.dataset.parser.flort_kn__stc_imodem',
                'particle_class': 'Flort_kn__stc_imodemParserDataParticleRecovered'
            })
        else:
            return None

        log.debug("My Config: %s", config)
        parser = Flort_kn__stc_imodemParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_single_harvester(self, driver_state, key):
        """
        Build and return the harvester
        """
        if key in self._harvester_config:
                self._harvester = SingleDirectoryHarvester(
                    self._harvester_config,
                    driver_state,
                    self._new_file_callback,
                    self._modified_file_callback,
                    self._exception_callback
                )
        else:
            self._harvestor = None
        return self._harvester
