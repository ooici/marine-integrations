"""
@package mi.dataset.driver.flord_l_wfp.sio_mule.driver
@file marine-integrations/mi/dataset/driver/flord_l_wfp/sio_mule/driver.py
@author Maria Lutz
@brief Driver for the flord_l_wfp_sio_mule
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_single_driver import SioMuleSingleDataSetDriver
from mi.dataset.parser.flord_l_wfp_sio_mule import FlordLWfpSioMuleParser, FlordLWfpSioMuleParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester, SingleFileHarvester

class FlordLWfpSioMuleDataSetDriver(SioMuleSingleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlordLWfpSioMuleParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flord_l_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordLWfpSioMuleParserDataParticle'
        })
           
        log.debug("My Config: %s", config)
        self._parser = FlordLWfpSioMuleParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback 
        )
        return self._parser

