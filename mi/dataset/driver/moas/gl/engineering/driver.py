"""
@package mi.dataset.driver.moas.gl.engineering.driver
@file marine-integrations/mi/dataset/driver/moas/gl/engineering/driver.py
@author Stuart Pearce & Chris Wingard
@brief Driver for the glider Engineering
Release notes:

initial release
"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.glider import GliderEngineeringParser
from mi.dataset.parser.glider import EngineeringTelemeteredDataParticle
from mi.dataset.parser.glider import EngineeringScienceTelemeteredDataParticle
from mi.dataset.parser.glider import EngineeringMetadataDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class EngineeringDataSetDriver(SimpleDataSetDriver):
    @classmethod
    def stream_config(cls):
        return [EngineeringTelemeteredDataParticle.type(),
                EngineeringScienceTelemeteredDataParticle.type(),
                EngineeringMetadataDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.glider',
            'particle_class': ['EngineeringTelemeteredDataParticle',
                               'EngineeringScienceTelemeteredDataParticle',
                               'EngineeringMetdataDataParticle']
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = GliderEngineeringParser(
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