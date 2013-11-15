"""
@package mi.dataset.driver.hypm.ctd.driver
@file marine-integrations/mi/dataset/driver/wfp/vel3dk/driver.py
@author Bill French
@author Roger Unwin
@brief Driver for the wfp/vel3d-k
Release notes:

initial release
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.vel3dk import Vel3dkParser
from mi.dataset.parser.vel3dk import Vel3dkParserDataParticle
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class WfpVEL3DKDataSetDriver(SimpleDataSetDriver):
    @classmethod
    def stream_config(cls):
        return [Vel3dkParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.vel3dk',
            'particle_class': 'Vel3dkParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = Vel3dkParser(
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

