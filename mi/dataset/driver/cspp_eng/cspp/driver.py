"""
@package mi.dataset.driver.cspp_eng.cspp.driver
@file marine-integrations/mi/dataset/driver/cspp_eng/cspp/driver.py
@author Jeff Roy
@brief Driver for the cspp_eng_cspp
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.dbg_pdbg_cspp import CsppEngCsppParser, CsppEngCsppParserDataParticle

class CsppEngCsppDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [CsppEngCsppParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.cspp_eng_cspp',
            'particle_class': 'CsppEngCsppParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = CsppEngCsppParser(
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
