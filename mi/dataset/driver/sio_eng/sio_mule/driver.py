"""
@package mi.dataset.driver.sio_eng.sio_mule.driver
@file marine-integrations/mi/dataset/driver/sio_eng/sio_mule/driver.py
@author Mike Nicoletti
@brief Driver for the sio_eng_sio_mule
Release notes:

Starting SIO Engineering Driver
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.sio_eng_sio_mule import SioEngSioMuleParser, SioEngSioMuleParserDataParticle

class sioEngSioMuleDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [SioEngSioMuleParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.sio_eng_sio_mule',
            'particle_class': 'SioEngSioMuleParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = SioEngSioMuleParser(
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
