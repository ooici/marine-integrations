"""
@package mi.dataset.driver.vel3d_k.wfp.driver
@file marine-integrations/mi/dataset/driver/vel3d_k/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the vel3d_k_wfp
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.vel3d_k_wfp import Vel3dKWfpParser, Vel3dKWfpParserDataParticle

class Vel3dKWfp(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Vel3dKWfpParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3d_k_wfp',
            'particle_class': 'Vel3dKWfpParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Vel3dKWfpParser(
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
