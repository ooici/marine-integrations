"""
@package mi.dataset.driver.moas.gl.dosta.driver
@file marine-integrations/mi/dataset/driver/moas/gl/dosta/driver.py
@author Stuart Pearce & Chris Wingard
@brief Driver for the glider DOSTA
Release notes:

"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.dataset.parser.glider import GliderParser
from mi.dataset.parser.glider import DostaTelemeteredDataParticle
from mi.dataset.parser.glider import DostaRecoveredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType, DataSetDriverConfigKeys

class DataTypeKey(BaseEnum):
    DOSTA_TELEMETERED = 'dosta_telemetered'
    DOSTA_RECOVERED = 'dosta_recovered'


class DOSTADataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [DostaTelemeteredDataParticle.type(),
                DostaRecoveredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.DOSTA_TELEMETERED, DataTypeKey.DOSTA_RECOVERED]

        harvester_type = {DataTypeKey.DOSTA_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
                          DataTypeKey.DOSTA_RECOVERED: HarvesterType.SINGLE_DIRECTORY}

        super(DOSTADataSetDriver, self).__init__(config, memento, data_callback,
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

        if data_key == DataTypeKey.DOSTA_TELEMETERED:
            parser = self._build_dosta_telemetered_parser(parser_state, infile, data_key)

        elif data_key == DataTypeKey.DOSTA_RECOVERED:
            parser = self._build_dosta_recovered_parser(parser_state, infile, data_key)
        else:
            raise ConfigurationException("Parser Configuration incorrect, invalid key: %s" % data_key)

        return parser

    def _build_dosta_telemetered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaTelemeteredDataParticle'
        })

        parser = GliderParser(config,
                              parser_state,
                              infile,
                              lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                              self._data_callback,
                              self._sample_exception_callback)

        return parser

    def _build_dosta_recovered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostaRecoveredDataParticle'
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

        harvester_telem = self._build_single_dir_harvester(driver_state, DataTypeKey.DOSTA_TELEMETERED)
        if harvester_telem is not None:
            harvesters.append(harvester_telem)

        harvester_recov = self._build_single_dir_harvester(driver_state, DataTypeKey.DOSTA_RECOVERED)
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