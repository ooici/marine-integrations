#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_chunker
@file mi/core/instrument/test/test_chunker.py
@author Steve Foley
@brief Test cases for the base chunker module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import unittest
import re
from nose.plugins.attrib import attr
from pyon.util.unit_test import IonUnitTestCase
from ooi.logging import log

from mi.core.instrument.chunker import StringChunker

@attr('UNIT', group='mi')
class UnitTestStringChunker(IonUnitTestCase):
    """
    Test the basic functionality of the chunker system via unit tests
    """
    # For testing, use PAR sensor data here...short and easy to work with...
    # But cheat with the checksum. Make it easy to recognize which sample
    SAMPLE_1 = "SATPAR0229,10.01,2206748111,111"
    SAMPLE_2 = "SATPAR0229,10.02,2206748222,222"
    SAMPLE_3 = "SATPAR0229,10.03,2206748333,333"
    
    FRAGMENT_1 = "SATPAR0229,10.01,"
    FRAGMENT_2 = "2206748544,123"
    FRAGMENT_SAMPLE = FRAGMENT_1+FRAGMENT_2
    
    MULTI_SAMPLE_1 = "%s\r\n%s" % (SAMPLE_1,
                                   SAMPLE_2)
    
    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        return_list = []
        pattern = r'SATPAR(?P<sernum>\d{4}),(?P<timer>\d{1,7}.\d\d),(?P<counts>\d{10}),(?P<checksum>\d{1,3})'
        regex = re.compile(pattern)
        
        for match in regex.finditer(raw_data):
            return_list.append((match.start(), match.end()))        
            log.debug("Sieving: %s...%s",
                      raw_data[match.start():match.start()+5],
                      raw_data[match.end()-5:match.end()])
                
        return return_list
    
    
    def setUp(self):
        """ Setup a chunker for use in tests """
        self._chunker = StringChunker(UnitTestStringChunker.sieve_function)
        
    def _display_chunk_list(self, data, chunk_list):
        """ Display the data as viewed through the chunk list """
        data_list = []
        if chunk_list == None:
            return data_list
        for (s, e) in chunk_list:
            data_list.append(data[s:e])
        return data_list
    
    def test_sieve(self):
        """
        Do a quick test of the sieve to make sure it does what we want.
        """
        self.assertEquals([(0,31)],
                          UnitTestStringChunker.sieve_function(self.SAMPLE_1))
        self.assertEquals([],
                          UnitTestStringChunker.sieve_function(self.FRAGMENT_1))
        self.assertEquals([(0,31), (33, 64)],
                          UnitTestStringChunker.sieve_function(self.MULTI_SAMPLE_1))
        
    def test_generate_data_lists(self):
        sample_string = "Foo%sBar%sBat" % (self.SAMPLE_1, self.SAMPLE_2)
        self._chunker.add_chunk(sample_string)
        
        lists = self._chunker._generate_data_lists()
        log.debug("Data chunk list: %s",
                  self._display_chunk_list(sample_string,
                                          lists['data_chunk_list']))
        self.assertEquals(lists['data_chunk_list'], [(3,34), (37, 68)])
        log.debug("Non-data chunk list: %s",
                  self._display_chunk_list(sample_string,
                                          lists['non_data_chunk_list']))        
        self.assertEquals(lists['non_data_chunk_list'], [(0, 3), (34, 37)])        
        
    def test_clean_chunk_list(self):
        test_str = "abcdefghijklmnopqrstuvwxyz"
        short_test_str = test_str[10:]
        test_list = [(3, 5), (8, 12), (20, 25)]
        log.debug("Test string: %s", test_str)
        log.debug("Raw list: %s", self._display_chunk_list(test_str, test_list))
        result = self._chunker._clean_chunk_list(test_list, 10)
        log.debug("Shortened test string: %s", short_test_str)
        log.debug("Cleaned list: %s", self._display_chunk_list(short_test_str,
                                                              result))
        self.assertEquals(result, [(0, 2), (10, 15)])        
    
    def test_add_get_simple(self):
        """
        Add a simple string of data to the buffer, get the next chunk out
        """
        self._chunker.add_chunk(self.SAMPLE_1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        
        # It got cleared at the last fetch...
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        result = self._chunker.get_next_non_data()
        self.assertEquals(result, None)
        
    def test_no_clean_data(self):
        """
        Test an add/get without cleaning
        """
        self._chunker.add_chunk(self.SAMPLE_1)
        result = self._chunker.get_next_data(clean=False)
        self.assertEquals(result, self.SAMPLE_1)
        
        # It did NOT get cleared at the last fetch...
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        
        # and now it did
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
    
    def test_add_many_get_simple(self):
        """
        Add a few simple strings of data to the buffer, get the chunks out
        """
        self._chunker.add_chunk(self.SAMPLE_1)
        self._chunker.add_chunk(self.SAMPLE_2)
        self._chunker.add_chunk(self.SAMPLE_3)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_2)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_3)
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
    
    def test_get_non_data(self):
        """
        Get some non-data blocks
        """
        self._chunker.add_chunk("Foo")
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 0)
        self._chunker.add_chunk(self.SAMPLE_1)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)        
        self._chunker.add_chunk("Bar")
        self._chunker.add_chunk("Bat")
        self.assertEquals(len(self._chunker.nondata_chunk_list), 2)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)
        self._chunker.add_chunk(self.SAMPLE_2)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 2)
        self.assertEquals(len(self._chunker.data_chunk_list), 2)
        self._chunker.add_chunk("Baz")
        self.assertEquals(len(self._chunker.nondata_chunk_list), 3)
        self.assertEquals(len(self._chunker.data_chunk_list), 2)

        
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        result = self._chunker.get_next_non_data()
        self.assertEquals(result, "BarBat")
        result = self._chunker.get_next_non_data()
        self.assertEquals(result, "Baz")
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
    
    def test_add_get_fragment(self):
        """
        Add some fragments of a string, then verify that value is stitched together
        """
        # Add a part of a sample
        self._chunker.add_chunk(self.FRAGMENT_1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 0)
        
        # add the rest of the sample
        self._chunker.add_chunk(self.FRAGMENT_2)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 0)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.FRAGMENT_SAMPLE)
            
    def test_add_multiple_in_one(self):
        """
        Test multiple data bits input in a single sample. They will ultimately
        need to be split apart.
        """
        self._chunker.add_chunk(self.MULTI_SAMPLE_1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        result = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_2)
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
        
    def test_get_raw(self):
        """
        Test the ability to get raw data, but not totally hose data strings
        """
        # Put some data fragments in
        self._chunker.add_chunk("Foo")
        self._chunker.add_chunk(self.SAMPLE_1)
        self._chunker.add_chunk(self.FRAGMENT_1)
        self._chunker.add_chunk(self.FRAGMENT_2) 
        self._chunker.add_chunk("Baz")
        
        # Get a raw chunk out
        result = self._chunker.get_next_raw()
        self.assertEquals(result, "Foo")
        result = self._chunker.get_next_raw()
        self.assertEquals(result, self.SAMPLE_1)        
        result = self._chunker.get_next_raw()
        self.assertEquals(result, self.FRAGMENT_1) # Fragments got ripped up
        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
                
@unittest.skip("Write this when a binary chunker is needed")
@attr('UNIT', group='mi')
class UnitTestBinaryChunker(IonUnitTestCase):
    """
    Test the basic functionality of the chunker system via unit tests
    """
    SAMPLE_1 = []
    SAMPLE_2 = []
    SAMPLE_3 = []
    
    FRAGMENT_1 = []
    FRAGMENT_2 = []
    
    MULTI_SAMPLE_1 = []
    
    def test_add_get_simple(self):
        """
        Add a simple string of data to the buffer, get the next chunk out
        """
        pass
    
    def test_add_get_many_simple(self):
        """
        Add a few simple strings of data to the buffer, get the chunks out
        """
        # Add a sample,
        # Add a sample
        # Add another sample
        # get some samples out,
        # assert they were correct and in the right order
        pass
    
    def test_add_get_fragment(self):
        """
        Add some fragments of a string, then verify that value is stitched together
        """
        # Add a part of a sample
        # confirm you cant get anything out
        # add the rest of the sample
        # confirm that the rest comes out
        pass
    
    def test_add_multiple_in_one(self):
        """
        Test multiple data bits input in a single sample. They will ultimately
        need to be split apart.
        """
        pass
    
