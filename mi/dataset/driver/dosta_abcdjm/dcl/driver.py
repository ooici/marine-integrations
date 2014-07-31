"""
@package mi.dataset.driver.dosta_abcdjm.dcl.driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/dcl/driver.py
@author Steve Myerson
@brief Driver for the dosta_abcdjm_dcl
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

from mi.dataset.parser.dosta_abcdjm_dcl import \
    DostaAbcdjmDclRecoveredParser, \
    DostaAbcdjmDclTelemeteredParser, \
    DostaAbcdjmDclRecoveredInstrumentDataParticle, \
    DostaAbcdjmDclTelemeteredInstrumentDataParticle


class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    DOSTA_ABCDJM_RECOVERED = 'dosta_abcdjm_dcl_recovered'
    DOSTA_ABCDJM_TELEMETERED = 'dosta_abcdjm_dcl_telemetered'


class DostaAbcdjmDclDataSetDriver(MultipleHarvesterDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        # Initialize the possible types of harvester/parser pairs
        # for this driver.

        data_keys = DataTypeKey.list()

        # Link the data keys to the harvester type.
        # Recovered harvester is single directory.
        # Telemetered harvester is single directory.

        harvester_type = {
            DataTypeKey.DOSTA_ABCDJM_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.DOSTA_ABCDJM_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
        }

        super(DostaAbcdjmDclDataSetDriver, self).__init__(config, memento,
            data_callback, state_callback, event_callback,
            exception_callback, data_keys, harvester_type=harvester_type)
    
    @classmethod
    def stream_config(cls):
        return [
            DostaAbcdjmDclRecoveredInstrumentDataParticle.type(),
            DostaAbcdjmDclTelemeteredInstrumentDataParticle.type()
        ]

    def _build_harvester(self, driver_state):
        """
        Build the harvesters.
        Verify correctness of data keys.
        Display warnings if error detected in data keys or in the
        creation of the harvesters.
        @param driver_state The starting driver state
        """
        harvesters = []

        # Verify that the Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.

        if DataTypeKey.DOSTA_ABCDJM_RECOVERED in self._harvester_config:
            rec_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_RECOVERED),
               driver_state[DataTypeKey.DOSTA_ABCDJM_RECOVERED],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.DOSTA_ABCDJM_RECOVERED),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.DOSTA_ABCDJM_RECOVERED),
               self._exception_callback)

            harvesters.append(rec_harvester)

        else:
            log.warn('No configuration for dosta_abcdjm_dcl recovered harvester, not building')

        # Verify that the Telemetered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.

        if DataTypeKey.DOSTA_ABCDJM_TELEMETERED in self._harvester_config:
            tel_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.DOSTA_ABCDJM_TELEMETERED),
               driver_state[DataTypeKey.DOSTA_ABCDJM_TELEMETERED],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.DOSTA_ABCDJM_TELEMETERED),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.DOSTA_ABCDJM_TELEMETERED),
               self._exception_callback)

            harvesters.append(tel_harvester)

        else:
            log.warn('No configuration for dosta_abcdjm_dcl telemetered harvester, not building')

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

        if data_key == DataTypeKey.DOSTA_ABCDJM_RECOVERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.dosta_abcdjm_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    None
            })

            parser = DostaAbcdjmDclRecoveredParser(
                config,
                stream_in,
                parser_state,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        # Build the telemetered parser if requested.

        elif data_key == DataTypeKey.DOSTA_ABCDJM_TELEMETERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.dosta_abcdjm_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    None
            })

            parser = DostaAbcdjmDclTelemeteredParser(
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
            raise ConfigurationException('Dosta_abcdjm Parser configuration incorrect %s',
                                         data_key)

        return parser
