#!/usr/bin/env python

"""
@package mi.dataset.parsers.test.test_ctdpf Base dataset parser test code
@file mi/dataset/parsers/test/test_ctdpf.py
@author Steve Foley
@brief Test code for a CTDPF data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""
from mi.core.unit_test import MiUnitTestCase, MiIntTestCase

# Add a mixin here if needed

@attr('UNIT', group='mi')
class CtdpfParserUnitTestCase(ParserUnitTestCase):
    """
    CTDPF Parser unit test suite
    """
    TEST_DATA = """
* Sea-Bird SBE52 MP Data File *

** Starting profile number 42 **
10/01/2011 03:16:01
GPS1:
GPS2:
 42.2095, 13.4344,  143.63,   2830.2
 42.2102, 13.4346,  143.63,   2831.1
 42.2105, 13.4352,  143.63,   2830.6
 42.2110, 13.4350,  143.62,   2831.5
 42.2110, 13.4347,  143.62,   2832.1
 42.2105, 13.4352,  143.63,   2831.5
 42.2107, 13.4354,  143.62,   2832.7
 42.2112, 13.4355,  143.62,   2832.3
 42.2105, 13.4347,  143.63,   2833.5
 42.2110, 13.4352,  143.62,   2834.2
"""
    
    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {}
        self.position = DataSourcePosition()
        self.parser = CtdpfParser(config)
        
    def test_happy_path(self):
        """
        Test the happy path of operations where the parser takes the input
        and spits out a valid data particle given the stream.
        """
