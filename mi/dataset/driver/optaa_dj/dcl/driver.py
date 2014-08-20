"""
@package mi.dataset.driver.optaa_dj.dcl.driver
@file marine-integrations/mi/dataset/driver/optaa_dj/dcl/driver.py
@author Steve Myerson (Raytheon)
@brief Driver for the optaa_dj_dcl
Release notes:

Initial release
"""

__author__ = 'Steve Myerson (Raytheon)'
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

from mi.dataset.parser.optaa_dj_dcl import \
    OptaaDjDclRecoveredParser, \
    OptaaDjDclTelemeteredParser, \
    OptaaDjDclRecoveredInstrumentDataParticle, \
    OptaaDjDclTelemeteredInstrumentDataParticle

MODULE_NAME = 'mi.dataset.parser.optaa_dj_dcl'


class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    OPTAA_DJ_RECOVERED = 'optaa_dj_dcl_recovered'
    OPTAA_DJ_TELEMETERED = 'optaa_dj_dcl_telemetered'


class OptaaDjDclDataSetDriver(MultipleHarvesterDataSetDriver):
    
    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        # Initialize the possible types of harvester/parser pairs
        # for this driver.

        data_keys = DataTypeKey.list()

        # Link the data keys to the harvester type.
        # Recovered harvester is single directory.
        # Telemetered harvester is single directory.

        harvester_type = {
            DataTypeKey.OPTAA_DJ_RECOVERED: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.OPTAA_DJ_TELEMETERED: HarvesterType.SINGLE_DIRECTORY,
        }

        super(OptaaDjDclDataSetDriver, self).__init__(config, memento,
            data_callback, state_callback, event_callback,
            exception_callback, data_keys, harvester_type=harvester_type)
    
    @classmethod
    def stream_config(cls):
        return [
            OptaaDjDclRecoveredInstrumentDataParticle.type(),
            OptaaDjDclTelemeteredInstrumentDataParticle.type()
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

        if DataTypeKey.OPTAA_DJ_RECOVERED in self._harvester_config:
            harvesters.append(self.build_single_harvester(DataTypeKey.OPTAA_DJ_RECOVERED,
                                                          driver_state))
        else:
            log.warn('No configuration for optaa_dj_dcl recovered harvester, not building')

        # Verify that the Telemetered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.

        if DataTypeKey.OPTAA_DJ_TELEMETERED in self._harvester_config:
            harvesters.append(self.build_single_harvester(DataTypeKey.OPTAA_DJ_TELEMETERED,
                                                          driver_state))
        else:
            log.warn('No configuration for optaa_dj_dcl telemetered harvester, not building')

        return harvesters

    def build_single_harvester(self, key, driver_state):

        harvester = SingleDirectoryHarvester(
            self._harvester_config.get(key),
            driver_state[key],
            lambda filename: self._new_file_callback(filename, key),
            lambda modified: self._modified_file_callback(modified, key),
            self._exception_callback)

        return harvester
    
    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param stream_in Filename string to pass to parser
        @param data_key Key to determine which parser type is built
        """

        # Build the recovered parser if requested.

        if data_key == DataTypeKey.OPTAA_DJ_RECOVERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: MODULE_NAME,
                DataSetDriverConfigKeys.PARTICLE_CLASS: None
            })
            parser_class = OptaaDjDclRecoveredParser

        # Build the telemetered parser if requested.

        elif data_key == DataTypeKey.OPTAA_DJ_TELEMETERED:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: MODULE_NAME,
                DataSetDriverConfigKeys.PARTICLE_CLASS: None
            })
            parser_class = OptaaDjDclTelemeteredParser

        # Not one of the keys we recognize?
        # No parser for you!

        else:
            raise ConfigurationException('Optaa_dj Parser configuration incorrect %s',
                                         data_key)

        # Note that the Optaa_Dj parsers need the name of the file being parsed.

        parser = parser_class(
            config,
            stream_in,
            parser_state,
            lambda state, ingested:
                self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback,
            self._file_in_process[data_key])

        return parser
