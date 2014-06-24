"""
@package mi.dataset.driver.mflm.ctd.driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn (original telemetered), Steve Myerson (recovered)
@brief Driver for the mflm_ctd
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()

from mi.dataset.harvester import \
    SingleDirectoryHarvester, \
    SingleFileHarvester

from mi.dataset.driver.sio_mule.sio_mule_driver import \
    SioMuleDataSetDriver

from mi.dataset.dataset_driver import \
    DataSetDriverConfigKeys, \
    HarvesterType

from mi.dataset.parser.ctdmo import \
    CtdmoRecoveredCoParser, \
    CtdmoRecoveredCtParser, \
    CtdmoTelemeteredParser, \
    CtdmoRecoveredInstrumentDataParticle, \
    CtdmoRecoveredOffsetDataParticle, \
    CtdmoTelemeteredInstrumentDataParticle, \
    CtdmoTelemeteredOffsetDataParticle


class DataTypeKey(BaseEnum):
    """
    These are the possible harvester/parser pairs for this driver
    """
    CTDMO_GHQR_SIO_MULE = 'ctdmo_ghqr_sio_mule'
    CTDMO_GHQR_CO = 'ctdmo_ghqr_co'
    CTDMO_GHQR_CT = 'ctdmo_ghqr_ct'


class MflmCtdmoDataSetDriver(SioMuleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback,
                 event_callback, exception_callback):

        # Initialize the possible types of harvester/parser pairs
        # for this driver.
        data_keys = DataTypeKey.list()

        # Link the data keys to the harvester type.
        # Telemetered harvester is single file.
        # Recovered harvesters are single directory.
        harvester_type = {
            DataTypeKey.CTDMO_GHQR_SIO_MULE: HarvesterType.SINGLE_FILE,
            DataTypeKey.CTDMO_GHQR_CO: HarvesterType.SINGLE_DIRECTORY,
            DataTypeKey.CTDMO_GHQR_CT: HarvesterType.SINGLE_DIRECTORY,
        }

        super(MflmCtdmoDataSetDriver, self).__init__(config, memento,
            data_callback, state_callback, event_callback,
            exception_callback, data_keys, harvester_type=harvester_type)

    @classmethod
    def stream_config(cls):
        # Once the recovered parser exists, particles should be added here
        return [CtdmoRecoveredInstrumentDataParticle.type(),
                CtdmoRecoveredOffsetDataParticle.type(),
                CtdmoTelemeteredInstrumentDataParticle.type(),
                CtdmoTelemeteredOffsetDataParticle.type()]

    def _build_parser(self, parser_state, stream_in, data_key):
        """
        Build the requested parser based on the data key
        @param parser_state starting parser state to pass to parser
        @param stream_in Handle of open file to pass to parser
        @param stream_in Filename string to pass to parser
        @param data_key Key to determine which parser type is built
        """

        #
        # Build the telemetered parser if requested.
        #
        if data_key == DataTypeKey.CTDMO_GHQR_SIO_MULE:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.ctdmo',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    ['CtdmoTelemeteredInstrumentDataParticle',
                     'CtdmoTelemeteredOffsetDataParticle']
            })
            log.debug("MYCONFIG Telemetered: %s", config)

            parser = CtdmoTelemeteredParser(
                config,
                parser_state,
                stream_in,
                lambda state:
                    self._save_parser_state(state,
                                            DataTypeKey.CTDMO_GHQR_SIO_MULE),
                self._data_callback,
                self._sample_exception_callback)

        #
        # Build the recovered parser for CO data if requested.
        #
        elif data_key == DataTypeKey.CTDMO_GHQR_CO:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.ctdmo',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    'CtdmoRecoveredOffsetDataParticle'
            })
            log.debug("MYCONFIG CO Recovered: %s", config)

            parser = CtdmoRecoveredCoParser(
                config,
                parser_state,
                stream_in,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # Build the recovered parser for CT data if requested.
        #
        elif data_key == DataTypeKey.CTDMO_GHQR_CT:
            config = self._parser_config[data_key]
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE:
                    'mi.dataset.parser.ctdmo',
                DataSetDriverConfigKeys.PARTICLE_CLASS:
                    'CtdmoRecoveredInstrumentDataParticle'
            })
            log.debug("MYCONFIG CT Recovered: %s", config)

            parser = CtdmoRecoveredCtParser(
                config,
                parser_state,
                stream_in,
                lambda state, ingested:
                    self._save_parser_state(state, data_key, ingested),
                self._data_callback,
                self._sample_exception_callback)

        #
        # Not one of the keys we recognize?
        # No parser for you!
        #
        else:
            parser = None

        return parser

    def _build_harvester(self, driver_state):
        """
        Build the harvester
        @param driver_state The starting driver state
        """
        harvesters = []

        #
        # Verify that the CO Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.CTDMO_GHQR_CO in self._harvester_config:
            co_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.CTDMO_GHQR_CO),
               driver_state[DataTypeKey.CTDMO_GHQR_CO],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.CTDMO_GHQR_CO),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.CTDMO_GHQR_CO),
               self._exception_callback)

            if co_harvester is not None:
                harvesters.append(co_harvester)
            else:
                log.warn('Could not build ctdmo_ghqr_co harvester')

        else:
            log.warn('No configuration for ctdmo_ghqr_co harvester, not building')

        #
        # Verify that the CT Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.CTDMO_GHQR_CT in self._harvester_config:
            ct_harvester = SingleDirectoryHarvester(
               self._harvester_config.get(DataTypeKey.CTDMO_GHQR_CT),
               driver_state[DataTypeKey.CTDMO_GHQR_CT],
               lambda filename:
                   self._new_file_callback(filename,
                                           DataTypeKey.CTDMO_GHQR_CT),
               lambda modified:
                   self._modified_file_callback(modified,
                                                DataTypeKey.CTDMO_GHQR_CT),
               self._exception_callback)

            if ct_harvester is not None:
                harvesters.append(ct_harvester)
            else:
                log.warn('Could not build ctdmo_ghqr_ct harvester')

        else:
            log.warn('No configuration for ctdmo_ghqr_ct harvester, not building')

        #
        # Verify that the CT Recovered harvester has been configured.
        # If so, build the harvester and add it to the list of harvesters.
        #
        if DataTypeKey.CTDMO_GHQR_SIO_MULE in self._harvester_config:
            ctdmo_ghqr_sio_mule_harvester = SingleFileHarvester(
                self._harvester_config.get(DataTypeKey.CTDMO_GHQR_SIO_MULE),
                driver_state[DataTypeKey.CTDMO_GHQR_SIO_MULE],
                lambda file_state:
                    self._file_changed_callback(file_state,
                                                DataTypeKey.CTDMO_GHQR_SIO_MULE),
                self._exception_callback)

            if ctdmo_ghqr_sio_mule_harvester is not None:
                harvesters.append(ctdmo_ghqr_sio_mule_harvester)
            else:
                log.warn('Could not build ctdmo_ghqr_sio_mule harvester')

        else:
            log.warn('No configuration for ctdmo_ghqr_sio_mule harvester, not building')

        return harvesters
