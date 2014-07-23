"""
@package mi.dataset.driver.mflm.flort.driver
@file marine-integrations/mi/dataset/driver/mflm/flort/driver.py
@author Emily Hahn
@brief Driver for the mflm_flort
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.harvester import SingleFileHarvester, SingleDirectoryHarvester
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.dataset_driver import HarvesterType
from mi.dataset.parser.flortd import FlortdParser, FlortdRecoveredParser, \
                                     FlortdParserDataParticle, \
                                     FlortdRecoveredParserDataParticle

class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    FLORT_DJ_SIO_TELEMETERED = 'flort_dj_sio_telemetered'
    FLORT_DJ_SIO_RECOVERED = 'flort_dj_sio_recovered'

class MflmFLORTDDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [FlortdParserDataParticle.type(),
                FlortdRecoveredParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):

        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.FLORT_DJ_SIO_TELEMETERED: HarvesterType.SINGLE_FILE,
                          DataSourceKey.FLORT_DJ_SIO_RECOVERED: HarvesterType.SINGLE_DIRECTORY}

        super(MflmFLORTDDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, DataSourceKey.list(), harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """

        if data_key == DataSourceKey.FLORT_DJ_SIO_TELEMETERED:
            config = self._parser_config.get(DataSourceKey.FLORT_DJ_SIO_TELEMETERED)
            config.update({DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
                           DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdParserDataParticle'})
            # build the telemetered parser
            parser = FlortdParser(
                config,
                parser_state,
                stream_in,
                lambda state: self._save_parser_state(state, DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
                self._data_callback,
                self._sample_exception_callback
            )

        elif data_key == DataSourceKey.FLORT_DJ_SIO_RECOVERED:
            config = self._parser_config.get(DataSourceKey.FLORT_DJ_SIO_RECOVERED)
            config.update({DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
                           DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdRecoveredParserDataParticle'})
            # build the recovered parser
            parser = FlortdRecoveredParser(
                config,
                parser_state,
                stream_in,
                lambda state, ingested: self._save_parser_state(state, DataSourceKey.FLORT_DJ_SIO_RECOVERED, ingested),
                self._data_callback,
                self._sample_exception_callback
            )

        else:
            raise ConfigurationException('Tried to build parser for unknown data source key %s' % data_key)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.FLORT_DJ_SIO_TELEMETERED in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
                driver_state[DataSourceKey.FLORT_DJ_SIO_TELEMETERED],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.FLORT_DJ_SIO_TELEMETERED),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORT_DJ_SIO_TELEMETERED)

        if DataSourceKey.FLORT_DJ_SIO_RECOVERED in self._harvester_config:
            recov_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.FLORT_DJ_SIO_RECOVERED),
                driver_state[DataSourceKey.FLORT_DJ_SIO_RECOVERED],
                lambda filename: self._new_file_callback(filename, DataSourceKey.FLORT_DJ_SIO_RECOVERED),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.FLORT_DJ_SIO_RECOVERED),
                self._exception_callback
            )
            harvesters.append(recov_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.FLORT_DJ_SIO_RECOVERED)
        return harvesters

