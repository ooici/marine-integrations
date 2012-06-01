#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.test_driver0
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/test_driver0.py
@author Carlos Rueda
@brief Direct tests to the driver class.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver0 import VadcpDriver

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.driver_test_mixin import DriverTestMixin
from nose.plugins.attrib import attr

from mi.core.mi_logger import mi_logger as log

import os


@attr('UNIT', group='mi')
class DriverTest(VadcpTestCase, DriverTestMixin):
    """
    Direct tests to the Driver class. The actual set of tests
    is provided by DriverTestMixin.
    """

    def setUp(self):
        """
        Calls VadcpTestCase.setUp(self), creates and assigns the
        Driver instance, and assign the comm_config object.
        """

        os.environ["green_rcvr"] = "y"

        VadcpTestCase.setUp(self)

        def evt_callback(event):
            log.info("CALLBACK: %s" % str(event))

        # needed by DriverTestMixin
        self.driver = VadcpDriver(evt_callback)
        self.comms_config = {
            'addr': self.device_address,
            'port': self.device_port}
