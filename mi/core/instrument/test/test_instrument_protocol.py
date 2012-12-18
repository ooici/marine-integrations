#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_instrument_protocol
@file mi/core/instrument/test/test_instrument_protocol.py
@author Steve Foley
@brief Test cases for the base instrument protocol module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import logging
import time
import datetime
from nose.plugins.attrib import attr
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_protocol import InstrumentProtocol
from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.instrument.satlantic.par_ser_600m.driver import SAMPLE_REGEX
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticle

from mi.core.driver_scheduler import DriverScheduler
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.unit_test import MiUnitTestCase
import unittest
from mi.core.exceptions import InstrumentParameterException
from mi.core.common import BaseEnum

Directions = MenuInstrumentProtocol.MenuTree.Directions

@attr('UNIT', group='mi')
class TestUnitInstrumentProtocol(MiUnitTestCase):
    """
    Test cases for instrument protocol class. Functions in this class provide
    instrument protocol unit tests and provide a tutorial on use of
    the protocol interface.
    """ 
    def setUp(self):
        """
        """
        self.callback_result = None
        self._trigger_count = 0

        def protocol_callback(self, arg):
            callback_result = arg
            
        self.protocol = InstrumentProtocol(protocol_callback)

    def _scheduler_callback(self):
        """
        Callback to test the scheduler
        """
        self._trigger_count += 1

    def test_extraction(self):
        sample_line = "SATPAR0229,10.01,2206748544,234\r\n"
        result = self.protocol._extract_sample(SatlanticPARDataParticle,
                                               SAMPLE_REGEX,
                                               sample_line,
                                               publish=False)

        log.debug("R: %s" % result)
        self.assertEqual(result['stream_name'], SatlanticPARDataParticle(None, None).data_particle_type())

        # Test the format of the result in the individual driver tests. Here,
        # just tests that the result is there.

    @unittest.skip('Not Written')
    def test_publish_raw(self):
        """
        Tests to see if raw data is appropriately published back out to
        the InstrumentAgent via the event callback.
        """
        # build a packet
        # have it published by the protocol (force state if needed)
        # delay?
        # catch it in the  callback
        # confirm it came back
        # compare response to original packet
        
        self.assertTrue(False)

    @unittest.skip('Not Written')
    def test_publish_parsed_data(self):
        """
        Tests to see if parsed data is appropriately published back to the
        InstrumentAgent via the event callback.
        """
        # similar to above
        self.assertTrue(False)

    @unittest.skip('Not Written')
    def test_publish_engineering_data(self):
        """
        Tests to see if engineering data is appropriately published back to the
        InstrumentAgent via the event callback.
        """
        # similar to above
        self.assertTrue(False)
        
    def test_get_running_config(self):
        """
        Checks to see that one can successfully get the running config from an
        instrument protocol.
        """
        # set some values
        log.debug("First param_dict: %s", self.protocol._param_dict.get_config())
        self.protocol._param_dict.add("foo", r'foo=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=10)
        self.protocol._param_dict.set_default("foo") # test hack to set w/o fetch
        self.protocol._param_dict.add("bar", r'bar=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             default_value=15)
        self.protocol._param_dict.set_default("bar")
                
        self.assertEquals(self.protocol._param_dict.get("foo"), 10)
        self.assertEquals(self.protocol._param_dict.get("bar"), 15)
        result = self.protocol.get_cached_config()
        self.assertEquals(result['foo'], 10)
        self.assertEquals(result['bar'], 15)

        self.protocol._param_dict.update("bar=20")
        result = self.protocol.get_cached_config()
        self.assertEquals(result['foo'], 10)
        self.assertEquals(result['bar'], 20)
        self.assertEquals(self.protocol._param_dict.get("bar"), 20)
        
        # get and check the running config
        result = self.protocol.get_cached_config()
        self.assertTrue(isinstance(result, dict))
        self.assertEquals(result['foo'], 10)
        self.assertEquals(result['bar'], 20)

    def test_init_values(self):
        """
        Test getting and setting the initialization value for a parameter
        """
        # set an additional value for test
        self.protocol._param_dict.add("foo", r'foo=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             startup_param=True,
                             default_value=10)
        self.protocol._param_dict.add("bar", r'bar=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             startup_param=True,
                             default_value=0)
        self.protocol._param_dict.add("baz", r'baz=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=20)
        self.protocol._param_dict.add("bat", r'bat=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             default_value=20)
        self.protocol._param_dict.add("qux", r'qux=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=True)
        self.protocol._param_dict.update("qux=6666")
        
        # mark init params
        self.assertRaises(InstrumentParameterException,
                          self.protocol.set_init_params, [])
        self.protocol.set_init_params({DriverConfigKey.PARAMETERS: {"foo": 1111, "baz":2222}})
        
        # get new startup config
        result = self.protocol.get_startup_config()
        
        self.assertEquals(len(result), 3)
        self.assertEquals(result["foo"], 1111) # init param
        self.assertEquals(result["bar"], 0)   # default param
        self.assertEquals(result["qux"], 6666) # set param

    def test_scheduler(self):
        """
        Test to see that the scheduler can add and remove jobs properly
        Jobs are just queued for adding unit we call initialize_scheduler
        then the jobs are actually created.
        """
        dt = datetime.datetime.now() + datetime.timedelta(0,1)
        job_name = 'test_job'
        startup_config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE,
                        DriverSchedulerConfigKey.DATE: dt
                    }
                }
            }
        }

        self.protocol.set_init_params(startup_config)

        # Verify we are initialized properly
        self.assertIsNone(self.protocol._scheduler)
        self.assertEqual(self.protocol._scheduler_config, {})
        self.assertEqual(self.protocol._scheduler_callback, {})

        # Verify the the scheduler is created
        self.protocol.initialize_scheduler()
        self.assertIsInstance(self.protocol._scheduler, DriverScheduler)
        self.assertEqual(self.protocol._scheduler_config, {})
        self.assertEqual(self.protocol._scheduler_callback, {})

        # Now lets see some magic happen.  Lets add our schedulers.  Generally
        # This would be done as part of the protocol init, but it can happen
        # anytime.  If the scheduler has already been initialized the
        # job will be started right away
        self.protocol._add_scheduler(job_name, self._scheduler_callback)
        self.assertEqual(0, self._trigger_count)
        time.sleep(2)
        self.assertEqual(1, self._trigger_count)

        ##### Integration tests for test_scheduler in the SBE37 integration suite


@attr('UNIT', group='mi')
class TestUnitMenuInstrumentProtocol(MiUnitTestCase):
    """
    Test cases for instrument protocol class. Functions in this class provide
    instrument protocol unit tests and provide a tutorial on use of
    the protocol interface.
    """
    class SubMenu(BaseEnum):
        MAIN = "SUBMENU_MAIN"
        ONE = "SUBMENU_ONE"
        TWO = "SUBMENU_TWO"

    class Prompt(BaseEnum):
        CMD_PROMPT = "-->"
        CONTINUE_PROMPT = "Press ENTER to continue."
        MAIN_MENU = "MAIN -->"
        ONE_MENU = "MENU 1 -->"
        TWO_MENU = "MENU 2 -->"
    
    MENU = MenuInstrumentProtocol.MenuTree({
        SubMenu.MAIN:[],
        SubMenu.ONE:[Directions(command="1", response=Prompt.ONE_MENU)],
        SubMenu.TWO:[Directions(SubMenu.ONE),
                            Directions(command="2", response=Prompt.CONTINUE_PROMPT)]
    })

    def setUp(self):
        """
        """
        self.callback_result = None
        
        def protocol_callback(self, arg):
            callback_result = arg

        # Call no longer valid. MenuInstrumentProtocol now takes 4 args.
        #self.protocol = MenuInstrumentProtocol(protocol_callback)

    @unittest.skip("SKIP - Not Written")
    def test_navigation(self):
        """
        Test the navigate method to get between menus
        """
        pass
        
