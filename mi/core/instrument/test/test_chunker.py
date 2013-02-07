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
from mi.core.unit_test import MiUnitTest, MiUnitTestCase
import re
from nose.plugins.attrib import attr
from pyon.util.unit_test import IonUnitTestCase
from ooi.logging import log

from mi.core.exceptions import SampleException
from mi.core.instrument.chunker import StringChunker

@attr('UNIT', group='mi')
class UnitTestStringChunker(MiUnitTestCase):
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
    
    TIMESTAMP_1 = 3569168821.102485
    TIMESTAMP_2 = 3569168822.202485
    TIMESTAMP_3 = 3569168823.302485
    
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
        for (s, e, t) in chunk_list:
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
        self._chunker.add_chunk(sample_string, self.TIMESTAMP_1)
        
        lists = self._chunker._generate_data_lists(self.TIMESTAMP_1)
        log.debug("Data chunk list: %s",
                  self._display_chunk_list(sample_string,
                                          lists['data_chunk_list']))
        self.assertEquals(lists['data_chunk_list'], [(3,34, self.TIMESTAMP_1),
                                                     (37, 68, self.TIMESTAMP_1)])
        log.debug("Non-data chunk list: %s",
                  self._display_chunk_list(sample_string,
                                          lists['non_data_chunk_list']))        
        self.assertEquals(lists['non_data_chunk_list'],
                          [(0, 3, self.TIMESTAMP_1),
                           (34, 37, self.TIMESTAMP_1)])        
        
    def test_clean_chunk_list(self):
        test_str = "abcdefghijklmnopqrstuvwxyz"
        short_test_str = test_str[10:]
        test_list = [(3, 5, self.TIMESTAMP_1),
                     (8, 12, self.TIMESTAMP_2),
                     (20, 25, self.TIMESTAMP_3)]
        log.debug("Test string: %s", test_str)
        log.debug("Raw list: %s", self._display_chunk_list(test_str, test_list))
        result = self._chunker._clean_chunk_list(test_list, 10)
        log.debug("Shortened test string: %s", short_test_str)
        log.debug("Cleaned list: %s", self._display_chunk_list(short_test_str,
                                                              result))
        self.assertEquals(result, [(0, 2, self.TIMESTAMP_2),
                                   (10, 15, self.TIMESTAMP_3)])        
    
    def test_add_get_simple(self):
        """
        Add a simple string of data to the buffer, get the next chunk out
        """
        self._chunker.add_chunk(self.SAMPLE_1, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, self.TIMESTAMP_1)
        self.assertEquals(result, self.SAMPLE_1)
        
        # It got cleared at the last fetch...
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, None)
        self.assertEquals(result, None)

        (time, result) = self._chunker.get_next_non_data()
        self.assertEquals(time, None)
        self.assertEquals(result, None)
        
    def test_no_clean_data(self):
        """
        Test an add/get without cleaning
        """
        self._chunker.add_chunk(self.SAMPLE_1, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data(clean=False)
        self.assertEquals(result, self.SAMPLE_1)
        self.assertEquals(time, self.TIMESTAMP_1)
        
        # It did NOT get cleared at the last fetch...
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        self.assertEquals(time, self.TIMESTAMP_1)
        
        # and now it did
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(result, None)
    
    def test_add_many_get_simple(self):
        """
        Add a few simple strings of data to the buffer, get the chunks out
        """
        self._chunker.add_chunk(self.SAMPLE_1, self.TIMESTAMP_1)
        self._chunker.add_chunk(self.SAMPLE_2, self.TIMESTAMP_2)
        self._chunker.add_chunk(self.SAMPLE_3, self.TIMESTAMP_3)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, self.TIMESTAMP_1)
        self.assertEquals(result, self.SAMPLE_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, self.TIMESTAMP_2)
        self.assertEquals(result, self.SAMPLE_2)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, self.TIMESTAMP_3)
        self.assertEquals(result, self.SAMPLE_3)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(time, None)

    def test_get_non_data(self):
        """
        Get some non-data blocks
        """
        self._chunker.add_chunk("Foo", self.TIMESTAMP_1)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 0)
        self._chunker.add_chunk(self.SAMPLE_1, self.TIMESTAMP_2)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)        
        self._chunker.add_chunk("Bar", self.TIMESTAMP_2)
        self._chunker.add_chunk("Bat", self.TIMESTAMP_3)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 2)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)
        self._chunker.add_chunk(self.SAMPLE_2, self.TIMESTAMP_2)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 2)
        self.assertEquals(len(self._chunker.data_chunk_list), 2)
        self._chunker.add_chunk("Baz", self.TIMESTAMP_1)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 3)
        self.assertEquals(len(self._chunker.data_chunk_list), 2)

        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        self.assertEquals(time, self.TIMESTAMP_2)
        (time, result) = self._chunker.get_next_non_data()
        self.assertEquals(result, "BarBat")
        self.assertEquals(time, self.TIMESTAMP_2)
        (time, result) = self._chunker.get_next_non_data()
        self.assertEquals(result, "Baz")
        self.assertEquals(time, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(time, None)
    
    def test_add_get_fragment(self):
        """
        Add some fragments of a string, then verify that value is stitched together
        """
        # Add a part of a sample
        self._chunker.add_chunk(self.FRAGMENT_1, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, None)
        self.assertEquals(result, None)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 1)
        self.assertEquals(len(self._chunker.data_chunk_list), 0)
        
        # add the rest of the sample
        self._chunker.add_chunk(self.FRAGMENT_2, self.TIMESTAMP_2)
        self.assertEquals(len(self._chunker.nondata_chunk_list), 0)
        self.assertEquals(len(self._chunker.data_chunk_list), 1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, self.FRAGMENT_SAMPLE)
        self.assertEquals(time, self.TIMESTAMP_1)
            
    def test_add_multiple_in_one(self):
        """
        Test multiple data bits input in a single sample. They will ultimately
        need to be split apart.
        """
        self._chunker.add_chunk(self.MULTI_SAMPLE_1, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, self.SAMPLE_1)
        self.assertEquals(time, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(time, self.TIMESTAMP_1)
        self.assertEquals(result, self.SAMPLE_2)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(time, None)
        
    def test_get_raw(self):
        """
        Test the ability to get raw data, but not totally hose data strings
        """
        # Put some data fragments in
        self._chunker.add_chunk("Foo", self.TIMESTAMP_1)
        self._chunker.add_chunk(self.SAMPLE_1, self.TIMESTAMP_2)
        self._chunker.add_chunk(self.FRAGMENT_1, self.TIMESTAMP_2)
        self._chunker.add_chunk(self.FRAGMENT_2, self.TIMESTAMP_3) 
        self._chunker.add_chunk("Baz", self.TIMESTAMP_1)
        
        # Get a raw chunk out
        (time, result) = self._chunker.get_next_raw()
        self.assertEquals(result, "Foo")
        self.assertEquals(time, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_raw()
        self.assertEquals(result, self.SAMPLE_1)        
        self.assertEquals(time, self.TIMESTAMP_2)        
        (time, result) = self._chunker.get_next_raw()
        self.assertEquals(result, self.FRAGMENT_1) # Fragments got ripped up
        self.assertEquals(time, self.TIMESTAMP_2)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, None)
        self.assertEquals(time, None)
        
    def test_funky_chunks(self):
        def funky_sieve(data):
            return [(3,6),(0,3)]

        self._chunker = StringChunker(funky_sieve)
        self._chunker.add_chunk("BarFoo", self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, "Bar")
        self.assertEquals(time, self.TIMESTAMP_1)
        (time, result) = self._chunker.get_next_data()
        self.assertEquals(result, "Foo")
        self.assertEquals(time, self.TIMESTAMP_1)        
        
    def test_overlap(self):
        self.assertFalse(StringChunker.overlaps([(0, 5)]))
        self.assertFalse(StringChunker.overlaps([]))
        self.assertTrue(StringChunker.overlaps([(0, 5), (3, 6)]))
        self.assertTrue(StringChunker.overlaps([(0, 5), (5, 7), (6, 8)]))
        self.assertTrue(StringChunker.overlaps([(0, 5), (6, 9), (5, 7)]))

        def overlap_sieve(data):
            return [(0,3),(2,6)]

        self._chunker = StringChunker(overlap_sieve)
        self.assertRaises(SampleException,
                          self._chunker.add_chunk, "foobar", self.TIMESTAMP_1)

@unittest.skip("Write this when a binary chunker is needed")
@attr('UNIT', group='mi')
class UnitTestBinaryChunker(MiUnitTestCase):
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
    
