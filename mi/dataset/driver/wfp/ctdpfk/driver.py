"""
@package mi.dataset.driver.wfp.ctd.driver
@file marine-integrations/mi/dataset/driver/wfp/ctd/driver.py
@author Bill French
@author Roger Unwin
@brief Driver for the hypm/ctd
Release notes:

initial release
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.ctdpfk import CtdpfkParser
from mi.dataset.parser.ctdpfk import CtdpfkParserDataParticle
from mi.dataset.harvester import AdditiveSequentialModifyingFileHarvester


class WfpCTDPFKDataSetDriver(SimpleDataSetDriver):
    @classmethod
    def stream_config(cls):
        return [CtdpfkParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdpfk',
            'particle_class': 'CtdpfkParserDataParticle'
        })

        self._parser = CtdpfkParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback
        )

        return self._parser

    def _build_harvester(self, harvester_state):
        self._harvester = AdditiveSequentialModifyingFileHarvester(
            self._harvester_config,
            harvester_state,
            self._new_file_callback,
            self._exception_callback,
            self._file_preprocessing_callback
        )

        return self._harvester

    def _file_preprocessing_callback(self, raw_file_name):
        """
        Take an open file handle, read its contents and create a new file 
        that has been re-arranged into a better contents order. 
        return the open file handle for the new file.
        """

        processed_file = raw_file_name + "P"

        with open(raw_file_name,'rb') as raw_file:
            with open(processed_file, 'w') as f:
                for line in raw_file:
                    if "CTD turned" in line:
                        f.write(line)
                raw_file.seek(0)
                for line in raw_file:
                    if "CTD turned" not in line:
                        f.write(line)

        return processed_file
