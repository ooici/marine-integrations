#!/usr/bin/env python

"""
@package mi.dataset.test.test_sorting_file_harvester.py
@file mi/dataset/test/test_sorting_file_harvester.py
@author Emily Hahn
@brief Test code to exercize the sorting directory harvester
"""

import os
import gevent
import time
import glob

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.dataset.harvester import SortingDirectoryHarvester

#bin/nosetests -x -v mi/dataset/test/test_sorting_file_harvester.py
TESTDIR = '/tmp/dsatest'
CONFIG = {'directory': TESTDIR,
          'pattern': '*.mrg',
          'exclude'
          'frequency': 1}

INDICIES = ['363_2013_245_6_8', '363_2013_245_6_9', '363_2013_245_6_10', '363_2013_245_6_11', 
            '363_2013_245_7_0', '363_2013_245_7_1', '363_2013_245_7_10', '363_2013_246_0_0',
            '363_2013_246_7_0', '363_2013_246_7_1', '363_2014_12_0_0', '363_2014_12_0_1', ]

@attr('INT', group='eoi')
class TestSortingDirectoryHarvester(MiUnitTest):
    found_file_count = 0

    def setUp(self):
        """
        reset counters and ensure we have test files in place
        """
        log.info('*** Starting test %s ***', self._testMethodName)
        self.found_file_count = 0

        if(not os.path.exists(TESTDIR)):
            os.makedirs(TESTDIR)
        
        # clean directory again in case directory filler went over
        self.clean_directory(TESTDIR, CONFIG['pattern'])

        # Create a file for testing
        open(os.path.join(TESTDIR, "unit_363_2013_245_6_7.mrg"), 'a').close()

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
        file_harvester = SortingDirectoryHarvester(config, memento,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback)
        file_harvester.start()

        # start a new event which will increase the file index using INDICIES
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 0, 2)

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
        file_harvester = SortingDirectoryHarvester(CONFIG, memento,
                                                   self.new_file_found_callback,
                                                   self.file_exception_callback)
        file_harvester.start()
        
        # start a new event which will increase the file index using INDICIES
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 0, 6)
        
        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
         
        file_harvester.shutdown()
        
    def test_harvester_with_memento(self):
        """
        Test that the harvester can find file as they are added to a directory,
        using a memento to start partway through the indices
        """
        
        # make sure we have 2 files already in the directory
        self.fill_directory_with_files(CONFIG['directory'], CONFIG['pattern'], 0, 2, 0)
        
        # start at index 2
        memento = CONFIG['directory'] + '/' + 'unit_' + INDICIES[1] + CONFIG['pattern'].replace('*', '')
        log.debug("starting with memento %s", memento)
        file_harvester = SortingDirectoryHarvester(CONFIG, memento,
                                                   self.new_file_found_callback,
                                                   self.file_exception_callback)
        file_harvester.start()
        
        # start a new event which will increase the file index using INDICIES
        # with a delay in between
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 2, 9)
        
        # Wait for three sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
         
        file_harvester.shutdown()
        
    def test_harvester_multi_file(self):
        """
        Set the timing so the harvester finds multiple new files at once
        """
        
        # start the harvester from scratch
        memento = None
        file_harvester = SortingDirectoryHarvester(CONFIG, memento,
                                                    self.new_file_found_callback,
                                                    self.file_exception_callback)
        file_harvester.start()
        
        # set the file filler to generate files with only .5 secs between,
        # meaning 2 files will appear in the 1 seconds between the
        # harvester checking
        self.directory_filler = gevent.spawn(self.fill_directory_with_files,
                                             CONFIG['directory'],
                                             CONFIG['pattern'], 0, 12, .5)
        
        # Wait for sets of new files to be discovered
        self.wait_for_file(0)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        self.wait_for_file(self.found_file_count)
        
        file_harvester.shutdown()
        
    def test_harvester_exception(self):
        """
        Verify exceptions
        """
        config = "blah"
        self.assertRaises(TypeError, SortingDirectoryHarvester,
                                                        (config, None,
                                                         self.new_file_found_callback,
                                                         self.file_exception_callback))
        
    def wait_for_file(self, starting_count, delay=1, timeout=30):
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
    
    def clean_directory(self, data_directory, pattern):
        """
        Clean out the data directory of all files
        """
        dir_files = glob.glob(data_directory + '/' + pattern)
        if len(dir_files) > 1:
            for file_name in dir_files:
                    log.debug("Removing file %s", file_name)
                    os.remove(file_name)