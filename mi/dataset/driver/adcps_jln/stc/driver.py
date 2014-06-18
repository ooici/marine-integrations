"""
@package mi.dataset.driver.adcps_jln.stc.driver
@file marine-integrations/mi/dataset/driver/adcps_jln/stc/driver.py
@author Maria Lutz
@brief Driver for the adcps_jln_stc
Release notes: Release 0.0.3 Driver modified to incorporate the
recovered data using ADCPS JLN parser to parse bindary PD0 files
modifications done by Jeff Roy jeffrey_a_roy@raytheon.com

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'


from mi.core.common import BaseEnum
from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import ConfigurationException
from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcParser, AdcpsJlnStcInstrumentParserDataParticle
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcMetadataParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

from mi.dataset.parser.adcp_pd0 import AdcpPd0Parser
from mi.dataset.parser.adcps_jln import \
    AdcpsJlnParticle


class DataTypeKey(BaseEnum):
    ADCPS_JLN_STC = 'adcps_jln_stc'
    ADCPS_JLN = 'adcps_jln'


class AdcpsJlnStcDataSetDriver(MultipleHarvesterDataSetDriver):
    
    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        super(AdcpsJlnStcDataSetDriver, self).__init__(config, memento, data_callback,
                                                       state_callback, event_callback,
                                                       exception_callback, data_keys)

    @classmethod
    def stream_config(cls):
        return [AdcpsJlnStcInstrumentParserDataParticle.type(),
                AdcpsJlnStcMetadataParserDataParticle.type(),
                AdcpsJlnParticle.type()]

    def _build_parser(self, parser_state, file_handle, data_key=None):

        # configure the parser based on the data_key
        if data_key == DataTypeKey.ADCPS_JLN_STC:
            config = self._parser_config.get(data_key)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps_jln_stc',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsJlnStcInstrumentParserDataParticle'
            })

            parser = AdcpsJlnStcParser(config, parser_state, file_handle,
                                       lambda state, ingested:
                                       self._save_parser_state(state, data_key, ingested),
                                       self._data_callback, self._sample_exception_callback)

        elif data_key == DataTypeKey.ADCPS_JLN:
            config = self._parser_config.get(data_key)
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps_jln',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsJlnParticle'
            })

            parser = AdcpPd0Parser(config, parser_state, file_handle,
                                   lambda state, ingested:
                                   self._save_parser_state(state, data_key, ingested),
                                   self._data_callback, self._sample_exception_callback)

        else:  # if we don't get a valid data_key raise exception
            log.warn('Parser got bad configuration DataTypeKey')
            raise ConfigurationException

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        harvesters = []

        instrument_harvester = self.build_single_harvester(
            driver_state,
            DataTypeKey.ADCPS_JLN_STC)
        if instrument_harvester is not None:
            harvesters.append(instrument_harvester)

        recovered_harvester = self.build_single_harvester(
            driver_state,
            DataTypeKey.ADCPS_JLN)
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

