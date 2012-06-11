#!/usr/bin/env python

"""
@package mi.idk.test.test_ia_client
@file mi/idk/test/test_ia_client.py
@author Bill French
@brief test the instrument agent startup
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mock import Mock
import unittest

from mi.core.log import log
from mi.idk.instrument_agent_client import InstrumentAgentClient

@attr('UNIT', group='mi')
class TestIAStart(unittest.TestCase):
    """
    Test the instrument agent startup
    """
    def setUp(self):
        """
        Setup the test case
        """
        self.ia_client = InstrumentAgentClient()

    def test_container_rabbitmq(self):
        """Test that rabbitmq can be started"""

        self.ia_client.start_rabbitmq_server()
        pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("rabbitmq"))
        self.assertTrue(pid)

        self.ia_client.start_rabbitmq_server()
        new_pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("rabbitmq"))
        self.assertEqual(pid, new_pid)

        self.ia_client.stop_rabbitmq_server()
        pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("rabbitmq"))
        self.assertFalse(pid)


    def test_container_couchdb(self):
        """Test that couchdb can be started"""

        self.ia_client.start_couchdb()
        pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("couchdb"))
        self.assertTrue(pid)

        self.ia_client.start_couchdb()
        new_pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("couchdb"))
        self.assertEqual(pid, new_pid)

        self.ia_client.stop_couchdb()
        pid = self.ia_client._read_pidfile(self.ia_client._pid_filename("couchdb"))
        self.assertFalse(pid)


    def test_container_start(self):
        """Test that a container can be started"""
        self.ia_client.start_container()
        self.assertTrue(self.ia_client.container)
        self.ia_client.stop_container()
        self.assertFalse(self.ia_client.container)






