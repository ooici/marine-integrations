"""
@package mi.dataset.driver.cg_stc_eng.stc.test.test_driver
@file marine-integrations/mi/dataset/driver/cg_stc_eng/stc/driver.py
@author Emily Hahn
@brief Test cases for cg_stc_eng_stc driver

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

from nose.plugins.attrib import attr
from mock import Mock

from mi.idk.util import remove_all_files
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.exceptions import SampleEncodingException, UnexpectedDataException
from mi.idk.exceptions import SampleTimeout
from mi.core.instrument.data_particle import DataParticleKey

from pyon.core.exception import Timeout
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentConnectionLostErrorEvent
from interface.objects import ResourceAgentErrorEvent

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.driver.cg_stc_eng.stc.driver import CgStcEngStcDataSetDriver, DataTypeKey
from mi.dataset.parser.cg_stc_eng_stc import CgStcEngStcParserDataParticle, CgDataParticleType
from mi.dataset.parser.rte_o_dcl import RteODclParserDataParticle, RteDataParticleType
from mi.dataset.parser.mopak_o_dcl import MopakODclAccelParserDataParticle, MopakODclRateParserDataParticle
from mi.dataset.parser.mopak_o_dcl import MopakDataParticleType, StateKey
from mi.dataset.parser.mopak_o_dcl import MopakODclAccelParserDataParticleKey

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.cg_stc_eng.stc.driver',
    driver_class='CgStcEngStcDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = CgStcEngStcDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'cg_stc_eng_stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CG_STC_ENG:
            {
                DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest1',
                DataSetDriverConfigKeys.PATTERN: '*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.MOPAK:
            {
                DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest2',
                DataSetDriverConfigKeys.PATTERN: '*.mopak.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.RTE:
            {
                DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest3',
                DataSetDriverConfigKeys.PATTERN: '*.rte.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {}
    }
)

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    
    def clear_sample_data(self):
        log.debug("Driver Config: %s", self._driver_config())
        if os.path.exists('/tmp/dsatest1'):
            log.debug("Clean all data from %s", '/tmp/dsatest1')
            remove_all_files('/tmp/dsatest1')
        else:
            os.makedirs('/tmp/dsatest1')
        if os.path.exists('/tmp/dsatest2'):
            log.debug("Clean all data from %s", '/tmp/dsatest2')
            remove_all_files('/tmp/dsatest2')
        else:
            os.makedirs('/tmp/dsatest2')
        if os.path.exists('/tmp/dsatest3'):
            log.debug("Clean all data from %s", '/tmp/dsatest3')
            remove_all_files('/tmp/dsatest3')
        else:
            os.makedirs('/tmp/dsatest3')

    def test_get(self):
        """
        Test that we can get data from files for all 3 harvester / parsers.
        """
        # Start sampling and watch for an exception
        self.driver.start_sampling()
        
        self.clear_async_data()
        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_first.result.yml',
                         count=1, timeout=10)

        self.create_sample_data_set_dir('first.mopak.log', '/tmp/dsatest2',
                                        "20140120_140004.mopak.log")
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
            'first_mopak.result.yml', count=5, timeout=10)
        
        self.clear_async_data()
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")
        self.assert_data(RteODclParserDataParticle, 'first_rte.result.yml',
                         count=2, timeout=10)
        
        self.clear_async_data()
        self.create_sample_data_set_dir('stc_status_second.txt', '/tmp/dsatest1')
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_second.result.yml',
                         count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('second.mopak.log', '/tmp/dsatest2',
                                        "20140120_150004.mopak.log")
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'second_mopak.result.yml', count=2, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('second.rte.log', '/tmp/dsatest3',
                                        "20140120_150004.rte.log")
        self.assert_data(RteODclParserDataParticle, 'second_rte.result.yml',
                         count=2, timeout=10)

    def test_get_any_order(self):
        """
        Test that we can get data from files for all 3 harvester / parsers by just 
        creating many files and getting results in any order.  
        """
        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('stc_status_all.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('first_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")
        self.create_sample_data_set_dir('second_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_201853.mopak.log")
        self.create_sample_data_set_dir('second.rte.log', '/tmp/dsatest3',
                                        "20140120_150004.rte.log")
        
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_first.result.yml',
                         count=1, timeout=10)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_all.result.yml',
                         count=1, timeout=10)
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'first_rate_mopak.result.yml', count=6, timeout=10)
        self.assert_data(RteODclParserDataParticle, 'first_rte.result.yml',
                         count=2, timeout=10)
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'second_rate_mopak.result.yml', count=3, timeout=10)
        self.assert_data(RteODclParserDataParticle, 'second_rte.result.yml',
                         count=2, timeout=10)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        # create the file so that it is unreadable
        self.create_sample_data_set_dir("20140313_191853.mopak.log", '/tmp/dsatest2',
                                        create=True, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)
        self.clear_async_data()

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("stc_status.txt", '/tmp/dsatest1',
                                        create=True, mode=000)
        self.assert_exception(IOError)
        self.clear_async_data()

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("foo.rte.log", '/tmp/dsatest3',
                                        create=True, mode=000)
        self.assert_exception(IOError)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the driver sampling
        """
        # create some data to parse
        path_1 = self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        path_2 = self.create_sample_data_set_dir('stc_status_second.txt', '/tmp/dsatest1')
        path_3 = self.create_sample_data_set_dir('stc_status_third.txt', '/tmp/dsatest1')
        path_4 = self.create_sample_data_set_dir('first.mopak.log', '/tmp/dsatest2',
                                                 "20140120_140004.mopak.log")
        path_5 = self.create_sample_data_set_dir('second.mopak.log', '/tmp/dsatest2',
                                                 "20140120_150004.mopak.log")
        path_6 = self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                                 "20140120_140004.rte.log")
        path_7 = self.create_sample_data_set_dir('second_resume.rte.log', '/tmp/dsatest3',
                                                 "20140120_150004.rte.log")

        # Create and store the new driver state
        state = {
            DataTypeKey.CG_STC_ENG:{
                "stc_status.txt": self.get_file_state(path_1, True),
                "stc_status_second.txt": self.get_file_state(path_2, True),
                "stc_status_third.txt": self.get_file_state(path_3, False)
                },
            DataTypeKey.MOPAK: {
                "20140120_140004.mopak.log": self.get_file_state(path_4, False, 172),
                "20140120_150004.mopak.log": self.get_file_state(path_5, False, 0)
                },
            DataTypeKey.RTE: {
                "20140120_140004.rte.log": self.get_file_state(path_6, True, 549),
                "20140120_150004.rte.log": self.get_file_state(path_7, False, 154)
            }
        }
        log.debug('generated state %s', state)
        state[DataTypeKey.MOPAK]['20140120_140004.mopak.log']['parser_state'].update({StateKey.TIMER_START: 33456})
        state[DataTypeKey.MOPAK]['20140120_140004.mopak.log']['parser_state'].update({StateKey.TIMER_ROLLOVER: 0})
        state[DataTypeKey.MOPAK]['20140120_150004.mopak.log']['parser_state'].update({StateKey.TIMER_START: None})
        state[DataTypeKey.MOPAK]['20140120_150004.mopak.log']['parser_state'].update({StateKey.TIMER_ROLLOVER: 0})
        state[DataTypeKey.MOPAK]['20140120_150004.mopak.log']['parser_state'].update({StateKey.POSITION: 0})
        log.debug('generated state after fields %s', state)
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                            'partial_second_mopak.result.yml', count=3, timeout=10)
        self.assert_data(RteODclParserDataParticle, 'second_resume_rte.result.yml',
                         count=2, timeout=10)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_third.result.yml',
                         count=1, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        self.driver.start_sampling()

        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('stc_status_second.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('first.mopak.log', '/tmp/dsatest2',
                                        "20140120_140004.mopak.log")
        self.create_sample_data_set_dir('second.mopak.log', '/tmp/dsatest2',
                                        "20140120_150004.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")
        self.create_sample_data_set_dir('second.rte.log', '/tmp/dsatest3',
                                        "20140120_150004.rte.log")

        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'first_mopak.result.yml', count=5, timeout=10)
        self.assert_file_ingested("20140120_140004.mopak.log", DataTypeKey.MOPAK)
        self.assert_data(RteODclParserDataParticle, 'first_rte.result.yml',
                         count=2, timeout=10)
        self.assert_file_ingested("20140120_140004.rte.log", DataTypeKey.RTE)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_first.result.yml',
                         count=1, timeout=10)
        self.assert_file_ingested("stc_status.txt", DataTypeKey.CG_STC_ENG)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'second_mopak.result.yml', count=2, timeout=10)
        self.assert_file_ingested("20140120_150004.mopak.log", DataTypeKey.MOPAK)
        self.assert_data(RteODclParserDataParticle, 'second_rte.result.yml',
                         count=2, timeout=10)
        self.assert_file_ingested("20140120_150004.rte.log", DataTypeKey.RTE)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_second.result.yml',
                         count=1, timeout=10)
        self.assert_file_ingested("stc_status_second.txt", DataTypeKey.CG_STC_ENG)

    def test_sample_exception_mopak(self):
        """
        Test that the mopak produces a sample exception with noisy data and confirm the
        sample exception occurs
        """
        self.create_sample_data_set_dir('noise.mopak.log', '/tmp/dsatest2',
                                        "20140120_140004.mopak.log")

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle),
                          'first_mopak.result.yml', count=5, timeout=10)
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested("20140120_140004.mopak.log", DataTypeKey.MOPAK)

    def test_sample_exception_eng(self):
        """
        Test that the stc eng procuces a sample exception when the time is missing and 
        confirm the sample exception occurs
        """
        self.create_sample_data_set_dir('stc_status_missing_time.txt', '/tmp/dsatest1')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('stc_status_missing_time.txt', DataTypeKey.CG_STC_ENG)

    def test_encoding_exception(self):
        self.create_sample_data_set_dir('stc_status_bad_encode.txt', '/tmp/dsatest1')

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        # assert that the exception callback received a sample encoding exception
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_bad_encode.result.yml',
                         count=1, timeout=10)
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('stc_status_bad_encode.txt', DataTypeKey.CG_STC_ENG)

    def test_mopak_unexpected(self):
        self.create_sample_data_set_dir('20131209_103919.3dmgx3.log', '/tmp/dsatest2',
                                        "20131209_103919.mopak.log")

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle), None,
                         count=2857, timeout=100)

    def test_bad_checksum(self):
        """
        Assert we skip samples with bad checksums
        """
        self.create_sample_data_set_dir('20140313_191853_bad_chksum.3dmgx3.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        # Start sampling
        self.driver.start_sampling()
        # assert we get 5 samples then the file is ingested
        self.assert_data((MopakODclAccelParserDataParticle,
                          MopakODclRateParserDataParticle), None, count=5)
        self.assert_file_ingested('20140313_191853.mopak.log', DataTypeKey.MOPAK)

    def test_mopak_timer_reset(self):
        """
        test that we get the sample exception for the mopak timer resetting
        """
        self.create_sample_data_set_dir('20140313_191853_timer_reset.3dmgx3.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        # Start sampling
        self.driver.start_sampling()
        # assert we get the sample exception for the timer resetting
        self.assert_event('ResourceAgentErrorEvent')

    def test_mopak_timer_rollover(self):
        """
        confirm mopak times are increasing when expected, then rollover and confirm the timer
        resets and the timestamp keeps increasing
        """
        self.create_sample_data_set_dir('20140313_191853_rollover.3dmgx3.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        # Start sampling
        self.driver.start_sampling()
        try:
            particles = self.get_samples((MopakODclAccelParserDataParticle,
                                          MopakODclRateParserDataParticle), 7, 10)
        except Timeout:
            log.error("Failed to detect particle %s, expected %d particles, found %d", (MopakODclAccelParserDataParticle,
                                          MopakODclRateParserDataParticle), 7, found)
            self.fail("particle detection failed. Expected %d, Found %d" % (7, found))

        # expect particle increase for 5 samples, then rollover
        last_timer = 0
        last_timestamp = 0.0
        for i in range(0,4):
            (particle_timer, particle_timestamp) = self.get_mopak_particle_time(particles[i])
            if particle_timer == None or particle_timestamp == None:
                log.warn("unable to find timer or timestamp for particle %d", i)
                self.fail("Unable to find timer or timestamp for particle %d", i)

            if particle_timer < last_timer:
                log.warn("Timer did not increase when expected")
                self.fail("Timer did not increase when expected")
            if particle_timestamp < last_timestamp:
                log.warn("Timestamp did not increase when expected")
                self.fail("Timestamp did not increase when expected")
            last_timer = particle_timer
            last_timestamp = particle_timestamp

        (particle_timer, particle_timestamp) = self.get_mopak_particle_time(particles[5])
        if particle_timer == None or particle_timestamp == None:
            log.warn("unable to find timer or timestamp for particle 5")
            self.fail("Unable to find timer or timestamp for particle 5")
        # now check that we rolled over
        if particle_timer >= last_timer:
            log.warn("Timer did not rollover when expected, last timer %d, particle timer %d", last_timer, particle_timer)
            self.fail("Timer did not rollover when expected")
        if particle_timestamp < last_timestamp:
            log.warn("Timestamp did not increase on rollover when expected, particle_timestamp %f, last timestamp %f",
                     particle_timestamp, last_timestamp)
            self.fail("Timestamp did not increase on rollover when expected")
        last_timer = particle_timer
        last_timestamp = particle_timestamp

        (particle_timer, particle_timestamp) = self.get_mopak_particle_time(particles[6])
        if particle_timer < last_timer:
            log.warn("Timer did not increase when expected")
            self.fail("Timer did not increase when expected")
        if particle_timestamp < last_timestamp:
            log.warn("Timestamp did not increase when expected")
            self.fail("Timestamp did not increase when expected")

    def get_mopak_particle_time(self, particle):
        """
        Get the internal timestamp and the value of the mopak timer field from a mopak particle
        @param single particle to obtain the timestamp and timer from
        @returns tuple of particle timer and internal timestamp
        """
        particle_timer = (None, None)
        internal_timestamp = particle.get_value(DataParticleKey.INTERNAL_TIMESTAMP)
        particle_dict = particle.generate_dict()
        particle_vals = particle_dict.get('values')
        for val in particle_vals:
            # this will catch both rate and accel timers since the key has the same text string
            if val.get(DataParticleKey.VALUE_ID) == MopakODclAccelParserDataParticleKey.MOPAK_TIMER:
                particle_timer = val.get(DataParticleKey.VALUE)
        return (particle_timer, internal_timestamp)

    def test_partial_config(self):
        """
        test with only cg_stc_eng and rte configured
        """
        partial_config = {
            DataSourceConfigKey.RESOURCE_ID: 'cg_stc_eng_stc',
            DataSourceConfigKey.HARVESTER:
            {
                DataTypeKey.CG_STC_ENG:
                {
                    DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest1',
                    DataSetDriverConfigKeys.PATTERN: '*.txt',
                    DataSetDriverConfigKeys.FREQUENCY: 1,
                },
                DataTypeKey.RTE:
                {
                    DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest3',
                    DataSetDriverConfigKeys.PATTERN: '*.rte.log',
                    DataSetDriverConfigKeys.FREQUENCY: 1,
                }
            },
            DataSourceConfigKey.PARSER: {}
        }
        self.driver = self._get_driver_object(config=partial_config)
        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('stc_status_all.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('first_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")
        self.create_sample_data_set_dir('second_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_201853.mopak.log")
        self.create_sample_data_set_dir('second.rte.log', '/tmp/dsatest3',
                                        "20140120_150004.rte.log")

        self.assert_data(CgStcEngStcParserDataParticle, 'stc_first.result.yml',
                         count=1, timeout=10)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_all.result.yml',
                         count=1, timeout=10)
        self.assert_data(RteODclParserDataParticle, 'first_rte.result.yml',
                         count=2, timeout=10)
        self.assert_data(RteODclParserDataParticle, 'second_rte.result.yml',
                         count=2, timeout=10)

    def test_single_config(self):
        """
        test with only cg_stc_eng configured
        """
        partial_config = {
            DataSourceConfigKey.RESOURCE_ID: 'cg_stc_eng_stc',
            DataSourceConfigKey.HARVESTER:
            {
                DataTypeKey.CG_STC_ENG:
                {
                    DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest1',
                    DataSetDriverConfigKeys.PATTERN: '*.txt',
                    DataSetDriverConfigKeys.FREQUENCY: 1,
                }
            },
            DataSourceConfigKey.PARSER: {}
        }
        self.driver = self._get_driver_object(config=partial_config)
        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('stc_status_all.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('first_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")
        self.create_sample_data_set_dir('second_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_201853.mopak.log")
        self.create_sample_data_set_dir('second.rte.log', '/tmp/dsatest3',
                                        "20140120_150004.rte.log")

        self.assert_data(CgStcEngStcParserDataParticle, 'stc_first.result.yml',
                         count=1, timeout=10)
        self.assert_data(CgStcEngStcParserDataParticle, 'stc_all.result.yml',
                         count=1, timeout=10)

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

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def clear_sample_data(self):
        """
        Need to override this from base class to clean all three directories
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

    def remove_sample_dir(self):
        """
        Remove the sample dir and all files
        """
        data_dirs = self.create_data_dir()
        self.clear_sample_data()
        for data_dir in data_dirs:
            os.rmdir(data_dir)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('stc_status.txt', '/tmp/dsatest1')
        self.create_sample_data_set_dir('first.mopak.log', '/tmp/dsatest2',
                                        "20140120_140004.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")

        self.assert_initialize()

        # Verify we get one sample
        try:
            result_cg = self.data_subscribers.get_samples(CgDataParticleType.SAMPLE,1)
            result_mopak = self.data_subscribers.get_samples(MopakDataParticleType.ACCEL, 5)
            result_rte = self.data_subscribers.get_samples(RteDataParticleType.SAMPLE, 2)
            log.debug("RESULT cg: %s", result_cg)
            log.debug("RESULT mopak: %s", result_mopak)
            log.debug("RESULT rte: %s", result_rte)

            # Verify values
            self.assert_data_values(result_cg, 'stc_first.result.yml')
            self.assert_data_values(result_mopak, 'first_mopak.result.yml')
            self.assert_data_values(result_rte, 'first_rte.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.
        need to override this from base unit test class to test each file type
        exception callback called.
        """
        filename = "20140313_191853.mopak.log"
        self.assert_new_file_exception(filename, '/tmp/dsatest2')

        filename = "foo.rte.log"
        self.assert_new_file_exception(filename, '/tmp/dsatest3')

        filename = "foo.txt"
        self.assert_new_file_exception(filename, '/tmp/dsatest1')

    def assert_new_file_exception(self, filename, path):
        """
        assert that an exception occurs and we recover from a new un-readable file 
        """
        self.clear_sample_data()
        self.create_sample_data_set_dir(filename, path, mode=000)

        state = self.dataset_agent_client.get_agent_state()
        if state == ResourceAgentState.STREAMING:
            # stop sampling to go into command state
            self.assert_stop_sampling()
        elif state != ResourceAgentState.COMMAND:
            # we are not in stream or command, initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir(filename, path)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        (only possible with mopak and rte, since cg_stc_eng is 1 sample per file)
        """
        self.create_sample_data_set_dir('20140120_140004.mopak.log', '/tmp/dsatest2')
        self.create_sample_data_set_dir('20131115.rte.log', '/tmp/dsatest3')
        
        self.assert_initialize()

        # get results for each of the data particle streams
        result_rte = self.get_samples(RteDataParticleType.SAMPLE, 23, 10)
        result_mopak = self.get_samples(MopakDataParticleType.ACCEL, 11964, 480)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result_mopak = self.get_samples(MopakDataParticleType.ACCEL, 2)
            result2_mopak = self.get_samples(MopakDataParticleType.RATE, 4)
            result_mopak.extend(result2_mopak)
            log.debug("RESULT MOPAK: %s", result_mopak)

            # Verify mopak values
            self.assert_data_values(result_mopak, 'first_rate_mopak.result.yml')
            self.assert_sample_queue_size(MopakDataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(MopakDataParticleType.RATE, 0)

            self.create_sample_data_set_dir('second_rate.mopak.log', '/tmp/dsatest2',
                                            "20140313_201853.mopak.log")

            # verify rte values
            result_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            self.assert_data_values(result_rte, 'first_rte.result.yml')
            self.assert_sample_queue_size(RteDataParticleType.SAMPLE, 0)
            
            self.create_sample_data_set_dir('four_samp.rte.log', '/tmp/dsatest3',
                                            "20140120.rte.log")

            # Now read the first records of the second mopak file then stop in the middle
            result_mopak = self.get_samples(MopakDataParticleType.RATE, 1)
            log.debug("got result 1 mopak %s", result_mopak)
            
            # Then read the first records of the second rte file and stop in the middle
            result_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            log.debug("got result 1 rte %s", result_rte)

            # stop sample
            self.assert_stop_sampling()
            # Restart sampling and ensure we get the last records of the file
            self.assert_start_sampling()

            # get the second half of mopak and verify
            result2_mopak = self.get_samples(MopakDataParticleType.RATE, 2)
            log.debug("got result 2 mopak %s", result2_mopak)
            result_mopak.extend(result2_mopak)
            self.assert_data_values(result_mopak, 'second_rate_mopak.result.yml')
            self.assert_sample_queue_size(MopakDataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(MopakDataParticleType.RATE, 0)

            # get the second half of rte and verify
            result2_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            log.debug("got result 2 rte %s", result2_rte)
            result_rte.extend(result2_rte)
            self.assert_data_values(result_rte, 'four_samp_rte.result.yml')
            self.assert_sample_queue_size(RteDataParticleType.SAMPLE, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first_rate.mopak.log', '/tmp/dsatest2',
                                        "20140313_191853.mopak.log")
        self.create_sample_data_set_dir('first.rte.log', '/tmp/dsatest3',
                                        "20140120_140004.rte.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result_mopak = self.get_samples(MopakDataParticleType.ACCEL, 2)
            result2_mopak = self.get_samples(MopakDataParticleType.RATE, 4)
            result_mopak.extend(result2_mopak)
            log.debug("RESULT MOPAK: %s", result_mopak)

            # Verify mopak values
            self.assert_data_values(result_mopak, 'first_rate_mopak.result.yml')
            self.assert_sample_queue_size(MopakDataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(MopakDataParticleType.RATE, 0)

            self.create_sample_data_set_dir('second_rate.mopak.log', '/tmp/dsatest2',
                                            "20140313_201853.mopak.log")

            # verify rte values
            result_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            self.assert_data_values(result_rte, 'first_rte.result.yml')
            self.assert_sample_queue_size(RteDataParticleType.SAMPLE, 0)
            
            self.create_sample_data_set_dir('four_samp.rte.log', '/tmp/dsatest3',
                                            "20140120.rte.log")

            # Now read the first records of the second mopak file then stop in the middle
            result_mopak = self.get_samples(MopakDataParticleType.RATE, 1)
            log.debug("got result 1 mopak %s", result_mopak)
            
            # Then read the first records of the second rte file and stop in the middle
            result_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            log.debug("got result 1 rte %s", result_rte)

            self.assert_stop_sampling()
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Restart sampling and ensure we get the last records of the file
            self.assert_start_sampling()

            # get the second half of mopak and verify
            result2_mopak = self.get_samples(MopakDataParticleType.RATE, 2)
            log.debug("got result 2 mopak %s", result2_mopak)
            result_mopak.extend(result2_mopak)
            self.assert_data_values(result_mopak, 'second_rate_mopak.result.yml')
            self.assert_sample_queue_size(MopakDataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(MopakDataParticleType.RATE, 0)

            # get the second half of rte and verify
            result2_rte = self.get_samples(RteDataParticleType.SAMPLE, 2)
            log.debug("got result 2 rte %s", result2_rte)
            result_rte.extend(result2_rte)
            self.assert_data_values(result_rte, 'four_samp_rte.result.yml')
            self.assert_sample_queue_size(RteDataParticleType.SAMPLE, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception_mopak(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('noise.mopak.log', '/tmp/dsatest2',
                                        "20140120_140004.mopak.log")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(MopakDataParticleType.ACCEL, 5)
        self.assert_data_values(result, 'first_mopak.result.yml')
        self.assert_sample_queue_size(MopakDataParticleType.ACCEL, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_sample_exception_stc(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('stc_status_missing_time.txt', '/tmp/dsatest1')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        self.assert_sample_queue_size(CgDataParticleType.SAMPLE, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_exception_stc(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('stc_status_bad_encode.txt', '/tmp/dsatest1')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(CgDataParticleType.SAMPLE, 1)
        self.assert_data_values(result, 'stc_bad_encode.result.yml')
        self.assert_sample_queue_size(CgDataParticleType.SAMPLE, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

