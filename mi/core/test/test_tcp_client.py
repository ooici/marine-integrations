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

from mi.core.log import get_logger
log = get_logger()

import mock
import re
from nose.plugins.attrib import attr

from mi.core.unit_test import MiUnitTest
from mi.core.tcp_client import TcpClient


@attr('UNIT', group='mi')
class TestTCPClient(MiUnitTest):
    """
    Test the logger object
    """    
    def setUp(self):
        """
        Setup the test case
        """

    def test_expect(self):
        client = TcpClient()
        client.s = mock.Mock()
        client.s.recv.return_value = 'abcdefghi'

        # true if string is found
        self.assertTrue(client.expect('def'))
        # buf should contain only the text following the expected string
        self.assertEqual(client.buf, 'ghi')

    def test_expect_regex(self):
        client = TcpClient()
        client.s = mock.Mock()
        client.s.recv.return_value = 'abcdefghi'

        # un-compiled regex
        # expect_regex returns a match object
        self.assertEqual(client.expect_regex('[def]{3}').group(), 'def')
        # buf should contain only the text following the matched string
        self.assertEqual(client.buf, 'ghi')

        # pre-compiled regex with groups
        result = client.expect_regex(re.compile(r'(abc)(def)'))
        self.assertEqual(result.group(1), 'abc')
        self.assertEqual(result.group(2), 'def')
        self.assertEqual(client.buf, 'ghi')