"""
@package mi.dataset.driver.flntu_x.mmps_cds.driver
@file marine-integrations/mi/dataset/driver/flntu_x/mmp_cds/driver.py
@author Jeremy Amundson
Release notes:

initial release

This driver contains both the flntu_x_mmps_cds parser and the flcdr_x_mmp_cds
parser
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger; log = get_logger()
from mi.core.exceptions import ConfigurationException
from mi.core.common import BaseEnum

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.flntu_x_mmp_cds import FlntuXMmpCdsParser,\
                                              FlntuXMmpCdsParserDataParticle
from mi.dataset.parser.flcdr_x_mmp_cds import FlcdrXMmpCdsParser,\
                                              FlcdrXMmpCdsParserDataParticle

from mi.dataset.harvester import SingleDirectoryHarvester


class DataParticleType(BaseEnum):
    FLNTU_X_MMP_CDS_INSTRUMENT = 'flntu_x_mmp_cds_instrument'
    FLCDR_X_MMP_CDS_INSTRUMENT = 'flcdr_x_mmp_cds_instrument'


class FlntuXMmpCdsDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataParticleType.list()

        super(FlntuXMmpCdsDataSetDriver, self).__init__(config, memento, data_callback,
                                                                 state_callback, event_callback,
                                                                 exception_callback, data_keys)
    @classmethod
    def stream_config(cls):
        return [FlntuXMmpCdsParserDataParticle.type(),
                FlcdrXMmpCdsParserDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the parser
        """

        parser = None

        if data_key == DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT:

            config = self._parser_config.get(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flntu_x_mmp_cds',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlntuXMmpCdsParserDataParticle'
            })

            log.debug("My Config: %s", config)
            parser = FlntuXMmpCdsParser(
                config,
                parser_state,
                infile,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback
            )

        elif data_key == DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT:

            config = self._parser_config.get(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flcdr_x_mmp_cds',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlcdrXMmpCdsParserDataParticle'
            })


            log.debug("My Config: %s", config)
            parser = FlcdrXMmpCdsParser(
                config,
                parser_state,
                infile,
                lambda state, ingested:
                     self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback
            )
        else:
            raise ConfigurationException('flntu/flcdr parser not built due to missing key')
        if parser is None:
            raise ConfigurationException('flntu/flcdr parser not built due to failed instantiation')
        return parser

    def _build_harvester(self, driver_state):

        harvesters = []

        flntu_harvester = self.build_single_harvester(
                                    driver_state,
                                    DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT)
        if flntu_harvester is not None:
            harvesters.append(flntu_harvester)

        flcdr_harvester = self.build_single_harvester(
                                   driver_state,
                                   DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT)
        if flcdr_harvester is not None:
            harvesters.append(flcdr_harvester)

        return harvesters

    def build_single_harvester(self, driver_state, key):
        """
        Build and return the harvester
        """
        if key in self._harvester_config:
                harvester = SingleDirectoryHarvester(
                self._harvester_config.get(key),
                driver_state[key],
                lambda filename: self._new_file_callback(filename, key),
                lambda modified: self._modified_file_callback(modified, key),
                self._exception_callback)
        else:
            harvester = None
            log.warn('flntu/flcdr harvester not built because missing config')
        return harvester
