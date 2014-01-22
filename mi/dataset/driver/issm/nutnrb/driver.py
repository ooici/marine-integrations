"""
@package mi.dataset.driver.issm.nutnrb.driver
@file marine-integrations/mi/dataset/driver/issm/nutnrb/driver.py
@author Roger Unwin
@brief Driver for the CE_ISSM_RI_NUTNR_B
Release notes:

test
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.nutnrb import NutnrbParser, NutnrbDataParticle
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class IssmRiNUTNRBDataSetDriver(SimpleDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [NutnrbDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.nutnrb',
            'particle_class': 'NutnrbDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = NutnrbParser(
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