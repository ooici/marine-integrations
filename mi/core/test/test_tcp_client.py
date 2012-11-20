#!/usr/bin/env python

"""
@package mi.core.test.test_tcp_client
@file mi/core/test/test_tcp_client.py
@author Bill French
@brief Test class for the TCPClient Modules
provides unit tests for the TCPClient.  When the TCP client was written there were no tests.  We should add
unit test whenever we touch this code.
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os.path import exists
import sys

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
import unittest

from mi.core.tcp_client import TcpClient


@attr('UNIT', group='mi')
class TestTCPClient(unittest.TestCase):
    """
    Test the logger object
    """    
    def setUp(self):
        """
        Setup the test case
        """

    def test_remove_from_buffer(self):
        """
        Test the remove from buffer method.  Verify that all bytes before the match string are removed.
        """
        client = TcpClient()
        target = "MATCH"

        # Remove with an None target
        self.assertFalse(client.remove_from_buffer(None))

        # Remove with a zero length target
        self.assertFalse(client.remove_from_buffer(""))

        # Remove from buffer when buffer empty
        client.buf = None
        self.assertFalse(client.remove_from_buffer(target))
        self.assertIsNone(client.buf)

        # Remove from buffer when target the only thing in the list
        client.buf = target
        self.assertTrue(client.remove_from_buffer(target))
        self.assertEqual(len(client.buf), 0)

        # Remove from buffer when target the last thing in the list
        client.buf = "foo" + target
        self.assertTrue(client.remove_from_buffer(target))
        self.assertEqual(len(client.buf), 0)

        # Remove from buffer when target in the middle
        client.buf = "foo" + target + "remains"
        self.assertTrue(client.remove_from_buffer(target))
        self.assertEqual(client.buf, "remains")

        # Remove from buffer when target not in the buff
        client.buf = "target not in the list"
        self.assertFalse(client.remove_from_buffer(target))
        self.assertEqual(client.buf, "target not in the list")

        # Remove from buffer when target in the list more than once        client.buf = "foo" + target + "remains"
        client.buf = "foo" + target + "remains" + target
        self.assertTrue(client.remove_from_buffer(target))
        self.assertEqual(client.buf, "remains" + target)


