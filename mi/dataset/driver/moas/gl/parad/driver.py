"""
@package mi.dataset.driver.moas.gl.parad.driver
@file marine-integrations/mi/dataset/driver/moas/gl/parad/driver.py
@author Nick Almonte
@brief Driver for the glider PARAD
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
from mi.dataset.parser.glider import ParadTelemeteredDataParticle, ParadRecoveredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType, DataSetDriverConfigKeys

class DataTypeKey(BaseEnum):
    PARAD_TELEMETERED = 'parad_telemetered'
    PARAD_RECOVERED = 'parad_recovered'

class PARADDataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [ParadTelemeteredDataParticle.type(),
                ParadRecoveredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.PARAD_TELEMETERED, DataTypeKey.PARAD_RECOVERED]

        harvester_type = {DataTypeKey.PARAD_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
                          DataTypeKey.PARAD_RECOVERED: HarvesterType.SINGLE_DIRECTORY}

        super(PARADDataSetDriver, self).__init__(config, memento, data_callback,
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

        if data_key == DataTypeKey.PARAD_TELEMETERED:
            parser = self._build_parad_telemetered_parser(parser_state, infile, data_key)

        elif data_key == DataTypeKey.PARAD_RECOVERED:
            parser = self._build_parad_recovered_parser(parser_state, infile, data_key)
        else:
            raise ConfigurationException("Parser Configuration incorrect, invalid key: %s" % data_key)

        return parser

    def _build_parad_telemetered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ParadTelemeteredDataParticle'
        })

        parser = GliderParser(config,
                              parser_state,
                              infile,
                              lambda state, ingested: self._save_parser_state(state, data_key, ingested),
                              self._data_callback,
                              self._sample_exception_callback)

        return parser

    def _build_parad_recovered_parser(self, parser_state, infile, data_key):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        config = self._parser_config

        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ParadRecoveredDataParticle'
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

        harvester_telem = self._build_single_dir_harvester(driver_state, DataTypeKey.PARAD_TELEMETERED)
        if harvester_telem is not None:
            harvesters.append(harvester_telem)

        harvester_recov = self._build_single_dir_harvester(driver_state, DataTypeKey.PARAD_RECOVERED)
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
