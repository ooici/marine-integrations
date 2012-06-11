#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.test_driver
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/test_driver.py
@author Carlos Rueda
@brief Direct tests to the driver class.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver import VadcpDriver

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.driver_test_mixin import DriverTestMixin
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.receiver import \
    ReceiverBuilder

from nose.plugins.attrib import attr

from mi.core.mi_logger import mi_logger as log


@attr('UNIT', group='mi')
class Test(VadcpTestCase, DriverTestMixin):
    """
    Direct tests to the VadcpDriver class. The actual set of tests
    is provided by DriverTestMixin.
    """

    def setUp(self):
        """
        Calls VadcpTestCase.setUp(self), creates and assigns the
        VadcpDriver instance, and assign the comm_config object.
        """
        ReceiverBuilder.use_greenlets()

        VadcpTestCase.setUp(self)

        def evt_callback(event):
            log.info("CALLBACK: %s" % str(event))

        # needed by DriverTestMixin
        self.driver = VadcpDriver(evt_callback)
        self.comms_config = self._conn_config[self._vadcp_unit]
