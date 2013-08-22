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
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class HypmCTDPFDataSetDriver(SimpleDataSetDriver):
    def _build_parser(self, memento):
        pass

    def _build_harvester(self, memento):
        pass
