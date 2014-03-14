"""
@package mi.dataset.driver.RTE.STC.driver
@file marine-integrations/mi/dataset/driver/RTE/STC/driver.py
@author Jeff Roy
@brief Driver for the RTE_xx__stc
Release notes:

Initial Release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.rte_xx__stc import Rte_xx__stcParser, Rte_xx__stcParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class RTE_xx__stc_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Rte_xx__stcParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.rte_xx__stc',
            'particle_class': 'Rte_xx__stcParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Rte_xx__stcParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
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

