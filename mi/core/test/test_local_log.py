#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os.path import exists
import sys

from mi.core.log import log

from nose.plugins.attrib import attr
from mock import Mock
import unittest

from mi.idk.exceptions import InvalidParameters

@attr('UNIT', group='mi')
class TestLogger(unittest.TestCase):
    """
    Test the logger object
    """    
    def setUp(self):
        """
        Setup the test case
        """
        
    def test_constructor(self):
        """
        Test object creation
        """
        log.setLevel("DEBUG")
        log.info("boom")
