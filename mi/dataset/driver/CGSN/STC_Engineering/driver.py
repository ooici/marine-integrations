"""
@package mi.dataset.driver.CGSN.STC_Engineering.driver
@file marine-integrations/mi/dataset/driver/CGSN/STC_Engineering/driver.py
@author Mike Nicoletti
@brief Driver for the CG_STC_ENG__STC
Release notes:

Starting the CG_STC_ENG__STC driver
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.cg_stc_eng__stc import Cg_stc_eng__stcParser, Cg_stc_eng__stcParserDataParticle

class CGSN_STC_Engineering_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Cg_stc_eng__stcParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.cg_stc_eng__stc',
            'particle_class': 'Cg_stc_eng__stcParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = Cg_stc_eng__stcParser(
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
