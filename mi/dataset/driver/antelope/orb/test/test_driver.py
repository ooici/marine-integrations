"""
@package mi.dataset.driver.antelope.orb.test.test_driver
@file marine-integrations/mi/dataset/driver/antelope/orb/driver.py
@author cgoodrich
@brief Test cases for antelope_orb driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

from contextlib import contextmanager
import shutil
import subprocess
import tempfile
import os
import signal
import time

import unittest

from nose.plugins.attrib import attr
from mock import Mock, call

import gevent

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.core.log import get_logger ; log = get_logger()
import logging
log.setLevel(logging.TRACE)

from mi.core.unit_test import MiIntTestCase

from mi.idk.exceptions import SampleTimeout
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetTestConfig
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.antelope.orb.driver import AntelopeOrbDataSetDriver
from mi.dataset.parser.antelope_orb import AntelopeOrbPacketParticle, DataParticleType
from mi.dataset.parser.antelope_orb import StateKey
from mi.dataset.parser.antelope_orb import ParserConfigKey

from mock import patch, MagicMock

#try:
#    import yappi
#except ImportError:
#    log.warning('yappi not available; profiling disabled')
#    yappi = Mock()
yappi = Mock()

import cProfile
profile = cProfile.Profile()


from mi.core.kudu.brttpkt import NoData
import _Pkt as _pkt
from mi.core.kudu.orb import Orb


# The integration and qualification tests generated here are suggested tests,
# but may not be enough to fully test your driver. Additional tests should be
# written as needed.


ORB_PORT = 54320
ORB_NAME = 'localhost:%s' % ORB_PORT
ORB_SERVER_PATH='/opt/antelope/5.3/bin/orbserver'


# Fill in driver details
DataSetIntegrationTestCase.initialize(
    driver_module='mi.dataset.driver.antelope.orb.driver',
    driver_class='AntelopeOrbDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = AntelopeOrbDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'antelope_orb',
        DataSourceConfigKey.HARVESTER:
        {
            # IDK requires this to be present; it's not very friendly to
            # drivers that don't use a harvester.
            DataSetDriverConfigKeys.DIRECTORY: 'not used',
            DataSetDriverConfigKeys.PATTERN: 'not used',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {
            ParserConfigKey.ORBNAME: ORB_NAME,
            ParserConfigKey.SELECT: '',
            ParserConfigKey.REJECT: '',
        }
    }
)



def makepacket(data, samprate=666, net='net', sta='sta',
                chan='chan', loc='loc', type='GENC', time=0):
    """returns stuffed packet in form (pkttype, packet, srcname, time)

    Packet has one channel.
    """
    pkt = _pkt._newPkt()
    try:
        _pkt._Pkt_pkttype_set(pkt, type)
        _pkt._Pkt_time_set(pkt, time)
        pktchan = _pkt._newPktChannel()
        _pkt._PktChannel_time_set(pktchan, time)
        _pkt._PktChannel_data_set(pktchan, data)
        _pkt._PktChannel_samprate_set(pktchan, samprate)
        _pkt._PktChannel_net_set(pktchan, net)
        _pkt._PktChannel_sta_set(pktchan, sta)
        _pkt._PktChannel_chan_set(pktchan, chan)
        _pkt._PktChannel_loc_set(pktchan, loc)
        _pkt._Pkt_channels_set(pkt, [pktchan,])
        return _pkt._stuffPkt(pkt)
    finally:
        _pkt._freePkt(pkt)


@contextmanager
def tempdir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path)


@contextmanager
def orbserver(packets_to_send, samples_per_packet):
    BYTES_PER_SAMPLE = 4
    BYTES_PER_PACKET = samples_per_packet * BYTES_PER_SAMPLE
    SAFETY = 1.5
    ORB_BYTES = int(packets_to_send * BYTES_PER_PACKET * SAFETY)
    if ORB_BYTES < 16384:
        ORB_BYTES = 16384
    with tempdir() as prefix:
        p = subprocess.Popen([
                ORB_SERVER_PATH,
                '-p', str(ORB_PORT),
                '-P', "%s/orb" % prefix,
                '-s', str(ORB_BYTES),
                'orbserver' 
            ]
        )
        log.debug("Started ORB server %s", p.pid)


        try:
            # give orb server a chance to start up
            gevent.sleep(3) 
            # Empty orbs are wonky; put one packet in
            with Orb(ORB_NAME, permissions='w') as myorb:
                # Write packets to ORB
                pkttype, packet, srcname, time = makepacket([])
                myorb.putx(srcname, 1, packet)
            yield p
        finally:
            log.debug("Terminating ORB server %s", p.pid)
            subprocess.call(['kill', str(p.pid)])


class AntelopeMixin(object):
    pass


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTestCase(DataSetIntegrationTestCase):
    # configuration singleton
#    test_config = DataSetTestConfig()

#    def __init__(self, *args, **kwargs):
#        super(IntegrationTest, self).__init__(*args, **kwargs)

    def test_harvester_config_exception(self):
        pass

    def test_harvester_new_file_exception(self):
        pass

#    @classmethod
#    def initialize(cls, *args, **kwargs):
#        """
#        Initialize the test_configuration singleton
#        """
#        cls.test_config.initialize(*args,**kwargs)

    def setUp(self):
        log.debug("*********************************************************************")
        log.debug("Starting Dataset Test %s", self._testMethodName)
        log.debug("*********************************************************************")
        log.debug("ID: %s", self.id())
        log.debug("DataSetTestCase setUp")

        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            return TestNotInitialized(msg="Tests non initialized. Missing DataSetTestCase.initialize(...)?")

        log.debug("Driver Config: %s", self._driver_config())


        self.state_callback_result = []
        self.data_callback_result = []
        self.event_callback_result = []
        self.exception_callback_result = []

        self.memento = {}

        self.PKT_ID = PKT_ID = 123
        self.PKT_TYPE = PKT_TYPE = 'GENC'
        self.PKT_DATA = PKT_DATA = 1,2,3,4
        self.PKT_TIME = PKT_TIME = 999
        self.PKT_SAMPRATE = PKT_SAMPRATE = 666
        self.PKT_NET = PKT_NET = 'net'
        self.PKT_STA = PKT_STA = 'sta'
        self.PKT_CHAN = PKT_CHAN = 'chan'
        self.PKT_LOC = PKT_LOC = 'loc'

        pkt = _pkt._newPkt()
        _pkt._Pkt_pkttype_set(pkt, PKT_TYPE)
        pktchan = _pkt._newPktChannel()
        _pkt._PktChannel_data_set(pktchan, PKT_DATA)
        _pkt._PktChannel_samprate_set(pktchan, PKT_SAMPRATE)
        _pkt._PktChannel_time_set(pktchan, PKT_TIME)
        _pkt._PktChannel_net_set(pktchan, PKT_NET)
        _pkt._PktChannel_sta_set(pktchan, PKT_STA)
        _pkt._PktChannel_chan_set(pktchan, PKT_CHAN)
        _pkt._PktChannel_loc_set(pktchan, PKT_LOC)
        _pkt._Pkt_channels_set(pkt, [pktchan,])
        self.pkttype, self.packet, self.srcname, self.time = _pkt._stuffPkt(pkt)
        _pkt._freePkt(pkt)

        self.driver = self._get_driver_object()

        # NOTE why not do this in tearDown?
        self.addCleanup(self._stop_driver)

        self._metadata = None
        self._get_metadata()

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        rvals = [(self.PKT_ID, sn, ts, pkt) for (pt, pkt, sn, ts) in [
                        makepacket(self.PKT_DATA, time=n+1) for n in range(2)]]
        def orbget():
            if rvals:
                log.trace('returning 1st packet')
                return rvals.pop(0)
            else:
                log.trace('no more packets')
                raise NoData()
        with patch('mi.dataset.parser.antelope_orb.OrbReapThr') as MockOrbReapThr:
            orbreapthr = MagicMock()
            orbreapthr.get = orbget
            MockOrbReapThr.return_value = orbreapthr
            self.driver.start_sampling()

        log.trace("STARTED SAMPLING")

        self.assert_data(None, 'first.result.yml', count=2, timeout=5)
        log.trace("ASSERTED DATA")

    def test_orbreapthr_args(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        def orbget():
            log.trace('no more packets')
            raise NoData()

        tafter = 999
        state={'parser_state': {
            StateKey.TAFTER: tafter,
            ParserConfigKey.ORBNAME: ORB_NAME,
            ParserConfigKey.SELECT: '',
            ParserConfigKey.REJECT: '',
        }}

        self.driver = self._get_driver_object(memento=state)

        with patch('mi.dataset.parser.antelope_orb.OrbReapThr') as MockOrbReapThr:
            orbreapthr = MagicMock()
            orbreapthr.get = orbget
            MockOrbReapThr.return_value = orbreapthr
            self.driver.start_sampling()
            expected_call_args = call(
                    ORB_NAME,
                    '',
                    '',
                    tafter,
                    timeout=0, queuesize=100)
            self.assertEquals(MockOrbReapThr.call_args, expected_call_args)

    def test_orbreapthr_args_changed(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        # Start sampling and watch for an exception

        # TODO make some packets, put in mock orb
        # TODO assert data

        def orbget():
            log.trace('no more packets')
            raise NoData()

        tafter = 999
        state={'parser_state': {'tafter': tafter,
            }}

        self.driver = self._get_driver_object(memento=state)

        with patch('mi.dataset.parser.antelope_orb.OrbReapThr') as MockOrbReapThr:
            orbreapthr = MagicMock()
            orbreapthr.get = orbget
            MockOrbReapThr.return_value = orbreapthr
            self.driver.start_sampling()
            expected_call_args = call(
                    ORB_NAME,
                    '',
                    '',
                    0.0,
                    timeout=0, queuesize=100)
            self.assertEquals(MockOrbReapThr.call_args, expected_call_args)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_missing_directory(self):
        self.skipTest("Not applicable to Antelope ORB driver")

    def test_harvester_new_file_exception(self):
        self.skipTest("Not applicable to Antelope ORB driver")

    def assert_all_queue_empty(self):
        """
        Assert the sample queue for all 3 data streams is empty
        """
        self.assert_sample_queue_size(DataParticleType.ANTELOPE_ORB_PACKET, 0)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        PACKETS_TO_SEND = 2
        SAMPLES_PER_PACKET = 4
        DATA = range(SAMPLES_PER_PACKET)
        pkttype, packet, srcname, pkttime = makepacket(DATA)

        with orbserver(PACKETS_TO_SEND, SAMPLES_PER_PACKET):
            log.debug("Started orb server")
            with Orb(ORB_NAME, permissions='w') as myorb:
                # Write packets to ORB
                log.debug("Connected to orb server")
                for n in xrange(PACKETS_TO_SEND):
                    myorb.putx(srcname, n + 1, packet)
            log.debug("Sent packets to orb server")
#            gevent.sleep(1000)

            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            self.assert_start_sampling()

            # Verify we get one sample
            try:
                result = self.data_subscribers.get_samples(DataParticleType.ANTELOPE_ORB_PACKET, 2)
                log.debug("First RESULT: %s", result)

                # Verify values
                self.assert_data_values(result, 'first.result.yml')
            finally:
                pass
#            except Exception as e:
#                log.error("Exception trapped: %s", e)
#                self.fail("Sample timeout.")

    def test_performance(self):
        PACKETS_TO_SEND = 200
        SAMPLES_PER_PACKET = 64000
        DATA = range(SAMPLES_PER_PACKET)
        TEST_TIMEOUT = 15

        pkttype, packet, srcname, pkttime = makepacket(DATA)

        with orbserver(PACKETS_TO_SEND, SAMPLES_PER_PACKET):
          log.debug("Started orb server")
          with Orb(ORB_NAME, permissions='w') as myorb:
              # Write packets to ORB
              log.debug("Connected to orb server")
              for n in xrange(PACKETS_TO_SEND):
                  myorb.put(srcname, n + 1, packet)
          log.debug("Sent packets to orb server")
          #gevent.sleep(10000)
          # Read packets out of orb
          self.assert_initialize(final_state=ResourceAgentState.COMMAND)
          end_time = start_time = time.time()
          end_time += 0.000001
          self.assert_start_sampling()
          result = []
          nsamps = 0
          try:
              yappi.start()
              profile.enable()
              while True:
                  try:
                      nsamps = len(self.data_subscribers.samples_received.get(
                                                           DataParticleType.ANTELOPE_ORB_PACKET))
                  except TypeError:
                      log.warning("No samples received")
                  end_time = time.time()
                  period = end_time - start_time
                  if period > TEST_TIMEOUT:
                      break
                  if nsamps >= PACKETS_TO_SEND - 1:
                      break
                  gevent.sleep(1)

#                  result = self.data_subscribers.get_samples(
#                              DataParticleType.ANTELOPE_ORB_PACKET,
#                              PACKETS_TO_SEND - 1, 120)

          finally:
              profile.disable()
              yappi.stop()
              period = end_time - start_time
              log.critical("Processed %d PACKETS_TO_SEND in %s for a rate of %s pps"
                  % (nsamps, period,  float(nsamps) / period ))

#            self.assert_reset()
#            self.stop_dataset_agent_client()

        # review published particles
        with open('yappistats', 'w') as f:
            yappi.print_stats(out=f)

        profile.dump_stats('cprofile')

