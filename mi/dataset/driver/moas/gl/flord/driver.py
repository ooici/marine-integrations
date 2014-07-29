"""
@package mi.dataset.driver.moas.gl.flord.driver
@file marine-integrations/mi/dataset/driver/moas/gl/flord/driver.py
@author Stuart Pearce & Chris Wingard
@brief Driver for the glider FLORD
Release notes:

initial release
"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.dataset.parser.glider import GliderParser
from mi.dataset.parser.glider import FlordTelemeteredDataParticle, FlordRecoveredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType, DataSetDriverConfigKeys

class DataTypeKey(BaseEnum):
    FLORD_TELEMETERED = 'flord_telemetered'
    FLORD_RECOVERED = 'flord_recovered'

class FLORDDataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [FlordTelemeteredDataParticle.type(),
                FlordRecoveredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.FLORD_TELEMETERED, DataTypeKey.FLORD_RECOVERED]

        harvester_type = {DataTypeKey.FLORD_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
                          DataTypeKey.FLORD_RECOVERED: HarvesterType.SINGLE_DIRECTORY}

        super(FLORDDataSetDriver, self).__init__(config, memento, data_callback,
                                                 state_callback, event_callback,
                                                 exception_callback, data_keys, harvester_type)

    def _build_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        @param parser_state previous parser state to initialize parser with
        @param data_key harvester / parser key
        @param infile file name
        """
        parser = None

        if data_key == DataTypeKey.FLORD_TELEMETERED:
            parser = self._build_flord_telemetered_parser(parser_state, infile, data_key)

        elif data_key == DataTypeKey.FLORD_RECOVERED:
            parser = self._build_flord_recovered_parser(parser_state, infile, data_key)
        else:
            raise ConfigurationException("Parser Configuration incorrect, invalid key: %s" % data_key)

        return parser

    def _build_flord_telemetered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordTelemeteredDataParticle'
        })

        parser = GliderParser(config,
                              parser_state,
                              infile,
                              lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                              self._data_callback,
                              self._sample_exception_callback)

        return parser

    def _build_flord_recovered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordRecoveredDataParticle'
        })

        parser = GliderParser(config,
                              parser_state,
                              infile,
                              lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                              self._data_callback,
                              self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the list of harvesters
        """
        harvesters = []

        harvester_telem = self._build_single_dir_harvester(driver_state, DataTypeKey.FLORD_TELEMETERED)
        if harvester_telem is not None:
            harvesters.append(harvester_telem)

        harvester_recov = self._build_single_dir_harvester(driver_state, DataTypeKey.FLORD_RECOVERED)
        if harvester_recov is not None:
            harvesters.append(harvester_recov)

        return harvesters

    def _build_single_dir_harvester(self, driver_state, data_key):
        """
        Build and return a harvester
        """
        harvester = None
        if data_key in self._harvester_config:

            harvester = SingleDirectoryHarvester(self._harvester_config.get(data_key),
                                                 driver_state[data_key],
                                                 lambda filename: self._new_file_callback(filename, data_key),
                                                 lambda modified: self._modified_file_callback(modified, data_key),
                                                 self._exception_callback)
        else:
            log.warn('No configuration for %s harvester, not building', data_key)

        return harvester