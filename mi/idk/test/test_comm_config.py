#!/usr/bin/env python

"""
@package mi.idk.test.test_comm_config
@file mi.idk/test/test_comm_config.py
@author Bill French
@brief test metadata object
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os import remove
from os.path import exists
import sys
import string

from nose.plugins.attrib import attr
from mock import Mock
import unittest
from mi.core.unit_test import MiUnitTest

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig, ConfigTypes

from mi.idk.exceptions import DriverParameterUndefined
from mi.idk.exceptions import NoConfigFileSpecified
from mi.idk.exceptions import CommConfigReadFail
from mi.idk.exceptions import InvalidCommType

#
# Common
#
HOST = 'localhost'
SNIFFER_PORT = 6003

#
# Ethernet
#
INSTRUMENT_ADDR = 'localhost'
INSTRUMENT_PORT = 4000
COMMAND_PORT = 4001
DATA_PORT = 4002

#
# Serial
#
DEVICE_OS_PORT = '/dev/ttyS0'
DEVICE_BAUD = 9600
DEVICE_DATA_BITS = 8
DEVICE_PARITY = 0 # 0=none, 1=odd, 2=even
DEVICE_STOP_BITS = 1 # 1 or 2
DEVICE_FLOW_CONTROL = 0 # 0=none, 1=hardware, 2=software


ROOTDIR="/tmp/test_config.idk_test"
# /tmp is a link on OS X
if exists("/private/tmp"):
    ROOTDIR = "/private%s" % ROOTDIR
    
CONFIG_FILE="comm_config.yml"

@attr('UNIT', group='mi')
class TestCommConfig(MiUnitTest):
    """
    Test the comm config object.  
    """    
    def setUp(self):
        """
        Setup the test case
        """
        if not exists(ROOTDIR):
            makedirs(ROOTDIR)
            
        #self.write_config()
        
    def config_file(self):
        return "%s/comm_config.yml" % ROOTDIR
    
    def config_ethernet_content(self):
        return "comm:\n" +\
               "  command_port: %d\n" % (COMMAND_PORT) + \
               "  data_port: %d\n" % (DATA_PORT) + \
               "  device_addr: %s\n" % (INSTRUMENT_ADDR) + \
               "  device_port: %d\n" % (INSTRUMENT_PORT) + \
               "  host: %s\n" % (HOST) + \
               "  sniffer_port: %d\n" % (SNIFFER_PORT) + \
               "  method: ethernet\n"

    def config_serial_content(self):
        return "comm:\n" +\
               "  command_port: %d\n" % (COMMAND_PORT) +\
               "  data_port: %d\n" % (DATA_PORT) +\
               "  device_os_port: %s\n" % (DEVICE_OS_PORT) + \
               "  device_baud: %d\n" % (DEVICE_BAUD) + \
               "  device_data_bits: %d\n" % (DEVICE_DATA_BITS) + \
               "  device_parity: %d\n" % (DEVICE_PARITY) + \
               "  device_stop_bits: %d\n" % (DEVICE_STOP_BITS) + \
               "  device_flow_control: %d\n" % (DEVICE_FLOW_CONTROL) + \
               "  host: %s\n" % (HOST) + \
               "  sniffer_port: %d\n" % (SNIFFER_PORT) + \
               "  method: serial\n"

    def write_ethernet_config(self):
        ofile = open(self.config_file(), "w");
        ofile.write(self.config_ethernet_content())
        ofile.close()

    def write_serial_config(self):
        ofile = open(self.config_file(), "w");
        ofile.write(self.config_serial_content())
        ofile.close()

    def read_config(self):
        infile = open(self.config_file(), "r")
        result = infile.read()
        infile.close()
        return result
               
    def test_1_constructor(self):
        """
        Test object creation
        """
        config = CommConfig()
        self.assertTrue(config)
    
    def test_2_exceptions(self):
        """
        Test exceptions raised by the CommConfig object
        """
        ## No exception thrown if file doesn't exist
        error = None
        try:
            config = CommConfig("this_file_does_not_exist.foo")
        except CommConfigReadFail, e:
            error = e
        self.assertFalse(error)
        
        error = None
        try:
            config = CommConfig()
            config.read_from_file("/tmp");
        except CommConfigReadFail, e:
            log.debug("caught error %s" % e)
            error = e
        self.assertTrue(error)
        
        error = None
        try:
            config = CommConfig()
            config.store_to_file();
        except NoConfigFileSpecified, e:
            log.debug("caught error %s" % e)
            error = e
        self.assertTrue(error)
        
        error = None
        try:
            config = CommConfig.get_config_from_type(self.config_file(), "foo")
        except InvalidCommType, e:
            log.debug("caught error %s" % e)
            error = e
        self.assertTrue(error)
    
    def test_3_comm_config_type_list(self):
        types = CommConfig.valid_type_list()
        log.debug( "types: %s" % types)
        
        known_types = [ConfigTypes.ETHERNET, ConfigTypes.SERIAL, ConfigTypes.BOTPT]
        
        self.assertEqual(sorted(types), sorted(known_types))
        
    def test_4_config_write_ethernet(self):
        log.debug("Config File: %s" % self.config_file())
        if exists(self.config_file()):
            log.debug(" -- remove %s" % self.config_file())
            remove(self.config_file())
            
        self.assertFalse(exists(self.config_file()))
        
        config = CommConfig.get_config_from_type(self.config_file(), ConfigTypes.ETHERNET)
        config.device_addr = INSTRUMENT_ADDR
        config.device_port = INSTRUMENT_PORT
        config.data_port = DATA_PORT
        config.command_port = COMMAND_PORT
        
        log.debug("CONFIG: %s" % config.serialize())
        
        config.store_to_file()

        # order isnt the same, so lets turn it into an array of label: value's then sort and compare.
        self.assertEqual(sorted(string.replace(self.config_ethernet_content(), "\n", '').split('  ')),
                         sorted(string.replace(self.read_config(), "\n", '').split('  ')))
        
    def test_5_config_read_ethernet(self):
        config = CommConfig.get_config_from_type(self.config_file(), ConfigTypes.ETHERNET)
        
        self.assertEqual(config.device_addr, INSTRUMENT_ADDR)
        self.assertEqual(config.device_port, INSTRUMENT_PORT)
        self.assertEqual(config.data_port, DATA_PORT)
        self.assertEqual(config.command_port, COMMAND_PORT)


    def test_6_config_write_serial(self):
        log.debug("Config File: %s" % self.config_file())
        if exists(self.config_file()):
            log.debug(" -- remove %s" % self.config_file())
            remove(self.config_file())

        self.assertFalse(exists(self.config_file()))

        config = CommConfig.get_config_from_type(self.config_file(), ConfigTypes.SERIAL)
        config.device_os_port = DEVICE_OS_PORT
        config.device_baud = DEVICE_BAUD
        config.device_data_bits = DEVICE_DATA_BITS
        config.device_parity = DEVICE_PARITY
        config.device_stop_bits = DEVICE_STOP_BITS
        config.device_flow_control = DEVICE_FLOW_CONTROL
        config.data_port = DATA_PORT
        config.command_port = COMMAND_PORT

        log.debug("CONFIG: %s" % config.serialize())

        config.store_to_file()

        # order isnt the same, so lets turn it into an array of label: value's then sort and compare.
        self.assertEqual(sorted(string.replace(self.config_serial_content(), "\n", '').split('  ')),
                         sorted(string.replace(self.read_config(), "\n", '').split('  ')))

    def test_7_config_read_serial(self):
        config = CommConfig.get_config_from_type(self.config_file(), ConfigTypes.SERIAL)

        self.assertEqual(config.device_os_port, DEVICE_OS_PORT)
        self.assertEqual(config.device_baud, DEVICE_BAUD)
        self.assertEqual(config.device_data_bits, DEVICE_DATA_BITS)
        self.assertEqual(config.device_parity, DEVICE_PARITY)
        self.assertEqual(config.device_stop_bits, DEVICE_STOP_BITS)
        self.assertEqual(config.device_flow_control, DEVICE_FLOW_CONTROL)
        self.assertEqual(config.data_port, DATA_PORT)
        self.assertEqual(config.command_port, COMMAND_PORT)



