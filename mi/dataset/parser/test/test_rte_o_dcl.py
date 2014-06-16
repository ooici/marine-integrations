#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_rte_o_dcl
@file marine-integrations/mi/dataset/parser/test/test_rte_o_dcl.py
@author Jeff Roy
@brief Test code for a rte_o_dcl data parser
"""

import time
import copy
import re
import ntplib

from nose.plugins.attrib import attr
from StringIO import StringIO

from dateutil import parser

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.rte_o_dcl import RteODclParser, RteODclParserDataParticle, StateKey, LOG_TIME_MATCHER

@attr('UNIT', group='mi')
class RteODclParserUnitTestCase(ParserUnitTestCase):
    
    TEST_DATA = """
2013/11/16 20:35:35.965 [rte:DLOGP3]:3712-50060, RTE Control Board Firmware REV 1.0, 11/07/2013\r
2013/11/16 20:35:35.999 [rte:DLOGP3]:>Standard Power Mode activated!\r
2013/11/16 20:36:22.111 [rte:DLOGP3]:Instrument Started [No Initialize]\r
2013/11/16 20:46:24.989 Coulombs = 1.1110C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.02V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 20:56:25.633 Coulombs = 1.1055C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:06:26.400 Coulombs = 1.1055C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:16:27.303 Coulombs = 1.1073C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:26:30.002 Coulombs = 1.1110C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 23:17:13.193 [rte:DLOGP3]:Instrument Stopped [No Initialize]\r
"""

    BAD_TEST_DATA = """
2013/11/16 20:35:35.965 [rte:DLOGP3]:3712-50060, RTE Control Board Firmware REV 1.0, 11/07/2013\r
2013/11/16 20:35:35.999 [rte:DLOGP3]:>Standard Power Mode activated!\r
2013/11/16 20:36:22.111 [rte:DLOGP3]:Instrument Started [No Initialize]\r
2013/11/16 20:46:24.989 Coulombs = 1.1110C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.02V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 20:56:25.633 Coulombs = 1.1055C, AVG Q_RTE CurrAnt = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:06:26.400 Coulombs = 1.1055C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:16:27.303 Coulombs = 1.1073C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 21:26:30.002 Coulombs = 1.1110C, AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r
2013/11/16 23:17:13.193 [rte:DLOGP3]:Instrument Stopped [No Initialize]\r
"""

    """
    RteODcl Parser unit test suite
    """
    @staticmethod
    
    # Since this came from the code we are testing there is no way to tell if the timestamp is acutally correct!
    def _convert_string_to_timestamp(ts_str):
        """
        Converts the given string from this data stream's format into an NTP
        timestamp. 
        @param ts_str The timestamp string in the format "yyyy/mm/dd hh:mm:ss.sss"
        @retval The NTP4 timestamp
        """
        match = LOG_TIME_MATCHER.match(ts_str)
        if not match:
            raise ValueError("Invalid time format: %s" % ts_str)

        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%fZ" % (
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), float(match.group(6))
        )
        log.trace("converted ts '%s' to '%s'", ts_str[match.start(0):(match.start(0) + 24)], zulu_ts)

        converted_time = float(parser.parse(zulu_ts).strftime("%s.%f"))
        adjusted_time = converted_time - time.timezone
        ntptime = ntplib.system_to_ntp_time(adjusted_time)

        log.trace("Converted time \"%s\" (unix: %s) into %s", ts_str, adjusted_time, ntptime)
        return ntptime

    
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to match what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.rte_o_dcl',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'RteODclParserDataParticle'
            }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        
        self.start_state = {StateKey.POSITION:0}
        self.timestamp1 = self._convert_string_to_timestamp('2013/11/16 20:46:24.989 ')
        self.particle_a = RteODclParserDataParticle(
            "2013/11/16 20:46:24.989 Coulombs = 1.1110C, AVG Q_RTE Current = 0.002A, " \
            "AVG RTE Voltage = 12.02V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r\n" ,
            internal_timestamp=self.timestamp1)  

        self.timestamp2 = self._convert_string_to_timestamp('2013/11/16 20:56:25.633 ')
        self.particle_b = RteODclParserDataParticle(
            "2013/11/16 20:56:25.633 Coulombs = 1.1055C, AVG Q_RTE Current = 0.002A, " \
            "AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r\n" ,
            internal_timestamp=self.timestamp2)  
 
        self.timestamp3 = self._convert_string_to_timestamp('2013/11/16 21:06:26.400 ')
        self.particle_c = RteODclParserDataParticle(
            "2013/11/16 21:06:26.400 Coulombs = 1.1055C, AVG Q_RTE Current = 0.002A, " \
            "AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r\n" ,
            internal_timestamp=self.timestamp3)  

        self.timestamp4 = self._convert_string_to_timestamp('2013/11/16 21:16:27.303 ')
        self.particle_d = RteODclParserDataParticle(
            "2013/11/16 21:16:27.303 Coulombs = 1.1073C, AVG Q_RTE Current = 0.002A, " \
            "AVG RTE Voltage = 12.03V, AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1\r\n" ,
            internal_timestamp=self.timestamp4)
        
        self.state_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(RteODclParserUnitTestCase.TEST_DATA)
        self.parser = RteODclParser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 395, self.timestamp1, self.particle_a)
 
        result = self.parser.get_records(1)
        self.assert_result(result, 549, self.timestamp2, self.particle_b)

        result = self.parser.get_records(1)
        self.assert_result(result, 703, self.timestamp3, self.particle_c)

        result = self.parser.get_records(1)
        self.assert_result(result, 857, self.timestamp4, self.particle_d)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(RteODclParserUnitTestCase.TEST_DATA)
        self.parser = RteODclParser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_d])
        self.assertEqual(self.parser._state[StateKey.POSITION], 857)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 857)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:549}
        self.stream_handle = StringIO(RteODclParserUnitTestCase.TEST_DATA)
        self.parser = RteODclParser(self.config, new_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 703, self.timestamp3, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 857, self.timestamp4, self.particle_d)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:549}
        self.stream_handle = StringIO(RteODclParserUnitTestCase.TEST_DATA)
        self.parser = RteODclParser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 395, self.timestamp1, self.particle_a)

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 703, self.timestamp3, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 857, self.timestamp4, self.particle_d)

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        self.stream_handle = StringIO(RteODclParserUnitTestCase.BAD_TEST_DATA)
        self.parser = RteODclParser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 395, self.timestamp1, self.particle_a)
 
        result = self.parser.get_records(1)
        self.assert_result(result, 703, self.timestamp3, self.particle_c)

