"""
@package mi.dataset.driver.optaa_dj.dcl.driver
@file marine-integrations/mi/dataset/driver/optaa_dj/dcl/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the optaa_dj_dcl
Release notes:

Initial release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.optaa_dj_dcl import OptaaDjDclParser, OptaaDjDclParserDataParticle

class OptaaDjDclDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [OptaaDjDclParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.optaa_dj_dcl',
            'particle_class': 'OptaaDjDclParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = OptaaDjDclParser(
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
