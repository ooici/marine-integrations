"""
@package mi.dataset.driver.flntu_x.mmp_cds.test.test_driver
@file marine-integrations/mi/dataset/driver/flntu_x/mmp_cds/driver.py
@author Jeremy Amundson
@brief Test cases for Flntu/Flcdr-x-mmps-cds driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger;
log = get_logger()
from mi.idk.exceptions import SampleTimeout
import os
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.flntu_x.mmp_cds.driver import FlntuXMmpCdsDataSetDriver, \
                                                     DataParticleType

from mi.dataset.parser.flntu_x_mmp_cds import FlntuXMmpCdsParserDataParticle
from mi.dataset.parser.flcdr_x_mmp_cds import FlcdrXMmpCdsParserDataParticle

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

DIR_FLNTU = '/tmp/flntu/flntu'
DIR_FLCDR = '/tmp/flntu/flcdr'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.flntu_x.mmp_cds.driver',
    driver_class='FlntuXMmpCdsDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = FlntuXMmpCdsDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'flntu_x_mmp_cds',
        DataSourceConfigKey.HARVESTER:
        {
            DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_FLNTU,
                DataSetDriverConfigKeys.PATTERN: '*.mpk',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_FLCDR,
                DataSetDriverConfigKeys.PATTERN: '*.mpk',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT: {},
            DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT: {}
        }
    }
)



###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        #self.clear_async_data()
        self.create_sample_data_set_dir('flntu_1_20131124T005004_458.mpk', DIR_FLNTU, "E0000001.mpk")
        self.create_sample_data_set_dir('flcdr_1_20131124T005004_458.mpk', DIR_FLCDR, "E0000001.mpk")

        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first.yml', count=1, timeout=5)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_cdr.yml', count=1, timeout=5)

        self.get_samples(FlntuXMmpCdsParserDataParticle, count=91, timeout=10)
        self.get_samples(FlcdrXMmpCdsParserDataParticle, count=196, timeout=10)


        self.create_sample_data_set_dir('flntu_1_20131124T005004_459.mpk', DIR_FLNTU, "E0000002.mpk")
        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first1.yml', count=1, timeout=5)

        self.create_sample_data_set_dir('flcdr_1_20131124T005004_459.mpk', DIR_FLCDR, "E0000002.mpk")
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first1_cdr.yml', count=1, timeout=5)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data_set_dir('flcdr_1_20131124T005004_458.mpk', DIR_FLCDR, "test_stop_resume.mpk")
        self.create_sample_data_set_dir('flntu_1_20131124T005004_458.mpk', DIR_FLNTU, "test_stop_resume.mpk")

        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_cdr.yml', count=1, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.assert_data(FlntuXMmpCdsParserDataParticle, 'second.yml', count=1, timeout=10)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'second_cdr.yml', count=1, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data_set_dir('flcdr_1_20131124T005004_459.mpk', DIR_FLCDR, "F0000001.mpk")
        self.create_sample_data_set_dir('flntu_1_20131124T005004_459.mpk', DIR_FLNTU, "E0000001.mpk")
        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first_four.yml', count=4, timeout=10)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_four_cdr.yml', count=4, timeout=10)

        self.create_sample_data_set_dir('flcdr_1_20131124T005004_458.mpk', DIR_FLCDR, "F0000000.mpk")
        self.create_sample_data_set_dir('flntu_1_20131124T005004_458.mpk', DIR_FLNTU, "E0000000.mpk")
        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_cdr.yml', count=1, timeout=10)

        # Retrieve all remaining samples
        self.get_samples(FlntuXMmpCdsParserDataParticle, count=91, timeout=10)
        self.get_samples(FlcdrXMmpCdsParserDataParticle, count=196, timeout=15)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Clear the sample file data
        self.clear_sample_data()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.create_sample_data_set_dir('flntu_1_20131124T005004_458.mpk', DIR_FLNTU, "E0000002.mpk")
        self.create_sample_data_set_dir('flcdr_1_20131124T005004_458.mpk', DIR_FLCDR, "F0000002.mpk")

        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_cdr.yml', count=1, timeout=10)

    def test_get_any_order(self):
        """
        Test that we can get data from files for all harvesters / parsers.
        """
        log.info("=========== START INTEG TEST GET ANY ORDER ================")

        # Start sampling.
        self.driver.start_sampling()

        self.clear_async_data()

        self.create_sample_data_set_dir(
            'flntu_1_20131124T005004_459.mpk', DIR_FLNTU, 'E0000002.mpk')

        self.create_sample_data_set_dir(
            'flntu_1_20131124T005004_458.mpk', DIR_FLNTU, 'E0000001.mpk')

        self.create_sample_data_set_dir(
            'flcdr_1_20131124T005004_459.mpk', DIR_FLCDR, 'E0000004.mpk')

        self.create_sample_data_set_dir(
            'flcdr_1_20131124T005004_458.mpk', DIR_FLCDR, 'E0000003.mpk')

        # get the first particle from the live directory
        self.assert_data(FlntuXMmpCdsParserDataParticle, 'first.yml',
                         count=1, timeout=10)

        # get the first particle from the recovered directory
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'first_cdr.yml',
                         count=1, timeout=10)

        # get the next 4 particles from the live directory
        self.assert_data(FlntuXMmpCdsParserDataParticle, 'second.yml',
                         count=1, timeout=10)

        # get the next 4 particles from the recovered directory
        self.assert_data(FlcdrXMmpCdsParserDataParticle, 'second_cdr.yml',
                         count=1, timeout=10)


    def test_sample_exception(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        self.create_sample_data_set_dir('not-msg-pack.mpk', DIR_FLNTU, 'BAD.mpk')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        self.create_sample_data_set_dir('BAD.mpk', DIR_FLCDR, 'BAD.mpk')

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('flntu_1_20131124T005004_459.mpk', DIR_FLNTU, 'E0000001.mpk')
        self.create_sample_data_set_dir('flcdr_1_20131124T005004_459.mpk', DIR_FLCDR, 'E0000002.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            resulta = self.data_subscribers.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 4)
            resultb = self.data_subscribers.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 4)
            log.debug("RESULT: %s", resulta)
            log.debug("RESULT: %s", resultb)

            # Verify values
            self.assert_data_values(resulta, 'first_four.yml')
            self.assert_data_values(resultb, 'first_four_cdr.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('flntu_1_20131124T005004_458.mpk', DIR_FLNTU)
        self.create_sample_data_set_dir('flcdr_1_20131124T005004_458.mpk',  DIR_FLCDR)
        self.assert_initialize()

        # get results for each of the data particle streams
        self.data_subscribers.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 92, 40)
        self.data_subscribers.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 196, 40)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get two samples
        try:

            self.create_sample_data_set_dir('flntu_1_20131124T005004_459.mpk', DIR_FLNTU, "E0000002.mpk")
            self.create_sample_data_set_dir('flcdr_1_20131124T005004_459.mpk', DIR_FLCDR, "E0000002.mpk")
            # Now read the first two records of the second file then stop
            resulta = self.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 2)
            resultb = self.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 2)

            log.debug("got result 1 %s", resulta)
            log.debug("got result 1 %s", resultb)

            self.assert_stop_sampling()

            self.assert_sample_queue_size(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 0)
            self.assert_sample_queue_size(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 0)

            self.assert_start_sampling()
            result2a = self.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 2)
            result2b = self.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 2)
            log.debug("got result 2 %s", result2a)
            resulta.extend(result2a)
            resultb.extend(result2b)
            self.assert_data_values(resulta, 'first_four.yml')
            self.assert_data_values(resultb, 'first_four_cdr.yml')

            self.assert_sample_queue_size(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 0)
            self.assert_sample_queue_size(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.create_sample_data_set_dir('flntu_1_20131124T005004_459.mpk', DIR_FLNTU,  "E0000002.mpk")
        self.create_sample_data_set_dir('flcdr_1_20131124T005004_459.mpk', DIR_FLCDR,  "E0000002.mpk")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data


            # Now read the first two records of the second file then stop
            resulta = self.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 2)
            resultb = self.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 2)
            log.debug("RESULT: %s", resulta)
            log.debug("RESULT: %s", resultb)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 0)
            self.assert_sample_queue_size(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 0)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            result2a = self.get_samples(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 2)
            result2b = self.get_samples(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 2)
            log.debug("got result 2 %s", result2a)
            resulta.extend(result2a)
            log.debug("got result 2 %s", result2b)
            resultb.extend(result2b)
            self.assert_data_values(resulta, 'first_four.yml')
            self.assert_data_values(resultb, 'first_four_cdr.yml')
            self.assert_sample_queue_size(DataParticleType.FLNTU_X_MMP_CDS_INSTRUMENT, 0)
            self.assert_sample_queue_size(DataParticleType.FLCDR_X_MMP_CDS_INSTRUMENT, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.assert_initialize()

        # Clear any prior events
        self.event_subscribers.clear_events()

        filename = 'not-msg-pack.mpk'
        self.create_sample_data_set_dir(filename, DIR_FLNTU)
        self.create_sample_data_set_dir(filename, DIR_FLCDR)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)



