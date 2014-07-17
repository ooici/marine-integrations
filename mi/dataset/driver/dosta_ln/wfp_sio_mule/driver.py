"""
@package mi.dataset.driver.dosta_ln.wfp_sio_mule.driver
@file marine-integrations/mi/dataset/driver/dosta_ln/wfp_sio_mule/driver.py
@author Christopher Fortin
@brief Driver for the dosta_ln_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'Christopher Fortin'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.driver.sio_mule.sio_mule_single_driver import SioMuleSingleDataSetDriver
from mi.dataset.parser.dosta_ln_wfp_sio_mule import DostaLnWfpSioMuleParser, DostaLnWfpSioMuleParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester, SingleFileHarvester
from mi.dataset.dataset_driver import DataSetDriverConfigKeys


class DostaLnWfpSioMuleDataSetDriver(SioMuleSingleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        # Fill in below with particle stream
        return [DostaLnWfpSioMuleParserDataParticle.type()]

    def _build_parser(self, parser_state, stream_in):
        """
        Build and return the parser
        """
        config = self._parser_config
        # Fill in blanks with particle info
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_ln_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaLnWfpSioMuleParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = DostaLnWfpSioMuleParser(
            config,
            parser_state,
            stream_in,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._parser

