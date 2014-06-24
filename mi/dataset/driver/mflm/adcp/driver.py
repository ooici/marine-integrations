"""
@package mi.dataset.driver.mflm.adcp.driver
@file marine-integrations/mi/dataset/driver/mflm/adcp/driver.py
@author Emily Hahn
@brief Driver for the mflm_adcp
Release notes:

Initial version.
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.core.log import get_logger
log = get_logger()

from mi.dataset.harvester import SingleFileHarvester, SingleDirectoryHarvester
from mi.dataset.dataset_driver import HarvesterType, DataSetDriverConfigKeys
from mi.dataset.driver.sio_mule.sio_mule_driver import SioMuleDataSetDriver
from mi.dataset.parser.adcps import AdcpsParser, AdcpsParserDataParticle
from mi.dataset.parser.adcp_pd0 import AdcpPd0Parser
from mi.dataset.parser.adcps_jln import AdcpsJlnParticle


class DataSourceKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    ADCPS_JLN_SIO_MULE = 'adcps_jln_sio_mule'
    ADCPS_JLN = 'adcps_jln'

class MflmADCPSDataSetDriver(SioMuleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [AdcpsParserDataParticle.type(),
                AdcpsJlnParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = DataSourceKey.list()

        # link the data keys to the harvester type, multiple or single file harvester
        harvester_type = {DataSourceKey.ADCPS_JLN_SIO_MULE: HarvesterType.SINGLE_FILE,
                          DataSourceKey.ADCPS_JLN: HarvesterType.SINGLE_DIRECTORY}

        super(MflmADCPSDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys, harvester_type=harvester_type)

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param data_key Key to determine which parser type is built
        """
        if data_key == DataSourceKey.ADCPS_JLN_SIO_MULE:
            parser = self._build_telemetered_parser(parser_state, stream_in)
        elif data_key == DataSourceKey.ADCPS_JLN:
            parser = self._build_recovered_parser(parser_state, stream_in)
        else:
            raise ConfigurationException("Invalid data source key %s" % data_key)
        return parser

    def _build_telemetered_parser(self, parser_state, infile):
        """
        Build and return the telemetered parser
        @param parser_state starting parser state to pass to parser
        @param infile Handle of open file to pass to parser
        """
        config = self._parser_config.get(DataSourceKey.ADCPS_JLN_SIO_MULE)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        parser = AdcpsParser(
            config,
            parser_state,
            infile,
            lambda state: self._save_parser_state(state, DataSourceKey.ADCPS_JLN_SIO_MULE),
            self._data_callback,
            self._sample_exception_callback
        )
        return parser

    def _build_recovered_parser(self, parser_state, infile):
        """
        Build and return the recovered parser
        @param parser_state starting parser state to pass to parser
        @param infile Handle of open file to pass to parser
        """

        config = self._parser_config.get(DataSourceKey.ADCPS_JLN)
        config.update({
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps_jln',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsJlnParticle'
        })

        log.debug("MYCONFIG: %s", config)

        parser = AdcpPd0Parser(config, parser_state, infile,
                               lambda state, ingested:
                               self._save_parser_state(state, DataSourceKey.ADCPS_JLN, ingested),
                               self._data_callback, self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build the harvesters
        @param driver_state The starting driver state
        """
        harvesters = []
        if DataSourceKey.ADCPS_JLN_SIO_MULE in self._harvester_config:
            telem_harvester = SingleFileHarvester(
                self._harvester_config.get(DataSourceKey.ADCPS_JLN_SIO_MULE),
                driver_state[DataSourceKey.ADCPS_JLN_SIO_MULE],
                lambda file_state: self._file_changed_callback(file_state, DataSourceKey.ADCPS_JLN_SIO_MULE),
                self._exception_callback
            )
            harvesters.append(telem_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.ADCPS_JLN_SIO_MULE)

        if DataSourceKey.ADCPS_JLN in self._harvester_config:

            recov_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.ADCPS_JLN),
                driver_state[DataSourceKey.ADCPS_JLN],
                lambda filename: self._new_file_callback(filename, DataSourceKey.ADCPS_JLN),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.ADCPS_JLN),
                self._exception_callback)

            harvesters.append(recov_harvester)
        else:
            log.warn('No configuration for %s harvester, not building', DataSourceKey.ADCPS_JLN)

        return harvesters


