#!/usr/bin/env python

"""
@package mi.dataset.test.test_parser Base dataset parser test code
@file mi/dataset/test/test_driver.py
@author Emily Hahn
@brief Test code for the dataset parser base classes and common structures for
testing parsers.
"""
import os

from mi.core.exceptions import DatasetParserException
from mi.core.unit_test import MiUnitTestCase
from mi.idk.config import Config
from mi.idk.result_set import ResultSet

BASE_RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver')


# Shared parser unit test suite
class ParserUnitTestCase(MiUnitTestCase):

    def setUp(self):
        """
        Initial set up which will run at the start of each nosetest.
        An additional setUp should be defined in each parser unit test sub 
        class, which calls this setUp.
        """
        # call the parent class setUp
        MiUnitTestCase.setUp(self)

        # clear the publish and exception callback values
        self.publish_callback_value = None
        self.exception_callback_value = []

    def publish_callback(self, publish):
        """
        Watch what comes back through the publish callback

        @param publish particles that have been published
        """
        self.publish_callback_value = publish

    def exception_callback(self, exception):
        """
        Store any exceptions that come into the exception callback

        @param exception The exception that occurred
        """
        self.exception_callback_value.append(exception)

    def assert_particles(self, particles, yml_file, resource_path=None):
        """
        Assert that the contents of the particles match those in the results
        yaml file.

        @param particles either a DataParticle sub-class or particle dictionary 
        to compare with the particles in the .yml file
        @param yml_file the .yml file name or full path containing particles
        to compare
        @param resource_path the path to the .yml file, used only if yml_file
        does not contain the full path 
        """

        # see if .yml file has the full path
        if os.path.exists(yml_file):
            rs_file = yml_file
        # if not the full path, check if resource path was defined
        elif resource_path is not None:
            rs_file = os.path.join(resource_path, yml_file)
        # out of places to check for the file, raise an error
        else:
            raise DatasetParserException('Test yaml file cannot be found to assert particles')

        # initialize result set with this .yml results file
        rs = ResultSet(rs_file)
        # compare results particles and assert that the output was successful
        self.assertTrue(rs.verify(particles),
                        msg=('Failed unit test data validation for file %s' % yml_file))
