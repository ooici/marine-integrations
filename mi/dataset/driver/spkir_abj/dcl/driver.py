"""
@package mi.dataset.driver.spkir_abj.dcl.driver
@file marine-integrations/mi/dataset/driver/spkir_abj/dcl/driver.py
@author Steve Myerson
@brief Driver for the spkir_abj_dcl
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson'
__license__ = 'Apache 2.0'


from mi.core.common import BaseEnum
from mi.core.exceptions import ConfigurationException
from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_driver import \
    DataSetDriverConfigKeys, \
    HarvesterType, \
    MultipleHarvesterDataSetDriver

from mi.dataset.harvester import \
    SingleDirectoryHarvester

from mi.dataset.parser.spkir_abj_dcl import \
    SpkirAbjDclRecoveredParser, \
    SpkirAbjDclTelemeteredParser, \
    SpkirAbjDclRecoveredInstrumentDataParticle, \
    SpkirAbjDclTelemeteredInstrumentDataParticle


class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    SPKIR_ABJ_RECOVERED = 'spkir_abcdjm_dcl_recovered'
    SPKIR_ABJ_TELEMETERED = 'spkir_abcdjm_dcl_telemetered'


class SpkirAbjDclDataSetDriver(MultipleHarvesterDataSetDriver):
    
    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        # Initialize the possible types of harvester/parser pairs
        # for this driver.

        data_keys = DataTypeKey.list()

        # Link the data keys to the harvester type.
        # Recovered harvester is single directory.
        # Telemetered harvester is single directory.

        harvester_type = {
            DataTypeKey.SPKIR_ABJ_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.SPKIR_ABJ_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
        }

        super(SpkirAbjDclDataSetDriver, self).__init__(config, memento,
            data_callback, state_callback, event_callback,
            exception_callback, data_keys, harvester_type=harvester_type)
    
    @classmethod
    def stream_config(cls):
        return [
            SpkirAbjDclRecoveredInstrumentDataParticle.type(),
            SpkirAbjDclTelemeteredInstrumentDataParticle.type()
        ]

    def _build_harvester(self, driver_state):
        """
        Build the harvesters.
        Verify correctness of data keys.
        Display warnings if error detected in data keys.
        @param driver_state The starting driver state
        """
        harvesters = []

        # Verify that the Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.

        if DataTypeKey.SPKIR_ABJ_RECOVERED in self._harvester_config:
            rec_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.SPKIR_ABJ_RECOVERED),
               driver_state[DataTypeKey.SPKIR_ABJ_RECOVERED],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.SPKIR_ABJ_RECOVERED),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.SPKIR_ABJ_RECOVERED),
               self._exception_callback)

            harvesters.append(rec_harvester)

        else:
            log.warn('No configuration for spkir_abj_dcl recovered harvester, not building')

        # Verify that the Telemetered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.

        if DataTypeKey.SPKIR_ABJ_TELEMETERED in self._harvester_config:
            tel_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.SPKIR_ABJ_TELEMETERED),
               driver_state[DataTypeKey.SPKIR_ABJ_TELEMETERED],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.SPKIR_ABJ_TELEMETERED),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.SPKIR_ABJ_TELEMETERED),
               self._exception_callback)

            harvesters.append(tel_harvester)

        else:
            log.warn('No configuration for spkir_abj_dcl telemetered harvester, not building')

        return harvesters
    
    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param stream_in Filename string to pass to parser
        @param data_key Key to determine which parser type is built
        """

        # Build the recovered parser if requested.

        if data_key == DataTypeKey.SPKIR_ABJ_RECOVERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.spkir_abj_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    None
            })

            parser = SpkirAbjDclRecoveredParser(
                config,
                stream_in,
                parser_state,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        # Build the telemetered parser if requested.

        elif data_key == DataTypeKey.SPKIR_ABJ_TELEMETERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.spkir_abj_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    None
            })

            parser = SpkirAbjDclTelemeteredParser(
                config,
                stream_in,
                parser_state,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        # Not one of the keys we recognize?
        # No parser for you!

        else:
            raise ConfigurationException('Spkir_abj Parser configuration incorrect %s',
                                         data_key)

        return parser