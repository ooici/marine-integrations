"""
@package mi.dataset.driver.ADCPS_JLN.stc_imodem.driver
@file marine-integrations/mi/dataset/driver/ADCPS_JLN/stc_imodem/driver.py
@author Maria Lutz
@brief Driver for the ADCPS_JLN__stc_imodem
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.adcps_jln__stc_imodem import Adcps_jln__stc_imodemParser, Adcps_jln__stc_imodemParserDataParticle

class ADCPS_JLN__stc_imodem_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Adcps_jln__stc_imodemParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.adcps_jln__stc_imodem',
            'particle_class': 'Adcps_jln__stc_imodemParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Adcps_jln__stc_imodemParser(
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
        # *** Replace the following with harvester initialization ***
        self._harvester = None     
        return self._harvester
