"""
@package mi.dataset.driver.ADCPS_JLN.stc_imodem.driver
@file marine-integrations/mi/dataset/driver/ADCPS_JLN/stc_imodem/driver.py
@author Maria Lutz
@brief Driver for the ADCPS_JLN_stc
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.adcps_jln_stc import Adcps_jln_stcParser, Adcps_jln_stc_instrumentParserDataParticle, Adcps_jln_stc_metadataParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class ADCPS_JLN_stc_DataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Adcps_jln_stc_instrumentParserDataParticle.type(), Adcps_jln_stc_metadataParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.adcps_jln_stc',
            'particle_class': ['Adcps_jln_stc_instrumentParserDataParticle', 'Adcps_jln_stc_metadataParserDataParticle']
        })
        log.debug("My Config: %s", config)
        self._parser = Adcps_jln_stcParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        ) #mopak also has 'filename' listed here
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        # *** Replace the following with harvester initialization ***
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )     
        return self._harvester
