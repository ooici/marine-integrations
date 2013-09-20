#!/usr/bin/env python

"""
@package mi.idk.dataset.test.test_metadata
@file mi.idk/dataset/test/test_metadata.py
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
from mi.idk.dataset.metadata import Metadata

from mi.idk.exceptions import InvalidParameters
import os

BASE_DIR = "/tmp"
DRIVER_PATH = "test_driver/foo"
METADATA_DIR = "/tmp/mi/dataset/driver/test_driver/foo"
METADATA_FILE = "metadata.yml"

@attr('UNIT', group='mi')
class TestMetadata(MiUnitTest):
    """
    Test the metadata object
    """    
    def setUp(self):
        """
        Setup the test case
        """
        self.createMetadataFile()


    def createMetadataFile(self):
        """
        """
        self.addCleanup(self.removeMetadataFile)

        if(not exists(METADATA_DIR)):
            os.makedirs(METADATA_DIR)
        md_file = open("%s/%s" % (METADATA_DIR, METADATA_FILE), 'w')

        md_file.write("driver_metadata:\n")
        md_file.write("  author: Bill French\n")
        md_file.write("  driver_path: test_driver/foo\n")
        md_file.write("  driver_name: test_driver_foo\n")
        md_file.write("  email: wfrench@ucsd.edu\n")
        md_file.write("  release_notes: some note\n")
        md_file.write("  version: 0.2.2\n")

        md_file.close()


    def removeMetadataFile(self):
        filename = "%s/%s" % (METADATA_DIR, METADATA_FILE)
        if(exists(filename)):
            pass
            #os.unlink(filename)


    def test_constructor(self):
        """
        Test object creation
        """
        default_metadata = Metadata()
        self.assertTrue(default_metadata)
        
        specific_metadata = Metadata(DRIVER_PATH, BASE_DIR)
        self.assertTrue(specific_metadata)
        self.assertTrue(os.path.isfile(specific_metadata.metadata_path()), msg="file doesn't exist: %s" % specific_metadata.metadata_path())

        self.assertEqual(specific_metadata.driver_path, "test_driver/foo")
        self.assertEqual(specific_metadata.driver_name, "test_driver_foo")
        self.assertEqual(specific_metadata.author, "Bill French")
        self.assertEqual(specific_metadata.email, "wfrench@ucsd.edu")
        self.assertEqual(specific_metadata.notes, "some note")
        self.assertEqual(specific_metadata.version, "0.2.2")


