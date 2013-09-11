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

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.dataset.harvester import SingleFileHarvester

#bin/nosetests -x -v mi/dataset/test/test_single_file_harvester
TESTDIR = '/tmp/dsatest'
FILENAME = 'testfile.txt'
CONFIG = {'directory': TESTDIR,
          'filename': FILENAME,
          'frequency': 2}


@attr('INT', group='eoi')
class TestExternalDatasetHarvester(MiUnitTest):
    data_found = False
    current_offset = 0
    
    def setUp(self):
        """
        reset counters and ensure we have test files in place
        """
        log.info('*** Starting test %s ***', self._testMethodName)
        self.data_found = False
        self.current_offset = 0

        if(not os.path.exists(TESTDIR)):
            os.makedirs(TESTDIR)

        # Create a file for testing
        open(os.path.join(TESTDIR, FILENAME), 'a').close()

    def tearDown(self):
        """
        Cleanup files we have created
        """
        if os.path.isfile(os.path.join(TESTDIR, FILENAME)):
            os.remove(os.path.join(TESTDIR, FILENAME))
        
    def test_harvester_from_scratch(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start the harvester from scratch
        file_offset = None
        file_harvester = SingleFileHarvester(CONFIG, file_offset,
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()
        
        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG['directory'],
                                             CONFIG['filename'], 2)
        
        # Wait for three lines of new data to be discovered
        self.wait_for_data()
        self.wait_for_data()
         
        file_harvester.shutdown()
        
    def test_harvester_with_initial_data(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start with 2 lines in the file
        self.fill_file_with_data(CONFIG['directory'], CONFIG['filename'], 2, 0)
        
        # start the harvester with data in the file
        file_offset = None
        file_harvester = SingleFileHarvester(CONFIG, file_offset,
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()
        
        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG['directory'],
                                             CONFIG['filename'], 1)
        
        # Wait for three lines of new data to be discovered
        self.wait_for_data()
        self.wait_for_data()
         
        file_harvester.shutdown()
        
    def test_harvester_with_offset(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start with 2 lines in the file
        self.fill_file_with_data(CONFIG['directory'], CONFIG['filename'], 2, 0)
        
        # start the harvester at the end of the current data
        self.current_offset = 32
        file_offset = 32
        file_harvester = SingleFileHarvester(CONFIG, file_offset,
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()
        
        # start a new event which will write new lines of data into the file
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG['directory'],
                                             CONFIG['filename'], 2)
        
        # Wait for lines of new data to be discovered
        self.wait_for_data()
        self.wait_for_data()
         
        file_harvester.shutdown()
        
    def test_harvester_multi_line(self):
        """
        Test that the harvester can find files as they are added to a directory,
        starting with just the base file in the directory
        """
        # start the harvester from scratch
        file_offset = None
        file_harvester = SingleFileHarvester(CONFIG, file_offset,
                                             self.new_data_found_callback,
                                             self.harvester_exception_callback)
        file_harvester.start()
        
        # set the filler to write 1 line just under every second, meaning that 2 lines will
        # appear for each wait_for_data
        self.file_filler = gevent.spawn(self.fill_file_with_data,
                                             CONFIG['directory'],
                                             CONFIG['filename'], 4, .9)
        
        # Wait for lines of new data to be discovered
        self.wait_for_data()
        self.wait_for_data()
         
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
        
    def new_data_found_callback(self, file_handle, file_size):
        """
        Callback when a new file is found by the harvester.  This should pass the file
        to the parser, but from this test we don't have the parser, so just close the file. 
        """

        bytes_to_read = file_size - self.current_offset
        data = file_handle.read(bytes_to_read)
        file_handle.close()
        self.data_found = True
        log.info("Read new data from %d to %d: %s", self.current_offset, file_size, data)
        self.current_offset = file_size
    
    def harvester_exception_callback(self, exception):
        """
        Callback if there is an exception in the harvester, just raise an exception
        """
        log.error("Error polling for files: %s", exception)
        raise Exception("Error polling for files: %s", exception)
    
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
            
    def wait_for_data(self, delay=2, timeout=60):
        """
        Wait for a new round of files to be discovered
        """
        end_time = 0
        while(not self.data_found):
            log.debug("Waiting for next data...")
            time.sleep(delay)
            end_time += delay
            if end_time > timeout:
                raise Exception("Timeout waiting to find data")
        self.data_found = False



