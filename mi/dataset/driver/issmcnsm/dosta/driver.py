"""
@package mi.dataset.driver.issmcnsm.dosta.driver
@file marine-integrations/mi/dataset/driver/issmcnsm/dosta/driver.py
@author Emily Hahn
@brief Driver for the issmcnsm_dosta
Release notes:

Initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.issmcnsm_dostad import Issmcnsm_dostadParser, Issmcnsm_dostadParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class IssmCnsmDOSTADDataSetDriver(SimpleDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [Issmcnsm_dostadParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.issmcnsm_dostad',
            'particle_class': 'Issmcnsm_dostadParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Issmcnsm_dostadParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback
        )
        return self._parser

    def _build_harvester(self, driver_state, file_mod_wait_time):
        """
        Build and return the harvester
        """
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            file_mod_wait_time,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )
        return self._harvester
