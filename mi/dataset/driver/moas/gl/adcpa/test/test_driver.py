"""
@package mi.dataset.driver.moas.gl.adcpa.test_driver
@file marine-integrations/mi/dataset/driver/moas.gl/adcpa/driver.py
@author Jeff Roy (Raytheon)
@brief Test cases for moas_gl_adcpa driver (for both telemetered and recovered data)

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeff Roy (Raytheon)'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from mi.core.log import get_logger; log = get_logger()
import os

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.idk.exceptions import IDKConfigMissing, IDKException
from mi.idk.util import remove_all_files

from mi.dataset.parser.adcpa_m_glider import DataParticleType

from mi.dataset.driver.moas.gl.adcpa.driver import \
    AdcpaDataSetDriver, \
    DataTypeKey, \
    AdcpaMGliderInstrumentParticle, \
    AdcpaMGliderRecoveredParticle

from mi.dataset.dataset_driver import \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys, \
    DriverParameter

from pyon.agent.agent import ResourceAgentState

DIR_ADCPA_LIVE = '/tmp/dsatest1'
DIR_ADCPA_RECOVERED = '/tmp/dsatest2'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.moas.gl.adcpa.driver',
    driver_class='AdcpaDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=AdcpaDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'moas_gl_adcpa',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.ADCPA_INSTRUMENT:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_ADCPA_LIVE,
                DataSetDriverConfigKeys.PATTERN: '*.PD0',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.ADCPA_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_ADCPA_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: '*.PD0',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.ADCPA_INSTRUMENT: {},
            DataTypeKey.ADCPA_RECOVERED: {}
        }
    }
)


# The integration and qualification tests generated here are suggested tests,
# but may not be enough to fully test your driver. Additional tests should be
# written as needed.

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def assert_file_ingested(self, filename, data_key):
        """
        Assert that a particular file was ingested
        Need to override for multiple harvester since we have the additional data_key
        If the ingested flag is not set in the driver state for this file, fail the test
        @ param filename name of the file to check that it was ingested using the ingested flag
        """
        log.debug("last state callback result %s", self.state_callback_result[-1])
        last_state = self.state_callback_result[-1][data_key]
        if not filename in last_state or not last_state[filename]['ingested']:
            self.fail("File %s was not ingested" % filename)

    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()

        log.info("LA101636_20.PD0 placed in Live directory")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'LA101636_20.PD0', DIR_ADCPA_LIVE)
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20.yml',
                         count=20, timeout=10)

        log.info("LB180210_50.PD0 placed in Recovered directory")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'LB180210_50.PD0', DIR_ADCPA_RECOVERED)
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_recovered.yml',
                         count=50, timeout=10)

    def test_get_any_order(self):
        """
        Test that we can get data from files for all harvesters / parsers.
        """
        log.info("=========== START INTEG TEST GET ANY ORDER  ================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()

        log.info("LA101636_20.PD0 placed in Live directory")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'LA101636_20.PD0', DIR_ADCPA_LIVE)

        log.info("LB180210_50.PD0 placed in Recovered directory")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'LB180210_50.PD0', DIR_ADCPA_RECOVERED)

        # get the first 5 particles from the live directory
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20_1_5.yml',
                         count=5, timeout=10)

        # get the first 12 particles from the recovered directory
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_1_12.yml',
                         count=12, timeout=10)

        # get the next 15 particles from the live directory
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20_6_20.yml',
                         count=15, timeout=10)

        # get the next 8 particles from the recovered directory
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_13_20.yml',
                         count=8, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("=========== START INTEG TEST STOP RESUME  ================")

        filename_1 = 'File_1.PD0'
        filename_2 = 'File_2.PD0'
        filename_3 = 'File_3.PD0'
        filename_4 = 'File_4.PD0'

        path_1 = self.create_sample_data_set_dir('LA101636_20.PD0', DIR_ADCPA_LIVE, filename_1)
        path_2 = self.create_sample_data_set_dir('LA101636_20.PD0', DIR_ADCPA_LIVE, filename_2)
        path_3 = self.create_sample_data_set_dir('LB180210_50.PD0', DIR_ADCPA_RECOVERED, filename_3)
        path_4 = self.create_sample_data_set_dir('LB180210_50.PD0', DIR_ADCPA_RECOVERED, filename_4)

        # these files have 446 byte ensembles in them
        ensemble_bytes = 446
        position_1 = 20 * ensemble_bytes
        position_2 = 5 * ensemble_bytes
        position_3 = 20 * ensemble_bytes
        position_4 = 12 * ensemble_bytes

        # Create and store the new driver state.
        # Set status of file 1 to completely read.
        # Set status of file 2 to start reading at record 6 of a 20 record file.
        # Set status of file 3 to completely read.
        # Set status of file 4 to start reading at record 13 of a 50 record file.

        state = {DataTypeKey.ADCPA_INSTRUMENT:
                    {filename_1: self.get_file_state(path_1, True, position_1),
                     filename_2: self.get_file_state(path_2, False, position_2)},
                 DataTypeKey.ADCPA_RECOVERED:
                    {filename_3: self.get_file_state(path_3, True, position_3),
                     filename_4: self.get_file_state(path_4, False, position_4)}
                 }

        # set the driver to the predetermined state and start sampling
        self.driver = self._get_driver_object(memento=state)
        self.driver.start_sampling()

        # get the next 15 particles from the live directory
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20_6_20.yml',
                         count=15, timeout=10)

        # get the next 8 particles from the recovered directory
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_13_20.yml',
                         count=8, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        log.info("========== START INTEG TEST STOP START RESUME  ===============")
        self.clear_async_data()
        self.driver.start_sampling()

        filename_1 = 'File_1.PD0'
        filename_2 = 'File_2.PD0'
        filename_3 = 'File_3.PD0'
        filename_4 = 'File_4.PD0'

        self.create_sample_data_set_dir('LA101636_20.PD0', DIR_ADCPA_LIVE, filename_1)
        self.create_sample_data_set_dir('LA101636_20.PD0', DIR_ADCPA_LIVE, filename_2)
        self.create_sample_data_set_dir('LB180210_50.PD0', DIR_ADCPA_RECOVERED, filename_3)
        self.create_sample_data_set_dir('LB180210_50.PD0', DIR_ADCPA_RECOVERED, filename_4)

        # Read all of the first live data file
        # Verify that the entire file has been read.
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20.yml',
                         count=20, timeout=10)
        self.assert_file_ingested(filename_1, DataTypeKey.ADCPA_INSTRUMENT)

        # Read all of the first recovered data file
        # Verify that the entire file has been read.
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_recovered.yml',
                         count=50, timeout=10)
        self.assert_file_ingested(filename_3, DataTypeKey.ADCPA_RECOVERED)

        # get the first 5 particles from the 2nd live file
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20_1_5.yml',
                         count=5, timeout=10)

        # get the first 12 particles from the recovered directory
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_1_12.yml',
                         count=12, timeout=10)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # get the next 15 particles from the live directory
        self.assert_data(AdcpaMGliderInstrumentParticle, 'LA101636_20_6_20.yml',
                         count=15, timeout=10)
        self.assert_file_ingested(filename_2, DataTypeKey.ADCPA_INSTRUMENT)

        # get the next 8 particles from the recovered directory
        self.assert_data(AdcpaMGliderRecoveredParticle, 'LB180210_50_13_20.yml',
                         count=8, timeout=10)
        self.assert_file_ingested(filename_4, DataTypeKey.ADCPA_RECOVERED)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def clear_sample_data(self):
        """
        Need to override this from base class to clean all directories
        """
        data_dirs = self.create_data_dir()
        log.debug("Startup Config: %s", self._driver_config().get('startup_config'))
        for data_dir in data_dirs:
            log.debug("Clean all data from %s", data_dir)
            remove_all_files(data_dir)

    def create_data_dir(self):
        """
        Verify the test data directory is created and exists.  Return the path to
        the directory.
        @return: path to data directory
        @raise: IDKConfigMissing no harvester config
        @raise: IDKException if data_dir exists, but not a directory
        """
        startup_config = self._driver_config().get('startup_config')
        if not startup_config:
            raise IDKConfigMissing("Driver config missing 'startup_config'")

        harvester_config = startup_config.get('harvester')
        if not harvester_config:
            raise IDKConfigMissing("Startup config missing 'harvester' config")

        data_dir = []

        for key in harvester_config:
            data_dir_key = harvester_config[key].get("directory")
            if not data_dir_key:
                raise IDKConfigMissing("Harvester config missing 'directory'")

            if not os.path.exists(data_dir_key):
                log.debug("Creating data dir: %s", data_dir_key)
                os.makedirs(data_dir_key)

            elif not os.path.isdir(data_dir_key):
                raise IDKException("%s is not a directory" % data_dir_key)
            data_dir.append(data_dir_key)

        return data_dir

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("=========== START QUAL TEST PUBLISH PATH =================")

        log.info("LA101636_20.PD0 placed in Live directory")
        self.create_sample_data_set_dir(
            'LA101636_20.PD0', DIR_ADCPA_LIVE)

        log.info("LB180210_50.PD0 placed in Recovered directory")
        self.create_sample_data_set_dir(
            'LB180210_50.PD0', DIR_ADCPA_RECOVERED)

        self.assert_initialize()

        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                                   20, 100)
        self.assert_data_values(result, 'LA101636_20.yml')

        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                                   50, 100)

        self.assert_data_values(result, 'LB180210_50_recovered.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the files at once
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        # create the sample data for both live and recovered
        # using files with thousands of records
        self.create_sample_data_set_dir(
            'LA101636.PD0', DIR_ADCPA_LIVE)
        self.create_sample_data_set_dir(
            'LB180210.PD0', DIR_ADCPA_RECOVERED)

        #initialise the driver and start sampling
        self.assert_initialize()

        num_samples = 200
        max_time = 600  # seconds

        #get a bunch of live praticles
        self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                          num_samples, max_time)

        #get a bunch of reciovere praticles
        self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                          num_samples, max_time)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("========== START QUAL TEST STOP START ===============")

        log.info("LA101636_20.PD0 placed in Live directory")
        self.create_sample_data_set_dir(
            'LA101636_20.PD0', DIR_ADCPA_LIVE)

        log.info("LB180210_50.PD0 placed in Recovered directory")
        self.create_sample_data_set_dir(
            'LB180210_50.PD0', DIR_ADCPA_RECOVERED)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        #get 5 records from the live data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                                   5, 100)
        self.assert_data_values(result, 'LA101636_20_1_5.yml')

        #get 12 records from the recovered data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                                   12, 100)
        self.assert_data_values(result, 'LB180210_50_1_12.yml')

        # stop sampling
        self.assert_stop_sampling()

        #restart sampling
        self.assert_start_sampling()

        #get 5 records from the live data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                                   15, 100)
        self.assert_data_values(result, 'LA101636_20_6_20.yml')
        #verify the queue is empty
        self.assert_sample_queue_size(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT, 0)

        #get 12 records from the recovered data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                                   8, 100)
        self.assert_data_values(result, 'LB180210_50_13_20.yml')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        log.info("========== START QUAL TEST SHUTDOWN RESTART ===============")

        log.info("LA101636_20.PD0 placed in Live directory")
        self.create_sample_data_set_dir(
            'LA101636_20.PD0', DIR_ADCPA_LIVE)

        log.info("LB180210_50.PD0 placed in Recovered directory")
        self.create_sample_data_set_dir(
            'LB180210_50.PD0', DIR_ADCPA_RECOVERED)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        #get 5 records from the live data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                                   5, 100)
        self.assert_data_values(result, 'LA101636_20_1_5.yml')

        #get 12 records from the recovered data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                                   12, 100)
        self.assert_data_values(result, 'LB180210_50_1_12.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        #restart sampling
        self.assert_start_sampling()

        #get 5 records from the live data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT,
                                                   15, 100)
        self.assert_data_values(result, 'LA101636_20_6_20.yml')
        #verify the queue is empty
        self.assert_sample_queue_size(DataParticleType.ADCPA_M_GLIDER_INSTRUMENT, 0)

        #get 12 records from the recovered data, verify the values
        result = self.data_subscribers.get_samples(DataParticleType.ADCPA_M_GLIDER_RECOVERED,
                                                   8, 100)
        self.assert_data_values(result, 'LB180210_50_13_20.yml')














