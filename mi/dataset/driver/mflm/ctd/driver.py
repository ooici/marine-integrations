"""
@package mi.dataset.driver.mflm.ctd.driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Driver for the mflm_ctd
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.ctdmo import CtdmoParser
from mi.dataset.harvester import AdditiveSequentialFileHarvester


class MflmCTDMODataSetDriver(SimpleDataSetDriver):
    def _build_parser(self, parser_state, infile):
        self._parser = CtdmoParser(
            self._parser_config,
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
