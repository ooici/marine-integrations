#! /usr/bin/env python

"""
@file ion/core/unit_test.py
@author Bill French
@brief Base test class for all MI tests.  Provides two base classes, 
One for pyon tests and one for stand alone MI tests. 

We have the stand alone test case for tests that don't require or can't
integrate with the common ION test case.
"""

from unittest import TestCase

class MIUnitTest(unittest.TestCase):
    """
    Base class for non-ion tests.  Use only if needed to avoid ion 
    test common code.
    """


class IONTestCase(IonIntegrationTestCase):
    """
    Base class for most tests in MI.
    """
