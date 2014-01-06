"""
@package mi.dataset.driver.issmcnsm.flort.driver
@file marine-integrations/mi/dataset/driver/issmcnsm/flort/driver.py
@author Emily Hahn
@brief Driver for the issmcnsm_flort
Release notes:

Initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.issmcnsm_flortd import Issmcnsm_flortdParser, Issmcnsm_flortdParserDataParticle
from mi.dataset.harvester import AdditiveSequentialFileHarvester

class IssmCnsmFLORTDDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Issmcnsm_flortdParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.issmcnsm_flortd',
            'particle_class': 'Issmcnsm_flortdParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Issmcnsm_flortdParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback
        )
        return self._parser

    def _build_harvester(self, harvester_state):
        """
        Build and return the harvester
        """
        self._harvester = AdditiveSequentialFileHarvester(
            self._harvester_config,
            harvester_state,
            self._new_file_callback,
            self._exception_callback
        )         
        return self._harvester
