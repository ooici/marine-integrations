#!/usr/bin/env python

"""
@package mi.dataset.test.test_single_file_harvester.py
@file mi/dataset/test/test_single_file_harvester.py
@author Emily Hahn
@brief Test code to exercize single file harvester
"""

import os
import gevent
import time
import hashlib

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.dataset.harvester import SingleFileHarvester
from mi.dataset.dataset_driver import DriverStateKey, DataSetDriverConfigKeys

#bin/nosetests -x -v mi/dataset/test/test_single_file_harvester
TESTDIR = '/tmp/dsatest'
STOREDIR = '/tmp/stored_dsatest'
FILENAME = 'testfile.txt'
CONFIG = {DataSetDriverConfigKeys.DIRECTORY: TESTDIR,
          DataSetDriverConfigKeys.STORAGE_DIRECTORY: STOREDIR,
          DataSetDriverConfigKeys.PATTERN: FILENAME,
          DataSetDriverConfigKeys.FREQUENCY: 2,
          DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 15}


@attr('INT', group='eoi')
class TestSingleFileHarvester(MiUnitTest):
    data_found = False
    number_lines = 0
    starting_lines = 0

    def setUp(self):
        """
        reset counters and ensure we have test files in place
        """
        log.info('*** Starting test %s ***', self._testMethodName)
        self.data_found = False
        self.number_lines = 0
        self.starting_lines = 0

        if(not os.path.exists(TESTDIR)):
            os.makedirs(TESTDIR)

        if(not os.path.exists(STOREDIR)):
            os.makedirs(STOREDIR)

    def tearDown(self):
        """
        Cleanup files we have created
        """
        if os.path.isfile(os.path.join(TESTDIR, FILENAME)):
            os.remove(os.path.join(TESTDIR, FILENAME))
        if os.path.isfile(os.path.join(STOREDIR, FILENAME)):
            os.remove(os.path.join(STOREDIR, FILENAME))

    def test_harvester_from_scratch(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # just touch the file so it is created
	file_path = os.path.join(CONFIG.get(DataSetDriverConfigKeys.DIRECTORY), FILENAME)
        open(file_path, 'a').close()

        # start the harvester from scratch
        memento = None
        file_harvester = SingleFileHarvester(CONFIG, memento, 
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()

        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             FILENAME, 2)

        # Wait for two lines of new data to be discovered
        self.wait_for_data(2)
        file_harvester.shutdown()

    def test_harvester_with_initial_data(self):
        """
        Test that the harvester can find the file changes from a file already in the directory
        """
        # start with 2 lines in the file
        self.fill_file_with_data(CONFIG[DataSetDriverConfigKeys.DIRECTORY], FILENAME, 2, 0)

        # start the harvester with data in the file
        file_offset = None
        file_harvester = SingleFileHarvester(CONFIG, file_offset, 
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()
        self.wait_for_data(2)

        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             FILENAME, 2)

        # Wait for two lines of new data to be discovered
        self.wait_for_data(2)
        file_harvester.shutdown()

    def test_harvester_with_offset(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start with 2 lines in the file
        self.fill_file_with_data(CONFIG[DataSetDriverConfigKeys.DIRECTORY], FILENAME, 2, 0)
        memento = self.get_file_metadata(FILENAME)
        log.debug('Starting with memento %s', memento)
        self.starting_lines = 2

        # start the harvester at the end of the current data
        file_harvester = SingleFileHarvester(CONFIG, memento, 
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()

        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                        CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                        FILENAME, 2)

        # Wait for lines of new data to be discovered
        self.wait_for_data(2)
        file_harvester.shutdown()

    def test_file_mod_wait_time(self):
        """
        Test that the harvester waits the required amount of time before finding
        files that are being modified
        """
        # just touch the file to create it
        file_path = os.path.join(CONFIG.get(DataSetDriverConfigKeys.DIRECTORY), FILENAME)
        open(file_path, 'a').close()

        # start the harvester from scratch
        memento = None
        file_harvester = SingleFileHarvester(CONFIG, memento, 
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()

        # set the filler to write 1 line just under every second, meaning that 2 lines will
        # appear for each wait_for_data
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             FILENAME, 2, 0)
        # keep track of how long it takes to find the file approximately
	file_found_time = 0;
        while(not self.data_found):
            time.sleep(1)
	    file_found_time += 1
            if file_found_time > 60:
                raise Exception("Timeout waiting to find file")

	if file_found_time < CONFIG.get(DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME):
	    # we found the file before the mod time, this is bad!
	    file_harvester.shutdown()
	    self.fail('Files found in %s seconds' % file_found_time)
	log.debug('File found in %s seconds', file_found_time)
	file_harvester.shutdown()

    def test_harvester_exception(self):
        """
        Verify exceptions
        """
        # bad config
        config = "blah"
        self.assertRaises(TypeError, SingleFileHarvester, (config, None, 
                                                           self.new_data_found_callback,
                                                           self.harvester_exception_callback))
        # bad file mod wait time
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = -5
        self.assertRaises(TypeError, SingleFileHarvester, (CONFIG, None,
                                                           self.new_data_found_callback,
                                                           self.harvester_exception_callback))

    def new_data_found_callback(self, new_state):
        """
        Callback when a new file is found by the harvester.  This should pass the file
        to the parser, but from this test we don't have the parser, so just close the file. 
        """
        self.data_found = True
        storage_directory = CONFIG.get(DataSetDriverConfigKeys.DIRECTORY)
	file_path = os.path.join(storage_directory, FILENAME)
        self.number_lines = 0
        with open(file_path) as filehandle:
            for line in filehandle:
                self.number_lines += 1
        log.info("New data number of lines %d, state %s", self.number_lines, new_state)

    def harvester_exception_callback(self, exception):
        """
        Callback if there is an exception in the harvester, just raise an exception
        """
        log.error("Error polling for files: %s", exception)
        raise Exception("Error polling for files: %s", exception)

    def get_file_metadata(self, filename):
	"""
	Get the file size, modification time and checksum and return it in a dictionary
	"""
	storage_directory = CONFIG.get(DataSetDriverConfigKeys.DIRECTORY)
	file_path = os.path.join(storage_directory, filename)
	# even though the file is copied, copy2 preserves the original file modification time
	mod_time = os.path.getmtime(file_path)
	file_size = os.path.getsize(file_path)
	with open(file_path) as filehandle:
	    md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
	return {DriverStateKey.FILE_SIZE: file_size,
                DriverStateKey.FILE_MOD_DATE: mod_time,
                DriverStateKey.FILE_CHECKSUM: md5_checksum}

    def fill_file_with_data(self, data_directory, filename, num_lines=1, delay=6):
        """
        Copy the first index file to generate files with sequential increasing indices.
        Search the directory to find the current highest index, then increase one index. 
        """
        fullfile = os.path.join(data_directory, filename)
        if not os.path.isfile(fullfile):
            # just touch the file to create it
            open(fullfile, 'a').close()

        for i in range(0, num_lines):
            time.sleep(delay)
            file_handle = open(fullfile, 'a')
            data = 'new data line %d\n' % i
            file_handle.write(data)
            file_handle.close()
            log.debug("Added file line %s", data)

    def wait_for_data(self, required_lines=1, delay=2, timeout=60):
        """
        Wait for a new round of files to be discovered
        """
        end_time = 0
        while((self.number_lines - self.starting_lines) < required_lines):
            log.debug("Waiting for next data...")
            time.sleep(delay)
            end_time += delay
            if end_time > timeout:
                raise Exception("Timeout waiting to find data")
        self.data_found = False



