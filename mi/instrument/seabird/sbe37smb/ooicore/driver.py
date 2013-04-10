#!/usr/bin/env python

"""
@package ion.services.mi.drivers.sbe37.sbe37.sbe37_driver
@file ion/services/mi/drivers/sbe37/sbe37_driver.py
@author Edward Hunter
@brief Driver class for sbe37 CTD instrument.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

import base64
import logging
import time
import re
import datetime
from threading import Timer
import string
import ntplib
import json

from mi.core.common import BaseEnum
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM, ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, CommonDataParticleType
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.log import get_logger
log = get_logger()

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'parsed'
    DEVICE_CALIBRATION = 'device_calibration_parsed'
    DEVICE_STATUS = 'device_status_parsed'
    
class InstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that must be sent to the instrument to
    execute the command.
    """ 
    DISPLAY_CALIBRATION = 'dc'
    DISPLAY_STATUS = 'ds'
    
    TAKE_SAMPLE = 'ts'
    START_LOGGING = 'startnow'
    STOP_LOGGING = 'stop'
    SET = 'set'
    
    #'tc'
    #'tt'
    #'tp'

class SBE37ProtocolState(BaseEnum):
    """
    Protocol states for SBE37. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class SBE37ProtocolEvent(BaseEnum):
    """
    Protocol events for SBE37. Cherry picked from DriverEvent enum.
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS                     # DS
    ACQUIRE_CONFIGURATION = "PROTOCOL_EVENT_ACQUIRE_CONFIGURATION"  # DC
    
class SBE37Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = SBE37ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = SBE37ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = SBE37ProtocolEvent.STOP_AUTOSAMPLE
    TEST = SBE37ProtocolEvent.TEST
    ACQUIRE_STATUS  = SBE37ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_CONFIGURATION = SBE37ProtocolEvent.ACQUIRE_CONFIGURATION

# Device specific parameters.
class SBE37Parameter(DriverParameter):
    """
    Device parameters for SBE37.
    """
    OUTPUTSAL = 'OUTPUTSAL'
    OUTPUTSV = 'OUTPUTSV'
    NAVG = 'NAVG'
    SAMPLENUM = 'SAMPLENUM'
    INTERVAL = 'INTERVAL'
    STORETIME = 'STORETIME'
    TXREALTIME = 'TXREALTIME'
    SYNCMODE = 'SYNCMODE'
    SYNCWAIT = 'SYNCWAIT'
    TCALDATE = 'TCALDATE'
    TA0 = 'TA0'
    TA1 = 'TA1'
    TA2 = 'TA2'
    TA3 = 'TA3'
    CCALDATE = 'CCALDATE'
    CG = 'CG'
    CH = 'CH'
    CI = 'CI'
    CJ = 'CJ'
    WBOTC = 'WBOTC'
    CTCOR = 'CTCOR'
    CPCOR = 'CPCOR'
    PCALDATE = 'PCALDATE'
    PA0 = 'PA0'
    PA1 = 'PA1'
    PA2 = 'PA2'
    PTCA0 = 'PTCA0'
    PTCA1 = 'PTCA1'
    PTCA2 = 'PTCA2'
    PTCB0 = 'PTCB0'
    PTCB1 = 'PTCB1'
    PTCB2 = 'PTCB2'
    POFFSET = 'POFFSET'
    RCALDATE = 'RCALDATE'
    RTCA0 = 'RTCA0'
    RTCA1 = 'RTCA1'
    RTCA2 = 'RTCA2'

