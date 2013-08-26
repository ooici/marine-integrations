"""
@package mi.dataset.driver.hypm.ctd.driver
@file marine-integrations/mi/dataset/driver/hypm/ctd/driver.py
@author Bill French
@brief Driver for the hypm/ctd
Release notes:

initial release
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.ctdpf import CtdpfParser
from mi.dataset.parser.ctdpf import CtdpfParserDataParticle
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class HypmCTDPFDataSetDriver(SimpleDataSetDriver):
    @classmethod
    def stream_config(cls):
        return [CtdpfParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._harvester_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdpf',
            'particle_class': 'CtdpfParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = CtdpfParser(
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

