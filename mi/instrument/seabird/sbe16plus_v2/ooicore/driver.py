#!/usr/bin/env python

"""
@package ion.services.mi.sbe16_driver
@file mi/instrument/seabird/sbe16plus_v2/ooicore/driver.py
@author David Everett 
@brief Driver class for sbe16plus V2 CTD instrument.
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import time
import datetime
import re
import string
from threading import Timer

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

#import ion.services.mi.mi_logger
from mi.core.log import get_logger
log = get_logger()

###############################################################################
# Module-wide values
###############################################################################

###############################################################################
# Static enumerations for this class
###############################################################################

class Command(BaseEnum):
        DS  = 'ds'
        DCAL = 'dcal' # DHE dcal replaces dc
        TS = 'ts'
        STARTNOW = 'startnow'
        STOP = 'stop'
        TC = 'tc'
        TT = 'tt'
        TP = 'tp'
        SET = 'set'

class ProtocolState(BaseEnum):
    """
    Protocol states for SBE16. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ProtocolEvent(BaseEnum):
    """
    Protocol events for SBE16. Cherry picked from DriverEvent enum.
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
    FORCE_STATE = DriverEvent.FORCE_STATE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    NOTE: I have GET and SET here because these do not get exported
    to the run_instrument (or any other UI) at this point, and I 
    need their functionality.
    """
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    TEST = DriverEvent.TEST
    DISCOVER = DriverEvent.DISCOVER


# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters for SBE16.
    """
    OUTPUTSAL = 'OUTPUTSAL'
    OUTPUTSV = 'OUTPUTSV'
    NAVG = 'NAVG'
    SAMPLENUM = 'SAMPLENUM'
    INTERVAL = 'INTERVAL'
    TXREALTIME = 'TXREALTIME'
    DATE_TIME = "DateTime"
    LOGGING = "logging"
    
# Device prompts.
class Prompt(BaseEnum):
    """
    SBE16 io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '?cmd S>'
    #AUTOSAMPLE = 'S>\r\n'
    AUTOSAMPLE = 'S>'
    EXECUTED = '<Executed/>'

# SBE16 newline.
NEWLINE = '\r\n'

# SBE16 default timeout.
SBE16_TIMEOUT = 10
                
SAMPLE_PATTERN = r'#? *(-?\d+\.\d+), *(-?\d+\.\d+), *(-?\d+\.\d+)'     # T, C, D/P
SAMPLE_PATTERN += r',? *(-?\d+\.\d+)?'                                  # Salinity
SAMPLE_PATTERN += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
SAMPLE_PATTERN += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'    
SAMPLE_PATTERN += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'
SAMPLE_REGEX = re.compile(SAMPLE_PATTERN)

# pattern for the first line of the 'ds' command
STATUS_PATTERN =  r'SBE 16plus V *(\d+.\d+) *SERIAL NO. *(\d+) *(\d+ *[a-zA-Z]+ *\d+ *\d+:\d+:\d+) *\r\n'
STATUS_PATTERN += r'vbatt = (\d+.\d+), *vlith *= *(\d+.\d+), *ioper *= *(\d+.\d+ *[a-zA-Z]+), *ipump *= *(\d+.\d+ *[a-zA-Z]+), *\r\n'
STATUS_PATTERN += r'status *= *(\w+ +\w+) *\r\n'
STATUS_PATTERN += r'samples *= *(\d+), free *= *(\d+) *\r\n' 
STATUS_PATTERN += r'sample interval *= *(\d+ *\w+), *number of measurements per sample *= *(\d+) *\r\n' 
STATUS_PATTERN += r'pump *= *(.*) *, *delay before sampling *= *(\d+.\d+ *\w+) *\r\n'  
STATUS_PATTERN += r'transmit real-time *= *(\w+) *\r\n'  
STATUS_PATTERN += r'battery cutoff *= *(\d+.\d+ \w+) *\r\n' 
STATUS_PATTERN += r'pressure sensor *= *(.+) *, range *= *(\d+.\d+) *\r\n' 
STATUS_PATTERN += r'SBE 38 *= *(.+), *SBE 50 *= *(.+), *WETLABS *= *(.+), *OPTODE *= *(.+), *Gas Tension Device *= *(\w+) *\r\n' 
STATUS_PATTERN += r'Ext Volt 0 *= *(\w+), Ext Volt 1 *= *(\w+) *\r\n'  
STATUS_PATTERN += r'Ext Volt 2 *= *(\w+), Ext Volt 3 *= *(\w+) *\r\n'  
STATUS_PATTERN += r'Ext Volt 4 *= *(\w+), Ext Volt 5 *= *(\w+) *\r\n'  
STATUS_PATTERN += r'echo characters = (\w+) *\r\n'  
STATUS_PATTERN += r'output format = ([ a-zA-Z]+) *\r\n'  
STATUS_PATTERN += r'output salinity = ([ a-zA-Z]+) *, output sound velocity = ([ a-zA-Z]+) *\r\n'  
STATUS_PATTERN += r'serial sync mode *([ a-zA-Z]+) *'  
STATUS_REGEX = re.compile(STATUS_PATTERN)

