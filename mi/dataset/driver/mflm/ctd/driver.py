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


from mi.core.log import get_logger ; log = get_logger()
from mi.dataset.driver.mflm.driver import MflmDataSetDriver
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle


class MflmCTDMODataSetDriver(MflmDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [CtdmoParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdmo',
            'particle_class': 'CtdmoParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = CtdmoParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )

        return self._parser
