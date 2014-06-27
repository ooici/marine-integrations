"""
@package mi.dataset.driver.cg_stc_eng.stc.driver
@file marine-integrations/mi/dataset/driver/cg_stc_eng/stc/driver.py
@author Emily Hahn
@brief Driver for the cg_stc_eng_stc
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import os
import gevent

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.core.common import BaseEnum

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverStateKey

from mi.dataset.parser.cg_stc_eng_stc import \
    CgStcEngStcParser, \
    CgStcEngStcParserDataParticle, \
    CgStcEngStcParserRecoveredDataParticle

from mi.dataset.parser.mopak_o_dcl import \
    MopakODclParser, \
    MopakODclAccelParserDataParticle, \
    MopakODclAccelParserRecoveredDataParticle, \
    MopakODclRateParserDataParticle, \
    MopakODclRateParserRecoveredDataParticle, \
    MopakParticleClassType

from mi.dataset.parser.rte_o_dcl import \
    RteODclParser, \
    RteODclParserDataParticle, \
    RteODclParserRecoveredDataParticle

from mi.dataset.harvester import SingleDirectoryHarvester


class DataTypeKey(BaseEnum):
    CG_STC_ENG_TELEM = 'cg_stc_eng_telem'
    CG_STC_ENG_RECOV = 'cg_stc_eng_recov'
    MOPAK_TELEM = 'mopak_telem'
    MOPAK_RECOV = 'mopak_recov'
    RTE_TELEM = 'rte_telem'
    RTE_RECOV = 'rte_recov'


class CgStcEngStcDataSetDriver(MultipleHarvesterDataSetDriver):
    """  Single driver for CG STC ENG STC, RTE O DCL and MOPAK O DCL
    includes harvesters for both telemetered and recovered data streams
    """

    @classmethod
    def stream_config(cls):
        return [CgStcEngStcParserDataParticle.type(),
                CgStcEngStcParserRecoveredDataParticle.type(),
                MopakODclAccelParserDataParticle.type(),
                MopakODclAccelParserRecoveredDataParticle.type(),
                MopakODclRateParserDataParticle.type(),
                MopakODclRateParserRecoveredDataParticle.type(),
                RteODclParserDataParticle.type(),
                RteODclParserRecoveredDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):

        #data_keys = [DataTypeKey.CG_STC_ENG_TELEM, DataTypeKey.MOPAK_TELEM, DataTypeKey.RTE_TELEM]
        data_keys = DataTypeKey.list()

        log.info("data keys in driver constructor are %s", data_keys)

        super(CgStcEngStcDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                       exception_callback, data_keys)

    def _build_parser(self, parser_state, stream_in, data_key, file_in):
        """
        Build the parser based on which data_key is input.  The file name is only
        needed for mopak, and it just not passed in to the other parser builders
        @param parser_state previous parser state to initialize parser with
        @param stream_in handle of the opened file to parse
        @param data_key harvester / parser key 
        @param file_in file name
        """

        # get the config for the correct parser instance
        config = self._parser_config.get(data_key)

        if config is None:
            log.warn('Parser config does not exist for key = %s.  Not building parser', data_key)
            raise ConfigurationException

        if data_key == DataTypeKey.CG_STC_ENG_TELEM:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.cg_stc_eng_stc',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'CgStcEngStcParserDataParticle'
            })
            parser = CgStcEngStcParser(config,
                                       parser_state,
                                       stream_in,
                                       lambda state, ingested:
                                       self._save_parser_state(state, data_key, ingested),
                                       self._data_callback,
                                       self._sample_exception_callback)

        elif data_key == DataTypeKey.CG_STC_ENG_RECOV:
            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.cg_stc_eng_stc',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'CgStcEngStcParserRecoveredDataParticle'
            })
            parser = CgStcEngStcParser(config,
                                       parser_state,
                                       stream_in,
                                       lambda state, ingested:
                                       self._save_parser_state(state, data_key, ingested),
                                       self._data_callback,
                                       self._sample_exception_callback)

        elif data_key == DataTypeKey.MOPAK_TELEM:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.mopak_o_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                # particle_class configuration does nothing for multi-particle parsers
                # put the class names in specific config parameters so the parser can get them
                # use real classes as objects instead of strings to make it easier
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
                    {MopakParticleClassType.ACCEL_PARTCICLE_CLASS: MopakODclAccelParserDataParticle,
                     MopakParticleClassType.RATE_PARTICLE_CLASS: MopakODclRateParserDataParticle}
            })

            parser = MopakODclParser(config,
                                     parser_state,
                                     stream_in,
                                     file_in,
                                     lambda state, ingested:
                                     self._save_parser_state(state, data_key, ingested),
                                     self._data_callback,
                                     self._sample_exception_callback)

        elif data_key == DataTypeKey.MOPAK_RECOV:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.mopak_o_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                # particle_class configuration does nothing for multi-particle parsers
                # put the class names in specific config parameters so the parser can get them
                # use real classes as objects instead of strings to make it easier
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT:
                    {MopakParticleClassType.ACCEL_PARTCICLE_CLASS: MopakODclAccelParserRecoveredDataParticle,
                     MopakParticleClassType.RATE_PARTICLE_CLASS: MopakODclRateParserRecoveredDataParticle}
            })

            parser = MopakODclParser(config,
                                     parser_state,
                                     stream_in,
                                     file_in,
                                     lambda state, ingested:
                                     self._save_parser_state(state, data_key, ingested),
                                     self._data_callback,
                                     self._sample_exception_callback)

        elif data_key == DataTypeKey.RTE_TELEM:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.rte_o_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'RteODclParserDataParticle'})
            parser = RteODclParser(config,
                                   parser_state,
                                   stream_in,
                                   lambda state, ingested:
                                   self._save_parser_state(state, data_key, ingested),
                                   self._data_callback,
                                   self._sample_exception_callback)

        elif data_key == DataTypeKey.RTE_RECOV:

            config.update({
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.rte_o_dcl',
                DataSetDriverConfigKeys.PARTICLE_CLASS: 'RteODclParserRecoveredDataParticle'})
            parser = RteODclParser(config,
                                   parser_state,
                                   stream_in,
                                   lambda state, ingested:
                                   self._save_parser_state(state, data_key, ingested),
                                   self._data_callback,
                                   self._sample_exception_callback)

        else:
            log.warn('Invalid Data_Key %s.  Not building parser', data_key)
            raise ConfigurationException

        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvesters
        """
        self._harvester = []

        if DataTypeKey.CG_STC_ENG_TELEM in self._harvester_config:
            cg_stc_eng_harvester = self.build_single_harvester(driver_state, DataTypeKey.CG_STC_ENG_TELEM)
            self._harvester.append(cg_stc_eng_harvester)
        else:
            log.warn('No configuration for cg_stc_eng telemetered harvester, not building')

        if DataTypeKey.CG_STC_ENG_RECOV in self._harvester_config:
            cg_stc_eng_harvester = self.build_single_harvester(driver_state, DataTypeKey.CG_STC_ENG_RECOV)
            self._harvester.append(cg_stc_eng_harvester)
        else:
            log.warn('No configuration for cg_stc_eng recovered harvester, not building')

        if DataTypeKey.MOPAK_TELEM in self._harvester_config:
            mopak_harvester = self.build_single_harvester(driver_state, DataTypeKey.MOPAK_TELEM)
            self._harvester.append(mopak_harvester)
        else:
            log.warn('No configuration for mopak telemetered harvester, not building')

        if DataTypeKey.MOPAK_RECOV in self._harvester_config:
            mopak_harvester = self.build_single_harvester(driver_state, DataTypeKey.MOPAK_RECOV)
            self._harvester.append(mopak_harvester)
        else:
            log.warn('No configuration for mopak recovered harvester, not building')

        if DataTypeKey.RTE_TELEM in self._harvester_config:
            rte_harvester = self.build_single_harvester(driver_state, DataTypeKey.RTE_TELEM)
            self._harvester.append(rte_harvester)
        else:
            log.warn('No configuration for rte telemetered harvester, not building')

        if DataTypeKey.RTE_RECOV in self._harvester_config:
            rte_harvester = self.build_single_harvester(driver_state, DataTypeKey.RTE_RECOV)
            self._harvester.append(rte_harvester)
        else:
            log.warn('No configuration for rte recovered harvester, not building')

        return self._harvester

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

    def _get_parser_results(self, file_name, data_key):

        """
        Build the parser and get all the records until there are no more available
        Need to override this from the base parser class to pass in the filename for mopak
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser

        Overloaded inherited method to pass filename into _build_parser
        filename is needed by the MOPAK parser constructor
        """

        count = 1
        delay = None

        directory = self._harvester_config[data_key].get(DataSetDriverConfigKeys.DIRECTORY)

        if self._generate_particle_count:
            # Calculate the delay between grabbing records to publish.
            delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
            count = self._generate_particle_count

        # Open the copied file in the storage directory so we know the file won't be
        # changed while we are reading it
        path = os.path.join(directory, file_name)

        self._raise_new_file_event(path)
        log.debug("Open new data source file: %s", path)
        handle = open(path)

        self._file_in_process[data_key] = file_name

        # the file directory is initialized in the harvester, so it will exist by this point
        parser = self._build_parser(self._driver_state[data_key][file_name][DriverStateKey.PARSER_STATE],
                                    handle, data_key, file_name)

        while True:
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break