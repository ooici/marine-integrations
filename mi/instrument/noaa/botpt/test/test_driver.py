"""
@package mi.instrument.noaa.iris.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/iris/ooicore/driver.py
@author David Everett
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

import time

import ntplib
from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger


log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.chunker import StringChunker
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.exceptions import SampleException
from mi.instrument.noaa.botpt.driver import NEWLINE


#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
# noinspection PyProtectedMember
@attr('UNIT', group='mi')
class BotptDriverUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def _send_port_agent_packet(self, driver, data_item):
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data_item)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(self._DataParticleType())
        self.assert_enum_has_no_duplicates(self._ProtocolState())
        self.assert_enum_has_no_duplicates(self._ProtocolEvent())
        self.assert_enum_has_no_duplicates(self._DriverParameter())
        self.assert_enum_has_no_duplicates(self._InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(self._Capability())
        self.assert_enum_complete(self._Capability(), self._ProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = self._Driver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(self._Protocol.sieve_function)

        for sample in self._sample_chunks:
            self.assert_chunker_sample(chunker, sample)
            self.assert_chunker_fragmented_sample(chunker, sample)
            self.assert_chunker_combined_sample(chunker, sample)
            self.assert_chunker_sample_with_noise(chunker, sample)

    def test_connect(self, initial_protocol_state=DriverProtocolState.COMMAND):
        """
        Verify driver transitions correctly and connects
        """
        driver = self._Driver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        return driver

    def test_data_build_parsed_values(self):
        """
        Verify that the BOTPT IRIS driver build_parsed_values method
        raises SampleException when an invalid sample is encountered
        and that it returns a result when a valid sample is encountered
        """
        for raw_data, particle_class, is_valid in self._build_parsed_values_items:
            sample_exception = False
            result = None
            try:
                result = particle_class(raw_data)._build_parsed_values()
            except SampleException as e:
                log.debug('SampleException caught: %s.', e)
                sample_exception = True
            if is_valid:
                self.assertFalse(sample_exception)
                self.assertIsInstance(result, list)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """

        driver = self._Driver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

    def test_handlers(self):
        for handler, initial_state, expected_state, prompt in self._test_handlers_items:
            driver = self.test_connect(initial_protocol_state=initial_state)
            driver._connection.send.side_effect = self.my_send(driver)
            result = getattr(driver._protocol, handler)()
            log.debug('handler: %r - result: %r expected: %r', handler, result, prompt)
            next_state = result[0]
            return_value = result[1][1]
            self.assertEqual(next_state, expected_state)
            if prompt is not None:
                self.assertTrue(return_value.endswith(prompt))

    def test_command_responses(self):
        """
        Verify that the driver correctly handles the various responses
        """
        driver = self.test_connect()
        for response, expected_prompt in self._command_response_items:
            log.debug('test_command_response: response: %r expected_prompt: %r', response, expected_prompt)
            self._send_port_agent_packet(driver, response)
            self.assertTrue(driver._protocol._get_response(expected_prompt=expected_prompt))

    def test_direct_access(self):
        driver = self.test_connect()
        for command in self._InstrumentCommand.list():
            driver._protocol._handler_direct_access_execute_direct(command)
        driver._protocol._handler_direct_access_execute_direct('BOGUS')
        self.assertEqual(driver._protocol._sent_cmds, self._InstrumentCommand.list())

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = self._Protocol(BaseEnum, NEWLINE, mock_callback)
        driver_capabilities = self._Capability().list()
        test_capabilities = self._Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities), sorted(protocol._filter_capabilities(test_capabilities)))