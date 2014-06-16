"""
@package mi.instrument.sunburst.sami2_pco2.ooicore.test.test_driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/ooicore/driver.py
@author Christopher Wingard
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Christopher Wingard & Kevin Stiemke'
__license__ = 'Apache 2.0'

import mock

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger

log = get_logger()

# MI imports.

# from mi.instrument.sunburst.driver import ProtocolEvent

# Added Imports (Note, these pick up some of the base classes not directly imported above)
from mi.instrument.sunburst.test.test_driver import SamiMixin
from mi.instrument.sunburst.test.test_driver import SamiUnitTest
from mi.instrument.sunburst.test.test_driver import SamiIntegrationTest
from mi.instrument.sunburst.test.test_driver import SamiQualificationTest
from mi.instrument.sunburst.test.test_driver import PumpStatisticsContainer
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocolState
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wParameter
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocolEvent

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

###
# Driver constant definitions
###


###############################################################################
#                           DRIVER TEST MIXIN                                 #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                            #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class Pco2DriverTestMixinSub(SamiMixin):
    pass


###############################################################################
#                                UNIT TESTS                                   #
#         Unit Tests: test the method calls and parameters using Mock.        #
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
@attr('UNIT', group='mi')
class Pco2DriverUnitTest(SamiUnitTest, Pco2DriverTestMixinSub):
    def assert_pump_commands(self, driver):

        self.assert_initialize_driver(driver)

        driver._protocol._connection.send.side_effect = self.send_newline_side_effect(driver._protocol)

        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.COMMAND
        for param in driver._protocol._param_dict.get_keys():
            log.debug('startup param = %s', param)
            driver._protocol._param_dict.set_default(param)

        driver._protocol._param_dict.set_value(Pco2wParameter.PUMP_100ML_CYCLES, 0x3)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML
        driver._protocol._handler_deionized_water_flush_execute_100ml()
        call = mock.call('P03,08\r')
        driver._protocol._connection.send.assert_has_calls(call)
        command_count = driver._protocol._connection.send.mock_calls.count(call)
        log.debug('DEIONIZED_WATER_FLUSH_100ML command count = %s', command_count)
        self.assertEqual(6, command_count, 'DEIONIZED_WATER_FLUSH_100ML command count %s != 6' % command_count)
        driver._protocol._connection.send.reset_mock()

        driver._protocol._param_dict.set_value(Pco2wParameter.PUMP_100ML_CYCLES, 0x5)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.REAGENT_FLUSH_100ML
        driver._protocol._handler_reagent_flush_execute_100ml()
        call = mock.call('P01,08\r')
        driver._protocol._connection.send.assert_has_calls([call])
        command_count = driver._protocol._connection.send.mock_calls.count(call)
        log.debug('REAGENT_FLUSH_100ML command count = %s', command_count)
        self.assertEqual(10, command_count, 'REAGENT_FLUSH_100ML command count %s != 10' % command_count)
        driver._protocol._connection.send.reset_mock()

        driver._protocol._param_dict.set_value(Pco2wParameter.DEIONIZED_WATER_FLUSH_DURATION, 0x27)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH
        driver._protocol._handler_deionized_water_flush_execute()
        call = mock.call('P03,27\r')
        driver._protocol._connection.send.assert_has_calls([call])
        command_count = driver._protocol._connection.send.mock_calls.count(call)
        log.debug('DEIONIZED_WATER_FLUSH command count = %s', command_count)
        self.assertEqual(1, command_count, 'DEIONIZED_WATER_FLUSH command count %s != 1' % command_count)
        driver._protocol._connection.send.reset_mock()

        driver._protocol._param_dict.set_value(Pco2wParameter.REAGENT_FLUSH_DURATION, 0x77)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.REAGENT_FLUSH
        driver._protocol._handler_reagent_flush_execute()
        call = mock.call('P01,77\r')
        driver._protocol._connection.send.assert_has_calls(call)
        command_count = driver._protocol._connection.send.mock_calls.count(call)
        log.debug('REAGENT_FLUSH command count = %s', command_count)
        self.assertEqual(1, command_count, 'REAGENT_FLUSH command count %s != 1' % command_count)
        driver._protocol._connection.send.reset_mock()

    def assert_pump_timing(self, driver):
        self.assert_initialize_driver(driver)

        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.COMMAND
        for param in driver._protocol._param_dict.get_keys():
            log.debug('startup param = %s', param)
            driver._protocol._param_dict.set_default(param)

        driver._protocol._param_dict.set_value(Pco2wParameter.PUMP_100ML_CYCLES, 0x3)
        stats = PumpStatisticsContainer(self, ('P03', '08'))
        driver._protocol._do_cmd_resp_no_wakeup = Mock(side_effect=stats.side_effect)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML
        driver._protocol._handler_deionized_water_flush_execute_100ml()
        stats.assert_timing(2)

        driver._protocol._param_dict.set_value(Pco2wParameter.PUMP_100ML_CYCLES, 0x5)
        stats = PumpStatisticsContainer(self, ('P01', '08'))
        driver._protocol._do_cmd_resp_no_wakeup = Mock(side_effect=stats.side_effect)
        driver._protocol._protocol_fsm.current_state = Pco2wProtocolState.REAGENT_FLUSH_100ML
        driver._protocol._handler_reagent_flush_execute_100ml()
        stats.assert_timing(2)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class Pco2DriverIntegrationTest(SamiIntegrationTest, Pco2DriverTestMixinSub):
    def test_flush_pump(self):
        self.assert_initialize_driver()
        self.assert_driver_command(Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH, delay=15.0)
        self.assert_driver_command(Pco2wProtocolEvent.REAGENT_FLUSH, delay=15.0)
        self.assert_driver_command(Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH_100ML, delay=15.0)
        self.assert_driver_command(Pco2wProtocolEvent.REAGENT_FLUSH_100ML, delay=15.0)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class Pco2DriverQualificationTest(SamiQualificationTest, Pco2DriverTestMixinSub):
    pass
