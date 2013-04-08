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
import ntplib
import datetime
from mock import Mock
from nose.plugins.attrib import attr
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_protocol import InstrumentProtocol
from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.instrument.satlantic.par_ser_600m.driver import SAMPLE_REGEX
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticle

from mi.core.instrument.protocol_cmd_dict import Command, CommandArgument
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.driver_scheduler import DriverScheduler
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.unit_test import MiUnitTestCase
import unittest
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import NotImplementedException
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
        self._events = []

        self.protocol = InstrumentProtocol(self.event_callback)
                
    def event_callback(self, event, value=None):
        log.debug("Test event callback: %s" % event)
        self._events.append(event)
        self._trigger_count += 1

    def _scheduler_callback(self):
        """
        Callback to test the scheduler
        """
        self._trigger_count += 1

    def assert_scheduled_event_triggered(self, event_count=1):
        count = 0
        for i in range(0, 40):
            count = self._trigger_count
            log.debug("check for triggered event, count %d" % self._trigger_count)
            if(count >= event_count): break
            time.sleep(0.3)

        self.assertGreater(count, 0)

    def test_get_prompts(self):
        """
        ensure prompts are returned sorted by length
        """
        prompts = ['aa', 'bbb', 'c', 'dddd']
        expected = ['dddd', 'bbb', 'aa', 'c']
        class Prompts(BaseEnum):
            A = 'aa'
            B = 'bbb'
            C = 'c'
            D = 'dddd'

        self.protocol = CommandResponseInstrumentProtocol(prompts, '\r\n', self.event_callback)
        self.assertEqual(self.protocol._get_prompts(), expected)

        self.protocol = CommandResponseInstrumentProtocol(Prompts, '\r\n', self.event_callback)
        self.assertEqual(self.protocol._get_prompts(), expected)

    def test_extraction(self):
        sample_line = "SATPAR0229,10.01,2206748544,234\r\n"
        ntptime = ntplib.system_to_ntp_time(time.time())
        result = self.protocol._extract_sample(SatlanticPARDataParticle,
                                               SAMPLE_REGEX,
                                               sample_line,
                                               ntptime,
                                               publish=False)

        log.debug("R: %s" % result)
        self.assertEqual(result['stream_name'], SatlanticPARDataParticle(None, None).data_particle_type())

        # Test the format of the result in the individual driver tests. Here,
        # just tests that the result is there.

    def test_get_param_list(self):
        """
        verify get_param_list returns correct parameter lists.
        """
        params = ['foo', 'bar', 'baz']

        for key in params:
            self.protocol._param_dict.add(key, r'', None, None)

        # All can be passed in as a string
        self.assertEqual(sorted(params), sorted(self.protocol._get_param_list(DriverParameter.ALL)))

        # All can be passed in as a single element list
        self.assertEqual(sorted(params), sorted(self.protocol._get_param_list([DriverParameter.ALL])))

        # All can be in a list anywhere, not just the first element
        self.assertEqual(sorted(params), sorted(self.protocol._get_param_list(['foo', DriverParameter.ALL])))

        # Bad parameters raise exceptions event when ALL is specified
        with self.assertRaises(InstrumentParameterException):
            self.assertEqual(sorted(params), sorted(self.protocol._get_param_list(['noparam', DriverParameter.ALL])))

        # An exception is raised when the param is not a list or string
        with self.assertRaises(InstrumentParameterException):
            self.protocol._get_param_list({'other': 'struct'})

        # when a subset is given, the same set is returned.
        subset = ['bar', 'baz']
        self.assertEqual(sorted(subset), sorted(self.protocol._get_param_list(subset)))

        # verify we can accept a tuple
        subset = ['bar', 'baz']
        self.assertEqual(sorted(subset), sorted(self.protocol._get_param_list(('bar', 'baz'))))

        # An exception is raised when the param is not known
        with self.assertRaises(InstrumentParameterException):
            self.protocol._get_param_list(subset + ['boom'])

        # Verify we can send in a single parameter as a string, not ALL
        self.assertEqual(['bar'], self.protocol._get_param_list('bar'))

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
        self.protocol._param_dict.add("rok", r'rok=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x))

        # set an additional value for test
        self.protocol._param_dict.update("qux=6666")
        
        # mark init params
        self.assertRaises(InstrumentParameterException,
                          self.protocol.set_init_params, [])
        self.protocol.set_init_params({DriverConfigKey.PARAMETERS: {"foo": 1111, "baz":2222}})
        
        # get new startup config
        self.assertRaises(InstrumentProtocolException, self.protocol.get_startup_config)
        self.protocol.set_init_params({DriverConfigKey.PARAMETERS: {"foo": 1111, "baz":2222, "bat": 11, "qux": 22}})
        result = self.protocol.get_startup_config()
        
        self.assertEquals(len(result), 5)
        self.assertEquals(result["foo"], 1111) # init param
        self.assertEquals(result["bar"], 0)    # init param with default value
        self.assertEquals(result["baz"], 2222) # non-init param, but value specified
        self.assertEquals(result["bat"], 11)   # set param
        self.assertEquals(result["qux"], 22)   # set param
        self.assertIsNone(result.get("rok"))   # defined in paramdict, no config

    def test_apply_startup_params(self):
        """
        Test that the apply startup parameters method exists and throws
        a "not implemented" exception for the base class
        """
        self.assertRaises(NotImplementedException,
                          self.protocol.apply_startup_params)

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
        self.assert_scheduled_event_triggered()

    def test_scheduler_event(self):
        """
        Test if we can add and trigger jobs using events instead of callbacks
        We will create two event triggers, foo and bar.  They should come in
        that order.
        """
        self.protocol._protocol_fsm = Mock()
        #self.protocol._fsm.on_event = Mock()

        dt = datetime.datetime.now() + datetime.timedelta(0,1)
        foo_scheduler = 'foo'
        bar_scheduler = 'bar'
        startup_config = {
            DriverConfigKey.SCHEDULER: {
                foo_scheduler: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: 1
                    }
                },
                bar_scheduler: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: 2
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
        foo_event='foo'
        bar_event='bar'
        self.protocol._add_scheduler_event(foo_scheduler, foo_event)
        self.protocol._add_scheduler_event(bar_scheduler, bar_event)

        self.assertEqual(0, self._trigger_count)
        #self.assert_scheduled_event_triggered(2)

        ##### Integration tests for test_scheduler in the SBE37 integration suite

    def test_generate_config_metadata_json(self):
        """ Tests generate of the metadata structure """
        self.protocol._param_dict.add("foo", r'foo=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=10)
        self.protocol._param_dict.add("bar", r'bar=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             default_value=15)

        self.protocol._cmd_dict.add("cmd1",
                                    timeout=60,
                                    arguments=[CommandArgument("coeff"),
                                               CommandArgument("delay")
                                              ]
                                   )
        # different way of creating things, possibly more clear in some cases
        # and allows for testing arg and command later
        cmd2_arg1 = CommandArgument("trigger")
        cmd2 = Command("cmd2", arguments=[cmd2_arg1])
        
        self.protocol._cmd_dict.add_command(cmd2)

        self.protocol._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

        # Now do the real testing       
        result = self.protocol.get_config_metadata_dict()
        
        self.assert_(isinstance(result[ConfigMetadataKey.DRIVER], dict))
        self.assert_(isinstance(result[ConfigMetadataKey.COMMANDS], dict))
        self.assert_(isinstance(result[ConfigMetadataKey.PARAMETERS], dict))
        
        self.assertEquals(result[ConfigMetadataKey.DRIVER],
                          {DriverDictKey.VENDOR_SW_COMPATIBLE:True})

        # Check a few in the cmd list...the leaves in the structure are
        # tested in the cmd dict test cases
        self.assert_("cmd1" in result[ConfigMetadataKey.COMMANDS].keys())
        self.assert_("cmd2" in result[ConfigMetadataKey.COMMANDS].keys())
                
        # Check a few in the param list...the leaves in the structure are
        # tested in the param dict test cases
        self.assert_("foo" in result[ConfigMetadataKey.PARAMETERS].keys())
        self.assert_("bar" in result[ConfigMetadataKey.PARAMETERS].keys())

    def test_verify_muttable(self):
        """
        Verify the verify_not_read_only works as expected.
        """
        self.protocol._param_dict.add('ro', r'', None, None, visibility=ParameterDictVisibility.READ_ONLY)
        self.protocol._param_dict.add('immutable', r'', None, None, visibility=ParameterDictVisibility.IMMUTABLE)
        self.protocol._param_dict.add('rw', r'', None, None, visibility=ParameterDictVisibility.READ_WRITE)

        # Happy Path
        self.protocol._verify_not_readonly({'rw': 1})
        self.protocol._verify_not_readonly({'rw': 1, 'immutable': 2}, startup=True)

        with self.assertRaises(InstrumentParameterException):
            self.protocol._verify_not_readonly({'rw': 1, 'immutable': 2})

        with self.assertRaises(InstrumentParameterException):
            self.protocol._verify_not_readonly({'rw': 1, 'ro': 2})

        with self.assertRaises(InstrumentParameterException):
            self.protocol._verify_not_readonly({'rw': 1, 'ro': 2}, startup=True)

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
        