# Device prompts.
class SBE37Prompt(BaseEnum):
    """
    SBE37 io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '?cmd S>'
    AUTOSAMPLE = 'S>\r\n'

# SBE37 newline.
NEWLINE = '\r\n'

# SBE37 default timeout.
SBE37_TIMEOUT = 10

# Sample looks something like:
# '#87.9140,5.42747, 556.864,   37.1829, 1506.961, 02 Jan 2001, 15:34:51'
# Where C, T, and D are first 3 number fields respectively
# Breaks it down a bit
SAMPLE_PATTERN = r'#? *(-?\d+\.\d+), *(-?\d+\.\d+), *(-?\d+\.\d+)'
SAMPLE_PATTERN += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
SAMPLE_PATTERN += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'
SAMPLE_PATTERN += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'
SAMPLE_PATTERN_MATCHER = re.compile(SAMPLE_PATTERN)
 
#STATUS_DATA_REGEX = r"(SBE37-SMP V [\d\.]+ SERIAL NO.*? deg C)"          
STATUS_DATA_REGEX = r"(SBE37-SMP.*? deg C.*)"
STATUS_DATA_REGEX_MATCHER = re.compile(STATUS_DATA_REGEX, re.DOTALL)
#CALIBRATION_DATA_REGEX = r"(SBE37-SM V [\d\.]+.*?RTCA2 = -?[\d\.e\-\+]+)"
CALIBRATION_DATA_REGEX = r"(SBE37-SM.*?RTCA2 = -?[\d\.e\-\+]+)"
CALIBRATION_DATA_REGEX_MATCHER = re.compile(CALIBRATION_DATA_REGEX, re.DOTALL)

  
###############################################################################
# Seabird Electronics 37-SMP MicroCAT Driver.
###############################################################################

class SBE37Driver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass for SBE37 driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################
        

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE37Protocol(SBE37Prompt, NEWLINE, self._driver_event)

    def apply_startup_params(self):
        """
        Overload the default behavior which is to pass the buck to the protocol.
        Alternatively we could retrofit the protocol to better handle the apply
        startup params feature which would be preferred in production drivers.
        @raise InstrumentParameterException If the config cannot be applied
        """
        config = self._protocol.get_startup_config()

        if not isinstance(config, dict):
            raise InstrumentParameterException("Incompatible initialization parameters")

        self.set_resource(config)



class SBE37DataParticleKey(BaseEnum):
    TEMP = "temp"
    CONDUCTIVITY = "conductivity"
    DEPTH = "pressure"
    
class SBE37DataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PARSED

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_PATTERN_MATCHER.match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            temperature = float(match.group(1))
            conductivity = float(match.group(2))
            depth = float(match.group(3))
        except ValueError:
            raise SampleException("ValueError while decoding floats in data: [%s]" %
                                  self.raw_data)
        
        #TODO:  Get 'temp', 'cond', and 'depth' from a paramdict
        result = [{DataParticleKey.VALUE_ID: SBE37DataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE37DataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE37DataParticleKey.DEPTH,
                    DataParticleKey.VALUE: depth}]
        
        return result

##
## BEFORE ADDITION
##

      
class SBE37DeviceCalibrationParticleKey(BaseEnum):  
    TCALDATE = 'calibration_date_temperature'
    TA0 = 'sbe37_coeff_ta0'
    TA1 = 'sbe37_coeff_ta1'
    TA2 = 'sbe37_coeff_ta2'
    TA3 = 'sbe37_coeff_ta3'
    CCALDATE = 'calibration_date_conductivity'
    G = 'sbe37_coeff_g'
    H = 'sbe37_coeff_h'
    I = 'sbe37_coeff_i'
    J = 'sbe37_coeff_j'
    CPCOR = 'sbe37_coeff_cpcor'
    CTCOR = 'sbe37_coeff_ctcor'
    WBOTC = 'sbe37_coeff_wbotc'
    PCALDATE = 'calibration_date_pressure'
    PSN = 'sbe37_coeff_serial_number'
    PRANGE = 'sbe37_coeff_pressure_range'
    PA0 = 'sbe37_coeff_pa0'
    PA1 = 'sbe37_coeff_pa1'
    PA2 = 'sbe37_coeff_pa2'
    PTCA0 = 'sbe37_coeff_ptca0'
    PTCA1 = 'sbe37_coeff_ptca1'
    PTCA2 = 'sbe37_coeff_ptca2'
    PTCSB0 = 'sbe37_coeff_ptcsb0'
    PTCSB1 = 'sbe37_coeff_ptcsb1'
    PTCSB2 = 'sbe37_coeff_ptcsb2'
    POFFSET = 'sbe37_coeff_poffset'
    RTC = 'sbe37_coeff_rtc'
    RTCA0 = 'sbe37_coeff_rtca0'
    RTCA1 = 'sbe37_coeff_rtca1'
    RTCA2 = 'sbe37_coeff_rtca2'

 
class SBE37DeviceCalibrationParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def _string_to_date(datestr, fmt):
        """
        Extract a date tuple from an sbe37 date string.
        @param str a string containing date information in sbe37 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """

        if not isinstance(datestr, str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr, fmt)
            date = (date_time[2],date_time[1],date_time[0])

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))

        return date



    def _build_parsed_values(self):
        """
        Take something in the dc format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        log.debug("in SBE37DeviceCalibrationParticle._build_parsed_values")
        single_var_matchers  = {
            SBE37DeviceCalibrationParticleKey.TCALDATE:  (
                re.compile(r'temperature:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : self._string_to_date(match.group(1), '%d-%b-%y')
                ),
            SBE37DeviceCalibrationParticleKey.TA0:  (
                re.compile(r'\s+TA0 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.TA1:  (
                re.compile(r'\s+TA1 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.TA2:  (
                re.compile(r'\s+TA2 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.TA3:  (
                re.compile(r'\s+TA3 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.CCALDATE:  (
                re.compile(r'conductivity:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : self._string_to_date(match.group(1), '%d-%b-%y')
                ),     
            SBE37DeviceCalibrationParticleKey.G:  (
                re.compile(r'\s+G = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.H:  (
                re.compile(r'\s+H = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.I:  (
                re.compile(r'\s+I = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.J:  (
                re.compile(r'\s+J = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.CPCOR:  (
                re.compile(r'\s+CPCOR = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.CTCOR:  (
                re.compile(r'\s+CTCOR = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.WBOTC:  (
                re.compile(r'\s+WBOTC = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PCALDATE:  (
                re.compile(r'pressure S/N (\d+), range = ([\d\.]+) psia:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : self._string_to_date(match.group(3), '%d-%b-%y')
                ),
            SBE37DeviceCalibrationParticleKey.PRANGE:  (
                re.compile(r'pressure S/N (\d+), range = ([\d\.]+) psia:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : float(match.group(2))
                ),
            SBE37DeviceCalibrationParticleKey.PSN:  (
                re.compile(r'pressure S/N (\d+), range = ([\d\.]+) psia:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : int(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PA0:  (
                re.compile(r'\s+PA0 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PA1:  (
                re.compile(r'\s+PA1 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PA2:  (
                re.compile(r'\s+PA2 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PTCA0:  (
                re.compile(r'\s+PTCA0 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PTCA1:  (
                re.compile(r'\s+PTCA1 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PTCA2:  (
                re.compile(r'\s+PTCA2 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PTCSB0:  (
                re.compile(r'\s+PTCSB0 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),   
            SBE37DeviceCalibrationParticleKey.PTCSB1:  (
                re.compile(r'\s+PTCSB1 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.PTCSB2:  (
                re.compile(r'\s+PTCSB2 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.POFFSET:  (
                re.compile(r'\s+POFFSET = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.RTC:  (
                re.compile(r'rtc:\s+(\d+-[a-zA-Z]+-\d+)'),
                lambda match : self._string_to_date(match.group(1), '%d-%b-%y')
                ),
            SBE37DeviceCalibrationParticleKey.RTCA0:  (
                re.compile(r'\s+RTCA0 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.RTCA1:  (
                re.compile(r'\s+RTCA1 = (-?[\d\.e\-\+]+)'),
                lambda match : float(match.group(1))
                ),
            SBE37DeviceCalibrationParticleKey.RTCA2:  (
                re.compile(r'\s+RTCA2 = (-?[\d\.e\-\+]+)'   ),
                lambda match : float(match.group(1))
                )
        }


        result = [] # Final storage for particle
        vals = {}   # intermediate storage for particle values so they can be set to null first.

        for (key, (matcher, l_func)) in single_var_matchers.iteritems():
            vals[key] = None

        for line in self.raw_data.split(NEWLINE):
            for (key, (matcher, l_func)) in single_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    vals[key] = l_func(match)

        for (key, val) in vals.iteritems():
            result.append({DataParticleKey.VALUE_ID: key, DataParticleKey.VALUE: val})

        return result

class SBE37DeviceStatusParticleKey(BaseEnum):
    # DS
    SERIAL_NUMBER = "sbe37_serial_number"
    DATE_TIME = "sbe37_date_time"
    LOGGING = "sbe37_logging" 
    SAMPLE_INTERVAL = "sbe37_sample_interval" 
    SAMPLE_NUMBER = "sbe37_sample_number"
    MEMORY_FREE = "sbe37_memory_free"
    TX_REALTIME = "sbe37_tx_realtime"
    OUTPUT_SALINITY = "sbe37_output_salinity"
    OUTPUT_SOUND_VELOCITY = "sbe37_output_sound_velocity"
    STORE_TIME = "sbe37_store_time"
    NUMBER_OF_SAMPLES_TO_AVERAGE = "sbe37_number_of_samples_to_average"
    REFERENCE_PRESSURE = "sbe37_reference_pressure"
    SERIAL_SYNC_MODE = "sbe37_serial_sync_mode"
    SERIAL_SYNC_WAIT = "sbe37_serial_sync_wait"
    INTERNAL_PUMP = "sbe37_internal_pump_installed"
    TEMPERATURE = "sbe37_temperature"
#    LOW_BATTERY_WARNING = "sbe37_low_battery_warning"
    
class SBE37DeviceStatusParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS
    
    

    @staticmethod
    def _string_to_ntp_date_time(datestr, fmt):
        """
        Extract a date tuple from an sbe37 date string.
        @param str a string containing date information in sbe37 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """

        if not isinstance(datestr, str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr, fmt)
            timestamp = ntplib.system_to_ntp_time(time.mktime(date_time))

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))

        return timestamp


    def _build_parsed_values(self):
        """
        Take something in the dc format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        log.debug("in SBE37DeviceStatusParticle._build_parsed_values")
        
        single_var_matchers  = {
            SBE37DeviceStatusParticleKey.SERIAL_NUMBER:  (
                re.compile(r'SBE37-SMP V 2.6 SERIAL NO. (\d+)   (\d\d [a-zA-Z]+ \d\d\d\d\s+[ \d]+:\d\d:\d\d)'),
                lambda match : int(match.group(1))
                ),
            SBE37DeviceStatusParticleKey.DATE_TIME:  (
                re.compile(r'SBE37-SMP V 2.6 SERIAL NO. (\d+)   (\d\d [a-zA-Z]+ \d\d\d\d\s+[ \d]+:\d\d:\d\d)'),
                lambda match : float(self._string_to_ntp_date_time(match.group(2), "%d %b %Y %H:%M:%S"))
                ),                
            SBE37DeviceStatusParticleKey.LOGGING:  (
                re.compile(r'(logging data)'),
                lambda match : True if (match) else False,
                ),
            SBE37DeviceStatusParticleKey.SAMPLE_INTERVAL:  (
                re.compile(r'sample interval = (\d+) seconds'),
                lambda match : int(match.group(1))
                ),          
            SBE37DeviceStatusParticleKey.SAMPLE_NUMBER:  (
                re.compile(r'samplenumber = (\d+), free = (\d+)'),
                lambda match : int(match.group(1))
                ),
            SBE37DeviceStatusParticleKey.MEMORY_FREE:  (
                re.compile(r'samplenumber = (\d+), free = (\d+)'),
                lambda match : int(match.group(2))
                ),            
            SBE37DeviceStatusParticleKey.TX_REALTIME:  (
                re.compile(r'do not transmit real-time data'),
                lambda match : False if (match) else True,
                ),  
            SBE37DeviceStatusParticleKey.OUTPUT_SALINITY:  (
                re.compile(r'do not output salinity with each sample'),
                lambda match : False if (match) else True,
                ),             
            SBE37DeviceStatusParticleKey.OUTPUT_SOUND_VELOCITY:  (
                re.compile(r'do not output sound velocity with each sample'),
                lambda match : False if (match) else True,
                ),             
            SBE37DeviceStatusParticleKey.STORE_TIME:  (
                re.compile(r'do not store time with each sample'),
                lambda match : False if (match) else True,
                ),       
            SBE37DeviceStatusParticleKey.NUMBER_OF_SAMPLES_TO_AVERAGE:  (
                re.compile(r'number of samples to average = (\d+)'),
                lambda match : int(match.group(1))
                ),         
            SBE37DeviceStatusParticleKey.REFERENCE_PRESSURE:  (
                re.compile(r'reference pressure = ([\d\.]+) db'),
                lambda match : float(match.group(1))
                ),         
            SBE37DeviceStatusParticleKey.SERIAL_SYNC_MODE:  (
                re.compile(r'serial sync mode disabled'),
                lambda match : False if (match) else True,
                ),
            SBE37DeviceStatusParticleKey.SERIAL_SYNC_WAIT:  (
                re.compile(r'wait time after serial sync sampling = (\d+) seconds'),
                lambda match : int(match.group(1))
                ),     
            SBE37DeviceStatusParticleKey.INTERNAL_PUMP:  (
                re.compile(r'internal pump is installed'),
                lambda match : True if (match) else False,
                ),
            SBE37DeviceStatusParticleKey.TEMPERATURE:  (
                re.compile(r'temperature = ([\d\.\-]+) deg C'),
                lambda match : float(match.group(1))
                ),
  # Move to engineering?
  #          SBE37DeviceStatusParticleKey.LOW_BATTERY_WARNING:  (
  #              re.compile(r'WARNING: LOW BATTERY VOLTAGE!!'),
  #              lambda match : True if (match.group(1)=='WARNING: LOW BATTERY VOLTAGE!!') else False,
  #              )
        }


        result = [] # Final storage for particle
        vals = {}   # intermediate storage for particle values so they can be set to null first.

        for (key, (matcher, l_func)) in single_var_matchers.iteritems():
            vals[key] = None

        for line in self.raw_data.split(NEWLINE):
            for (key, (matcher, l_func)) in single_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    vals[key] = l_func(match)

        for (key, val) in vals.iteritems():
            result.append({DataParticleKey.VALUE_ID: key, DataParticleKey.VALUE: val})

        return result
    


##
## AFTER ADDITION
##

###############################################################################
# Seabird Electronics 37-SMP MicroCAT protocol.
###############################################################################

class SBE37Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for SBE37 driver.
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE37Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE37 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build SBE37 protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(SBE37ProtocolState, SBE37ProtocolEvent,
                            SBE37ProtocolEvent.ENTER, SBE37ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(SBE37ProtocolState.UNKNOWN, SBE37ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(SBE37ProtocolState.UNKNOWN, SBE37ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(SBE37ProtocolState.UNKNOWN, SBE37ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        
        
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.ACQUIRE_STATUS,         self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(SBE37ProtocolState.COMMAND, SBE37ProtocolEvent.ACQUIRE_CONFIGURATION,  self._handler_command_acquire_configuration)
        
        
        self._protocol_fsm.add_handler(SBE37ProtocolState.AUTOSAMPLE, SBE37ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(SBE37ProtocolState.AUTOSAMPLE, SBE37ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(SBE37ProtocolState.AUTOSAMPLE, SBE37ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(SBE37ProtocolState.AUTOSAMPLE, SBE37ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(SBE37ProtocolState.TEST, SBE37ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(SBE37ProtocolState.TEST, SBE37ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(SBE37ProtocolState.TEST, SBE37ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(SBE37ProtocolState.TEST, SBE37ProtocolEvent.GET, self._handler_command_autosample_test_get)

        self._protocol_fsm.add_handler(SBE37ProtocolState.DIRECT_ACCESS, SBE37ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(SBE37ProtocolState.DIRECT_ACCESS, SBE37ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(SBE37ProtocolState.DIRECT_ACCESS, SBE37ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(SBE37ProtocolState.DIRECT_ACCESS, SBE37ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_driver_dict()
        self._build_command_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.DISPLAY_STATUS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_CALIBRATION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TAKE_SAMPLE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_LOGGING, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.STOP_LOGGING, self._build_simple_command)
        self._add_build_handler('tc', self._build_simple_command)
        self._add_build_handler('tt', self._build_simple_command)
        self._add_build_handler('tp', self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SET, self._build_set_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.DISPLAY_STATUS, self._parse_dsdc_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_CALIBRATION, self._parse_dsdc_response)
        self._add_response_handler(InstrumentCmds.TAKE_SAMPLE, self._parse_ts_response)
        self._add_response_handler(InstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler('tc', self._parse_test_response)
        self._add_response_handler('tt', self._parse_test_response)
        self._add_response_handler('tp', self._parse_test_response)

       # Add sample handlers.


        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(SBE37ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(self.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.  The chunks are all the same type.
        """
        sieve_matchers = [SAMPLE_PATTERN_MATCHER,
                          STATUS_DATA_REGEX_MATCHER,
                          CALIBRATION_DATA_REGEX_MATCHER]

        return_list = []

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list
    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if SBE37Capability.has(x)]
        return events_out

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (SBE37ProtocolState.COMMAND or
        SBE37State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        next_state = None
        result = None

        current_state = self._protocol_fsm.get_current_state()
        
        # Driver can only be started in streaming, command or unknown.
        if current_state == SBE37ProtocolState.AUTOSAMPLE:
            result = ResourceAgentState.STREAMING
        
        elif current_state == SBE37ProtocolState.COMMAND:
            result = ResourceAgentState.IDLE
        
        elif current_state == SBE37ProtocolState.UNKNOWN:

            # Wakeup the device with timeout if passed.
            timeout = kwargs.get('timeout', SBE37_TIMEOUT)
            prompt = self._wakeup(timeout)
            prompt = self._wakeup(timeout)

            # Set the state to change.
            # Raise if the prompt returned does not match command or autosample.
            if prompt.strip() == SBE37Prompt.COMMAND:
                next_state = SBE37ProtocolState.COMMAND
                result = ResourceAgentState.IDLE
            elif prompt.strip() == SBE37Prompt.AUTOSAMPLE:
                next_state = SBE37ProtocolState.AUTOSAMPLE
                result = ResourceAgentState.STREAMING
            else:
                raise InstrumentStateException('Unknown state.')

        return (next_state, result)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:

            for (key, val) in params.iteritems():
                result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
            self._update_params()

        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE37.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(InstrumentCmds.TAKE_SAMPLE, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # Assure the device is transmitting.
        if not self._param_dict.get(SBE37Parameter.TXREALTIME):
            self._do_cmd_resp(InstrumentCmds.SET, SBE37Parameter.TXREALTIME, True, **kwargs)

        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(InstrumentCmds.START_LOGGING, *args, **kwargs)

        next_state = SBE37ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (SBE37ProtocolState.TEST, None).
        """
        next_state = None
        result = None

        next_state = SBE37ProtocolState.TEST
        next_agent_state = ResourceAgentState.TEST

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = SBE37ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', SBE37_TIMEOUT)
        tries = kwargs.get('tries',5)
        notries = 0
        try:
            self._wakeup_until(timeout, SBE37Prompt.AUTOSAMPLE)
        
        except InstrumentTimeoutException:
            notries = notries + 1
            if notries >=tries:
                raise

        # Issue the stop command.
        self._do_cmd_resp(InstrumentCmds.STOP_LOGGING, *args, **kwargs)

        # Prompt device until command prompt is seen.
        self._wakeup_until(timeout, SBE37Prompt.COMMAND)

        next_state = SBE37ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND
        
        return (next_state, (next_agent_state, result))

    ########################################################################
    # Common handlers.
    ########################################################################

    def _handler_command_autosample_test_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        return self._handler_get(*args, **kwargs)

    ########################################################################
    # Test handlers.
    ########################################################################

    def _handler_test_enter(self, *args, **kwargs):
        """
        Enter test state. Setup the secondary call to run the tests.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Forward the test event again to run the test handler and
        # switch back to command mode afterward.
        Timer(1, lambda: self._protocol_fsm.on_event(SBE37ProtocolEvent.RUN_TEST)).start()

    def _handler_test_exit(self, *args, **kwargs):
        """
        Exit test state.
        """
        pass

    def _handler_test_run_tests(self, *args, **kwargs):
        """
        Run test routines and validate results.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        tc_pass = False
        tt_pass = False
        tp_pass = False
        tc_result = None
        tt_result = None
        tp_result = None

        test_result = {}

        try:
            tc_pass, tc_result = self._do_cmd_resp('tc', timeout=200)
            tt_pass, tt_result = self._do_cmd_resp('tt', timeout=200)
            tp_pass, tp_result = self._do_cmd_resp('tp', timeout=200)

        except Exception as e:
            test_result['exception'] = e
            test_result['message'] = 'Error running instrument tests.'

        finally:
            test_result['cond_test'] = 'Passed' if tc_pass else 'Failed'
            test_result['cond_data'] = tc_result
            test_result['temp_test'] = 'Passed' if tt_pass else 'Failed'
            test_result['temp_data'] = tt_result
            test_result['pres_test'] = 'Passed' if tp_pass else 'Failed'
            test_result['pres_data'] = tp_result
            test_result['success'] = 'Passed' if (tc_pass and tt_pass and tp_pass) else 'Failed'
            test_result['desc'] = 'SBE37 self-test result'
            test_result['cmd'] = DriverEvent.TEST

        self._driver_event(DriverAsyncEvent.RESULT, test_result)
        self._driver_event(DriverAsyncEvent.AGENT_EVENT, ResourceAgentEvent.DONE)
        #TODO send event to switch agent state.
        next_state = SBE37ProtocolState.COMMAND

        return (next_state, result)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None
        
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None
 
        next_state = SBE37ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))


    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        result = self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_configuration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        result = self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION, *args, **kwargs)

        return (next_state, (next_agent_state, result))


    ########################################################################
    # Private helpers.
    ########################################################################

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the SBE37 device.
        """
        self._connection.send(NEWLINE)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', SBE37_TIMEOUT)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS,timeout=timeout)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION,timeout=timeout)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic SBE37 commands.
        @param cmd the simple sbe37 command to format.
        @retval The command to be sent to the device.
        """
        return cmd+NEWLINE

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE

        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        if prompt.strip() != SBE37Prompt.COMMAND:
            raise InstrumentProtocolException('Set command not recognized: %s' % response)

    def _parse_dsdc_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt.strip() != SBE37Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            self._param_dict.update(line)

    def _parse_ts_response(self, response, prompt):
        """
        Response handler for ts command.
        @param response command response string.
        @param prompt prompt following command response.
        @retval sample dictionary containig c, t, d values.
        @throws InstrumentProtocolException if ts command misunderstood.
        @throws InstrumentSampleException if response did not contain a sample
        """

        if prompt.strip() != SBE37Prompt.COMMAND:
            raise InstrumentProtocolException('ts command not recognized: %s', response)

        # don't know why we are returning a particle here
        #sample = None
        #for line in response.split(NEWLINE):
        #    sample = self._extract_sample(SBE37DataParticle, SAMPLE_PATTERN_MATCHER, line, None, False)
        #    if sample:
        #        break
        #
        #if not sample:
        #    raise SampleException('Response did not contain sample: %s' % repr(response))
        #
        # return sample

        return response

    def _parse_test_response(self, response, prompt):
        """
        Do minimal checking of test outputs.
        @param response command response string.
        @param promnpt prompt following command response.
        @retval tuple of pass/fail boolean followed by response
        """

        success = False
        lines = response.split()
        if len(lines)>2:
            data = lines[1:-1]
            bad_count = 0
            for item in data:
                try:
                    float(item)

                except ValueError:
                    bad_count += 1

            if bad_count == 0:
                success = True

        return (success, response)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        # need to verify it works correctly.
        #if self.get_current_state() == SBE37ProtocolState.AUTOSAMPLE:
        #    self._extract_sample(SBE37DataParticle, SAMPLE_PATTERN_MATCHER, chunk)
        
        result = self._extract_sample(SBE37DataParticle, SAMPLE_PATTERN_MATCHER, chunk, timestamp)
        result = self._extract_sample(SBE37DeviceStatusParticle, STATUS_DATA_REGEX_MATCHER, chunk, timestamp)
        result = self._extract_sample(SBE37DeviceCalibrationParticle, CALIBRATION_DATA_REGEX_MATCHER, chunk, timestamp)

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(SBE37Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(SBE37Capability.TEST, display_name="test instrument")
        self._cmd_dict.add(SBE37Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(SBE37Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(SBE37Capability.ACQUIRE_CONFIGURATION, display_name="get configuration data")
        self._cmd_dict.add(SBE37Capability.ACQUIRE_SAMPLE, display_name="acquire sample")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE37 parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict.add(SBE37Parameter.OUTPUTSAL,
                             r'(do not )?output salinity with each sample',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE37Parameter.OUTPUTSV,
                             r'(do not )?output sound velocity with each sample',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE37Parameter.NAVG,
                             r'number of samples to average = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             direct_access=True)
        self._param_dict.add(SBE37Parameter.SAMPLENUM,
                             r'samplenumber = (\d+), free = \d+',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(SBE37Parameter.INTERVAL,
                             r'sample interval = (\d+) seconds',
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             default_value=1,
                             startup_param=True)
        self._param_dict.add(SBE37Parameter.STORETIME,
                             r'(do not )?store time with each sample',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE37Parameter.TXREALTIME,
                             r'(do not )?transmit real-time data',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE37Parameter.SYNCMODE,
                             r'serial sync mode (enabled|disabled)',
                             lambda match : False if (match.group(1)=='disabled') else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE37Parameter.SYNCWAIT,
                             r'wait time after serial sync sampling = (\d+) seconds',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(SBE37Parameter.TCALDATE,
                             r'temperature: +((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE37Parameter.TA0,
                             r' +TA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.TA1,
                             r' +TA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.TA2,
                             r' +TA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.TA3,
                             r' +TA3 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CCALDATE,
                             r'conductivity: +((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE37Parameter.CG,
                             r' +G = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CH,
                             r' +H = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CI,
                             r' +I = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CJ,
                             r' +J = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.WBOTC,
                             r' +WBOTC = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CTCOR,
                             r' +CTCOR = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.CPCOR,
                             r' +CPCOR = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PCALDATE,
                             r'pressure .+ ((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE37Parameter.PA0,
                             r' +PA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PA1,
                             r' +PA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PA2,
                             r' +PA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCA0,
                             r' +PTCA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCA1,
                             r' +PTCA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCA2,
                             r' +PTCA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCB0,
                             r' +PTCSB0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCB1,
                             r' +PTCSB1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.PTCB2,
                             r' +PTCSB2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.POFFSET,
                             r' +POFFSET = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.RCALDATE,
                             r'rtc: +((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE37Parameter.RTCA0,
                             r' +RTCA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.RTCA1,
                             r' +RTCA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE37Parameter.RTCA2,
                             r' +RTCA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)


    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe37 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not a bool.
        """

        if not isinstance(v,bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        if v:
            return 'y'
        else:
            return 'n'

    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for sbe37 set operations.
        @param v An int val.
        @retval an int string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not an int.
        """

        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe37 set operations.
        @param v A float val.
        @retval a float string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe37 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe37 set operations.
        @throws InstrumentParameterException if date tuple is not valid.
        """

        if not isinstance(v,(list,tuple)):
            raise InstrumentParameterException('Value %s is not a list, tuple.' % str(v))

        if not len(v)==3:
            raise InstrumentParameterException('Value %s is not length 3.' % str(v))

        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep',
                  'Oct','Nov','Dec']
        day = v[0]
        month = v[1]
        year = v[2]

        if len(str(year)) > 2:
            year = int(str(year)[-2:])

        if not isinstance(day,int) or day < 1 or day > 31:
            raise InstrumentParameterException('Value %s is not a day of month.' % str(day))

        if not isinstance(month,int) or month < 1 or month > 12:
            raise InstrumentParameterException('Value %s is not a month.' % str(month))

        if not isinstance(year,int) or year < 0 or year > 99:
            raise InstrumentParameterException('Value %s is not a 0-99 year.' % str(year))

        return '%02i-%s-%02i' % (day,months[month-1],year)

    @staticmethod
    def _string_to_date(datestr,fmt):
        """
        Extract a date tuple from an sbe37 date string.
        @param str a string containing date information in sbe37 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """
        if not isinstance(datestr,str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr,fmt)
            date = (date_time[2],date_time[1],date_time[0])

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))

        return date
