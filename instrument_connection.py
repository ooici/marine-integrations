#!/usr/bin/env python

"""
@package ion.services.mi.instrument_connection Instrument connection structures
@file ion/services/mi/instrument_connection.py
@author Steve Foley
@brief Instrument connection classes that provide base connect/disconnect
structure interactions with individual instruments.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

# imports go here

class InstrumentConnection(Object):
    '''The structure to handle connecting and disconnecting from instruments
    
    This class is a base structure for subclasses that connect and disconnect
    from instruments in different ways.
    '''
    
    def connect(self, params={}):
        '''Connect to the instrument
        
        @param params Dict of parameters that define how the connection should
        be made. Parameter names are in the subclasses.
        @throws Exception
        '''
        
    def disconnect(self):
        '''Disconnect from the instrument
        
        @throws Exception
        '''
    
    def reset(self):
        '''Reset the connection if that is appropriate'''
        
    def get_state(self):
        '''Get the state of the connection
        
        @retval state The connection state as per the Instrument Driver states
        '''
    
class EthernetInstrumentConnection(InstrumentConnection):
    '''Ethernet-based instrument connection'''
    
    '''Enumeration name for IP address to connect to'''
    IP_ADDRESS = "IP Address"
    
    '''Enumeration name for the IP port to connect to'''
    PORT = "Port"
    
    '''Enumeration name for the protocol to connect with'''
    PROTOCOL = "Protocol" # TCP, UDP, etc
    
    def connect(self, params={}):
        '''Connect with IP address and port parameters
        
        Possibly proxy info if needed in the future.
        '''
    
    def disconnect(self):
        pass
    
    def reset(self):
        pass
    
    def get_state(self):
        pass
        


