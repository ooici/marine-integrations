"""
@package mi.dataset.driver.RTE.STC.driver
@file marine-integrations/mi/dataset/driver/RTE/STC/driver.py
@author Jeff Roy
@brief Driver for the rte_o_stc
Release notes:

Initial Release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.rte_o_stc import RteOStcParser, RteOStcParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class RteOStcDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [RteOStcParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        filename = None
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.rte_o_stc',
            'particle_class': 'RteOStcParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = RteOStcParser(
            config,
            parser_state,
            infile,
            filename,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback,
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )
    
        return self._harvester

