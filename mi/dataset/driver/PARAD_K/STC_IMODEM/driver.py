"""
@package mi.dataset.driver.PARAD_K.STC_IMODEM.driver
@file marine-integrations/mi/dataset/driver/PARAD_K/STC_IMODEM/driver.py
@author Mike Nicoletti
@brief Driver for the PARAD_K_STC_IMODEM
Release notes:

New driver started for PARAD_K_STC_IMODEM
"""

__author__ = 'Mike Nicoletti, Steve Myerson (recovered)'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()
from mi.core.exceptions import ConfigurationException

from mi.dataset.dataset_driver import \
    DataSetDriverConfigKeys, \
    HarvesterType, \
    MultipleHarvesterDataSetDriver

from mi.dataset.harvester import \
    SingleDirectoryHarvester

from mi.dataset.parser.parad_k_stc_imodem import \
    Parad_k_stc_imodemParser, \
    Parad_k_stc_imodemRecoveredParser, \
    Parad_k_stc_imodemDataParticle, \
    Parad_k_stc_imodemRecoveredDataParticle


class DataTypeKey(BaseEnum):
    PARAD_K_STC = 'parad_k_stc_imodem'
    PARAD_K_STC_RECOVERED = 'parad_k_stc_imodem_recovered'


class PARAD_K_STC_IMODEM_DataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        data_keys = DataTypeKey.list()

        harvester_type = {
            DataTypeKey.PARAD_K_STC: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.PARAD_K_STC_RECOVERED: HarvesterType.SINGLE_DIRECTORY
        }

        super(PARAD_K_STC_IMODEM_DataSetDriver, self).__init__(config, memento,
            data_callback, state_callback, event_callback, exception_callback,
            data_keys, harvester_type)

    @classmethod
    def stream_config(cls):
        return [Parad_k_stc_imodemDataParticle.type(),
                Parad_k_stc_imodemRecoveredDataParticle.type()]

    def _build_parser(self, parser_state, infile, data_key=None):
        """
        Build and return the specified parser as indicated by the data_key.
        """
        #
        # If the key is PARAD_K_STC, build the telemetered parser.
        #
        if data_key == DataTypeKey.PARAD_K_STC:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.parad_k_stc_imodem',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    'Parad_k_stc_imodemDataParticle'
            })
            log.debug("My Config: %s", config)
            parser = Parad_k_stc_imodemParser(
                config,
                parser_state,
                infile,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is PARAD_K_STC_RECOVERED, build the recovered parser.
        #
        elif data_key == DataTypeKey.PARAD_K_STC_RECOVERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.parad_k_stc_imodem',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    'Parad_k_stc_imodemRecoveredDataParticle'
            })
            log.debug("My Config: %s", config)
            parser = Parad_k_stc_imodemRecoveredParser(
                config,
                parser_state,
                infile,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # If the key is one that we're not expecting, don't build any parser.
        #
        else:
            raise ConfigurationException('Parser configuration incorrect %s',
                                         data_key)

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """

        harvesters = []    # list of harvesters to be returned

        #
        # Verify that the Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.PARAD_K_STC_RECOVERED in self._harvester_config:
            recovered_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.PARAD_K_STC_RECOVERED),
                driver_state[DataTypeKey.PARAD_K_STC_RECOVERED],
                lambda filename:
                    self._new_file_callback(filename, DataTypeKey.PARAD_K_STC_RECOVERED),
                lambda modified:
                    self._modified_file_callback(modified, DataTypeKey.PARAD_K_STC_RECOVERED),
                self._exception_callback)

            if recovered_harvester is not None:
                harvesters.append(recovered_harvester)
            else:
                log.warn('Unable to build Harvester %s',
                         DataTypeKey.PARAD_K_STC_RECOVERED)

        else:
            log.warn('Harvester configuration missing key %s',
                     DataTypeKey.PARAD_K_STC_RECOVERED)

        #
        # Verify that the Telemetered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.PARAD_K_STC in self._harvester_config:
            telemetered_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.PARAD_K_STC),
                driver_state[DataTypeKey.PARAD_K_STC],
                lambda filename:
                    self._new_file_callback(filename, DataTypeKey.PARAD_K_STC),
                lambda modified:
                    self._modified_file_callback(modified, DataTypeKey.PARAD_K_STC),
                self._exception_callback)

            if telemetered_harvester is not None:
                harvesters.append(telemetered_harvester)
            else:
                log.warn('Unable to build Harvester %s',
                         DataTypeKey.PARAD_K_STC)

        else:
            log.warn('Harvester configuration missing key %s',
                     DataTypeKey.PARAD_K_STC)

        return harvesters
