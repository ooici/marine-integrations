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

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.flort_kn__stc_imodem import Flort_kn__stc_imodemParser, Flort_kn__stc_imodemParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class FLORT_KN__STC_IMODEM_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Flort_kn__stc_imodemParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flort_kn__stc_imodem',
            'particle_class': 'Flort_kn__stc_imodemParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Flort_kn__stc_imodemParser(
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
