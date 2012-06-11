#!/usr/bin/env python

"""
@file mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/test_client.py
@author Carlos Rueda
@brief VADCP Client tests
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.client import VadcpClient
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    md_section_names, State
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0 import PD0DataStructure
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import prefix
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import \
    ReceiverBuilder

import time
from mi.core.mi_logger import mi_logger as log

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from nose.plugins.attrib import attr


@attr('UNIT', group='mi')
class Test(VadcpTestCase):

    # this class variable is to keep a single reference to the VadcpClient
    # object in the current test. setUp will first finalize such object in case
    # tearDown/cleanup does not get called. Note that any test with an error
    # will likely make subsequent tests immediately fail because of the
    # potential problem with a second connection.
    _client = None

    @classmethod
    def _end_client_if_any(cls):
        """Ends the current VadcpClient, if any."""
        if Test._client:
            log.info("releasing not finalized VadcpClient object")
            try:
                Test._client.end()
            finally:
                Test._client = None

    @classmethod
    def tearDownClass(cls):
        """Make sure we end the last VadcpClient object if still remaining."""
        try:
            cls._end_client_if_any()
        finally:
            super(Test, cls).tearDownClass()

    def setUp(self):
        """
        Sets up and connects the _client.
        """

        ReceiverBuilder.use_greenlets()

        Test._end_client_if_any()

        super(Test, self).setUp()

        self._ensembles_recd = 0

        conn_config = self._conn_config[self._vadcp_unit]
        outfilename = 'vadcp_output_%s_%s.txt' % (conn_config.host, conn_config.port)
        outfile = file(outfilename, 'w')
        prefix_state = True
        Test._client = VadcpClient(conn_config, outfile, prefix_state)

        # prepare client including going to the main menu
        Test._client.set_generic_timeout(self._timeout)

        log.info("connecting")
        Test._client.set_data_listener(self._data_listener)
        Test._client.connect()

    def tearDown(self):
        """
        Ends the _client.
        """
        ReceiverBuilder.use_default()
        client = Test._client
        Test._client = None
        try:
            if client:
                log.info("ending VadcpClient object")
                client.end()
        finally:
            super(Test, self).tearDown()

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
        sections = None  # None => all sections
        result = self._client.get_metadata(sections)
        self.assertTrue(isinstance(result, dict))
        s = ''
        for name, text in result.items():
            self.assertTrue(name in md_section_names)
            s += "**%s:%s\n\n" % (name, prefix(text, "\n    "))
        log.info("METADATA result=%s" % prefix(s))

    def test_execute_run_recorder_tests(self):
        result = self._client.run_recorder_tests()
        log.info("run_recorder_tests result=%s" % prefix(result))

    def test_all_tests(self):
        result = self._client.run_all_tests()
        log.info("ALL TESTS result=%s" % prefix(result))

    def test_start_and_stop_autosample(self):
        self._ensembles_recd = 0
        if State.COLLECTING_DATA != self._client.get_current_state():
            result = self._client.start_autosample()
            log.info("start_autosample result=%s" % result)

        self.assertEqual(State.COLLECTING_DATA, self._client.get_current_state())

        time.sleep(6)
        log.info("ensembles_recd = %s" % self._ensembles_recd)

        result = self._client.stop_autosample()
        log.info("stop_autosample result=%s" % result)

        self.assertEqual(State.PROMPT, self._client.get_current_state())
