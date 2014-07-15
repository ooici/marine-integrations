"""
@package mi.dataset.driver.vel3d_a.mmp_cds.driver
@file marine-integrations/mi/dataset/driver/vel3d_a/mmp_cds/driver.py
@author Jeremy Amundson
@brief Driver for the vel3d_a_mmp_cds
Release notes:

initial release
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.vel3d_a_mmp_cds import Vel3dAMmpCdsParser, Vel3dAMmpCdsParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.core.exceptions import ConfigurationException


class Vel3dAMmpCdsDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [Vel3dAMmpCdsParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.vel3d_a_mmp_cds',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'Vel3dAMmpCdsParserDataParticle'
        })
        log.debug("My Config: %s", config)
        _parser = Vel3dAMmpCdsParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        if _parser is None:
            raise ConfigurationException('vel3d_a_mmp_cds parser failed instantiation')
        return _parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """

        _harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )
        if _harvester is None:
            log.warn('harverster failed instantiation due to missing config')
        return _harvester