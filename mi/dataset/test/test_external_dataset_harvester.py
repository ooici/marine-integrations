#!/usr/bin/env python

"""
@package mi.dataset.test.test_external_dataset_harvester
@file mi/dataset/test/test_external_dataset_agent_harvester
@author Emily Hahn
@brief Test code to exercise the harvester
"""

import time
import gevent
import shutil
import os
import re
import glob

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.dataset.harvester import AdditiveSequentialFileHarvester

# bin/nosetests -s -v --nologcapture mi.dataset.test.test_external_dataset_harvester

TESTDIR = '/tmp/dsatest'
CONFIG = {'directory': TESTDIR,
          'pattern': '*.txt',
          'frequency': 5}

@attr('INT', group='eoi')
class TestExternalDatasetHarvester(MiUnitTest):
    found_file_count = 0

    def setUp(self):
        """
        reset counters and ensure we have test files in place
        """
        self.found_file_count = 0

        # Create a file for testing
        open(os.path.join(TESTDIR, "test_000.txt"), 'a').close()

        if(not os.path.exists(TESTDIR)):
            os.makedirs(TESTDIR)

    def tearDown(self):
        """
        Cleanup files we have created
        """
        self.clean_directory(TESTDIR, CONFIG['pattern'])

    def test_harvester_without_frequency(self):
        """
        Test that we can use a default frequency
        """
        config = {'directory': TESTDIR, 'pattern': CONFIG['pattern']}

        # start the harvester from scratch
        memento = None
        file_harvester = AdditiveSequentialFileHarvester(config, memento,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback)
        file_harvester.start()

        # start a new event which will copy the first file and increase the
        # file index into data directory with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 2)

        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)

        file_harvester.shutdown()

    def test_harvester_from_scratch(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start the harvester from scratch
        memento = None
        file_harvester = AdditiveSequentialFileHarvester(CONFIG, memento,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback)
        file_harvester.start()
        
        # start a new event which will copy the first file and increase the
        # file index into data directory with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 2)
        
        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
         
        file_harvester.shutdown()
        
    def test_harvester_with_memento(self):
        """
        Test that the harvester can find file as they are added to a directory,
        using a memento to start partway through the indices
        """
        # make sure we have 2 files already in the directory
        self.fill_directory_with_files(CONFIG['directory'], CONFIG['pattern'], 2, 0)
        
        # start at index 2
        dir_files = glob.glob(CONFIG['directory'] + '/' + CONFIG['pattern'])
        memento = self.replace_file_index(dir_files[0], 2)
        file_harvester = AdditiveSequentialFileHarvester(CONFIG, memento,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback)
        file_harvester.start()
        
        # start a new event which will copy the first file and increase the
        # file index into data directory with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 3)
        
        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
         
        file_harvester.shutdown()
        
    def test_harvester_multi_file(self):
        """
        Set the timing so the harvester finds multiple new files at once
        """
        # start the harvester from scratch
        memento = None
        file_harvester = AdditiveSequentialFileHarvester(CONFIG, memento,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback)
        file_harvester.start()
        
        # set the file filler to generate files with only 1.5 secs between,
        # meaning 3 files will appear in the 5 seconds between the
        # harvester checking
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 9, 1.5)
        
        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
         
        file_harvester.shutdown()

    def test_harvester_exception(self):
        """
        Verify exceptions
        """
        config = "blah"
        self.assertRaises(TypeError, AdditiveSequentialFileHarvester,
                                                        (config, None,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback))


    def wait_for_file(self, starting_count, delay=5, timeout=60):
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
        
    def new_file_found_callback(self, file_handle, file_name):
        """
        Callback when a new file is found by the harvester.  This should pass the file
        to the parser, but from this test we don't have the parser, so just close the file. 
        """
        self.found_file_count += 1
        file_handle.close()
        log.info("Found new file %s", file_name)
    
    def file_exception_callback(self, exception):
        """
        Callback if there is an exception in the harvester, just raise an exception
        """
        log.error("Error polling for files: %s", exception)
        raise Exception("Error polling for files: %s", exception)
        
    def fill_directory_with_files(self, data_directory, pattern, num_files=1, delay=15):
        """
        Copy the first index file to generate files with sequential increasing indices.
        Search the directory to find the current highest index, then increase one index. 
        """
        dir_files = glob.glob(data_directory + '/' + pattern)
        if len(dir_files) > 0:
            # find the highest indexed file and get its index
            dir_files.sort()
            file_idx_matcher = re.compile('0+(\d+)')
            last_file = dir_files[-1].split('/')[-1]
            file_idx_match = file_idx_matcher.search(last_file)
            if file_idx_match:
                file_idx = file_idx_match.group(1)
                next_file_idx = int(file_idx) + 1
                log.debug("next file index %s", next_file_idx)
            else:
                log.warn("Unable to find file index, starting at 1 again")
                next_file_idx = 1
        else:
            raise Exception("At least one file is needed so we can copy it to make more") 
        
        for i in range(0, num_files):
            time.sleep(delay)
            next_file = self.replace_file_index(dir_files[0], next_file_idx + i)
            log.debug("Create next test file: %s", next_file)
            shutil.copy(dir_files[0], next_file)
            log.debug("Added file %s to directory", next_file)
            
    def replace_file_index(self, original_file, new_index):
        """
        Update a full file path or file name to use a new index
        instead of the original index 
        """
        new_file = None
        # make sure we just have the file name to find numbers in
        original_filename = original_file.split('/')[-1]
        # get the last index of the path so we can add it back at the end
        path_stop_idx = original_file.find(original_filename)
        # find the current file index
        match = re.search("\d+", original_filename)
        if match:
            # turn the index into a string so we can determine how many digits it is
            new_index_str = str(new_index)
            # get indicies for replacing the new index
            start_replace_idx = match.end() - len(new_index_str)
            after_replace_idx = start_replace_idx + len(new_index_str)
            # replace the required digits with the new index
            new_filename = original_filename[:start_replace_idx] + new_index_str + original_filename[after_replace_idx:]
            # add the path back in
            new_file = original_file[:path_stop_idx] + new_filename
        else:
            raise Exception("Error finding integer index in filename")
        return new_file     
    
    def clean_directory(self, data_directory, pattern):
        """
        Clean out the data directory of all files, leaving just the 0 index
        file so we can copy it to make more files
        """
        dir_files = glob.glob(data_directory + '/' + pattern)
        if len(dir_files) > 1:
            dir_files.sort()
            # loop and delete all files, excluding the first one so we can use
            # it for copying and making more files
            for file_name in dir_files:
                # don't delete the first (lowest index) file
                if file_name != dir_files[0]:
                    log.debug("Removing file %s", file_name)
                    os.remove(file_name)

    
