#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.driver_test_mixin
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/driver_test_mixin.py
@author Carlos Rueda
@brief A convenient mixin class for driver tests where the actual driver
       operations are implemented by a subclass.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    md_section_names
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver import DriverState
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util import prefix

import time
from mi.core.mi_logger import mi_logger as log


class DriverTestMixin(object):
    """
    A very convenient mixin class for driver tests where the actual driver
    implementation is given by a subclass. This mixin greatly facilitates
    to perform a complete set of tests on various different mechanisms to
    access the actual driver implementation without having to duplicate lots
    of code.

    The only requirement for a subclass is to provide the concrete driver
    implementation object by assigning it to self.driver, and to provide
    a configuration object and assign it to self.comm_config, which is
    used for the self.driver.configure call.
    """

    def _prepare_and_connect(self):
        self._assert_driver_unconfigured()
        self._initialize()
        self._configure()
        self._connect()
        self._init_protocol()

    def _assert_driver_unconfigured(self):
        state = self.driver.get_current_state()
        log.info("driver connected -> %s" % str(state))
        self.assertEqual(DriverState.UNCONFIGURED, state)

    def _initialize(self):
        self.driver.initialize()
        state = self.driver.get_current_state()
        log.info("intitialize -> %s" % str(state))
        self.assertEqual(DriverState.UNCONFIGURED, state)

    def _configure(self):
        self.driver.configure(config=self.comms_config)
        state = self.driver.get_current_state()
        log.info("configure -> %s" % str(state))
        self.assertEqual(DriverState.DISCONNECTED, state)

    def _connect(self):
        self.driver.connect()
        state = self.driver.get_current_state()
        log.info("connect -> %s" % str(state))
#        self.assertEqual(DriverState.CONNECTED, state)
        if DriverState.CONNECTED == state:
            pass  # OK
        else:
            self.assertTrue(state.startswith('PROTOCOL_STATE'))

    def _init_protocol(self):
        self.driver.execute_init_protocol()
        state = self.driver.get_current_state()
        log.info("execute_init_protocol -> %s" % str(state))

    def _disconnect(self):
        self.driver.disconnect()
        state = self.driver.get_current_state()
        log.info("disconnect -> %s" % str(state))
        self.assertEqual(DriverState.DISCONNECTED, state)

    def test_connect_disconnect(self):
        self._prepare_and_connect()
        self._disconnect()

    def test_execute_get_latest_sample(self):
        self._prepare_and_connect()

        result = self.driver.execute_get_latest_sample(timeout=self._timeout)
        log.info("get_latest_sample result = %s" % str(result))

        self._disconnect()

    def test_execute_get_metadata(self):
        self._prepare_and_connect()

        sections = None
        result = self.driver.execute_get_metadata(sections,
                                                  timeout=self._timeout)
        self.assertTrue(isinstance(result, dict))
        s = ''
        for unit, unit_result in result.items():
            s += "==UNIT: %s==\n\n" % unit
            for name, text in unit_result.items():
                self.assertTrue(name in md_section_names)
                s += "**%s:%s\n\n" % (name, prefix(text, "\n    "))
        log.info("METADATA result=%s" % prefix(s))

        self._disconnect()

    def test_execute_run_recorder_tests(self):
        self._prepare_and_connect()

        result = self.driver.execute_run_recorder_tests(timeout=self._timeout)
        log.info("execute_run_recorder_tests result=%s" % prefix(result))

        self._disconnect()

    def test_execute_run_all_tests(self):
        self._prepare_and_connect()

        result = self.driver.execute_run_all_tests(timeout=self._timeout)
        log.info("execute_run_all_tests result=%s" % prefix(result))

        self._disconnect()

    def test_start_and_stop_autosample(self):
        self._prepare_and_connect()

        result = self.driver.execute_start_autosample(timeout=self._timeout)
        log.info("execute_start_autosample result=%s" % prefix(result))

        time.sleep(6)

        result = self.driver.execute_stop_autosample(timeout=self._timeout)
        log.info("execute_stop_autosample result=%s" % prefix(result))

        self._disconnect()
