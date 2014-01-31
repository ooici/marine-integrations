#!/usr/bin/env python

"""
@package mi.dataset.test.test_single_dir_harvester.py
@file mi/dataset/test/test_single_dir_harvester.py
@author Emily Hahn
@brief Test code to exercize the single directory harvester
"""
import os
import glob
import gevent
import time
import shutil
import hashlib

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.dataset.harvester import SingleDirectoryHarvester
from mi.dataset.dataset_driver import DriverStateKey, DataSetDriverConfigKeys

TESTDIR = '/tmp/dsatest'
STOREDIR = '/tmp/stored_dsatest'
CONFIG = {
    DataSetDriverConfigKeys.DIRECTORY: TESTDIR,
    DataSetDriverConfigKeys.STORAGE_DIRECTORY: STOREDIR,
        DataSetDriverConfigKeys.PATTERN: '*.txt',
        DataSetDriverConfigKeys.FREQUENCY: 5,
        DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30
}

INDICIES = ['363_2013_0245_6_8', '363_2013_0245_6_9', '363_2013_0245_6_10', '363_2013_0245_6_11',
            '363_2013_0245_7_0', '363_2013_0245_7_1', '363_2013_0245_7_10', '363_2013_0246_0_0',
            '363_2013_0246_7_0', '363_2013_0246_7_1', '363_2014_0012_0_0', '363_2014_0012_0_1', ]