# Packet config for SBE37 data granules.
STREAM_NAME_PARSED = DataParticleValue.PARSED
STREAM_NAME_RAW = DataParticleValue.RAW
#PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]

# TODO: Where are the param dict definitions kept and related to driver versions?
PACKET_CONFIG = {
    STREAM_NAME_PARSED : 'ctd_parsed_param_dict',
    STREAM_NAME_RAW : 'ctd_raw_param_dict'
}


###############################################################################
# Seabird Electronics 16plus V2 MicroCAT Driver.
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass for SBE16 driver.
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

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()        

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE16Protocol(Prompt, NEWLINE, self._driver_event)


class SBE16DataParticleKey(BaseEnum):
    TEMP = "temp"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    SALINITY = "salinity"

class SBE16DataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            temperature = float(match.group(1))
            conductivity = float(match.group(2))
            pressure = float(match.group(3))
            salinity = float(match.group(4))
        except ValueError:
            raise SampleException("ValueError while decoding floats in data: [%s]" %
                                  self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: SBE16DataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.PRESSURE,
                    DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.SALINITY,
                    DataParticleKey.VALUE: salinity}]
        
        return result


class SBE16StatusParticleKey(BaseEnum):
    FIRMWARE_VERSION = "firmware_version"
    SERIAL_NUMBER = "serial_number"
    DATE_TIME = "date_time"
    VBATT = "vbatt"
    VLITH = "vlith"
    IOPER = "ioper"
    IPUMP = "ipump"
    STATUS = "status"
    SAMPLES = "samples"
    FREE = "free"
    SAMPLE_INTERVAL = "sample_interval"
    MEASUREMENTS_PER_SAMPLE = "measurements_per_sample"
    RUN_PUMP_DURING_SAMPLE = "run_pump_during_sample"
    DELAY_BEFORE_SAMPLING = "delay_before_sampling"
    TX_REAL_TIME = "tx_real_time"
    BATTERY_CUTOFF = "battery_cutoff"
    PRESSURE_SENSOR = "pressure_sensor"
    RANGE = "range"
    SBE38 = "sbe38"
    SBE50 = "sbe50"
    WETLABS = "wetlabs"
    OPTODE = "optode"
    GAS_TENSION_DEVICE = "gas_tension_device"
    EXT_VOLT_0 = "ext_volt_0"
    EXT_VOLT_1 = "ext_volt_1"
    EXT_VOLT_2 = "ext_volt_2"
    EXT_VOLT_3 = "ext_volt_3"
    EXT_VOLT_4 = "ext_volt_4"
    EXT_VOLT_5 = "ext_volt_5"
    ECHO_CHARACTERS = "echo_characters"
    OUTPUT_FORMAT = "output_format"
    OUTPUT_SALINITY = "output_salinity"
    OUTPUT_SOUND_VELOCITY = "output_sound_velocity"
    SERIAL_SYNC_MODE = "serial_sync_mode"

