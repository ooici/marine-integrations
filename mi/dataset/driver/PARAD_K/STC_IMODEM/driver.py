"""
@package mi.dataset.driver.PARAD_K.STC_IMODEM.driver
@file marine-integrations/mi/dataset/driver/PARAD_K/STC_IMODEM/driver.py
@author Mike Nicoletti
@brief Driver for the PARAD_K_STC_IMODEM
Release notes:

New driver started for PARAD_K_STC_IMODEM
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.parad_k_stc_imodem import Parad_k_stc_imodemParser, Parad_k_stc_imodemParserDataParticle

class PARAD_K_STC_IMODEM_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Parad_k_stc_imodemParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.parad_k_stc_imodem',
            'particle_class': 'Parad_k_stc_imodemParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Parad_k_stc_imodemParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )
        return self._harvester
