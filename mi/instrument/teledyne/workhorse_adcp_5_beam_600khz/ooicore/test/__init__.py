#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/__init__.py
@author Carlos Rueda

@brief Supporting stuff for tests
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    AdcpUnitConnConfig
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import \
    ReceiverBuilder

import yaml
import os
import unittest
from mi.core.unit_test import MiUnitTest
from mi.core.mi_logger import mi_logger as log


@unittest.skipIf(os.getenv('VADCP') is None,
                 'VADCP environment variable undefined')
class VadcpTestCase(MiUnitTest):
    """
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up _conn_config, _timeout, according to environment variables.
        """

        cls._skip_reason = None

        #
        # cls._conn_config
        #
        cls._conn_config = None
        vadcp = os.getenv('VADCP')
        if vadcp:
            filename = vadcp
            log.info("loading connection params from '%s'" % filename)
            try:
                f = open(filename)
                yml = yaml.load(f)
                f.close()

                def create_unit_conn_config(yml):
                    return AdcpUnitConnConfig(yml.get('host'),
                                              yml.get('port'),
                                              yml.get('ooi_digi_host'),
                                              yml.get('ooi_digi_port'))

                cls._conn_config = {
                    'four_beam': create_unit_conn_config(yml['four_beam']),
                    'fifth_beam': create_unit_conn_config(yml['fifth_beam'])
                }
            except Exception, e:
                cls._skip_reason = "Problem with connection config file: '%s': %s" % (
                                    filename, str(e))
                log.warn(cls._skip_reason)
        else:
            cls._skip_reason = 'environment variable VADCP undefined'

        #
        # cls._vadcp_unit
        #
        cls._vadcp_unit = os.getenv('VADCP_UNIT', 'four_beam')
        log.info("_adcp_unit set to: %s" % cls._vadcp_unit)

        #
        # cls._timeout
        #
        cls._timeout = 30
        timeout_str = os.getenv('timeout')
        if timeout_str:
            try:
                cls._timeout = int(timeout_str)
            except:
                log.warn("Malformed timeout environment variable value '%s'",
                         timeout_str)
        log.info("Generic timeout set to: %d" % cls._timeout)

    @classmethod
    def tearDownClass(self):
        ReceiverBuilder.use_default()

    def setUp(self):
        """
        """

        if self._skip_reason:
            self.skipTest(self._skip_reason)

        log.info("== VADCP _conn_config: %s" % self._conn_config)