@attr('INT', group='eoi')
class TestSingleDirHarvester(MiUnitTest):
    found_file_count = 0
    found_modified_count = 0

    def setUp(self):
        """
        reset counters and ensure we have test directories in place
        """
        log.info('*** Starting test %s ***', self._testMethodName)
        self.found_file_count = 0
        self.found_modified_count = 0
        if(not os.path.exists(TESTDIR)):
            os.makedirs(TESTDIR)
        self.clean_directory(TESTDIR, CONFIG[DataSetDriverConfigKeys.PATTERN])
        
        if(not os.path.exists(STOREDIR)):
            os.makedirs(STOREDIR)
        self.clean_directory(STOREDIR, CONFIG[DataSetDriverConfigKeys.PATTERN])

    def tearDown(self):
        """
        cleanup the files we have created
        """
        self.clean_directory(TESTDIR, CONFIG[DataSetDriverConfigKeys.PATTERN])
        self.clean_directory(STOREDIR, CONFIG[DataSetDriverConfigKeys.PATTERN])

    def test_init(self):
        """
        Test initialize
        """

        # start the harvester from scratch
        memento = None
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                self.new_file_found_callback,
                                                self.modified_files_found_callback,
                                                self.file_exception_callback)
        file_harvester.start()
        file_harvester.shutdown()

    def test_harvester_from_scratch(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start the harvester from scratch
        memento = None
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = 10
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                self.new_file_found_callback,
                                                                        self.modified_files_found_callback,
                                                self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 5, 10)

        # Wait for new files to be discovered
        self.wait_for_file(0, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)

        file_harvester.shutdown()

    def test_harvester_without_frequency(self):
        """
        Test that we can use a default frequency
        """
        config = {DataSetDriverConfigKeys.DIRECTORY: TESTDIR,
                  DataSetDriverConfigKeys.STORAGE_DIRECTORY: TESTDIR,
                  DataSetDriverConfigKeys.PATTERN: CONFIG[DataSetDriverConfigKeys.PATTERN],
                  DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 15}

        # start the harvester from scratch
        memento = None
        file_harvester = SingleDirectoryHarvester(config, memento,
                                                  self.new_file_found_callback,
                                                                          self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 2)

        # Wait for three sets of new files to be discovered
        self.wait_for_file(0, 2)
        self.wait_for_file(self.found_file_count, 2)

        file_harvester.shutdown()

    def test_harvester_without_mod_time(self):
        """
        Test that we can use a default frequency
        """
        config = {DataSetDriverConfigKeys.DIRECTORY: TESTDIR,
                  DataSetDriverConfigKeys.STORAGE_DIRECTORY: TESTDIR,
                  DataSetDriverConfigKeys.PATTERN: CONFIG[DataSetDriverConfigKeys.PATTERN],
                  DataSetDriverConfigKeys.FREQUENCY: 5}

        # start the harvester from scratch
        memento = None
        file_harvester = SingleDirectoryHarvester(config, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 2)

        # Wait for two sets of new files to be discovered
        self.wait_for_file(0, 2)
        self.wait_for_file(self.found_file_count, 2)

        file_harvester.shutdown()

    def test_harvester_multi_file(self):
        """
        Set the timing so the harvester finds multiple new files at once
        """
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FREQUENCY] = 1
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = 15
        # start the harvester from scratch
        memento = None
        file_harvester = SingleDirectoryHarvester(config, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()

        # set the file filler to generate files with only .5 secs between,
        # meaning 2 files will appear in the 1 seconds between the
        # harvester checking
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 12, .5)

        # Wait for sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        
        file_harvester.shutdown()

    def test_file_mod_wait_time(self):
        """
        that the file mod wait time is actually waiting before finding files
        """
        memento = None
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()
        # put a file in the directory, the mod time will be the create time
        self.fill_directory_with_files(CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                       CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 1, 0)
        # wait until just before the file mod time should allow us to find the files

        # keep track of how long it takes to find the file approximately
        file_found_time = 0;
        while(self.found_file_count == 0):
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

    def test_harvester_with_memento(self):
        """
        Test that the harvester can find file as they are added to a directory,
        using a memento to start partway through the indices
        """
        
        # make sure we have 2 files already in the directory
        self.fill_directory_with_files(CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                       CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 2, 0)

        filename_1 = 'unit_' + INDICIES[0] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')
        filename_2 = 'unit_' + INDICIES[1] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')

        # get metadata for the files
        metadata_1 = self.get_file_metadata(filename_1)
        metadata_1[DriverStateKey.INGESTED] = True
        metadata_1[DriverStateKey.PARSER_STATE] = None
        metadata_2 = self.get_file_metadata(filename_2)
        metadata_2[DriverStateKey.INGESTED] = True
        metadata_2[DriverStateKey.PARSER_STATE] = None
        # generate memento with two files ingested (parser state is not looked at)
        memento = {DriverStateKey.VERSION: 0.1,
                   filename_1: metadata_1,
                   filename_2: metadata_2
                    }
        log.debug("starting with memento %s", memento)
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = 15
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        # with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 2, 9, 5)

        # Wait for three sets of new files to be discovered
        self.wait_for_file(0, 2)
        self.wait_for_file(self.found_file_count, 2)
        self.wait_for_file(self.found_file_count, 2)
        self.wait_for_file(self.found_file_count, 2)
        self.wait_for_file(self.found_file_count, 2)
        self.wait_for_file(self.found_file_count, 2)

        file_harvester.shutdown()

    def test_harvester_with_memento_not_ingested(self):
        """
        Test that the harvester can find file as they are added to a directory,
        using a memento to start partway through the indices
        """

        # make sure we have 2 files already in the directory
        self.fill_directory_with_files(CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                       CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 2, 0)

        filename_1 = 'unit_' + INDICIES[0] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')
        filename_2 = 'unit_' + INDICIES[1] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')

        # get metadata for the files
        metadata_1 = self.get_file_metadata(filename_1)
        metadata_1[DriverStateKey.INGESTED] = True
        metadata_1[DriverStateKey.PARSER_STATE] = None
        metadata_2 = self.get_file_metadata(filename_2)
        metadata_2[DriverStateKey.INGESTED] = False
        metadata_2[DriverStateKey.PARSER_STATE] = None
        # generate memento with two files ingested (parser state is not looked at)
        memento = {DriverStateKey.VERSION: 0.1,
                   filename_1: metadata_1,
                   filename_2: metadata_2
                    }
        log.debug("starting with memento %s", memento)
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = 10
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        # with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                             CONFIG[DataSetDriverConfigKeys.PATTERN], 2, 4, 10)

        # Should find the 4 new files plus 1 not ingested file from state, so 5 total
        self.wait_for_file(0, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)
        self.wait_for_file(self.found_file_count, 5)

        file_harvester.shutdown()

    def test_harvester_with_modified(self):
        """
        Test that the harvester can find file as they are added to a directory,
        using a memento to start partway through the indices
        """

        # make sure we have 2 files already in the directory
        self.fill_directory_with_files(CONFIG[DataSetDriverConfigKeys.DIRECTORY],
                                       CONFIG[DataSetDriverConfigKeys.PATTERN], 0, 2, 0)

        filename_1 = 'unit_' + INDICIES[0] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')
        filename_2 = 'unit_' + INDICIES[1] + CONFIG[DataSetDriverConfigKeys.PATTERN].replace('*', '')

        # get metadata for the files
        metadata_1 = self.get_file_metadata(filename_1)
        metadata_1[DriverStateKey.INGESTED] = True
        metadata_1[DriverStateKey.PARSER_STATE] = None
        metadata_2 = self.get_file_metadata(filename_2)
        metadata_2[DriverStateKey.INGESTED] = True
        metadata_2[DriverStateKey.PARSER_STATE] = None
        # generate memento with two files ingested (parser state is not looked at)
        memento = {DriverStateKey.VERSION: 0.1,
                   filename_1: metadata_1,
                   filename_2: metadata_2
                    }
        log.debug("starting with memento %s", memento)
        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = 15
        file_harvester = SingleDirectoryHarvester(CONFIG, memento,
                                                  self.new_file_found_callback,
                                                  self.modified_files_found_callback,
                                                  self.file_exception_callback)
        file_harvester.start()
        
        file_path = os.path.join(CONFIG[DataSetDriverConfigKeys.DIRECTORY], filename_1)
        with open(file_path, 'a') as filehandle:
            filehandle.write('a b c d')

        end_time = 0
        while(self.found_modified_count == 0):
            log.debug("Waiting for modified file...")
            time.sleep(2)
            end_time += 2
            if end_time > 60:
                raise Exception("Timeout waiting to find modified files")

        file_harvester.shutdown()

    def test_harvester_exception(self):
        """
        Verify exceptions
        """
        config = "blah"
        memento = None
        self.assertRaises(TypeError, SingleDirectoryHarvester, (config, memento,
                                                         self.new_file_found_callback,
                                                         self.modified_files_found_callback,
                                                         self.file_exception_callback))

        config = CONFIG.copy()
        config[DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME] = -5
        self.assertRaises(TypeError, SingleDirectoryHarvester, (config, memento,
                                                         self.new_file_found_callback,
                                                         self.modified_files_found_callback,
                                                         self.file_exception_callback))

    def clean_directory(self, data_directory, pattern = "*"):
        """
        Clean out the data directory of all files
        """
        dir_files = glob.glob(data_directory + '/' + pattern)
        for file_name in dir_files:
            log.debug("Removing file %s", file_name)
            os.remove(file_name)

    def new_file_found_callback(self, file_name):
        """
        Callback when a new file is found by the harvester.  This should pass the file
        to the parser, but from this test we don't have the parser, so just close the file. 
        """
        self.found_file_count += 1
        log.info("New file in callback %s", file_name)

    def modified_files_found_callback(self):
        """
        Callback when a new file is found by the harvester.  This should pass the file
        to the parser, but from this test we don't have the parser, so just close the file. 
        """
        self.found_modified_count += 1
        log.info("Found modified file")

    def file_exception_callback(self, exception):
        """
        Callback if there is an exception in the harvester, just raise an exception
        """
        log.error("Error polling for files: %s", exception)
        raise Exception("Error polling for files: %s", exception)

    def fill_directory_with_files(self, data_directory, pattern, start_idx=0, num_files=1, delay=4):
        """
        Copy the first index file to generate files with sequential increasing indices.
        Search the directory to find the current highest index, then increase one index. 
        """

        for i in range(0, num_files):
            time.sleep(delay)
            next_file = data_directory + '/' + 'unit_' + INDICIES[start_idx + i] + pattern.replace('*', '')
            open(next_file, 'a').close()
            log.debug("Added file %s to directory, index %d", next_file, start_idx + i)
        log.debug("Done with directory filler")

    def get_file_metadata(self, filename):
        """
        Get the file size, modification time and checksum and return it in a dictionary
        """
        file_path = os.path.join(CONFIG.get(DataSetDriverConfigKeys.DIRECTORY), filename)
        # even though the file is copied, copy2 preserves the original file modification time
        mod_time = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        with open(file_path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
        return {DriverStateKey.FILE_SIZE: file_size,
                DriverStateKey.FILE_MOD_DATE: mod_time,
                DriverStateKey.FILE_CHECKSUM: md5_checksum}

    def wait_for_file(self, starting_count, delay=1, timeout=60):
        """
        Wait for a new round of files to be discovered
        """
        end_time = 0
        while(self.found_file_count == starting_count):
            log.debug("Waiting for next set of files...")
            time.sleep(delay)
            end_time += delay
            if end_time > timeout:
                raise Exception("Timeout waiting to find files")

    


