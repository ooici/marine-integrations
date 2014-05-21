"""
@package mi.dataset.driver.mflm.flort.driver
@file marine-integrations/mi/dataset/driver/mflm/flort/driver.py
@author Emily Hahn
@brief Driver for the mflm_flort
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.driver.mflm.driver import SioMuleDataSetDriver
from mi.dataset.parser.flortd import FlortdParser, FlortdParserDataParticle

class MflmFLORTDDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlortdParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flortd',
            'particle_class': 'FlortdParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = FlortdParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._parser
