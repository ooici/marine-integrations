"""
@package mi.dataset.driver.mflm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn (original telemetered), Steve Myerson (recovered)
@brief Test cases for mflm_ctd driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]

Recovered CO files:
  CTD02000.DAT
    1 CT block
    0 CO blocks
  CTD02001.DAT
    1 CT
    1 CO w/6 records, 5 valid IDs
  CTD02002.DAT
    1 CO w/4 records, 3 valid IDs
    1 CT
    1 CO w/6 records, 4 valid IDs
  CTD02004.DAT
    1 CT
    1 CO w/2 records, 0 valid IDs
    1 CO w/2 records, 1 valid ID
    1 CO w/5 records, 4 valid IDs
    1 CT
    1 CO w/10 records, 10 valid IDs
  CTD02100.DAT
    1 CT
    1 CO w/100 records, 100 valid IDs
    1 CO w/150 records, 150 valid IDs
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import unittest
import os
import binascii
from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.idk.util import remove_all_files
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import InstrumentParameterException
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.driver.mflm.ctd.driver import \
    MflmCtdmoDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.ctdmo import \
    CtdmoRecoveredCoParser, \
    CtdmoRecoveredCtParser, \
    CtdmoTelemeteredParser, \
    CtdmoRecoveredInstrumentDataParticle, \
    CtdmoRecoveredOffsetDataParticle, \
    CtdmoTelemeteredInstrumentDataParticle, \
    CtdmoTelemeteredOffsetDataParticle, \
    CtdmoStateKey, \
    DataParticleType

REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.ctd.driver',
    driver_class="MflmCtdmoDataSetDriver",
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmCtdmoDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CTDMO_GHQR_CO:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: 'CTD*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.CTDMO_GHQR_CT:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: 'SBE-37-IM_*.hex',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.CTDMO_GHQR_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.CTDMO_GHQR_CO: {CtdmoStateKey.INDUCTIVE_ID: 55},
            DataTypeKey.CTDMO_GHQR_CT: {CtdmoStateKey.INDUCTIVE_ID: 55,
                                        CtdmoStateKey.SERIAL_NUMBER: 03710261},
            DataTypeKey.CTDMO_GHQR_SIO_MULE: {CtdmoStateKey.INDUCTIVE_ID: 55}
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

    def test_back_fill(self):
        """
        Telemetered only.
        Test refilled blocks are sent correctly.  There is only one file
        that just has data appended or inserted into it, or if there is missing
        data can be added back later
        """

        self.create_sample_data_set_dir("node59p1_step1.dat", TEL_DIR, "node59p1.dat")

        self.driver.start_sampling()

        # step 1 contains 4 blocks, start with this and get both since we used them
        # separately in other tests
        self.clear_async_data()
        self.assert_data(CtdmoTelemeteredInstrumentDataParticle,
                         'test_data_1.txt.result.yml', count=4, timeout=10)

        # This file has had a section of CT data replaced with 0s
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step3.dat', TEL_DIR, "node59p1.dat")
        self.assert_data(CtdmoTelemeteredInstrumentDataParticle,
                         'test_data_3.txt.result.yml', count=2, timeout=10)

        # Now fill in the zeroed section from step3, this should just return the new
        # data
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TEL_DIR, "node59p1.dat")
        self.assert_data((CtdmoTelemeteredInstrumentDataParticle,
                          CtdmoTelemeteredOffsetDataParticle),
                        'test_data_4.txt.result.yml', count=4, timeout=10)

    def test_get(self):
        """
        Recovered and Telemetered.
        Test that we can get data from multiple files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Create sample data for telemetered and recovered data.
        self.create_sample_data_set_dir("node59p1_step1.dat", TEL_DIR, "node59p1.dat")
        self.create_sample_data_set_dir('CTD02001.DAT', REC_DIR, 'CTD02001.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.assert_data(CtdmoTelemeteredInstrumentDataParticle,
                         'test_data_1.txt.result.yml', count=4, timeout=10)

        log.info("============ TEST GET READ REC CO FILE =================")
        self.assert_data(CtdmoRecoveredOffsetDataParticle,
                         'CTD02001.yml', count=5, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", TEL_DIR, "node59p1.dat")
        self.assert_data(CtdmoTelemeteredInstrumentDataParticle,
                         'test_data_2.txt.result.yml', count=2, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step4.dat",
                                        TEL_DIR, "node59p1.dat")
        self.assert_data((CtdmoTelemeteredInstrumentDataParticle,
                          CtdmoTelemeteredOffsetDataParticle),
                         count=4, timeout=10)

        self.driver.stop_sampling()

        log.info("================ END INTEG TEST GET =====================")

    def test_harvester_new_file_exception(self):
        """
        Telemetered only.
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node59p1_step1.dat", TEL_DIR, "node59p1.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_harvester_new_file_exception_rec_co(self):
        """
        Recovered CO only.
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        log.info("=== START INTEG TEST HARVESTER NEW FILE EXCEPTION REC CO ===")

        # create the file so that it is unreadable
        self.create_sample_data_set_dir('CTD02000.DAT', REC_DIR,
                                        'CTD02000.DAT', mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

        log.info("=== END INTEG TEST HARVESTER NEW FILE EXCEPTION REC CO ===")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.create_sample_data_set_dir("node59p1_step1.dat", TEL_DIR, "node59p1.dat")
        driver_config = self._driver_config()['startup_config']

        full_file = os.path.join(
            driver_config['harvester'][DataTypeKey.CTDMO_GHQR_SIO_MULE]['directory'],
            driver_config['harvester'][DataTypeKey.CTDMO_GHQR_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(full_file)

        # Create the data for the Recovered CO parser.
        rec_co_path = self.create_sample_data_set_dir('CTD02002.DAT', REC_DIR,
                                                      'CTD02002.DAT')

        # Create and store the new driver state
        memento = {
            DataTypeKey.CTDMO_GHQR_SIO_MULE: {
                "node59p1.dat": {
                    DriverStateKey.FILE_SIZE: 6000,
                    DriverStateKey.FILE_CHECKSUM: 'aa1cc1aa816e99e11d8e88fc56f887e7',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.IN_PROCESS_DATA: [],
                        StateKey.UNPROCESSED_DATA:
                            [[0, 12], [336, 394], [5924,6000]],
                        StateKey.FILE_SIZE: 6000
                    }
                }
            },
            DataTypeKey.CTDMO_GHQR_CO: {
                'CTD02002.DAT': self.get_file_state(rec_co_path, False, 0x92)
            },
            DataTypeKey.CTDMO_GHQR_CT: {

            }
        }
        driver = MflmCtdmoDataSetDriver(
            self._driver_config()['startup_config'],
            memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat",
                                        TEL_DIR, "node59p1.dat")

        driver.start_sampling()

        # verify data is produced
        log.info("=== MID STATE READ TEL FILE ===")
        self.assert_data(CtdmoTelemeteredInstrumentDataParticle,
                         'test_data_2.txt.result.yml', count=2, timeout=10)

        # Only the last 4 particles should be read.
        log.info("=== MID STATE READ END OF REC CO FILE ===")
        self.assert_data(CtdmoRecoveredOffsetDataParticle,
                         'CTD02002_last4.yml', count=4, timeout=10)

    
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        self.create_sample_data_set_dir('node59p1_step4.dat', TEL_DIR, "node59p1.dat", mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TEL_DIR, "node59p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_large_import(self):
        """
        Test a large import
        """
        self.create_sample_data_set_dir('node59p1.dat', TEL_DIR)
        self.create_sample_data_set_dir('CTD02100.DAT', REC_DIR)
        self.assert_initialize()

        self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 2550, 200)
        self.data_subscribers.get_samples(DataParticleType.REC_CO_PARTICLE, 150, 150)
        self.data_subscribers.get_samples(DataParticleType.TEL_CO_PARTICLE, 100, 60)
        self.data_subscribers.get_samples(DataParticleType.REC_CO_PARTICLE, 100, 150)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """

        self.create_sample_data_set_dir('CTD02004.DAT', REC_DIR, 'CTD02004.DAT')
        self.create_sample_data_set_dir('node59p1_step1.dat', TEL_DIR, "node59p1.dat")

        self.assert_initialize()

        try:
            # Verify we get samples
            result = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 4)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')

            # Get the Recovered CO particles.
            result = self.data_subscribers.get_samples(DataParticleType.REC_CO_PARTICLE, 15)

            # Verify values
            self.assert_data_values(result, 'CTD02004.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent and
        confirm it restarts at the correct spot.
        """
        self.create_sample_data_set_dir('CTD02002.DAT', REC_DIR, 'CTD02002.DAT')
        self.create_sample_data_set_dir('node59p1_step1.dat', TEL_DIR, "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get the correct samples
        try:
            # Read the first Telemetered file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 4)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 0)
            self.assert_sample_queue_size(DataParticleType.TEL_CO_PARTICLE, 0)

            # Read and verify the first 3 records from the Recovered CO file.
            rec_co_result = self.data_subscribers.get_samples(DataParticleType.REC_CO_PARTICLE, 3)
            self.assert_data_values(rec_co_result, 'CTD02002_first3.yml')

            # Update the Telemetered file.
            self.create_sample_data_set_dir('node59p1_step4.dat', TEL_DIR, "node59p1.dat")

            # Now read the first record of the second Telemetered file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 3)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 0)
            self.assert_sample_queue_size(DataParticleType.TEL_CO_PARTICLE, 0)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # Restart sampling and ensure we get the last record of the file
            result2 = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 2)

            # Read and verify the last 4 records from the Recovered CO file.
            rec_co_result = self.data_subscribers.get_samples(DataParticleType.REC_CO_PARTICLE, 4)
            self.assert_data_values(rec_co_result, 'CTD02002_last4.yml')

            # Back to the telemetered file.
            result3 = self.data_subscribers.get_samples(DataParticleType.TEL_CO_PARTICLE, 1)
            result = result1
            result.extend(result2)
            result.extend(result3)
            self.assert_data_values(result, 'test_data_2-4.txt.result.yml')

            # there are 3 more CT samples in this telemetered file
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 3)
            self.assert_sample_queue_size(DataParticleType.TEL_CO_PARTICLE, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        self.create_sample_data_set_dir('node59p1_step1.dat', TEL_DIR, "node59p1.dat")
        self.create_sample_data_set_dir('CTD02004.DAT', REC_DIR, 'CTD02004.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        co_particle = DataParticleType.REC_CO_PARTICLE

        # Verify we get the correct samples
        try:
            # Read and verify the first 5 records from the Recovered CO file.
            #rec_co_result = self.data_subscribers.get_samples(co_particle, 5, 10)
            #self.assert_data_values(rec_co_result, 'CTD02004_first5.yml')

            # Read the first telemetered file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 4)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 0)

            # Update telemetered file.
            self.create_sample_data_set_dir('node59p1_step2.dat', TEL_DIR, "node59p1.dat")

            # Read the first record of the second telemetered file.
            result1 = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 1)

            # Stop sampling.
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 0)

            # Restart sampling and ensure we get the last record of the file
            self.assert_start_sampling()

            result2 = self.data_subscribers.get_samples(DataParticleType.TEL_CT_PARTICLE, 1)
            result = result1
            result.extend(result2)
            self.assert_data_values(result, 'test_data_2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.TEL_CT_PARTICLE, 0)

            # Read and verify the last 10 records from the Recovered CO file.
            #rec_co_result = self.data_subscribers.get_samples(co_particle, 10, 20)
            #self.assert_data_values(rec_co_result, 'CTD02004_last10.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('======= END OF QUAL TEST STOP START ======')

    def test_stop_start_rec(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        co_particle = DataParticleType.REC_CO_PARTICLE

        #self.create_sample_data_set_dir('CTD02002.DAT', REC_DIR, 'CTD02002.DAT')
        #expected_particles = 7

        self.create_sample_data_set_dir('CTD02004.DAT', REC_DIR, 'CTD02004.DAT')
        expected_particles = 15

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()
        log.debug('SIO SET QQQ0 %d',
                  len(self.data_subscribers.samples_received.get(co_particle)))

        # Verify we get the correct samples
        try:
            first_read = 1
            second_read = expected_particles - first_read

            log.debug('SIO SET QQQ1 %d',
                      len(self.data_subscribers.samples_received.get(co_particle)))

            # Get the first 5 Recovered CO particles.
            if first_read > 0:
                result1 = self.data_subscribers.get_samples(co_particle, first_read, 20)
            else:
                result1 = []

            log.debug('SIO SET QQQ2 %d',
                      len(self.data_subscribers.samples_received.get(co_particle)))

            # Stop and then restart sampling.
            self.assert_stop_sampling()
            self.assert_start_sampling()
            log.debug('SIO SET QQQ3 %d',
                      len(self.data_subscribers.samples_received.get(co_particle)))

            # Get the last 10 Recovered CO particles.
            #result2 = self.data_subscribers.get_samples(co_particle, 10, 20)
            result2 = self.data_subscribers.get_samples(co_particle, second_read, 20)

            # Verify values
            result1.extend(result2)
            #self.assert_data_values(result1, 'CTD02002.yml')
            self.assert_data_values(result1, 'CTD02004.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('======= END OF QUAL TEST STOP START REC ======')

    def test_simple(self):

        self.create_sample_data_set_dir('CTD02004.DAT', REC_DIR, 'CTD02004.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        co_particle = DataParticleType.REC_CO_PARTICLE

        # Verify we get the correct samples
        try:
            # Get the first 5 Recovered CO particles.
            result1 = self.data_subscribers.get_samples(co_particle, 5, 10)

            # Get the last 10 Recovered CO particles.
            result2 = self.data_subscribers.get_samples(co_particle, 10, 20)

            # Verify values
            result1.extend(result2)
            self.assert_data_values(result1, 'CTD02004.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")
