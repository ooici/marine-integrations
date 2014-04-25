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

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver
from mi.dataset.parser.cg_stc_eng_stc import CgStcEngStcParser, CgStcEngStcParserDataParticle
from mi.dataset.parser.mopak_o_dcl import MopakODclParser, MopakODclAccelParserDataParticle, MopakODclRateParserDataParticle
from mi.dataset.parser.rte_o_dcl import RteODclParser, RteODclParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class DataTypeKey(BaseEnum):
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
        data_keys = [DataTypeKey.CG_STC_ENG, DataTypeKey.MOPAK, DataTypeKey.RTE]
        super(CgStcEngStcDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                       exception_callback, data_keys)

    def _build_parser(self, parser_state, stream_in, file_in, data_key):
        parser = None
        if data_key == DataTypeKey.CG_STC_ENG:
            parser = self._build_cg_stc_eng_parser(parser_state, stream_in, file_in)
        if data_key == DataTypeKey.MOPAK:
            parser = self._build_mopak_parser(parser_state, stream_in, file_in)
        elif data_key == DataTypeKey.RTE:
            parser = self._build_rte_parser(parser_state, stream_in, file_in)
        return parser

    def _build_cg_stc_eng_parser(self, parser_state, stream_in, file_in):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.cg_stc_eng_stc',
            'particle_class': 'CgStcEngStcParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._cg_stc_eng_parser = CgStcEngStcParser(
            config,
            parser_state,
            stream_in,
            file_in,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._cg_stc_eng_parser

    def _build_mopak_parser(self, parser_state, stream_in, file_in):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.mopak_o_dcl',
            'particle_class': ['MopakODclAccelParserDataParticle',
                               'MopakODclRateParserDataParticle']
        })
        log.debug("My Config: %s", config)
        self._mopak_parser = MopakODclParser(
            config,
            parser_state,
            stream_in,
            file_in,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._mopak_parser

    def _build_rte_parser(self, parser_state, stream_in, file_in):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.rte_o_dcl',
            'particle_class': 'RteODclParserDataParticle'
        })
        log.debug("My Config: %s", config)
        self._rte_parser = RteODclParser(
            config,
            parser_state,
            stream_in,
            file_in,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback
        )
        return self._rte_parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = []
        if DataTypeKey.CG_STC_ENG in self._harvester_config:
            self._cg_stc_eng_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.CG_STC_ENG),
                driver_state,
                self._new_cg_stc_eng_file_callback,
                self._modified_file_callback,
                self._exception_callback
            )
            self._harvester.append(self._cg_stc_eng_harvester)
        else:
            log.warn('No configuration for cg_stc_eng harvester, not building')

        if DataTypeKey.MOPAK in self._harvester_config:
            self._mopak_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.MOPAK),
                driver_state,
                self._new_mopak_file_callback,
                self._modified_file_callback,
                self._exception_callback
            )
            self._harvester.append(self._mopak_harvester)
        else:
            log.warn('No configuration for mopak harvester, not building')

        if DataTypeKey.RTE in self._harvester_config:
            self._rte_harvester = SingleDirectoryHarvester(
                self._harvester_config.get(DataTypeKey.RTE),
                driver_state,
                self._new_rte_file_callback,
                self._modified_file_callback,
                self._exception_callback
            )
            self._harvester.append(self._rte_harvester)
        else:
            log.warn('No configuration for rte harvester, not building')
        return self._harvester

    def _new_cg_stc_eng_file_callback(self, file_name):
        """
        Callback used by the cg_stc_eng single directory harvester called when a new file is detected.  Store the
        filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.CG_STC_ENG)

    def _new_mopak_file_callback(self, file_name):
        """
        Callback used by the MOPAK single directory harvester called when a new file is detected.  Store the
        filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.MOPAK)

    def _new_rte_file_callback(self, file_name):
        """
        Callback used by the RTE single directory harvester called when a new file is detected.  Store the
        filename in a queue.
        @param file_name: file name of the found file.
        """
        self._new_file_callback(file_name, DataTypeKey.RTE)

    

