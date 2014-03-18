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
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodemParser
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_statusParserDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_startParserDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_engineeringParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class WFP_ENG__STC_IMODEM_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Wfp_eng__stc_imodem_statusParserDataParticle.type(),
                Wfp_eng__stc_imodem_startParserDataParticle.type(),
                Wfp_eng__stc_imodem_engineeringParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.wfp_eng__stc_imodem',
            'particle_class': ['Wfp_eng__stc_imodem_statusParserDataParticle',
                               'Wfp_eng__stc_imodem_startParserDataParticle',
                               'Wfp_eng__stc_imodem_engineeringParserDataParticle']
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
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )
        return self._harvester
