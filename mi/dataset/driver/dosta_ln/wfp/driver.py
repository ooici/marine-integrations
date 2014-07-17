"""
@package mi.dataset.driver.dosta_ln.wfp.driver
@file marine-integrations/mi/dataset/driver/dosta_ln/wfp/driver.py
@author Mark Worden
@brief Driver for the dosta_ln_wfp
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.dosta_ln_wfp import DostaLnWfpParser, DostaLnWfpInstrumentParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester


class DostaLnWfpDataSetDriver(SimpleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        super(DostaLnWfpDataSetDriver, self).__init__(config,
                                                      memento,
                                                      data_callback,
                                                      state_callback,
                                                      event_callback,
                                                      exception_callback)

        self._parser = None

    @classmethod
    def stream_config(cls):
        return [DostaLnWfpInstrumentParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.dosta_ln_wfp',
            'particle_class': 'DostaLnWfpInstrumentParserDataParticle'
        })
        log.info("My Config: %s", config)
        self._parser = DostaLnWfpParser(
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
