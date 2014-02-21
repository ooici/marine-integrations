"""
@package mi.dataset.driver.WFP_ENG.STC_IMODEM.driver
@file marine-integrations/mi/dataset/driver/WFP_ENG/STC_IMODEM/driver.py
@author Emily Hahn
@brief Driver for the WFP_ENG__STC_IMODEM
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodemParser, Wfp_eng__stc_imodemParserDataParticle

class WFP_ENG__STC_IMODEM_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Wfp_eng__stc_imodemParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.wfp_eng__stc_imodem',
            'particle_class': 'Wfp_eng__stc_imodemParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Wfp_eng__stc_imodemParser(
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
