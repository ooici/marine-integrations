"""
@package mi.dataset.driver.mflm.ctd.driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Driver for the mflm_ctd
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import string
import hashlib
import gevent

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_driver import SimpleDataSetDriver
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.harvester import SingleFileChangeHarvester, FileChangeHarvesterMementoKey


class MflmCTDMODataSetDriver(SimpleDataSetDriver):

    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        super(MflmCTDMODataSetDriver, self).__init__(config, memento, data_callback,
                                                     state_callback, exception_callback)
        # need to override initialization of states to be a dict
        if self._harvester_state == None:
            self._harvester_state = {}
        if self._parser_state == None:
            self._parser_state = {}

    @classmethod
    def stream_config(cls):
        return [CtdmoParserDataParticle.type()]

    def _build_parser(self, parser_state, infile):
        config = self._parser_config
        config.update({
            'particle_module': 'mi.dataset.parser.ctdmo',
            'particle_class': 'CtdmoParserDataParticle'
        })
        log.debug("MYCONFIG: %s", config)
        self._parser = CtdmoParser(
            config,
            parser_state,
            infile,
            self._save_parser_state,
            self._data_callback
        )

        return self._parser

    def _build_harvester(self, harvester_state):
        self._harvester = SingleFileChangeHarvester(
            self._harvester_config,
            harvester_state,
            self._new_file_callback,
            self._exception_callback
        )

        return self._harvester

    def clear_states(self):
        """
        Clear both the parser and harvester states
        """
        self._parser_state = {}
        self._harvester_state = {}

    def _got_file(self, file_tuple):
        """
        We have a file that we want to parse.  Stand up the parser and do some work.
        @param file_tuple: (file_handle, file_size) tuple returned by the harvester
        """
        handle, size = file_tuple
        log.info("Detected new file, handle: %r, size: %d", handle, size)
        count = 1
        delay = None

        # Calulate the delay between grabbing records to publish.
        if self._generate_particle_count:
            delay = float(1) / float(self._particle_count_per_second) * float(self._generate_particle_count)

        if self._generate_particle_count:
            count = self._generate_particle_count

        # For some reason when adding the handle to the _new_file_queue the file
        # handle is closed.  Haven't had a chance to investigate, but this hack
        # re-opens the file.
        handle = open(handle.name, handle.mode)
        data = handle.read()
        checksum = hashlib.md5(data).hexdigest()
        # reset position after reading data to calculate checksum
        handle.seek(0)
        # need to check if the file has grown larger, if it has update the last
        # unprocessed data index
        log.debug('About to check parser state %s', self._parser_state)
        if self._parser_state != {} and \
        self._parser_state[StateKey.UNPROCESSED_DATA][-1][1] < size:
            last_size = self._harvester_state[FileChangeHarvesterMementoKey.LAST_FILESIZE]
            new_parser_state = self._parser_state
            # the file is larger, need to update last unprocessed index
            # set the new parser unprocessed data state
            if last_size == new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if the last unprocessed is the last file size, just increase the last index
                log.debug('Replacing last unprocessed parser with %d', size)
                new_parser_state[StateKey.UNPROCESSED_DATA][-1][1] = size
            elif last_size  > new_parser_state[StateKey.UNPROCESSED_DATA][-1][1]:
                # if we processed past the last file size, append a new unprocessed block
                # that goes from the last file size to the new file size
                log.debug('Appending new unprocessed parser %d,%d', last_size, size)
                new_parser_state[StateKey.UNPROCESSED_DATA].append([last_size, size])
            log.debug("Saving new parser state %s", new_parser_state)
            self._save_parser_state(new_parser_state)

        parser = self._build_parser(self._parser_state, handle)

        while(True):
            result = parser.get_records(count)
            if result:
                log.trace("Record parsed: %r delay: %f", result, delay)
                if delay:
                    gevent.sleep(delay)
            else:
                break

        # Once we have successfully imported the file reset the parser state
        # and store the harvester state.
        state = {FileChangeHarvesterMementoKey.LAST_FILESIZE: size,
                 FileChangeHarvesterMementoKey.LAST_CHECKSUM: checksum}
        self._save_harvester_state(state)

    def _save_harvester_state(self, state):
        """
        Store the harvester state in the driver when a file is successfully parsed.
        Don't reset the parser state since we are just working with one file here.
        @param filename: file name we successfully parsed and imported.
        """
        log.debug("saving harvester state: %r", state)
        self._harvester_state = state
        self._save_driver_state()

    def _new_file_callback(self, file_handle, file_size):
        """
        Callback used by the harvester called when a new file is detected.  Store the
        file handle and filename in a queue.
        @param file_handle: file handle to the new found file.
        @param file_name: file name of the found file.
        """
        index = len(self._new_file_queue)

        log.trace("Add new file to the new file queue: handle: %r, size: %d", file_handle, file_size)
        self._new_file_queue.append((file_handle, file_size))

        count = len(self._new_file_queue)
        log.trace("Current new file queue length: %d", count)