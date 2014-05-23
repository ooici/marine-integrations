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

import string
import os
import gevent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverStateKey
from mi.dataset.parser.cg_stc_eng_stc import CgStcEngStcParser, CgStcEngStcParserDataParticle
from mi.dataset.parser.mopak_o_dcl import MopakODclParser, MopakODclAccelParserDataParticle
from mi.dataset.parser.mopak_o_dcl import MopakODclRateParserDataParticle
from mi.dataset.parser.rte_o_dcl import RteODclParser, RteODclParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class DataSourceKey(BaseEnum):
    CG_STC_ENG = 'cg_stc_eng'
    MOPAK = 'mopak'
    RTE = 'rte'

class CgStcEngStcDataSetDriver(MultipleHarvesterDataSetDriver):
    """
    A different harvester configuration is needed to support the 3 different harvesters
    'harvester':
        {
            'cg_stc_eng':
                {
                    'directory': '/tmp/dsatest',
                    'pattern': '*.txt',
                    'frequency': 1,
                    'file_mod_wait_time': 30
                }
            'mopak':
                {
                    'directory': '/tmp/dsatest',
                    'pattern': '*.txt',
                    'frequency': 1,
                    'file_mod_wait_time': 30
                }
            'rte':
                {
                    'directory': '/tmp/dsatest',
                    'pattern': '*.txt',
                    'frequency': 1,
                    'file_mod_wait_time': 30
                }
        },
    """

    @classmethod
    def stream_config(cls):
        return [CgStcEngStcParserDataParticle.type(),
                MopakODclAccelParserDataParticle.type(),
                MopakODclRateParserDataParticle.type(),
                RteODclParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        data_keys = [DataSourceKey.CG_STC_ENG, DataSourceKey.MOPAK, DataSourceKey.RTE]
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
        parser = None
        if data_key == DataSourceKey.CG_STC_ENG:
            parser = self._build_cg_stc_eng_parser(parser_state, stream_in)
        if data_key == DataSourceKey.MOPAK:
            # mopak requires the filename to obtain the time from the name
            parser = self._build_mopak_parser(parser_state, stream_in, file_in)
        elif data_key == DataSourceKey.RTE:
            parser = self._build_rte_parser(parser_state, stream_in)
        return parser

    def _build_cg_stc_eng_parser(self, parser_state, stream_in):
        """
        Build and return the parser
        @param parser_state previous parser state to initialize parser with
        @param stream_in handle of the opened file to parse
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.cg_stc_eng_stc',
            'particle_class': 'CgStcEngStcParserDataParticle'
        })
        log.debug("My Config: %s", config)
        cg_stc_eng_parser = CgStcEngStcParser(
            config,
            parser_state,
            stream_in,
            lambda state, ingested: self._save_parser_state(state, DataSourceKey.CG_STC_ENG, ingested),
            self._data_callback,
            self._sample_exception_callback
        )
        return cg_stc_eng_parser

    def _build_mopak_parser(self, parser_state, stream_in, file_in):
        """
        Build and return the parser
        @param parser_state previous parser state to initialize parser with
        @param stream_in handle of the opened file to parse
        @param file_in the filename of the file to parse
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.mopak_o_dcl',
            'particle_class': ['MopakODclAccelParserDataParticle',
                               'MopakODclRateParserDataParticle']
        })
        log.debug("My Config: %s", config)
        mopak_parser = MopakODclParser(
            config,
            parser_state,
            stream_in,
            file_in,
            lambda state, ingested: self._save_parser_state(state, DataSourceKey.MOPAK, ingested),
            self._data_callback,
            self._sample_exception_callback
        )
        return mopak_parser

    def _build_rte_parser(self, parser_state, stream_in):
        """
        Build and return the parser
        @param parser_state previous parser state to initialize parser with
        @param stream_in handle of the opened file to parse
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.rte_o_dcl',
            'particle_class': 'RteODclParserDataParticle'
        })
        log.debug("My Config: %s", config)
        rte_parser = RteODclParser(
            config,
            parser_state,
            stream_in,
            lambda state, ingested: self._save_parser_state(state, DataSourceKey.RTE, ingested),
            self._data_callback,
            self._sample_exception_callback
        )
        return rte_parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        harvesters = []
        if DataSourceKey.CG_STC_ENG in self._harvester_config:
            cg_stc_eng_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.CG_STC_ENG),
                driver_state[DataSourceKey.CG_STC_ENG],
                lambda filename: self._new_file_callback(filename, DataSourceKey.CG_STC_ENG),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.CG_STC_ENG),
                self._exception_callback
            )
            harvesters.append(cg_stc_eng_harvester)
        else:
            log.warn('No configuration for cg_stc_eng harvester, not building')

        if DataSourceKey.MOPAK in self._harvester_config:
            mopak_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.MOPAK),
                driver_state[DataSourceKey.MOPAK],
                lambda filename: self._new_file_callback(filename, DataSourceKey.MOPAK),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.MOPAK),
                self._exception_callback
            )
            harvesters.append(mopak_harvester)
        else:
            log.warn('No configuration for mopak harvester, not building')

        if DataSourceKey.RTE in self._harvester_config:
            rte_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataSourceKey.RTE),
                driver_state[DataSourceKey.RTE],
                lambda filename: self._new_file_callback(filename, DataSourceKey.RTE),
                lambda modified: self._modified_file_callback(modified, DataSourceKey.RTE),
                self._exception_callback
            )
            harvesters.append(rte_harvester)
        else:
            log.warn('No configuration for rte harvester, not building')
        return harvesters

    def _get_parser_results(self, file_name, data_key):
        """
        Build the parser and get all the records until there are no more available
        Need to override this from the base parser class to pass in the filename for mopak
        @param file_name name of the file to parse
        @param data_key The key to index into the harvester and parser
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
        parser = self._build_parser(self._driver_state[data_key][file_name][DriverStateKey.PARSER_STATE], handle, data_key, file_name)

        while(True):
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break




    

