#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/__init__.py
@author Carlos Rueda

@brief Supporting stuff for tests
"""

__author__ = 'Carlos Rueda'
__license__ = 'Apache 2.0'

import yaml
import os
import unittest
from mi.core.mi_logger import mi_logger as log


@unittest.skipIf(os.getenv('VADCP') is None,
                 'VADCP environment variable undefined')
class VadcpTestCase(unittest.TestCase):
    """
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up _vadcp, _timeout, according to corresponding
        environment variables.
        """
        cls._vadcp = os.getenv('VADCP')

        cls._timeout = 30
        timeout_str = os.getenv('timeout')
        if timeout_str:
            try:
                cls._timeout = int(timeout_str)
            except:
                log.warn("Malformed timeout environment variable value '%s'",
                         timeout_str)
        log.info("Generic timeout set to: %d" % cls._timeout)

    def setUp(self):
        """
        """

        if self._vadcp is None:
            # should not happen, but anyway just skip here:
            self.skipTest("Environment variable VADCP undefined")

        if self._vadcp.endswith(".yml"):
            filename = self._vadcp
            log.info("loading connection params from %s" % filename)
            f = open(filename)
            yml = yaml.load(f)
            f.close()

            four_beam = yml['four_beam']
            fifth_beam = yml['fifth_beam']
            self._conn_config = {
                'four_beam': {'address': four_beam.get('address'),
                              'port': four_beam.get('port'),
                              'digi_port': four_beam.get('ooi_digi_port')},

                'fifth_beam': {'address': fifth_beam.get('address'),
                               'port': fifth_beam.get('port'),
                               'telnet_port': fifth_beam.get('telnet_port')}
            }

        else:
            try:
                device_address, p = self._vadcp.split(':')
                port = int(p)
            except:
                self.skipTest("Malformed VADCP value")

            # TODO None's here TBD:
            self._conn_config = {
                'four_beam': {'address': device_address,
                              'port': port,
                              'digi_port': None},

                'fifth_beam': {'address': None,
                               'port': None,
                               'telnet_port': None}
            }


        log.info("== VADCP _conn_config: %s" % self._conn_config)
