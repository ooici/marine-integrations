"""
@package mi.dataset.driver.mflm.dosta.driver
@file marine-integrations/mi/dataset/driver/mflm/dosta/driver.py
@author Emily Hahn
@brief Driver for the mflm_dosta
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.driver.mflm.driver import SioMuleDataSetDriver
from mi.dataset.parser.dostad import DostadParser, DostadParserDataParticle

class MflmDOSTADDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        # Fill in below with particle stream
        return [DostadParserDataParticle.type()]

    def _build_parser(self, parser_state, stream_in):
        """
        Build and return the parser
        """
        config = self._parser_config
        # Fill in blanks with particle info
        config.update({
            'particle_module': 'mi.dataset.parser.dostad',
            'particle_class': 'DostadParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = DostadParser(
            config,
            parser_state,
            stream_in,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._parser

