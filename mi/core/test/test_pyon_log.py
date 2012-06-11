#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os.path import exists
import sys

from pyon.util.log import log as pyon_log
from mi.core.log import log, log_manager
from pyon.util.log import log as pyon_log

from mi.core.test.log_class import debug

from nose.plugins.attrib import attr
from mock import Mock
import unittest

@attr('UNIT', group='mi')
class TestLogger(unittest.TestCase):
    """
    Test the logger object
    """    
    def test_constructor(self):
        """
        Test object creation
        """
        log_manager.set_log_file("/tmp/out")
        log_manager.set_log_level("WARN")

        log.error("error message")
        log.warn("warn message")
        log.info("info message")
        log.debug("debug message")

        log_manager.set_log_level("INFO")
        log.info("info message 2")
        log.debug("debug message 2")

        log_manager.set_log_level("DEBUG")
        log.debug("debug message 3")

    def test_module_logger(self):
        debug("test message")
        pass

    def test_pyon_logger(self):
        #pyon_log.error("Pyon logger message")
        pass


