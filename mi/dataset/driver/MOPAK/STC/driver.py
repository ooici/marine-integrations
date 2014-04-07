"""
@package mi.dataset.driver.MOPAK.STC.driver
@file marine-integrations/mi/dataset/driver/MOPAK/STC/driver.py
@author Emily Hahn
@brief Driver for the MOPAK__STC
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import os
import gevent
import string

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.dataset_driver import SimpleDataSetDriver, DataSetDriverConfigKeys, DriverStateKey
from mi.dataset.parser.mopak_o_stc import MopakOStcParser
from mi.dataset.parser.mopak_o_stc import MopakOStcAccelParserDataParticle
from mi.dataset.parser.mopak_o_stc import MopakOStcRateParserDataParticle
from mi.dataset.harvester import SingleDirectoryHarvester

class MopakOStcDataSetDriver(SimpleDataSetDriver):
    
    @classmethod
    def stream_config(cls):
        return [MopakOStcAccelParserDataParticle.type(),
                MopakOStcRateParserDataParticle.type()]

    def _build_parser(self, parser_state, infile, filename):
        """
        Build and return the parser
        """
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.mopak_o_stc',
            'particle_class': ['MopakOStcAccelParserDataParticle',
                               'MopakOStcRateParserDataParticle']
        })
        log.debug("My Config: %s", config)
        self._parser = MopakOStcParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback,
            self._sample_exception_callback,
            filename
        )
        return self._parser

    def _build_harvester(self, driver_state):
        """
        Build and return the harvester
        """
        self._harvester = SingleDirectoryHarvester(
            self._harvester_config,
            driver_state,
            self._new_file_callback,
            self._modified_file_callback,
            self._exception_callback
        )     
        return self._harvester

    def _got_file(self, file_name):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_name: name of the file to parse
        """
        try:
            log.debug('got file, resource_id: %s, driver state %s', self._resource_id, self._driver_state)

            directory = self._harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)

            if directory != self._ingest_directory:
                log.error("Detected harvester configuration change. Resource ID: %s Original: %s, new: %s",
                          self._resource_id,
                          self._ingest_directory,
                          directory
                )

            # Removed this for the time being to get new driver code out.  May bring this back in the future
            #self._stage_input_file(os.path.join(directory, file_name))

            count = 1
            delay = None

            if self._generate_particle_count:
                # Calculate the delay between grabbing records to publish.
                delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)
                count = self._generate_particle_count

            self._file_in_process = file_name

            # Open the copied file in the storage directory so we know the file won't be
            # changed while we are reading it
            path = os.path.join(directory, file_name)

            self._raise_new_file_event(path)
            log.debug("Open new data source file: %s", path)
            handle = open(path)

            # the file directory is initialized in the harvester, so it will exist by this point
            parser = self._build_parser(self._driver_state[file_name][DriverStateKey.PARSER_STATE], handle, file_name)

            while(True):
                result = parser.get_records(count)
                if result:
                    log.trace("Record parsed: %r delay: %f", result, delay)
                    if delay:
                        gevent.sleep(delay)
                else:
                    break

        except SampleException as e:
            # need to mark the bad file as ingested so we don't re-ingest it
            self._save_parser_state_after_error()
            self._sample_exception_callback(e)

        finally:
            self._file_in_process = None
