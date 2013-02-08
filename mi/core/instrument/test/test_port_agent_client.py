#!/usr/bin/env python

"""
@package ion.services.mi.test.test_port_agent_client
@file ion/services/mi/test/test_port_agent_client.py
@author David Everett
@brief Some unit tests for R2 port agent client
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import logging
import unittest
from mi.core.unit_test import MiUnitTest
import re
import time
import datetime
import array
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket

# MI logger
from mi.core.log import get_logger ; log = get_logger()

@unittest.skip('BROKEN - Useful in past, likely in future, but not just now')
@attr('UNIT', group='mi')
class TestPortAgentClient(MiUnitTest):
    def setUp(self):
        self.ipaddr = "67.58.49.194"
        self.port  = 4000
    
    def resetTestVars(self):
        self.rawCallbackCalled = False
        self.dataCallbackCalled = False
        self.errorCallbackCalled = False
            
    def myGotData(self, paPacket):
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())
        
    def myGotData(self, paPacket):
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent data packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotRaw(self, paPacket):
        if paPacket.is_valid():
            validity = "valid"
        else:
            validity = "invalid"
            
        print "Got " + validity + " port agent raw packet with data length " + str(paPacket.get_data_size()) + ": " + str(paPacket.get_data())

    def myGotError(self, errorString = "No error string passed in."):
        print "Got error: " +  errorString + "\r\n"
                       
    def test_handle_packet(self):

        """
        Test that a default PortAgentPacket creates a DATA_FROM_DRIVER packet,
        and that the handle_packet method invokes the raw callback
        """
        paListener = Listener(None, None, 0, self.myGotData, self.myGotRaw, self.myGotError)
        
        test_data = "This is a great big test"
        self.resetTestVars()
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(rawCallbackCalled)

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
        
        self.assertTrue(rawCallbackCalled)
        self.assertTrue(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)

        """
        Test PORT_AGENT_COMMAND; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_COMMAND)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(rawCallbackCalled)
        self.assertFalse(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)
        
        """
        Test PORT_AGENT_STATUS; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_STATUS)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(rawCallbackCalled)
        self.assertFalse(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)
        
        """
        Test PORT_AGENT_FAULT; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.PORT_AGENT_FAULT)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(rawCallbackCalled)
        self.assertFalse(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)
        
        """
        Test INSTRUMENT_COMMAND; handle_packet should invoke raw callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.INSTRUMENT_COMMAND)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertTrue(rawCallbackCalled)
        self.assertFalse(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)
        
        """
        Test HEARTBEAT; handle_packet should not invoke any callback.
        """
        self.resetTestVars()
        paPacket = PortAgentPacket(PortAgentPacket.HEARTBEAT)         
        paPacket.attach_data(test_data)
        paPacket.pack_header()
        paPacket.verify_checksum()

        paListener.handle_packet(paPacket)
        
        self.assertFalse(rawCallbackCalled)
        self.assertFalse(dataCallbackCalled)
        self.assertFalse(errorCallbackCalled)
        
        
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
