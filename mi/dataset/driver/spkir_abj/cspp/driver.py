"""
@package mi.dataset.driver.spkir_abj.cspp.driver
@file marine-integrations/mi/dataset/driver/spkir_abj/cspp/driver.py
@author Jeff Roy
@brief Driver for the spkir_abj_cspp
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.spkir_abj_cspp import SpkirAbjCsppParser, SpkirAbjCsppParserDataParticle

class SpkirAbjCsppDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [SpkirAbjCsppParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.spkir_abj_cspp',
            'particle_class': 'SpkirAbjCsppParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = SpkirAbjCsppParser(
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
