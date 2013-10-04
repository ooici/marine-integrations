"""
@package mi.dataset.driver.moas.gl.dosta.driver
@file marine-integrations/mi/dataset/driver/moas/gl/dosta/driver.py
@author Stuart Pearce & Chris Wingard
@brief Driver for the glider DOSTA
Release notes:

initial release
"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.glider import GliderParser
from mi.dataset.parser.glider import GgldrDostaDelayedDataParticle
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class DOSTADataSetDriver(SimpleDataSetDriver):
    @classmethod
    def stream_config(cls):
        return [GgldrDostaDelayedDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.glider',
            'particle_class': 'GgldrDostaDelayedDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = GliderParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback
        )

        return self._parser

    def _build_harvester(self, harvester_state):
        self._harvester = AdditiveSequentialFileHarvester(
            self._harvester_config,
            harvester_state,
            self._new_file_callback,
            self._exception_callback
        )

        return self._harvester

