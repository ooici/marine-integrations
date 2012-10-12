#!/usr/bin/env python

"""
@package mi.instrument.uw.res_probe.ooicore.test.test_trhph_driver_proc
@file    mi/instrument/uw/res_probe/ooicore/test/test_trhph_driver_proc.py
@author Carlos Rueda
@brief TrhphInstrumentDriver integration tests involving port agent
and driver process.
"""

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'


from gevent import monkey; monkey.patch_all()

from mi.instrument.uw.res_probe.ooicore.test import TrhphTestCase
from mi.instrument.uw.res_probe.ooicore.test.driver_test_mixin import DriverTestMixin

from mi.core.instrument.instrument_driver import InstrumentDriver

from pyon.core.exception import InstDriverError
from ion.agents.instrument.driver_int_test_support import DriverIntegrationTestSupport
#from mi.core.instrument.driver_int_test_support import DriverIntegrationTestSupport

from nose.plugins.attrib import attr

from mi.core.mi_logger import mi_logger
log = mi_logger


@attr('INT', group='mi')
class DriverTest(TrhphTestCase, DriverTestMixin):
    """
    TrhphInstrumentDriver integration tests involving port agent
    and driver process. The actual set of tests is provided by
    DriverTestMixin.
    """

    def setUp(self):
        """
        Calls TrhphTestCase.setUp(self), creates and assigns the
        TrhphDriverProxy, and assigns the comms_config object.
        """

        TrhphTestCase.setUp(self)

        # needed by DriverTestMixin
        self.driver = TrhphDriverProxy(self.device_address, self.device_port)
        self.comms_config = self.driver.comms_config

        def cleanup():
            self.driver._support.stop_pagent()
            ##<update-july-2012>
#            self.driver._support.stop_driver()
            self.driver._stop_driver()
            ##</update-july-2012>
        self.addCleanup(cleanup)


class TrhphDriverProxy(InstrumentDriver):
    """
    An InstrumentDriver serving as a proxy to the driver client
    connecting to the actual TrhphInstrumentDriver implementation.

    Extends InstrumentDriver (instead of TrhphInstrumentDriver) because
    that's the main driver interface in general whereas extending
    TrhphInstrumentDriver would bring unneeded implementation stuff.
    """

    def __init__(self, device_address, device_port):
        """
        Setup test cases.
        """

        driver_module = 'mi.instrument.uw.res_probe.ooicore.trhph_driver'
        driver_class = 'TrhphInstrumentDriver'

        self._support = DriverIntegrationTestSupport(driver_module,
                                                     driver_class,
                                                     device_address,
                                                     device_port)

        # Create and start the port agent.
        mi_logger.info('starting port agent')
        self.comms_config = {
            'addr': 'localhost',
            'port': self._support.start_pagent()}

        # Create and start the driver.
        mi_logger.info('starting driver client')

        ##<update-july-2012>:
        ## start_driver and _dvr_client no longer defined in
        ## DriverIntegrationTestSupport
#        self._support.start_driver()
#        self._dvr_client = self._support._dvr_client
        dvr_config = {
            'comms_config': self.comms_config,
            'dvr_mod': driver_module,
            'dvr_cls': driver_class,
            'workdir' : '/tmp/',
            'process_type': ('ZMQPyClassDriverLauncher',)
        }
        self._start_driver(dvr_config)
        ##</update-july-2012>

    def _start_driver(self, dvr_config):
        ## Part of <update-july-2012>
        ##
        ## Adapted from InstrumentAgent._start_driver(self, dvr_config).
        ##
        """
        Start the driver process and driver client.
        @param dvr_config The driver configuration.
        @raises InstDriverError If the driver or client failed to start properly.
        """

        from ion.agents.instrument.driver_process import DriverProcess

        self._dvr_proc = DriverProcess.get_process(dvr_config, True)
        self._dvr_proc.launch()

        # Verify the driver has started.
        if not self._dvr_proc.getpid():
            log.error('TrhphDriverProxy: error starting driver process.')
            raise InstDriverError('Error starting driver process.')

        def evt_recv(evt):
            """
            Callback to receive asynchronous driver events.
            @param evt The driver event received.
            """
            log.info('TrhphDriverProxy:received driver event %s' % str(evt))

        try:
            driver_client = self._dvr_proc.get_client()
            driver_client.start_messaging(evt_recv)
#            retval = driver_client.cmd_dvr('process_echo', 'Test.')
            self._dvr_client = driver_client

        except Exception, e:
            self._dvr_proc.stop()
            log.error('TrhphDriverProxy: error starting driver client: %s' % e)
            raise InstDriverError('Error starting driver client: %s' % e)

        log.info('TrhphDriverProxy: started driver.')

    def _stop_driver(self):
        ## Part of <update-july-2012>
        ##
        ## Adapted from InstrumentAgent._stop_driver(self).
        ##
        """
        Stop the driver process and driver client.
        """
        log.info('TrhphDriverProxy:stopped its driver.')
        self._dvr_proc.stop()

    def get_current_state(self, *args, **kwargs):
        state = self._dvr_client.cmd_dvr('get_resource_state',
                                         *args,
                                         **kwargs)
        mi_logger.info("get_current_state = %s" % state)
        return state

    def initialize(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('initialize')
        mi_logger.info("initialize reply = %s" % reply)
        return reply

    def configure(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('configure',
                                         *args,
                                         **kwargs)
        mi_logger.info("configure reply = %s" % reply)
        return reply

    def connect(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('connect',
                                         *args,
                                         **kwargs)
        mi_logger.info("connect reply = %s" % reply)
        return reply

    def disconnect(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('disconnect',
                                         *args,
                                         **kwargs)
        mi_logger.info("disconnect reply = %s" % reply)
        return reply

    def get_resource(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('get_resource',
                                         *args,
                                         **kwargs)
        mi_logger.info("get reply = %s" % reply)
        return reply

    def set_resource(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('set_resource',
                                         *args,
                                         **kwargs)
        mi_logger.info("set reply = %s" % reply)
        return reply

    def execute_stop_autosample(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('execute_stop_autosample',
                                         *args,
                                         **kwargs)
        mi_logger.info("execute_stop_autosample reply = %s" % reply)
        return reply

    def execute_get_metadata(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('execute_get_metadata',
                                         *args,
                                         **kwargs)
        mi_logger.info("execute_get_metadata reply = %s" % reply)
        return reply

    def execute_diagnostics(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('execute_diagnostics',
                                         *args,
                                         **kwargs)
        mi_logger.info("execute_diagnostics reply = %s" % reply)
        return reply

    def execute_get_power_statuses(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('execute_get_power_statuses',
                                         *args,
                                         **kwargs)
        mi_logger.info("execute_get_power_statuses reply = %s" % reply)
        return reply

    def execute_start_autosample(self, *args, **kwargs):
        reply = self._dvr_client.cmd_dvr('execute_start_autosample',
                                         *args,
                                         **kwargs)
        mi_logger.info("execute_start_autosample reply = %s" % reply)
        return reply
