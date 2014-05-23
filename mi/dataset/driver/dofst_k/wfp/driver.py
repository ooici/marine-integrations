"""
@package mi.dataset.driver.dofst_k.wfp.driver
@file marine-integrations/mi/dataset/driver/dofst_k/wfp/driver.py
@author Emily Hahn
@brief Driver for the dofst_k_wfp
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import os
import string
import gevent

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException

from mi.dataset.dataset_driver import MultipleHarvesterDataSetDriver, DataSetDriverConfigKeys, DriverStateKey
from mi.dataset.parser.dofst_k_wfp import DofstKWfpParser, DofstKWfpParserDataParticle
from mi.dataset.parser.dofst_k_wfp import DofstKWfpMetadataParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class DataSourceKey(BaseEnum):
    DOFST_K_WFP_TELEMETERED = 'dofst_k_wfp_telemetered'
    DOFST_K_WFP_RECOVERED = 'dofst_k_wfp_recovered'

class DofstKWfpDataSetDriver(MultipleHarvesterDataSetDriver):

    @classmethod
    def stream_config(cls):
        return [DofstKWfpMetadataParserDataParticle.type(),
                DofstKWfpParserDataParticle.type()]

    def __init__(self, config, memento, data_callback, state_callback, event_callback, exception_callback):
        # initialize the possible types of harvester/parser pairs for this driver
        data_keys = [DataSourceKey.DOFST_K_WFP_TELEMETERED, DataSourceKey.DOFST_K_WFP_RECOVERED]
        super(DofstKWfpDataSetDriver, self).__init__(config, memento, data_callback, state_callback, event_callback,
                                                     exception_callback, data_keys)

    def _build_parser(self, parser_state, infile, filesize, data_key):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.dofst_k_wfp',
            'particle_class': ['DofstKWfpMetadataParserDataParticle',
                               'DofstKWfpParserDataParticle']
        })
        log.debug("My Config: %s", config)
        parser = DofstKWfpParser(
            config,
            parser_state,
            infile,
            lambda state, ingested: self._save_parser_state(state, data_key, ingested),
            self._data_callback,
            self._sample_exception_callback,
            filesize
        )
        return parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        harvesters = []
        harvester_telem = self._build_single_dir_harvester(driver_state, DataSourceKey.DOFST_K_WFP_TELEMETERED)
        if harvester_telem != None:
            harvesters.append(harvester_telem)
        harvester_recov = self._build_single_dir_harvester(driver_state, DataSourceKey.DOFST_K_WFP_RECOVERED)
        if harvester_recov != None:
            harvesters.append(harvester_recov)
        return harvesters

    def _build_single_dir_harvester(self, driver_state, data_key):
        harvester = None
        if data_key in self._harvester_config:
            harvester = SingleDirectoryHarvester(
                self._harvester_config.get(data_key),
                driver_state[data_key],
                lambda filename: self._new_file_callback(filename, data_key),
                lambda modified: self._modified_file_callback(modified, data_key),
                self._exception_callback
            )
        else:
            log.warn('No configuration for %s harvester, not building', data_key)
        return harvester

    def _get_parser_results(self, file_name, data_key):
        """
        Build the parser and get all the records until there are no more available
        Need to override to pass in the file size to the parser
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

        filesize = os.path.getsize(path)

        self._file_in_process[data_key] = file_name

        # the file directory is initialized in the harvester, so it will exist by this point
        parser = self._build_parser(self._driver_state[data_key][file_name][DriverStateKey.PARSER_STATE], handle, filesize, data_key)

        while(True):
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break
