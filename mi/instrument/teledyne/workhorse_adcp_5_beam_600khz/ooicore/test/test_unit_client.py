#!/usr/bin/env python

"""
@file mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/test_unit_client.py
@author Carlos Rueda
@brief Tests for a VADCP unit.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.unit_client import UnitClient
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0 import PD0DataStructure
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    md_section_names, State
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import prefix
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import ReceiverBuilder

import time
from mi.core.mi_logger import mi_logger as log

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from nose.plugins.attrib import attr


@attr('UNIT', group='mi')
class Test(VadcpTestCase):

    _client = None
    _samples_recd = 0

    @classmethod
    def _data_listener(cls, sample):
        cls._samples_recd += 1
        log.info("_data_listener: received PD0=%s" % prefix(sample))

    @classmethod
    def setUpClass(cls):
        super(Test, cls).setUpClass()
        if cls._skip_reason:
            return

        ReceiverBuilder.use_greenlets()

        cc = cls._conn_config[cls._vadcp_unit]
        outfilename = 'vadcp_output_%s_%s.txt' % (cc.host, cc.port)
        outfile = file(outfilename, 'w')

        cls._client = UnitClient(cc, outfile)

        cls._client.set_generic_timeout(cls._timeout)

        log.info("connecting")
        cls._client.set_data_listener(cls._data_listener)
        cls._client.connect()

        log.info("sending break")
        cls._client.send_break()

        log.info("waiting from prompt")
        cls._client._get_prompt()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls._client:
                log.info("ending UnitClient object")
                cls._client.end()
        finally:
            super(Test, cls).tearDownClass()

    def test_basic(self):
        state = self._client.get_current_state()
        log.info("current instrument state: %s" % str(state))

    def test_get_latest_sample(self):
        sample = self._client.get_latest_sample()
        self.assertTrue(sample is None or isinstance(sample, PD0DataStructure))

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
        Test._samples_recd = 0
        if State.COLLECTING_DATA != self._client.get_current_state():
            result = self._client.start_autosample()
            log.info("start_autosample result=%s" % result)

        self.assertEqual(State.COLLECTING_DATA, self._client.get_current_state())

        time.sleep(6)
        log.info("ensembles_recd = %s" % Test._samples_recd)

        result = self._client.stop_autosample()
        log.info("stop_autosample result=%s" % result)

        self.assertEqual(State.PROMPT, self._client.get_current_state())
