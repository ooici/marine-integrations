#!/usr/bin/env python

"""
@package mi.idk.test.test_metadata
@file mi.idk/test/test_metadata.py
@author Bill French
@brief test metadata object
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os.path import exists
import sys

from nose.plugins.attrib import attr
from mock import Mock
import unittest
from mi.core.unit_test import MiUnitTest

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.metadata import Metadata

from mi.idk.exceptions import InvalidParameters

@attr('UNIT', group='mi')
class TestMetadata(MiUnitTest):
    """
    Test the metadata object
    """    
    def setUp(self):
        """
        Setup the test case
        """
        
    def test_constructor(self):
        """
        Test object creation
        """
        default_metadata = Metadata()
        self.assertTrue(default_metadata)
        
        specific_metadata = Metadata('seabird','sbe37smb','ooicore');
        self.assertTrue(specific_metadata)
        
        failure_metadata = None;
        try:
            failure_metadata = Metadata('seabird');
        except InvalidParameters, e:
            self.assertTrue(e)
        self.assertFalse(failure_metadata)
