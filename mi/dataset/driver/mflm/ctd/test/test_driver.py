"""
@package mi.dataset.driver.mflm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Test cases for mflm_ctd driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import unittest
import os
import binascii

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import InstrumentParameterException
from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverEvent

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetUnitTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.driver.mflm.ctd.driver import MflmCTDMODataSetDriver
from mi.dataset.parser.ctdmo import CtdmoParserDataParticle

from pyon.agent.agent import ResourceAgentState

from interface.objects import CapabilityType
from interface.objects import AgentCapability
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent


DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.ctd.driver',
    driver_class="MflmCTDMODataSetDriver",
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmCTDMODataSetDriver.stream_config(),
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': 'node59p1.dat',
            'frequency': 1,
        },
        'parser': {}
    }
)

SAMPLE_STREAM='ctdmo_parsed'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def clean_file(self):
        # remove just the file we are using
        driver_config = self._driver_config()['startup_config']
        log.debug('startup config %s', driver_config)
        fullfile = os.path.join(driver_config['harvester']['directory'],
                            driver_config['harvester']['pattern'])
        if os.path.exists(fullfile):
            os.remove(fullfile)

    def test_get(self):
        self.clean_file()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_1.txt.result.yml',
                         count=3, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_2.txt.result.yml',
                         count=11, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data("node59p1_step4.dat", "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, count=23, timeout=10)

        self.driver.stop_sampling()
        # reset the parser and harvester states
        self.driver.clear_states()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, count=3, timeout=10)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        self.clean_file()

        # create the file so that it is unreadable
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.clean_file()

        # Create and store the new driver state
        self.memento = {DataSourceConfigKey.HARVESTER: {'last_filesize': 893,
                                                        'last_checksum': 'b859e40320ac396a5991d80a655bc161'},
                        DataSourceConfigKey.PARSER: {'in_process_data': [],
                                                     'unprocessed_data':[[0,50], [374,432], [892,893]],
                                                     'timestamp': 3583656001.0}}
        self.driver = MflmCTDMODataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(CtdmoParserDataParticle, 'test_data_2.txt.result.yml',
                         count=11, timeout=10)

    def test_sequences(self):
        """
        Test new sequence flags are set correctly.  There is only one file
        that just has data appended or inserted into it, so new sequences
        can occur in both cases, or if there is missing data in between two sequences
        """

        self.clean_file()

        self.driver.start_sampling()

        self.clear_async_data()

        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests (no new sequences)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_1-2.txt.result.yml',
                         count=14, timeout=10)

        # This file has had a section of CT data replaced with 0s, this should start a new
        # sequence for the data following the missing CT data
        self.clear_async_data()
        self.create_sample_data('node59p1_step3.dat', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_3.txt.result.yml',
                         count=12, timeout=10)

        # Now fill in the zeroed section from step3, this should just return the new
        # data with a new sequence flag
        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_4.txt.result.yml',
                         count=12, timeout=10)

        # start over now, using step 4, make sure sequence flags just account for
        # missing data in file (there are some sections of bad data that don't
        # match in headers, [0-50], [374-432], [1197-1471]
        self.driver.stop_sampling()
        # reset the parser and harvester states
        self.driver.clear_states()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_1-4.txt.result.yml',
                         count=39, timeout=10)
    
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def clean_file(self):
        # remove just the file we are using
        driver_config = self._driver_config()['startup_config']
        log.debug('startup config %s', driver_config)
        fullfile = os.path.join(driver_config['harvester']['directory'],
                            driver_config['harvester']['pattern'])
        if os.path.exists(fullfile):
            os.remove(fullfile)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.clean_file()

        self.create_sample_data('node59p1_step1.dat', "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Right now, there is an issue with keeping records in order,
        # which has to do with the sleep time in get_samples in
        # instrument_agent_client.  By setting this delay more than the
        # delay in get_samples, the records are returned in the expected
        # otherwise they are returned out of order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Verify we get one sample
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 3)
            log.info("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test a large import
        """
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,38,120)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('node59p1_step1.dat', "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('node59p1_step2.dat', "node59p1.dat")
            # Now read the first four records of the second file then stop
            result1 = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 8 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(SAMPLE_STREAM, 8)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_2.txt.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        self.clean_file()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat", mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clean_file()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.clean_file()
        # file contains invalid sample values
        self.create_sample_data('node59p1_bad.dat', "node59p1.dat")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(SAMPLE_STREAM, 2)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_extra_data(self):
        """
        Test that the remaining part of a chunk is skipped if data is
        read with extra data in between samples (meaning data has
        been corrupted)
        """
        self.clean_file()
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        self.event_subscribers.clear_events()
        # this data has both extra data and invalid sample values in it
        self.create_sample_data('node59p1_extra.dat', "node59p1.dat")
        result = self.get_samples(SAMPLE_STREAM, 31, 60)
        # make sure the invalid sample is recognized
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        # check that the right samples are skipped
        self.assert_data_values(result, 'test_data_extra.txt.result.yml')
