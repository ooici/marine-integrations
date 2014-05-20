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
from mi.dataset.parser.glider import GliderParser
from mi.dataset.parser.glider import DostaTelemeteredDataParticle
from mi.dataset.parser.glider import DostaRecoveredDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, HarvesterType

class DataTypeKey(BaseEnum):
    GLIDER_TELEMETERED = 'glider_telemetered'
    GLIDER_RECOVERED = 'glider_recovered'


class DOSTADataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = [DataTypeKey.GLIDER_TELEMETERED, DataTypeKey.GLIDER_RECOVERED]
        harvester_type = {DataTypeKey.GLIDER_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
                          DataTypeKey.GLIDER_RECOVERED: HarvesterType.SINGLE_DIRECTORY}

        super(DOSTADataSetDriver, self).__init__(config, memento, data_callback,
                                                 state_callback, event_callback,
                                                 exception_callback, data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [DostaTelemeteredDataParticle.type(),
                DostaRecoveredDataParticle.type()]

    # def _build_parser(self, parser_state, infile, data_key=None):
    #     """
    #     Build and return the specified parser as indicated by the data_key.
    #     """
    #     config = self._parser_config
    #
    #     config.update({
    #         'particle_module': 'mi.dataset.parser.glider',
    #         'particle_class': ['DostaTelemeteredDataParticle',
    #                            'DostaRecoveredDataParticle']
    #     })
    #
    #     log.debug("MYCONFIG: %s", config)
    #
    #     self._parser = GliderParser(config,
    #                                 parser_state,
    #                                 infile,
    #                                 lambda state, ingested: self._save_parser_state(state, data_key, ingested),
    #                                 self._data_callback,
    #                                 self._sample_exception_callback)
    #
    #     return self._parser
    #
    # def _build_harvester(self, driver_state):
    #     """
    #     Build and return the list of harvesters
    #     """
    #     harvesters = []
    #
    #     harvester_telem = self._build_single_dir_harvester(driver_state, DataTypeKey.DOSTA_TELEMETERED)
    #     if harvester_telem is not None:
    #         harvesters.append(harvester_telem)
    #
    #     harvester_recov = self._build_single_dir_harvester(driver_state, DataTypeKey.DOSTA_RECOVERED)
    #     if harvester_recov is not None:
    #         harvesters.append(harvester_recov)
    #
    #     return harvesters
    #
    # def _build_single_dir_harvester(self, driver_state, data_key):
    #     """
    #     Build and return a harvester
    #     """
    #     harvester = None
    #     if data_key in self._harvester_config:
    #
    #         harvester = SingleDirectoryHarvester(self._harvester_config.get(data_key),
    #                                              driver_state[data_key],
    #                                              lambda filename: self._new_file_callback(filename, data_key),
    #                                              lambda modified: self._modified_file_callback(modified, data_key),
    #                                              self._exception_callback)
    #     else:
    #         log.warn('No configuration for %s harvester, not building', data_key)
    #
    #     return harvester