"""
@package mi.dataset.driver.optaa_dj.cspp.driver
@file marine-integrations/mi/dataset/driver/optaa_dj/cspp/driver.py
@author Joe Padula
@brief Driver for the optaa_dg_cspp
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.optaa_dg_cspp import OptaaDgCsppParser, OptaaDgCsppParserDataParticle

class OptaaDjCsppDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [OptaaDgCsppParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.optaa_dg_cspp',
            'particle_class': 'OptaaDgCsppParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = OptaaDgCsppParser(
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