class SBE16StatusParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = STATUS_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" %
                                  self.raw_data)
            
        try:
            firmware_version = str(match.group(1))
            serial_number = str(match.group(2))
            date_time = str(match.group(3))
            vbatt = str(match.group(4))
            vlith = str(match.group(5))
            ioper = str(match.group(6))
            ipump = str(match.group(7))
            status = str(match.group(8))
            samples = str(match.group(9))
            free = str(match.group(10))
            sample_interval = str(match.group(11))
            measurements_per_sample = str(match.group(12))
            run_pump_during_sample = str(match.group(13))
            delay_before_sampling = str(match.group(14))
            tx_real_time = str(match.group(15))
            battery_cutoff = str(match.group(16))
            pressure_sensor = str(match.group(17))
            range = str(match.group(18))
            sbe38 = str(match.group(19))
            sbe50 = str(match.group(20))
            wetlabs = str(match.group(21))
            optode = str(match.group(22))
            gas_tension_device = str(match.group(23))
            ext_volt_0 = str(match.group(24))
            ext_volt_1 = str(match.group(25))
            ext_volt_2 = str(match.group(26))
            ext_volt_3 = str(match.group(27))
            ext_volt_4 = str(match.group(28))
            ext_volt_5 = str(match.group(29))
            echo_characters = str(match.group(30))
            output_format = str(match.group(31))
            output_salinity = str(match.group(32))
            output_sound_velocity = str(match.group(33))
            serial_sync_mode = str(match.group(34))
            
        except ValueError:
            raise SampleException("ValueError while decoding status: [%s]" %
                                  self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: SBE16StatusParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.DATE_TIME,
                    DataParticleKey.VALUE: date_time},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.VBATT,
                    DataParticleKey.VALUE: vbatt},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.VLITH,
                    DataParticleKey.VALUE: vlith},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.IOPER,
                    DataParticleKey.VALUE: ioper},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.IPUMP,
                    DataParticleKey.VALUE: ipump},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.STATUS,
                    DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SAMPLES,
                    DataParticleKey.VALUE: samples},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.FREE,
                    DataParticleKey.VALUE: free},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SAMPLE_INTERVAL,
                    DataParticleKey.VALUE: sample_interval},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE,
                    DataParticleKey.VALUE: measurements_per_sample},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.RUN_PUMP_DURING_SAMPLE,
                    DataParticleKey.VALUE: run_pump_during_sample},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING,
                    DataParticleKey.VALUE: delay_before_sampling},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.TX_REAL_TIME,
                    DataParticleKey.VALUE: tx_real_time},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.BATTERY_CUTOFF,
                    DataParticleKey.VALUE: battery_cutoff},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.PRESSURE_SENSOR,
                    DataParticleKey.VALUE: pressure_sensor},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.RANGE,
                    DataParticleKey.VALUE: range},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SBE38,
                    DataParticleKey.VALUE: sbe38},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SBE50,
                    DataParticleKey.VALUE: sbe50},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.WETLABS,
                    DataParticleKey.VALUE: wetlabs},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.OPTODE,
                    DataParticleKey.VALUE: optode},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.GAS_TENSION_DEVICE,
                    DataParticleKey.VALUE: gas_tension_device},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_0,
                    DataParticleKey.VALUE: ext_volt_0},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_1,
                    DataParticleKey.VALUE: ext_volt_1},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_2,
                    DataParticleKey.VALUE: ext_volt_2},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_3,
                    DataParticleKey.VALUE: ext_volt_3},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_4,
                    DataParticleKey.VALUE: ext_volt_4},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.EXT_VOLT_5,
                    DataParticleKey.VALUE: ext_volt_5},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.ECHO_CHARACTERS,
                    DataParticleKey.VALUE: echo_characters},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.OUTPUT_FORMAT,
                    DataParticleKey.VALUE: output_format},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.OUTPUT_SALINITY,
                    DataParticleKey.VALUE: output_salinity},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.OUTPUT_SOUND_VELOCITY,
                    DataParticleKey.VALUE: output_sound_velocity},
                  {DataParticleKey.VALUE_ID: SBE16StatusParticleKey.SERIAL_SYNC_MODE,
                    DataParticleKey.VALUE: serial_sync_mode}]
        
        return result


###############################################################################
# Seabird Electronics 37-SMP MicroCAT protocol.
###############################################################################

