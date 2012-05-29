#!/usr/bin/env python

"""
@file ion/services/mi/drivers/vadcp/test/test_client.py
@author Carlos Rueda
@brief VADCP Client tests
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import Client
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import MetadataSections
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import md_section_names
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import State
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0 import PD0DataStructure
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import prefix

from mi.core.mi_logger import mi_logger
log = mi_logger

import time
import datetime

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from nose.plugins.attrib import attr

import unittest
import os


@unittest.skipIf(os.getenv('run_it') is None,
'''Not run by default because of mixed monkey-patching issues. \
Define environment variable run_it to force execution.''')
@attr('UNIT', group='mi')
class ClientTest(VadcpTestCase):

    # this class variable is to keep a single reference to the Client
    # object in the current test. setUp will first finalize such object in case
    # tearDown/cleanup does not get called. Note that any test with an error
    # will likely make subsequent tests immediately fail because of the
    # potential problem with a second connection.
    _client = None

    @classmethod
    def _end_client_if_any(cls):
        """Ends the current Client, if any."""
        if ClientTest._client:
            log.info("releasing not finalized Client object")
            try:
                ClientTest._client.end()
            finally:
                ClientTest._client = None

    @classmethod
    def tearDownClass(cls):
        """Make sure we end the last Client object if still remaining."""
        try:
            cls._end_client_if_any()
        finally:
            super(ClientTest, cls).tearDownClass()

    def setUp(self):
        """
        Sets up and connects the _client.
        """

        ClientTest._end_client_if_any()

        super(ClientTest, self).setUp()

        host = self.device_address
        port = self.device_port
        self._ensembles_recd = 0
        outfile = file('vadcp_output.txt', 'w')
        prefix_state = True
        _client = Client(host, port, outfile, prefix_state)

        # set the class and instance variables to refer to this object:
        ClientTest._client = self._client = _client

        # prepare client including going to the main menu
        _client.set_data_listener(self._data_listener)
        _client.set_generic_timeout(self._timeout)

        log.info("connecting")
        _client.connect()

    def tearDown(self):
        """
        Ends the _client.
        """
        client = ClientTest._client
        ClientTest._client = None
        try:
            if client:
                log.info("ending Client object")
                client.end()
        finally:
            super(ClientTest, self).tearDown()

    def _data_listener(self, pd0):
        self._ensembles_recd += 1
        log.info("_data_listener: received PD0=%s" % prefix(pd0))

    def test_connect_disconnect(self):
        state = self._client.get_current_state()
        log.info("current instrument state: %s" % str(state))

    def test_get_latest_ensemble(self):
        pd0 = self._client.get_latest_ensemble()
        self.assertTrue(pd0 is None or isinstance(pd0, PD0DataStructure))

    def test_get_metadata(self):
        sections = None  # all sections
        result = self._client.get_metadata(sections)
        self.assertTrue(isinstance(result, dict))
        s = ''
        for name, text in result.items():
            self.assertTrue(name in md_section_names)
            s += "**%s:%s\n\n" % (name, prefix(text, "\n    "))
        log.info("METADATA result=%s" % prefix(s))

    def test_all_tests(self):
        result = self._client.run_all_tests()
        log.info("ALL TESTS result=%s" % prefix(result))

