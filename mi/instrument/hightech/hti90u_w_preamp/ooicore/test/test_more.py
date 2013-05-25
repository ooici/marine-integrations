"""
@package mi.instrument.hightech.hti90u_w_preamp.ooicore.test.test_driver
@file marine-integrations/mi/instrument/hightech/hti90u_w_preamp/ooicore/driver.py
@author Jeff Laughlin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Jeff Laughlin'
__license__ = 'Apache 2.0'

from cStringIO import StringIO
from contextlib import contextmanager
from pprint import pprint, pformat
import shutil
import subprocess
import tempfile
import unittest
import os.path
import time


import gevent
import gevent.pool

import antelope.orb
import antelope.Pkt

from mock import Mock

import logging
log = logging.getLogger()

import mi.core.instrument.port_agent_client
import port_agent.cmdproc
import port_agent.config
import port_agent.port_agent

# MI imports.
# Does not exist
#from mi.idk.unit_test import InstrumentDriverDataParticleMixin

# from https://github.com/unwin/marine-integrations/blob/master/mi/instrument/teledyne/workhorse_monitor_75_khz/test/test_driver.py#L37


from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import InstrumentDriver
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import DataParticleType
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import InstrumentCommand
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import ProtocolState
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import ProtocolEvent
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import Capability
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import Parameter
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import Protocol
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import Prompt
from mi.instrument.hightech.hti90u_w_preamp.ooicore.driver import NEWLINE


SITECHANS = [line.split() for line in StringIO("""SUM1   HHZ
SUM1   HHN
SUM1   HHE
SUM1   BHZ
SUM1   BHN
SUM1   BHE
SUM1   LHZ
SUM1   LHN
SUM1   LHE
SUM1   HNZ
SUM1   HNN
SUM1   HNE
SUM1   LNZ
SUM1   LNN
SUM1   LNE
SUM13  HNZ
SUM13  HNN
SUM13  HNE
SUM13  LNZ
SUM13  LNN
SUM13  LNE
SUM13  HHZ
SUM13  HHN
SUM13  HHE
SUM13  LHZ
SUM13  LHN
SUM13  LHE""")]


class Test_ORB_thru_Protocol(unittest.TestCase):
    def test_it_all(self):
        ORB_PORT = 54320
        COMMAND_PORT = 54321
        DATA_PORT = 54322
        ORB_NAME = 'localhost:%s' % ORB_PORT

        PACKETS_TO_SEND = 1000
        SAMPLES_PER_PACKET = 128
        SAMPLES_TO_SEND = PACKETS_TO_SEND * SAMPLES_PER_PACKET 
        BYTES_PER_SAMPLE = 4
        BYTES_PER_PACKET = SAMPLES_PER_PACKET * BYTES_PER_SAMPLE
        SAFETY = 1.5
        ORB_BYTES = int(PACKETS_TO_SEND * BYTES_PER_PACKET * SAFETY)
        DATA = range(SAMPLES_PER_PACKET)

        samples_rx = [0]

        @contextmanager
        def tempdir():
            path = tempfile.mkdtemp()
            try:
                yield path
            finally:
                shutil.rmtree(path)

        @contextmanager
        def orbserver(prefix):
            p = subprocess.Popen('orbserver -p %s -P "%s/orb" -s %d orbserver' %
                                        (ORB_PORT, prefix, ORB_BYTES), shell=True)
            try:
                gevent.sleep(2)
                yield p
            finally:
                p.kill()

        @contextmanager
        def port_agent_antelope(path):
            conffilepath = os.path.join(path, 'paconf')
            conffile_contents = """heartbeat_interval 0
pid_dir %s
command_port %s
data_port %s
antelope_orb_name %s""" % (path, COMMAND_PORT, DATA_PORT, ORB_NAME)
            with open(conffilepath, 'w') as conffile:
                conffile.write(conffile_contents)
            pa = subprocess.Popen('port_agent_antelope -s -c "%s"' % conffilepath, shell=True)
            try:
                gevent.sleep(5)
                assert pa.poll() is None
                yield
            finally:
                assert pa.poll() is None
                pa.kill()

        _data_particle_received = []

        def driver_event(event_type, sample_value=None):
            samples_rx[0] += 1
            return # Do nothing FTM
            if event_type == DriverAsyncEvent.SAMPLE:
                particle_dict = json.loads(sample_value)
                _data_particle_received.append(sample_value)


        protocol = Protocol(None, None, driver_event)

        # set sample event callback _got_data_event_callback

        @contextmanager
        def port_agent_client():
            pac = mi.core.instrument.port_agent_client.PortAgentClient(
                host = 'localhost',
                port = DATA_PORT,
                cmd_port = COMMAND_PORT
            )
            pac.init_comms(
                user_callback_data = protocol.got_data,
            )
            try:
                yield pac
            finally:
                pac.done()

        def packet_maker(orb, samprate, net, sta, chan):
            global samples_sent
            sleep_period = 1.0 / samprate * SAMPLES_PER_PACKET
            pkt = antelope.Pkt.Packet()
            srcname = pkt.srcname
            srcname.net = net
            srcname.sta = sta
            srcname.chan = chan
            srcname.suffix = 'GEN'
            pktchan = antelope.Pkt.PktChannel()
            pktchan.samprate = samprate
            pktchan.data = DATA
            pktchan.chan = chan
            pkt.channels = [pktchan,]
            type, packet, srcname, pkttime = pkt.stuff()
            for n in xrange(PACKETS_TO_SEND):
                orb.put(srcname, n, packet)

        TEST_TIMEOUT = 60

        with tempdir() as path:
          with orbserver(path):
            with antelope.orb.orbopen(ORB_NAME, permissions='w') as myorb:
              with port_agent_antelope(path):
                with port_agent_client():
                    start_time = time.time()
                    packet_maker(myorb, 200, 'TA', 'SUM1', 'HYD')
                    for n in xrange(TEST_TIMEOUT):
                        gevent.sleep(1)
                        if samples_rx[0] >= SAMPLES_TO_SEND:
                            break
                    end_time = time.time()

        # review published particles

        period = end_time - start_time

        log.critical("Processed %d out of %d samples in %s for a rate of %s sps"
            % (samples_rx[0], SAMPLES_TO_SEND, period,  float(samples_rx[0]) / period ))

if __name__ == '__main__':
    logging.basicConfig()
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
