#!/usr/bin/env python

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.test_driver_proc
@file    mi/instrument/teledyne/workhorse_adcp_5_beam_600khz/ooicore/test/test_driver_proc.py
@author Carlos Rueda
@brief VADCP Driver integration tests involving port agent and driver process.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from gevent import monkey; monkey.patch_all()

from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver import VadcpDriver
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test import VadcpTestCase
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.driver_test_mixin import DriverTestMixin
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.defs import \
    AdcpUnitConnConfig

from mi.core.instrument.driver_int_test_support import DriverIntegrationTestSupport
from nose.plugins.attrib import attr

from mi.core.instrument.instrument_driver import InstrumentDriver

from mi.core.mi_logger import mi_logger as log


@attr('INT', group='mi')
class Test(VadcpTestCase, DriverTestMixin):
    """
    Driver integration tests involving port agent
    and driver process. The actual set of tests is provided by
    DriverTestMixin.
    """

    def setUp(self):
        """
        Calls VadcpTestCase.setUp(self), creates and assigns the a
        proxy for the driver that relies on the ZmqDriverClient object
        created by the DriverIntegrationTestSupport, and assigns the
        comms_config object.
        """

        VadcpTestCase.setUp(self)

        # needed by DriverTestMixin
        self.driver = VadcpDriverProxy(self._conn_config)
        self.comms_config = self.driver.comms_config

        def cleanup():
            self.driver._support.stop_pagent()
            self.driver._support.stop_driver()
        self.addCleanup(cleanup)


class VadcpDriverProxy(InstrumentDriver):
    """
    An InstrumentDriver serving as a proxy to the driver client
    connecting to the actual VadcpDriver implementation.

    Methods are programmatically added below based on the names of the
    public methods of the VadcpDriver class.
    """

    def __init__(self, conn_config):
        """
        Setup test cases.
        """
        driver_module = 'mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.driver'
        driver_class = 'VadcpDriver'

        u4_conn_config = conn_config['four_beam']

        device_address = u4_conn_config.host
        device_port = u4_conn_config.port

        # TODO set up port agent for the OOI Digi connection as well.

        self._support = DriverIntegrationTestSupport(driver_module,
                                                     driver_class,
                                                     device_address,
                                                     device_port)

        # Create and start the port agent, which runs on localhost
        log.info('starting port agent')
        pagent_port = self._support.start_pagent()

        # so, we now connect to the 4-beam via the port agent:
        # Note that only the raw connection is adjusted

        self.comms_config = {
            'four_beam': AdcpUnitConnConfig('localhost', pagent_port,
                                            u4_conn_config.ooi_digi_host,
                                            u4_conn_config.ooi_digi_port),
            'fifth_beam': conn_config['fifth_beam']
        }
        log.info("comms_config: %s" % self.comms_config)

        # Create and start the driver.
        log.info('starting driver client')
        self._support.start_driver()

        self._dvr_client = self._support._dvr_client


def _add_methods_to_proxy():
    """
    Creates and adds all methods to the proxy class based on the names of the
    public methods of the VadcpDriver class. The implementation in each case is
    a delegation to self._dvr_client.cmd_dvr(method_name, *args, **kwargs),
    where self will correspond to the VadcpDriverProxy instance.
    """
    def create_method(name):
        def method(self, *args, **kwargs):
            reply = self._dvr_client.cmd_dvr(name, *args, **kwargs)
            log.info("%s reply = %s" % (name, reply))
            return reply
        method.__name__ = '%s' % name
        return method

    from types import MethodType
    for name in dir(VadcpDriver):
        if not name.startswith("_"):
            a = getattr(VadcpDriver, name)
            if isinstance(a, MethodType):
                setattr(VadcpDriverProxy, name, create_method(name))

_add_methods_to_proxy()
