"""
@package mi.dataset.driver.moas.gl.adcpa.driver
@file marine-integrations/mi/dataset/driver/moas/gl/adcpa/driver.py
@author Jeff Roy
@brief Driver for the glider adcpa
Release notes:

initial release
"""
__author__ = 'Jeff Roy (Raytheon)'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.adcp_pd0 import AdcpPd0Parser
from mi.dataset.parser.adcpa_m_glider import \
    AdcpaMGliderInstrumentParticle, \
    AdcpaMGliderRecoveredParticle

from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    ADCPA_INSTRUMENT = 'adcpa_instrument'
    ADCPA_RECOVERED = 'adcpa_recovered'


class AdcpaDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        super(AdcpaDataSetDriver, self).__init__(config, memento, data_callback,
                                                 state_callback, event_callback,
                                                 exception_callback, data_keys)

    @classmethod
    def stream_config(cls):
        return [AdcpaMGliderInstrumentParticle.type(),
                AdcpaMGliderRecoveredParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):

        # configure the parser based on the data_key
        if data_key == DataTypeKey.ADCPA_INSTRUMENT:
            config = self._parser_config.get(data_key)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa_m_glider',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpaMGliderInstrumentParticle'
            })

        elif data_key == DataTypeKey.ADCPA_RECOVERED:
            config = self._parser_config.get(data_key)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa_m_glider',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpaMGliderRecoveredParticle'
            })

        else:  # if we don't get a valid data_key raise exception
            log.warn('Parser got bad configuration DataTypeKey')
            raise ConfigurationException
            return None

        parser = AdcpPd0Parser(config, parser_state, file_handle,
                               lambda state, ingested:
                               self._save_parser_state(state, data_key, ingested),
                               self._data_callback, self._sample_exception_callback)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        harvesters = []

        instrument_harvester = self.build_single_harvester(
                                    driver_state,
                                    DataTypeKey.ADCPA_INSTRUMENT)
        if instrument_harvester is not None:
            harvesters.append(instrument_harvester)

        recovered_harvester = self.build_single_harvester(
                                   driver_state,
                                   DataTypeKey.ADCPA_RECOVERED)
        if recovered_harvester is not None:
            harvesters.append(recovered_harvester)

        return harvesters

    def build_single_harvester(self, driver_state, key):

        if key in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(key),
                driver_state[key],
                lambda filename: self._new_file_callback(filename, key),
                lambda modified: self._modified_file_callback(modified, key),
                self._exception_callback)
        else:
            harvester = None

        return harvester
