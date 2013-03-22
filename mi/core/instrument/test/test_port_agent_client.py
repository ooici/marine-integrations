#!/usr/bin/env python

"""
@package ion.services.mi.test.test_port_agent_client
@file ion/services/mi/test/test_port_agent_client.py
@author David Everett
@brief Some unit tests for R2 port agent client
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent

import logging
import unittest
import re
import time
import datetime
import array
from nose.plugins.attrib import attr
from mock import Mock

from ion.agents.port.port_agent_process import PortAgentProcess
from ion.agents.port.port_agent_process import PortAgentProcessType

from mi.core.unit_test import MiUnitTest
from mi.core.unit_test import MiIntTestCase
from mi.core.port_agent_simulator import TCPSimulatorServer
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket, Listener
from mi.core.exceptions import InstrumentConnectionException

# MI logger
from mi.core.log import get_logger ; log = get_logger()

#@unittest.skip('BROKEN - Useful in past, likely in future, but not just now')
@attr('UNIT', group='mi')
class PAClientUnitTestCase(MiUnitTest):
    def setUp(self):
        self.ipaddr = "localhost"
        self.cmd_port = 9001
        self.data_port  = 9002
    
    def resetTestVars(self):
        self.rawCallbackCalled = False
        self.dataCallbackCalled = False
        self.errorCallbackCalled = False
            
    def myGotData(self, paPacket):
        self.dataCallbackCalled = True
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent data packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotRaw(self, paPacket):
        self.rawCallbackCalled = True
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent raw packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotError(self, errorString = "No error string passed in."):
        self.errorCallbackCalled = True
        print "Got error: " +  errorString + "\r\n"
                       
    def test_handle_packet(self):

        """
        Test that a default PortAgentPacket creates a DATA_FROM_DRIVER packet,
        and that the handle_packet method invokes the raw callback
        """
        paListener = Listener(None, None, 0, 5, self.myGotData, self.myGotRaw, self.myGotError)
        
        test_data = "This is a great big test"
        self.resetTestVars()
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)

        """
        Test DATA_FROM_INSTRUMENT; handle_packet should invoke data and raw
        callbacks.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.DATA_FROM_INSTRUMENT)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)
        self.assertTrue(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)

        """
        Test PORT_AGENT_COMMAND; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_COMMAND)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)
        
        """
        Test PORT_AGENT_STATUS; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_STATUS)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)
        
        """
        Test PORT_AGENT_FAULT; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_FAULT)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)
        
        """
        Test INSTRUMENT_COMMAND; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.INSTRUMENT_COMMAND)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)
        
        """
        Test HEARTBEAT; handle_packet should not invoke any callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.HEARTBEAT)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertFalse(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertFalse(self.errorCallbackCalled)
        
    def test_heartbeat_timeout(self):
        """
        Initialize the Listener with a heartbeat value, then
        start the heartbeat.  Wait long enough for the heartbeat
        to timeout MAX_MISSED_HEARTBEATS times, and then assert
        that the error_callback was called.
        """
        
        self.resetTestVars()
        test_heartbeat = 1
        test_max_missed_heartbeats = 5
        paListener = Listener(None, None, test_heartbeat, test_max_missed_heartbeats,
                              self.myGotData, self.myGotRaw, self.myGotError)
        
        paListener.start_heartbeat_timer()
        
        gevent.sleep((test_max_missed_heartbeats * paListener.heartbeat) + 4)
        
        self.assertFalse(self.rawCallbackCalled)
        self.assertFalse(self.dataCallbackCalled)
        self.assertTrue(self.errorCallbackCalled)
        
    def test_set_heartbeat(self):
        """
        Test the set_heart_beat function; make sure it returns False when 
        passed invalid values, and true when valid.  Also make sure it
        adds the HEARTBEAT_FUDGE
        """
        self.resetTestVars()
        test_heartbeat = 0
        test_max_missed_heartbeats = 5
        paListener = Listener(None, None, test_heartbeat, test_max_missed_heartbeats,
                              self.myGotData, self.myGotRaw, self.myGotError)

        """ 
        Test valid values
        """        
        test_heartbeat = 1
        retValue = paListener.set_heartbeat(test_heartbeat)
        self.assertTrue(retValue)
        self.assertTrue(paListener.heartbeat == test_heartbeat + paListener.HEARTBEAT_FUDGE)
                
        test_heartbeat = paListener.MAX_HEARTBEAT_INTERVAL
        retValue = paListener.set_heartbeat(test_heartbeat)
        self.assertTrue(retValue)
        self.assertTrue(paListener.heartbeat == test_heartbeat + paListener.HEARTBEAT_FUDGE)
        
        """
        Test that a heartbeat value of zero results in the listener.heartbeat being zero 
        (and doesn't include HEARTBEAT_FUDGE)
        """
        test_heartbeat = 0
        retValue = paListener.set_heartbeat(test_heartbeat)
        self.assertTrue(retValue)
        self.assertTrue(paListener.heartbeat == test_heartbeat)
                
        """
        Test invalid values
        """
        test_heartbeat = -1
        retValue = paListener.set_heartbeat(test_heartbeat)
        self.assertFalse(retValue)

        test_heartbeat = paListener.MAX_HEARTBEAT_INTERVAL + 1
        retValue = paListener.set_heartbeat(test_heartbeat)
        self.assertFalse(retValue)

    def test_callback_error(self):
        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)
        
        """
        Mock up the init_comms method; the callback_error will try to invoke
        it, which will try to connect to the port_agent
        """
        mock_init_comms = Mock(spec = "init_comms")
        paClient.init_comms = mock_init_comms
        
        """
        Test that True is returned because the callback will try a recovery, 
        and it doesn't matter at that point that there is no higher-level
        callback registered.  Also assert that mock_init_comms was called.
        """
        retValue = paClient.callback_error("This is a great big error")
        self.assertTrue(retValue)
        self.assertTrue(len(mock_init_comms.mock_calls) == 1)

        """
        Now call callback_error again.  This time it should return False
        because no higher-level callback has been registered.  Also assert
        that mock_init_calls hasn't been called again (still is 1).
        """
        retValue = paClient.callback_error("This is a big boo boo")
        self.assertFalse(retValue)
        self.assertTrue(len(mock_init_comms.mock_calls) == 1)

        """
        Now call again with a callback registered; assert that the retValue
        is True (callback registered), that mock_init_comms is still 1, and
        that the higher-level callback was called.
        """
        self.resetTestVars()
        paClient.user_callback_error = self.myGotError
        retValue = paClient.callback_error("Another big boo boo")
        self.assertTrue(retValue)
        self.assertTrue(len(mock_init_comms.mock_calls) == 1)
        self.assertTrue(self.errorCallbackCalled == 1)
        
    @unittest.skip('not finished yet')
    def test_port_agent_client_receive(self):
        ipaddr = "67.58.49.194"
        port  = 4000
        paClient = PortAgentClient(self.ipaddr, self.port)
        #paClient = PortAgentClient(ipaddr, port)
        paClient.init_comms(self.myGotData)
        
    @unittest.skip('not finished yet')
    def test_port_agent_client_send(self):
        ipaddr = "67.58.49.194"
        port  = 4000
        paClient = PortAgentClient(self.ipaddr, self.port)
        #paClient = PortAgentClient(ipaddr, port)
        paClient.init_comms(self.myGotData)
        
        paClient.send('this is a test\n')


SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[0:3])
NTP_EPOCH = datetime.date(1900, 1, 1)
NTP_DELTA = (SYSTEM_EPOCH - NTP_EPOCH).days * 24 * 3600

class TestPortAgentPacket(MiUnitTest):
    # time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(time.time()))
    #

    @staticmethod
    def ntp_to_system_time(date):
        """convert a NTP time to system time"""
        return date - NTP_DELTA

    @staticmethod
    def system_to_ntp_time(date):
        """convert a system time to a NTP time"""
        return date + NTP_DELTA

    def setUp(self):
        self.pap = PortAgentPacket()
        #self.test_time = time.time()
        #self.ntp_time = self.system_to_ntp_time(self.test_time)

        #self.pap.set_timestamp(self.ntp_time)


    def test_pack_header(self):
        self.pap.attach_data("Only the length of this matters?") # 32 chars
        #self.pap.set_timestamp(3564425404.85)
        self.pap.pack_header()
        header = self.pap.get_header()
        self.assertEqual(header, array.array('B', [163, 157, 122, 2, 0, 48, 14, 145, 65, 234, 142, 154, 23, 155, 51, 51]))
        pass

    def test_unpack_header(self):
        self.pap = PortAgentPacket()
        data = self.pap.unpack_header(array.array('B', [163, 157, 122, 2, 0, 48, 14, 145, 65, 234, 142, 154, 23, 155, 51, 51]))

        self.assertEqual(self.pap.get_header_type(), 2)
        self.assertEqual(self.pap.get_header_length(), 32)
        self.assertEqual(time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(self.ntp_to_system_time(self.pap.get_timestamp()))), "Thu, 13 Dec 2012 14:10:04 +0000")
        self.assertEqual(self.pap.get_header_recv_checksum(), 3729) #@TODO Probably should wire in one of these checksums.
        self.assertEqual(self.pap.get_header_checksum(), None)
        pass


    def test_get_time_stamp(self):
        result = self.pap.get_timestamp()
        self.assertEqual(self.ntp_time, result)
        pass

    def test_pack_unpack_header_timestamp(self):
        self.pap.attach_data("sweet polly purebread")
        self.pap.pack_header()
        header = self.pap.get_header()
        self.pap.unpack_header(header)

        result = self.pap.get_timestamp()
        self.assertEqual(self.ntp_time, result)
        pass

@attr('INT', group='mi')
class PAClientIntTestCase(InstrumentDriverTestCase):
#class PAClientIntTestCase(MiIntTestCase):

    def initialize(cls, *args, **kwargs):
        print "initialize"
        
    def setUp(self):
        #InstrumentDriverIntegrationTestCase.setUp(self)

        """
        DHE: Change this to init my own simulator
        """
        #self.ipaddr = "69.196.56.192"
        self.ipaddr = "localhost"
        self.cmd_port = 9001
        self.data_port  = 9002
        self.device_port = 9003
        
        self.rawCallbackCalled = False
        self.dataCallbackCalled = False
        self.errorCallbackCalled = False
        
    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("PACClientIntTestCase tearDown")

        InstrumentDriverTestCase.tearDown(self)

    def startPortAgent(self):
        pa_port = self.init_port_agent()
        print "port_agent started on port: " + str(pa_port)

    def resetTestVars(self):
        self.rawCallbackCalled = False
        self.dataCallbackCalled = False
        self.errorCallbackCalled = False
            
    def myGotData(self, paPacket):
        self.dataCallbackCalled = True
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent data packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotRaw(self, paPacket):
        self.rawCallbackCalled = True
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent raw packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotError(self, errorString = "No error string passed in."):
        self.errorCallbackCalled = True
        log.error("myGotError got error: %s" % errorString)
                       
    def init_instrument_simulator(self):
        """
        Startup a TCP server that we can use as an instrument simulator
        """
        self._instrument_simulator = TCPSimulatorServer()
        self.addCleanup(self._instrument_simulator.close)

        # Wait for the simulator to bind to a port
        timeout = time.time() + 10
        while (timeout > time.time()):
            if (self._instrument_simulator.port > 0):
                log.debug("Instrument simulator initialized on port %s" % self._instrument_simulator.port)
                return

            log.debug("waiting for simulator to bind. sleeping")
            time.sleep(1)

        raise IDKException("Timeout waiting for simulator to bind")

    def init_port_agent(self):
        """
        @brief Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @retval return the pid to the logger process
        """
        if (self.port_agent):
            log.error("Port agent already initialized")
            return

        log.debug("Startup Port Agent")

        #comm_config = self.get_comm_config()

        config = self.port_agent_config()
        log.debug("port agent config: %s" % config)

        port_agent = PortAgentProcess.launch_process(config, timeout = 60, test_mode = True)

        port = port_agent.get_data_port()
        pid  = port_agent.get_pid()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))

        self.addCleanup(self.stop_port_agent)
        self.port_agent = port_agent
        return port

    def port_agent_config(self):
        """
        Overload the default port agent configuration so that
        it connects to a simulated TCP connection.
        """
        config = {
            'device_addr' : self.ipaddr,
            'device_port' : self.device_port,

            'command_port': self.cmd_port,
            'data_port': self.data_port,

            'process_type': PortAgentProcessType.UNIX,
            'log_level': 5,
        }

        # Override the instrument connection information.
        config['device_addr'] = 'localhost'
        config['device_port'] = self._instrument_simulator.port

        return config
    
    def test_start_paClient_no_port_agent(self):

        print "port agent client test begin"

        self.resetTestVars()
        
        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)
        
        try:
            paClient.init_comms(self.myGotData, self.myGotRaw, self.myGotError)
 
        except InstrumentConnectionException as e:
            log.info("Exception caught as expected: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
        """
        Assert that the error_callback was not called, and that an exception
        was caught.
        """
        self.assertFalse(self.errorCallbackCalled)
        self.assertTrue(exceptionCaught)
    
    def test_start_paClient_with_port_agent(self):

        self.resetTestVars()
        
        self.init_instrument_simulator()
        self.startPortAgent()

        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)

        try:        
            paClient.init_comms(self.myGotData, self.myGotRaw, self.myGotError)
        
        except InstrumentConnectionException as e:
            log.error("Exception caught: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
            data = "this is a great big test"
            paClient.send(data)
        
            time.sleep(1)
    
            self._instrument_simulator.send(data)
            
            time.sleep(5)
    
        paClient.stop_comms()

        """
        Assert that the error_callback was not called, that an exception was not
        caught, and that the data and raw callbacks were called.
        """
        self.assertFalse(self.errorCallbackCalled)        
        self.assertFalse(exceptionCaught)
        self.assertTrue(self.rawCallbackCalled)
        self.assertTrue(self.dataCallbackCalled)
    
    def test_start_paClient_lost_port_agent_tx_rx(self):
        """
        This test starts the port agent and the instrument_simulator and
        tests that data is sent and received first; then it stops the port
        agent and tests that the error_callback was called.
        """

        self.resetTestVars()
        
        self.init_instrument_simulator()
        self.startPortAgent()

        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)

        """
        Give the port agent time to initialize
        """
        time.sleep(2)
        paClient.init_comms(self.myGotData, self.myGotRaw, self.myGotError)
        
        """
        Now send some data; there should be no errors.
        """
        try:
            data = "this is a great big test"
            paClient.send(data)
        
            time.sleep(1)
    
            self._instrument_simulator.send(data)
            
        except InstrumentConnectionException as e:
            log.error("Exception caught: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
        time.sleep(1)
    
        """
        Assert that the error_callback was NOT called, that an exception was NOT
        caught, and that the data and raw callbacks WERE called.
        """
        self.assertFalse(self.errorCallbackCalled)        
        self.assertFalse(exceptionCaught)
        self.assertTrue(self.rawCallbackCalled)
        self.assertTrue(self.dataCallbackCalled)

        """
        Now reset the test variables and try again; this time after stopping
        the port agent.  Should be errors
        """
        
        self.resetTestVars()

        try:
            self.stop_port_agent()    
            data = "this is another great big test"
            paClient.send(data)
        
            time.sleep(1)
    
            self._instrument_simulator.send(data)
            
        except InstrumentConnectionException as e:
            log.error("Exception caught: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
        time.sleep(5)
    
        """
        Assert that the error_callback WAS called.  The listener usually 
        is seeing the error first, and that does not call the exception, so
        only assert that the error callback was called.
        """
        self.assertTrue(self.errorCallbackCalled)        
    
    def test_start_paClient_lost_port_agent_rx(self):
        """
        This test starts the port agent and then stops the port agent and
        verifies that the error callback was called (because the listener
        is the only one that will see the error, since there is no send
        operation).
        """

        self.resetTestVars()
        
        self.init_instrument_simulator()
        self.startPortAgent()

        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)

        """
        Give the port agent time to initialize
        """
        time.sleep(2)
        
        paClient.init_comms(self.myGotData, self.myGotRaw, self.myGotError)
        
        try:
            self.stop_port_agent()    

        except InstrumentConnectionException as e:
            log.error("Exception caught: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
        time.sleep(5)
    
        """
        Assert that the error_callback was called.  At this moment the listener
        is seeing the error first, and that does not call the exception, so
        don't test for that yet.
        """
        self.assertTrue(self.errorCallbackCalled)        

    
    @unittest.skip('Skip; this test does not work consistently.')
    def test_start_paClient_lost_port_agent_tx(self):
        """
        This test starts the port agent and then starts the port agent client
        in a special way that will not start the listener thread.  This will
        guarantee that the send context is the one the sees the error.
        """

        self.resetTestVars()

        self.init_instrument_simulator()
        self.startPortAgent()

        paClient = PortAgentClient(self.ipaddr, self.data_port, self.cmd_port)

        """
        Give the port agent time to initialize
        """
        time.sleep(5)
        
        paClient.init_comms(self.myGotData, self.myGotRaw, self.myGotError, start_listener = False)
        
        try:
            self.stop_port_agent()    
            data = "this big ol' test should cause send context to fail"
            paClient.send(data)
        
            time.sleep(1)

        except InstrumentConnectionException as e:
            log.error("Exception caught: %r" % (e))
            exceptionCaught = True
            
        else:
            exceptionCaught = False
        
        time.sleep(5)
    
        """
        Assert that the error_callback was called.  For this test the listener
        should not be running, so the send context should see the error, and that
        should throw an exception.  Assert that the callback WAS called and that
        an exception WAS thrown.
        """
        self.assertTrue(self.errorCallbackCalled)        
        self.assertTrue(exceptionCaught)
