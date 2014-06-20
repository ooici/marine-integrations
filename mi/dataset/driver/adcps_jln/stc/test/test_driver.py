"""
@package mi.dataset.driver.adcps_jln.stc.test.test_driver
@file marine-integrations/mi/dataset/driver/adcps_jln/stc/driver.py
@author Maria Lutz
@brief Test cases for adcps_jln_stc driver
Release notes: Release 0.0.3 Driver modified to incorporate the
recovered data using ADCPS JLN parser to parse bindary PD0 files
modifications done by Jeff Roy jeffrey_a_roy@raytheon.com


USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'


from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from mi.core.log import get_logger
log = get_logger()

from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import \
    DataSetTestCase, \
    DataSetIntegrationTestCase, \
    DataSetQualificationTestCase

from mi.dataset.dataset_driver import \
    DriverParameter, \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys
from mi.dataset.driver.adcps_jln.stc.driver import \
    AdcpsJlnStcDataSetDriver, \
    DataTypeKey
from mi.dataset.parser.adcps_jln_stc import \
    DataParticleType as AdcpsJlnStcDataParticleType, \
    AdcpsJlnStcInstrumentParserDataParticle, \
    AdcpsJlnStcMetadataParserDataParticle
from mi.dataset.parser.adcps_jln import \
    DataParticleType as AdcpsJlnDataParticleType, \
    AdcpsJlnParticle


ADCPS_JLN_TELEM_DIR = '/tmp/dsatest1'
ADCPS_JLN_RECOVERED_DIR = '/tmp/dsatest2'

ADCPS_JLN_TELEM_PARTICLES = (AdcpsJlnStcInstrumentParserDataParticle,
                             AdcpsJlnStcMetadataParserDataParticle)

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.adcps_jln.stc.driver',
    driver_class='AdcpsJlnStcDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=AdcpsJlnStcDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'adcps_jln_stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.ADCPS_JLN_STC:
            {
                DataSetDriverConfigKeys.DIRECTORY: ADCPS_JLN_TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'adcp[st]_*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.ADCPS_JLN:
            {
                DataSetDriverConfigKeys.DIRECTORY: ADCPS_JLN_RECOVERED_DIR,
                DataSetDriverConfigKeys.PATTERN: '*.PD0',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.ADCPS_JLN_STC: {},
            DataTypeKey.ADCPS_JLN: {}

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
        log.info("### START INTEG TEST GET ###")

        self.clear_async_data()
        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_061817.DAT')

        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'first.result.yml', count=3, timeout=10)

        #adcpt_20140504_015742.DAT has headings in the 336 range to verify the heading fix
        self.create_sample_data_set_dir('adcpt_20140504_015742.DAT',
                                        ADCPS_JLN_TELEM_DIR)
        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'adcpt_20140504_015742.yml', count=13, timeout=10)

        self.create_sample_data_set_dir('ADCP_CCE1T_20.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        "ADCP_CCE1T_20.PD0")
        self.assert_data(AdcpsJlnParticle, 'ADCP_CCE1T_20.yml',
                         count=20, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("### START INTEG TEST STOP RESUME ###")

        self.clear_async_data()

        path_1 = self.create_sample_data_set_dir('first.DAT',
                                                 ADCPS_JLN_TELEM_DIR,
                                                 'adcpt_20130929_061817.DAT')

        path_2 = self.create_sample_data_set_dir('adcpt_20130929_091817.DAT',
                                                 ADCPS_JLN_TELEM_DIR)

        path_3 = self.create_sample_data_set_dir('ADCP_CCE1T_20.000',
                                                 ADCPS_JLN_RECOVERED_DIR,
                                                 'ADCP_CCE1T_20.PD0')
        path_4 = self.create_sample_data_set_dir('ADCP_CCE1T_21_40.000',
                                                 ADCPS_JLN_RECOVERED_DIR,
                                                 'ADCP_CCE1T_21_40.PD0')

        # Create and store the new driver state
        state = {DataTypeKey.ADCPS_JLN_STC: {
            'adcpt_20130929_061817.DAT': self.get_file_state(path_1, True, 880),
            'adcpt_20130929_091817.DAT': self.get_file_state(path_2, False, 880)},
            DataTypeKey.ADCPS_JLN: {
                # byte 1254 is the last byte of the first record
                'ADCP_CCE1T_20.PD0': self.get_file_state(path_3, True, 1254),
                # 9th record starts at 10032
                'ADCP_CCE1T_21_40.PD0': self.get_file_state(path_4, False, 10032)}
        }

        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(AdcpsJlnParticle, 'ADCP_CCE1T_29_40.yml', count=12, timeout=10)
        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'partial_second.result.yml', count=3, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        log.info("### START INTEG TEST STOP START RESUME ###")

        self.clear_async_data()
        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_061817.DAT')
        self.create_sample_data_set_dir('adcpt_20130929_091817.DAT',
                                        ADCPS_JLN_TELEM_DIR)
        self.create_sample_data_set_dir('ADCP_CCE1T_20.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T_20.PD0')
        self.create_sample_data_set_dir('ADCP_CCE1T_21_40.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T_21_40.PD0')

        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'first.result.yml', count=3, timeout=10)
        self.assert_file_ingested('adcpt_20130929_061817.DAT', DataTypeKey.ADCPS_JLN_STC)

        self.assert_data(AdcpsJlnParticle, 'ADCP_CCE1T_20.yml', count=20, timeout=10)
        self.assert_file_ingested('ADCP_CCE1T_20.PD0', DataTypeKey.ADCPS_JLN)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'second.result.yml', count=6, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

        self.assert_data(AdcpsJlnParticle, 'ADCP_CCE1T_21_40.yml', count=20, timeout=10)
        self.assert_file_ingested('ADCP_CCE1T_21_40.PD0', DataTypeKey.ADCPS_JLN)

    # The remaining integration tests only apply to the telemetered
    # data parsed by the adcps_jln_stc parser

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        log.info("### START INTEG TEST HARVESTER NEW FILE EXCEPTION ###")

        # need to override this because of or in configuration pattern '[st]' matches s or t
        filename = 'adcpt_foo.DAT'

        # create the file so that it is unreadable
        self.create_sample_data_set_dir(filename,
                                        ADCPS_JLN_TELEM_DIR,
                                        create=True, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST SAMPLE EXCEPTION ###")

        filename = 'adcpt_foo.DAT'
        self.create_sample_data_set_dir(filename,
                                        ADCPS_JLN_TELEM_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.ADCPS_JLN_STC)

    def test_no_footer(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST NO FOOTER ###")

        self.create_sample_data_set_dir('no_footer.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

    def test_no_header(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST NO HEADER ###")

        self.create_sample_data_set_dir('no_header.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

    def test_bad_id(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST BAD ID ###")

        self.create_sample_data_set_dir('bad_id.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'partial_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

    def test_bad_num_bytes(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST BAD NUM BYTES ###")

        self.create_sample_data_set_dir('missing_bytes.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'partial_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

    def test_receive_fail(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        log.info("### START INTEG TEST RECEIVE FAIL ###")

        # no error for receiveFailure marked samples
        self.create_sample_data_set_dir('recv_fail.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
    
        self.assert_data(ADCPS_JLN_TELEM_PARTICLES, 'first_fail.result.yml', count=3, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT', DataTypeKey.ADCPS_JLN_STC)

    def test_unpack_err(self):

        log.info("### START INTEG TEST UNPACK ERR ###")

        self.create_sample_data_set_dir('adcpt_20131113_002307.DAT',
                                        ADCPS_JLN_TELEM_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20131113_002307.DAT', DataTypeKey.ADCPS_JLN_STC)

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
        log.info("### START QUAL TEST PUBLISH PATH ###")

        #create telemtered data
        self.create_sample_data_set_dir('first.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_061817.DAT')
        #create recovered data
        self.create_sample_data_set_dir('ADCP_CCE1T_20.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T_20.PD0')

        self.assert_initialize()

        # Test Telemetered path

        # Verify we get 3 samples
        try:
            result = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Test Recovered path

        try:
            # Verify that we get 20  samples
            result = self.data_subscribers.get_samples(
                AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT, 20, 100)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'ADCP_CCE1T_20.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("### START QUAL TEST PUBLISH PATH ###")

        #create telemtered data
        self.create_sample_data_set_dir('adcpt_20130926_010110.DAT',
                                        ADCPS_JLN_TELEM_DIR)
        #create recovered data
        self.create_sample_data_set_dir('ADCP_CCE1T.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T.PD0')

        self.assert_initialize()

        # get results for each of the data particle streams
        self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
        self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 36, timeout=60)
        self.data_subscribers.get_samples(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT, 200, 400)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_061817.DAT')

        self.create_sample_data_set_dir('ADCP_CCE1T_21_40.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T_21_40.PD0')

        num_samples = 8
        max_time = 100  # seconds

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get 3 samples
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 0)

            self.create_sample_data_set_dir('adcpt_20130929_091817.DAT',
                                            ADCPS_JLN_TELEM_DIR)

            # Now read the first three records of the second file then stop
            result = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("got result %s", result)

            #get first 8 records and verify data
            samples1 = self.data_subscribers.get_samples(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT,
                                                         num_samples, max_time)
            self.assert_data_values(samples1, 'ADCP_CCE1T_21_28.yml')

            self.assert_stop_sampling()

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 3)
            log.debug("got result 3 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 0)

            num_samples = 12
            samples2 = self.data_subscribers.get_samples(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT,
                                                         num_samples, max_time)
            self.assert_data_values(samples2, 'ADCP_CCE1T_29_40.yml')

            #verify the queues is empty
            self.assert_sample_queue_size(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("START QUAL TEST SHUTDOWN RESTART")

        self.create_sample_data_set_dir('first.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_061817.DAT')

        self.create_sample_data_set_dir('ADCP_CCE1T_21_40.000',
                                        ADCPS_JLN_RECOVERED_DIR,
                                        'ADCP_CCE1T_21_40.PD0')

        num_samples = 8
        max_time = 100  # seconds

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get 3 samples
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 0)

            self.create_sample_data_set_dir('adcpt_20130929_091817.DAT', ADCPS_JLN_TELEM_DIR)

            # Now read the first three records of the second file then stop
            result = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
            result2 = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("got result %s", result)

            #get first 8 records and verify data
            samples1 = self.data_subscribers.get_samples(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT,
                                                         num_samples, max_time)

            self.assert_data_values(samples1, 'ADCP_CCE1T_21_28.yml')

            self.assert_stop_sampling()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            result3 = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 3)
            log.debug("got result 3 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 0)

            num_samples = 12
            samples2 = self.data_subscribers.get_samples(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT,
                                                         num_samples, max_time)
            self.assert_data_values(samples2, 'ADCP_CCE1T_29_40.yml')

            #verify the queues is empty
            self.assert_sample_queue_size(AdcpsJlnDataParticleType.ADCPS_JLN_INSTRUMENT, 0)

            log.info("END QUAL TEST SHUTDOWN RESTART")

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    #
    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file is empty, no samples
        filename = 'adcpt_foo.DAT'
        self.create_sample_data_set_dir(filename, ADCPS_JLN_TELEM_DIR)

        self.assert_initialize()

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_missing_bytes(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('missing_bytes.DAT',
                                        ADCPS_JLN_TELEM_DIR,
                                        'adcpt_20130929_091817.DAT')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 1)
        result2 = self.get_samples(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 1)
        result.extend(result2)
        
        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
        
        self.assert_data_values(result, 'partial_first.result.yml')
        self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_META, 0)
        self.assert_sample_queue_size(AdcpsJlnStcDataParticleType.ADCPS_JLN_INS, 0)

    def test_harvester_new_telem_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        filename = 'adcpt_foo.DAT'

        self.assert_new_file_exception(filename, ADCPS_JLN_TELEM_DIR)
    
    def test_harvester_new_recov_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        filename = 'adcpt_foo.PD0'

        self.assert_new_file_exception(filename, ADCPS_JLN_RECOVERED_DIR)

    def test_harvester_new_file_exception(self):
        """
        Need to overload the inherited test because it does not work for the
        adcps_jln_stc pattern.  The two tests above it replace it.
        """
        pass
