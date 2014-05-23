"""
@package mi.dataset.driver.adcps_jln.stc.driver
@file marine-integrations/mi/dataset/driver/adcps_jln/stc/driver.py
@author Maria Lutz
@brief Driver for the adcps_jln_stc
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcParser, AdcpsJlnStcInstrumentParserDataParticle
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcMetadataParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class AdcpsJlnStcDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [AdcpsJlnStcInstrumentParserDataParticle.type(),
                AdcpsJlnStcMetadataParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.adcps_jln_stc',
            'particle_class': ['AdcpsJlnStcInstrumentParserDataParticle',
                               'AdcpsJlnStcMetadataParserDataParticle']
        })
        log.debug("My Config: %s", config)
        self._parser = AdcpsJlnStcParser(
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
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )      
        return self._harvester