class SBE16Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for SBE16 driver.
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE16Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE16 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        
        # Build SBE16 protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE, self._handler_unknown_force_state) 
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(Command.DS, self._build_simple_command)
        # DHE dcal replaces dc
        self._add_build_handler(Command.DCAL, self._build_simple_command)
        self._add_build_handler(Command.TS, self._build_simple_command)
        self._add_build_handler(Command.STARTNOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.TC, self._build_simple_command)
        self._add_build_handler(Command.TT, self._build_simple_command)
        self._add_build_handler(Command.TP, self._build_simple_command)
        self._add_build_handler(Command.SET, self._build_set_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.DS, self._parse_dsdc_response)
        self._add_response_handler(Command.DCAL, self._parse_dcal_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.TC, self._parse_test_response)
        self._add_response_handler(Command.TT, self._parse_test_response)
        self._add_response_handler(Command.TP, self._parse_test_response)

        # State state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        
        self._chunker = StringChunker(self.sieve_function)
        

    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        patterns = []
        matchers = []
        return_list = []

        patterns.append((SAMPLE_PATTERN)) 

        patterns.append((STATUS_PATTERN)) 

        for pattern in patterns:
            matchers.append(re.compile(pattern))

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
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
        @retval (next_state, next_agent_state), (ProtocolState.COMMAND or
        SBE16State.AUTOSAMPLE, next_agent_state) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the device response does not correspond to
        an expected state.
        """
        
        current_state = self._protocol_fsm.get_current_state()
        
        next_state = None
        next_agent_state = None

        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        prompt = self._wakeup(timeout)
        prompt = self._wakeup(timeout)

        """
        get the configuration parameters; one of the params is the logging 
        parameter, which tells us if we're in AUTOSAMPLE or not.
        """
        self._do_cmd_resp(Command.DS,timeout=timeout)
        self._do_cmd_resp(Command.DCAL,timeout=timeout)
        config = self._param_dict.get_config()

        logging_state = config[Parameter.LOGGING]
        log.debug("SBE16plus_v2 logging state is: %s", str(logging_state))
        if logging_state == True:
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING
        elif logging_state == False:
            """
            Set the time here; might want to move this to somewhere else
            """
            str_utc_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
            self._do_cmd_resp(Command.SET, Parameter.DATE_TIME,
                      str_utc_time, **kwargs)
            log.info("SBE16plus_v2 time set to UTC: %s", str_utc_time) 

            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE
        else:
            errorString = 'Unknown state based on value of configuration parameter LOGGING: ' + str(logging_state)
            log.error(errorString)
            raise InstrumentStateException(errorString)
            
        return (next_state, next_agent_state)

    def _handler_unknown_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing 
        @param state=desired_state Required desired state to transition to.
        @raises InstrumentParameterException if no state parameter.
        """

        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        next_state = state
        result = state
        
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
                result = self._do_cmd_resp(Command.SET, key, val, **kwargs)
            self._update_params()
            
        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).        
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.TS, *args, **kwargs)
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # Assure the device is transmitting.
        if not self._param_dict.get(Parameter.TXREALTIME):
            self._do_cmd_resp(Command.SET, Parameter.TXREALTIME, True, **kwargs)
        
        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(Command.STARTNOW, *args, **kwargs)
                
        next_state = ProtocolState.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (ProtocolState.TEST, None).
        """

        result = None

        next_state = ProtocolState.TEST        
        next_agent_state = ResourceAgentState.TEST

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        prompt = self._wakeup(timeout=timeout)
        
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            error_msg = "Error synchronizing clock; instrument returned: " + prompt
            raise InstrumentProtocolException(error_msg)

        str_utc_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        # Using base class version
        #str_utc_time = self._get_utc_time_at_second_edge()
        self._do_cmd_resp(Command.SET, Parameter.DATE_TIME,
                  str_utc_time, **kwargs)
        log.info("SBE16plus_v2 time set to UTC: %s", str_utc_time) 

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
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        tries = kwargs.get('tries',5)
        notries = 0
        try:
            # DHE: there should really be a tuple of expected prompts
            #self._wakeup_until(timeout, Prompt.AUTOSAMPLE)
            self._wakeup_until(timeout, Prompt.EXECUTED)
        
        except InstrumentTimeoutException:
            notries = notries + 1
            if notries >= tries:
                raise

        # Issue the stop command.
        self._do_cmd_resp(Command.STOP, *args, **kwargs)        
        
        # Prompt device until command prompt is seen.
        # DHE: there should really be a tuple of expected prompts
        #self._wakeup_until(timeout, Prompt.COMMAND)
        self._wakeup_until(timeout, Prompt.EXECUTED)
        
        next_state = ProtocolState.COMMAND
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
        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]
           
        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()
                    
        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.
        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                try:
                    val = self._param_dict.get(key)
                    result[key] = val

                except KeyError:
                    raise InstrumentParameterException(('%s is not a valid parameter.' % key))
            
        return (next_state, result)

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30
        result = self._do_cmd_no_resp('ds', *args, **kwargs)

        return (next_state, (next_agent_state, result))

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
        Timer(1, lambda: self._protocol_fsm.on_event(ProtocolEvent.RUN_TEST)).start()
    
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
        #tp_pass = False
        tc_result = None
        tt_result = None
        #tp_result = None

        test_result = {}

        try:
            tc_pass, tc_result = self._do_cmd_resp(Command.TC, timeout=200)
            tt_pass, tt_result = self._do_cmd_resp(Command.TT, timeout=200)
            tp_pass, tp_result = self._do_cmd_resp(Command.TP, timeout=200)
        
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
            test_result['success'] = 'Passed' if (tc_pass and tt_pass) else 'Failed'
            test_result['desc'] = 'SBE16Plus-V2 self-test result'
            test_result['cmd'] = DriverEvent.TEST
            
        self._driver_event(DriverAsyncEvent.RESULT, test_result)
        self._driver_event(DriverAsyncEvent.AGENT_EVENT, ResourceAgentEvent.DONE)

        next_state = ProtocolState.COMMAND
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
 
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _get_utc_time_at_second_edge(self):
                
        while datetime.datetime.utcnow().microsecond != 0:
            pass

        gmTime = time.gmtime(time.mktime(time.localtime()))
        return time.strftime("%d %b %Y %H:%M:%S", gmTime)
        
    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the SBE16 device.
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
        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        self._do_cmd_resp(Command.DS, timeout=timeout)
        self._do_cmd_resp(Command.DCAL, timeout=timeout)
        
        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        
    def _build_simple_command(self, cmd):
        """
        Build handler for basic SBE16 commands.
        @param cmd the simple sbe16 command to format.
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
            
            if param == 'INTERVAL':
                param = 'sampleinterval'

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
        if prompt not in [Prompt.EXECUTED, Prompt.COMMAND]:
            log.error("Set command encountered error; instrument returned: %s", response) 
            raise InstrumentProtocolException('Set command not recognized: %s' % response)

    def _parse_dsdc_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]: 
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            if 'sample interval' in line:
                for sline in line.split(','):
                    self._param_dict.update(sline.lstrip())
            elif 'output salinity' in line:
                for sline in line.split(','):
                    self._param_dict.update(sline.lstrip())
            else: 
                self._param_dict.update(line)
            
    def _parse_dcal_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            raise InstrumentProtocolException('dcal command not recognized: %s.' % response)
            
        for line in response.split(NEWLINE):
            self._param_dict.update(line)
        
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
                
    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        self._extract_sample(SBE16DataParticle, SAMPLE_REGEX, chunk)
        self._extract_sample(SBE16StatusParticle, STATUS_REGEX, chunk)
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE16 parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.        
        self._param_dict.add(Parameter.OUTPUTSAL,
                             r'output salinity = (no)?',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string,
                             startup_param = True)
        self._param_dict.add(Parameter.OUTPUTSV,
                             r'output sound velocity = (no)?',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(Parameter.NAVG,
                             r'number of measurements per sample = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.SAMPLENUM,
                             r'samples = (\d+), free = \d+',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.INTERVAL,
                             r'sample interval = (\d+) seconds',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TXREALTIME,
                             r'transmit real-time = (yes|no)',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string)
        self._param_dict.add(Parameter.DATE_TIME,
                             r'SBE 16plus V ([\w.]+) +SERIAL NO. (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)', 
                             lambda match : string.upper(match.group(3)),
                             self._string_to_numeric_date_time_string)
        self._param_dict.add(Parameter.LOGGING,
                             r'status = (not )?logging',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string)
                             

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe16 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe16 set operations.
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
        Write an int value to string formatted for sbe16 set operations.
        @param v An int val.
        @retval an int string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value not an int.
        """
        
        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe16 set operations.
        @param v A float val.
        @retval a float string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe16 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe16 set operations.
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
        Extract a date tuple from an sbe16 date string.
        @param str a string containing date information in sbe16 format.
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

    @staticmethod
    def _string_to_numeric_date_time_string(date_time_string):
        """
        convert string from "21 AUG 2012  09:51:55" to numeric "mmddyyyyhhmmss"
        """

        return time.strftime("%m%d%Y%H%M%S", time.strptime(date_time_string, "%d %b %Y %H:%M:%S"))
    
