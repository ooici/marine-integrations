"""
@package mi.dataset.driver.hypm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/hypm/ctd/test/test_driver.py
@author Bill French
@brief Test cases for hypm/ctd driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import unittest
import gevent

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from exceptions import Exception

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetTestConfig
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.parser.ctdpf import CtdpfParser
from mi.dataset.parser.test.test_ctdpf import CtdpfParserUnitTestCase
from mi.dataset.harvester import AdditiveSequentialFileHarvester
from mi.dataset.driver.hypm.ctd.driver import HypmCTDPFDataSetDriver

from ion.services.dm.utility.granule_utils import RecordDictionaryTool


DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.hypm.ctd.driver',
    driver_class="HypmCTDPFDataSetDriver",

    agent_preload_id = 'EDA1',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = HypmCTDPFDataSetDriver.stream_config(),
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.txt',
            'frequency': 1,
        },
        'parser': {}
    }
)
    

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
        
    STREAM_NAME = ""

    def state_callback(self, state):
        self.state_callback_result.append(state)
    
    def data_callback(self, data):
        self.data_callback_result.append(data)

    def exception_callback(self, ex):
        self.exception_callback_result.append(ex)
    
    def setUp(self):
        self.create_sample_data()
        log.debug("Created test data")
        self.state_callback_result = []
        self.data_callback_result = []
        self.exception_callback_result = []
        
        self.memento = {DataSourceConfigKey.HARVESTER: {},
                        DataSourceConfigKey.PARSER: {}}
        self.driver = HypmCTDPFDataSetDriver(self._driver_config()['startup_config'],
                                             self.memento,
                                             self.data_callback,
                                             self.state_callback,
                                             self.exception_callback)
    def test_configuration(self):
        self.assert_data_particle_keys()
        

    @unittest.skip("Not complete")
    def test_simple_get(self):
        """
        Test the simple happy path of having one file get opened by the
        a harvester, handed to a parser, and confirm that particles are
        published as they should.
        """
        self.fail()
        # Start a harvester going to get one file, start parser, too
        self.driver.start_sampling()
        gevent.sleep(5)
        # Count particles that are generated, assert correct
        self.assertEqual(len(self.data_callback_result), 53)
        self.assertEqual(len(self.state_callback_result), 53)
        
        for particle in self.data_callback_result:
            self.assert_data_particle_header(particle, STREAM_NAME)
        
        # check the first value 10.5914,  4.1870,  161.06,   2693.0
        particle_dict = self.get_data_particle_values_as_dict(self.data_callback_result[0])
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.TEMPERATURE], 10.5941)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.CONDUCTIVITY], 4.1870)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.PRESSURE], 161.06)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.OXYGEN], 2693.0)
        
        # Check the last value 335.5913,  4.1866,  161.08,   2738.1
        particle_dict = self.get_data_particle_values_as_dict(self.data_callback_result[-1])
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.TEMPERATURE], 335.5913)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.CONDUCTIVITY], 4.1866)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.PRESSURE], 161.08)
        self.assertEqual(particle_dict[CtdpfParserDataParticleKey.OXYGEN], 2738.1)
        
    def test_multiple_sources(self):
        """
        Test that data comes from multiple source files with the correct number
        of particles being generated.
        """
        # Set up driver
        # Start a harvester going to get at least 2 files
        # Fire off a poller for each harvested file in order
        # Count particles that are generated, assert correct
        # Assert no errors on completion

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Set up driver
        # Start a harvester going with a large file
        # Fire off a poller
        # Stop the harvester
        # Verify state is reasonable at the driver level
        # Restart data collection
        # Verify the same stopped state is re-used
        # Count total particles that are generated, assert correct, no dups

    def test_parser_error(self):
        """
        Test for the correct response from a parser. Parser should
        toss an exception at bad data.
        """
        # Setup a driver
        # Insert a bad data file at the beginning of the sequence
        # When parser starts, catch the exception of the bad data
        
    def test_harvester_error(self):
        """
        Test to make sure the harvester errors are appropriately caught
        """
        # Do something bad for the harvester (non-dict config raises an exception)
        # Setup a driver
        # Verify harvester error made it to the driver
        
    def test_bad_configuration(self):
        """
        Feed a bad configuration to the harvester (and driver if it takes one).
        Parser doesnt error on a config right now, but it might some day.
        """
        # Create a bad, non-dict configuration for the harvester
        # Verify that the Type Error is raised on instantiation 

    
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_initialize(self):
        """
        Test that we can start the container and initialize the dataset agent.
        """
        self.assert_initialize()
        self.assert_stop_sampling()
        self.assert_reset()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data()
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples('ctdpf_parsed')
            log.debug("RESULT: %s", result)
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Verify the sample was correct
        #self.assertGranule(result.pop())

        # Create some test data
        # Setup the agent (and thus driver, harvester, and parser)
        # Start the driver going
        # See some data get published

    @unittest.skip("not implemented yet")
    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        # Create some large enough test data
        # Setup the agent
        # Start sampling
        # Wait a bit for some data to come in.
        # Stop sampling
        # Verify correct # of particles are PUBLISHED
        # Start sampling again
        # Stop or let complete
        # Verify correct # of particles, no gaps in the middle.

    @unittest.skip("not implemented yet")
    def test_missing_directory(self):
        """
        Test starting the driver when the data directory doesn't exists.  This
        should prevent the driver from going into streaming mode.  When the
        directory is created then we should be able to transition into streaming.
        """

        # Verify test directory doesn't exist
        # Initialize into command mode
        # Try to go streaming and verify failure
        # Create data directory
        # Try to go streaming again and verify success
