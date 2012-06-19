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
    md_section_names, State, VadcpSample
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import prefix
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import \
    ReceiverBuilder

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

        cls._samples_recd = 0

        c4 = cls._conn_config['four_beam']
        outfilename = 'vadcp_output_%s_%s.txt' % (c4.host, c4.port)
        u4_outfile = file(outfilename, 'w')
        c5 = cls._conn_config['fifth_beam']
        outfilename = 'vadcp_output_%s_%s.txt' % (c5.host, c5.port)
        u5_outfile = file(outfilename, 'w')

        cls._client = VadcpClient(cls._conn_config, u4_outfile, u5_outfile)

        cls._client.set_generic_timeout(cls._timeout)

        log.info("connecting")
        cls._client.set_data_listener(cls._data_listener)
        cls._client.connect()

        log.info("sending break and waiting for prompt")
        cls._client.send_break()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls._client:
                log.info("ending VadcpClient object")
                cls._client.end()
        finally:
            super(Test, cls).tearDownClass()

    def test_basic(self):
        state = self._client.get_current_state()
        log.info("current instrument state: %s" % str(state))

    def test_get_latest_sample(self):
        sample = self._client.get_latest_sample()
        self.assertTrue(sample is None or isinstance(sample, VadcpSample))

    def test_get_metadata(self):
        sections = None  # None => all sections
        result = self._client.get_metadata(sections)
        self.assertTrue(isinstance(result, dict))
        s = ''
        for unit, unit_result in result.items():
            s += "==UNIT: %s==\n\n" % unit
            for name, text in unit_result.items():
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

        # TODO handle state properly for comparison
#        self.assertEqual(State.COLLECTING_DATA, self._client.get_current_state())

        time.sleep(6)
        log.info("ensembles_recd = %s" % Test._samples_recd)

        result = self._client.stop_autosample()
        log.info("stop_autosample result=%s" % result)

        self.assertEqual(State.PROMPT, self._client.get_current_state())
