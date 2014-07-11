"""
@package mi.dataset.driver.optaa_ac.mmp_cds.driver
@file marine-integrations/mi/dataset/driver/optaa_ac/mmp_cds/driver.py
@author Mark Worden
@brief Driver for the optaa_ac_mmp_cds
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.optaa_ac_mmp_cds import OptaaAcMmpCdsParser, OptaaAcMmpCdsParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class OptaaAcMmpCdsDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [OptaaAcMmpCdsParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.optaa_ac_mmp_cds',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'OptaaAcMmpCdsParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = OptaaAcMmpCdsParser(
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