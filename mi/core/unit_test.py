#! /usr/bin/env python

"""
@file ion/core/unit_test.py
@author Bill French
@brief Base test class for all MI tests.  Provides two base classes, 
One for pyon tests and one for stand alone MI tests. 

We have the stand alone test case for tests that don't require or can't
integrate with the common ION test case.
"""


import unittest
from pyon.util.unit_test import IonUnitTestCase
from pyon.util.unit_test import PyonTestCase
from pyon.util.int_test  import IonIntegrationTestCase


class MiUnitTest(unittest.TestCase):
    """
    Base class for non-ion tests.  Use only if needed to avoid ion 
    test common code.
    """
    def shortDescription(self):
        return None


class MiUnitTestCase(IonUnitTestCase):
    """
    Base class for most tests in MI.
    """
    def shortDescription(self):
        return None

    def test_verify_service(self):
        pass

class MiTestCase(PyonTestCase):
    """
    Base class for most tests in MI.
    """
    def shortDescription(self):
        return None

    def test_verify_service(self):
        pass

class MiIntTestCase(IonIntegrationTestCase):
    """
    Base class for most tests in MI.
    """

    def shortDescription(self):
        return None

