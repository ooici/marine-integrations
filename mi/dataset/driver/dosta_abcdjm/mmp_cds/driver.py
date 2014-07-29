"""
@package mi.dataset.driver.dosta_abcdjm.mmp_cds.driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/mmp_cds/driver.py
@author Mark Worden
@brief Driver for the dosta_abcdjm_mmp_cds
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.dosta_abcdjm_mmp_cds import DostaAbcdjmMmpCdsParser, DostaAbcdjmMmpCdsParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DostaAbcdjmMmpCdsDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [DostaAbcdjmMmpCdsParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_abcdjm_mmp_cds',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaAbcdjmMmpCdsParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = DostaAbcdjmMmpCdsParser(
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