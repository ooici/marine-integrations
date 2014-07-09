"""
@package mi.dataset.driver.dosta_abcdjm.cspp.driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/cspp/driver.py
@author Mark Worden
@brief Driver for the dosta_abcdjm_cspp
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.dosta_abcdjm_cspp import DostaAbcdjmCsppParser, \
    DostaAbcdjmCsppInstrumentRecoveredDataParticle, DostaAbcdjmCsppInstrumentTelemeteredDataParticle, \
    DostaAbcdjmCsppMetadataRecoveredDataParticle, DostaAbcdjmCsppMetadataTelemeteredDataParticle


class DataTypeKey(BaseEnum):
    DOSTA_ABCDJM_CSPP_RECOVERED = 'dosta_abcdjm_cspp_recovered'
    DOSTA_ABCDJM_CSPP_TELEMETERED = 'dosta_abcdjm_cspp_telemetered'


class DostaAbcdjmCsppDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [DostaAbcdjmCsppInstrumentRecoveredDataParticle.type(),
                DostaAbcdjmCsppInstrumentTelemeteredDataParticle.type(),
                DostaAbcdjmCsppMetadataRecoveredDataParticle.type(),
                DostaAbcdjmCsppMetadataTelemeteredDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.dosta_abcdjm_cspp',
            'particle_class': 'DostaAbcdjmCsppParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._parser = DostaAbcdjmCsppParser(
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
        # *** Replace the following with harvester initialization ***
        self._harvester = None     
        return self._harvester
