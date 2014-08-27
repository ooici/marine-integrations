"""
@package mi.dataset.driver.flord_l.wfp.driver
@file marine-integrations/mi/dataset/driver/flord_l/wfp/driver.py
@author Joe Padula
@brief Driver for the flord_l_wfp
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.flord_l_wfp import FlordLWfpInstrumentParserDataParticle
from mi.dataset.parser.global_wfp_e_file_parser import GlobalWfpEFileParser


class FlordLWfpDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlordLWfpInstrumentParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.flord_l_wfp',
            'particle_class': 'FlordLWfpInstrumentParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = GlobalWfpEFileParser(
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
