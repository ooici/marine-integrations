"""
@package mi.instrument.wetlabs.ac_s.ooicore.driver
@file marine-integrations/mi/instrument/wetlabs/ac_s/ooicore/driver.py
@author Lytle Johnson
@brief Driver for the ooicore
Release notes:

initial version
"""

__author__ = 'Lytle Johnson'
__license__ = 'Apache 2.0'

import re
import time
import string
import ntplib

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

from struct import pack

# newline.
NEWLINE = '\n'

# default timeout.
TIMEOUT = 10

SAMPLE_REGEX = pack('4B',0xff,0x00,0xff,0x00)
SAMPLE_REGEX_MATCHER = re.compile(SAMPLE_REGEX)

STATUS_REGEX = r'AC-Spectra(.*?\n)*?(.*?quit\.)'
STATUS_REGEX_MATCHER = re.compile(STATUS_REGEX)

####
#    Driver Constant Definitions
####

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    OPTAA_SAMPLE = 'optaa_sample'
    OPTAA_STATUS = 'optaa_status'
    
class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS  = ProtocolEvent.ACQUIRE_STATUS
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
 
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """


def brute_force_search(p,a):
    """
    from Sedgewick, Algorithms, pseudocode translated into python.
    Modified for start at zero
    instead of one and to return list of all matches.
    @p = pattern to be searched for
    @a = string to be searched
    @i: index into string to be searched
    @M: length of pattern
    @j: index into pattern
    @N: length of string to be searched
    """
    retlist = []
    M = len(p)
    N = len(a)
    i = 0
    j = 0
    while i < N:
        if a[i] == p[j]:
            i += 1
            j += 1
            if j >= M:
                retlist.append(i-M)
                j = 0
                i = i-j+1
        else:
            i = i-j+1
            j = 0
    return retlist
    
###############################################################################
# Data Particles
###############################################################################
class OPTAA_SampleDataParticleKey(BaseEnum):
    RECORD_LENGTH = 'record_length'
    PACKET_TYPE = 'packet_type'
    METER_TYPE = 'meter_type'
    SERIAL_NUMBER = 'serial_number'
    A_REFERENCE_DARK_COUNTS = 'a_reference_dark_counts'
    PRESSURE_COUNTS = 'pressure_counts'
    A_SIGNAL_DARK_COUNTS = 'a_signal_dark_counts'
    EXTERNAL_TEMP_RAW = 'external_temp_raw'
    INTERNAL_TEMP_RAW = 'internal_temp_raw'
    C_REFERENCE_DARK_COUNTS = 'c_reference_dark_counts'
    C_SIGNAL_DARK_COUNTS = 'c_signal_dark_counts'
    ELAPSED_RUN_TIME = 'elapsed_run_time'
    NUM_WAVELENGTHS = 'num_wavelengths'
    C_REFERENCE_COUNTS = 'c_reference_counts'
    A_REFERENCE_COUNTS = 'a_reference_counts'
    C_SIGNAL_COUNTS = 'c_signal_counts'
    A_SIGNAL_COUNTS = 'a_signal_counts'
    CHECKSUM = 'checksum'
    
class OPTAA_SampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.OPTAA_SAMPLE
    
    
    def get_one_byte_value(self,str,index):
        return ord(str[index])

    def get_two_byte_value(self,str,index):
        return ord(str[index])*2**8 + ord(str[index+1])

    def get_three_byte_value(self,str,index):
        return ord(str[index])*2**16 + ord(str[index+1])*2**8 + ord(str[index+2])

    def get_four_byte_value(self,str,index):
        return ord(str[index])*2**24 + ord(str[index+1])*2**16 + ord(str[index+2])*2**8 + ord(str[index+3])
        
        
        
    def _build_parsed_values(self):
        RECORD_LENGTH_INDEX = 4
        PACKET_TYPE_INDEX = 6
        METER_TYPE_INDEX = 8
        SERIAL_NUMBER_INDEX = 9
        A_REFERENCE_DARK_COUNTS_INDEX = 12
        PRESSURE_COUNTS_INDEX = 14
        A_SIGNAL_DARK_COUNTS_INDEX = 16
        EXTERNAL_TEMP_RAW_INDEX = 18
        INTERNAL_TEMP_RAW_INDEX = 20
        C_REFERENCE_DARK_COUNTS_INDEX = 22
        C_SIGNAL_DARK_COUNTS_INDEX = 24
        ELAPSED_RUN_TIME_INDEX = 26
        NUM_WAVELENGTHS_INDEX = 31
        DATA_INDEX = 32
        C_REFERENCE_COUNTS_INDEX = 32
        A_REFERENCE_COUNTS_INDEX = 34
        C_SIGNAL_COUNTS_INDEX = 36
        A_SIGNAL_COUNTS_INDEX = 38
        
        num_wavelengths = None
        record_length = None
        result = []
        
        data_stream = self.raw_data
        
        num_wavelengths = self.get_one_byte_value(data_stream, NUM_WAVELENGTHS_INDEX)
        record_length = self.get_two_byte_value(data_stream, RECORD_LENGTH_INDEX)
        result = [{DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.NUM_WAVELENGTHS,
                   DataParticleKey.VALUE: num_wavelengths},
                  {DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.RECORD_LENGTH,
                  DataParticleKey.VALUE: record_length}]
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.PACKET_TYPE,
                       DataParticleKey.VALUE: self.get_one_byte_value(data_stream, PACKET_TYPE_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.METER_TYPE,
                       DataParticleKey.VALUE: self.get_one_byte_value(data_stream, METER_TYPE_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.SERIAL_NUMBER,
                       DataParticleKey.VALUE: self.get_three_byte_value(data_stream, SERIAL_NUMBER_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.A_REFERENCE_DARK_COUNTS,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, A_REFERENCE_DARK_COUNTS_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.PRESSURE_COUNTS,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, PRESSURE_COUNTS_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.A_SIGNAL_DARK_COUNTS,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, A_SIGNAL_DARK_COUNTS_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.EXTERNAL_TEMP_RAW,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, EXTERNAL_TEMP_RAW_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.INTERNAL_TEMP_RAW,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, INTERNAL_TEMP_RAW_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.C_REFERENCE_DARK_COUNTS,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, C_REFERENCE_DARK_COUNTS_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.C_SIGNAL_DARK_COUNTS,
                       DataParticleKey.VALUE: self.get_two_byte_value(data_stream, C_SIGNAL_DARK_COUNTS_INDEX)})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.ELAPSED_RUN_TIME,
                       DataParticleKey.VALUE: self.get_four_byte_value(data_stream, ELAPSED_RUN_TIME_INDEX)})

        packet_checksum = self.get_two_byte_value(data_stream, record_length)
        checksum = 0
        for i in range(0,record_length):
            checksum += ord(data_stream[i])
        checksum &= 0xffff
        if checksum == packet_checksum:
            result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.CHECKSUM,
                           DataParticleKey.VALUE: packet_checksum})
        else:
            raise SampleException('Checksum mismatch in data packet.')
            
        
        ### No requirement to check checksum at this point, but here's how to do it...
        ### checksum = 0
        ### for i in range(0,record_length): checksum += ord(data_stream[i])

        ### Now build four vectors out of the data
        end_index = record_length
        i = DATA_INDEX
        C_REFERENCE_COUNTS_VECTOR = []
        A_REFERENCE_COUNTS_VECTOR = []
        C_SIGNAL_COUNTS_VECTOR = []
        A_SIGNAL_COUNTS_VECTOR = []
        
        while i < end_index:
            C_REFERENCE_COUNTS_VECTOR.append(ord(data_stream[i])*256+ord(data_stream[i+1]))
            A_REFERENCE_COUNTS_VECTOR.append(ord(data_stream[i+2])*256+ord(data_stream[i+3]))
            C_SIGNAL_COUNTS_VECTOR.append(ord(data_stream[i+4])*256+ord(data_stream[i+5]))
            A_SIGNAL_COUNTS_VECTOR.append(ord(data_stream[i+6])*256+ord(data_stream[i+7]))
            i += 8

        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.C_REFERENCE_COUNTS,
                       DataParticleKey.VALUE: C_REFERENCE_COUNTS_VECTOR})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.A_REFERENCE_COUNTS,
                       DataParticleKey.VALUE: A_REFERENCE_COUNTS_VECTOR})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.C_SIGNAL_COUNTS,
                       DataParticleKey.VALUE: C_SIGNAL_COUNTS_VECTOR})
        result.append({DataParticleKey.VALUE_ID: OPTAA_SampleDataParticleKey.A_SIGNAL_COUNTS,
                       DataParticleKey.VALUE: A_SIGNAL_COUNTS_VECTOR})
        return result
    
    
class OPTAA_StatusDataParticleKey(BaseEnum):
    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_DATE = 'firmware_date'
    PERSISTOR_CF_SERIAL_NUMBER = 'persistor_cf_serial_number'
    PERSISTOR_CF_BIOS_VERSION = 'persistor_cf_bios_version'
    PERSISTOR_CF_PICODOS_VERSION = 'persistor_cf_picodos_version'
    
class OPTAA_StatusDataParticle(DataParticle):
    _data_particle_type = DataParticleType.OPTAA_STATUS
    

    def _build_parsed_values(self):
        result = []
        
        data_stream = self.raw_data
            
        ### This regex searching can be made a lot more specific, but at the expense of
        ### more code. For now, grabbing all three floating point numbers in one sweep is
        ### pretty efficient. Note, however, that if the manufacturer ever changes the 
        ### format of the status display, this code may have to be re-written.
        FLOAT_REGEX = r'\d+\.\d+'
        float_regex_matcher = re.compile(FLOAT_REGEX)
        fp_results = re.findall(float_regex_matcher, data_stream)
        if len(fp_results) == 3:
            version = fp_results[0]
            bios = fp_results[1]
            picodos = fp_results[2]
        else:
            raise SampleException('Unable to find exactly three floating-point numbers in status message.')
            
        
        ### find the date/time string and remove enclosing parens
        DATE_REGEX = r'\([A-Za-z]+\s+\d+\s+\d{4}\s+\d+:\d+:\d+\)'
        date_regex_matcher = re.compile(DATE_REGEX)
        m = re.search(date_regex_matcher, data_stream)
        if m is not None:
                p = m.group()
                date_of_version = p[1:-1]
        else:
                date_of_version = None
        
        PERSISTOR_REGEX = r'Persistor CF2 SN:\d+'
        persistor_regex_matcher = re.compile(PERSISTOR_REGEX)
        persis = re.search(persistor_regex_matcher, data_stream)
        if persis is not None:
                temp = persis.group()
                temp1 = re.search(r'\d{2,10}', temp)
                if temp1 is not None:
                        persistor_sn = temp1.group()
                else:
                        persistor_sn = None
        else:
                persistor_sn = None
        
        result = [{DataParticleKey.VALUE_ID: OPTAA_StatusDataParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: str(version) },
                  {DataParticleKey.VALUE_ID: OPTAA_StatusDataParticleKey.FIRMWARE_DATE,
                  DataParticleKey.VALUE: date_of_version },
                  {DataParticleKey.VALUE_ID: OPTAA_StatusDataParticleKey.PERSISTOR_CF_SERIAL_NUMBER,
                   DataParticleKey.VALUE: int(persistor_sn) },
                  {DataParticleKey.VALUE_ID: OPTAA_StatusDataParticleKey.PERSISTOR_CF_BIOS_VERSION,
                   DataParticleKey.VALUE: str(bios) },
                  {DataParticleKey.VALUE_ID: OPTAA_StatusDataParticleKey.PERSISTOR_CF_PICODOS_VERSION,
                   DataParticleKey.VALUE: str(picodos) } ]
        return result                      

###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.

        # Add response handlers for device commands.

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        CHECKSUM_PLUS_PAD = 3   #three bytes for these items
        
        global brute_force_search
        
        sieve_matchers = [SAMPLE_REGEX_MATCHER,
                          STATUS_REGEX_MATCHER]
        
        pattern = pack('4B',0xff,0x00,0xff,0x00)
        
        return_list = []
        
        for matcher in sieve_matchers:
            if matcher == SAMPLE_REGEX_MATCHER:
                start_pos_list = brute_force_search(pattern, raw_data)
                for start_pos in start_pos_list:
                    if start_pos+5 < len(raw_data):
                        expected_length = CHECKSUM_PLUS_PAD + ord(raw_data[start_pos+4])*256 + ord(raw_data[start_pos+5])
                        if start_pos+expected_length <= len(raw_data):
                            return_list.append((start_pos, start_pos+expected_length))
            elif matcher == STATUS_REGEX_MATCHER:
                for match in re.finditer(matcher,raw_data):
                    return_list.append((match.start(), match.end()))
                    

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if(self._extract_sample(OPTAA_StatusDataParticle, STATUS_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for STATUS")
            return

        if(self._extract_sample(OPTAA_SampleDataParticle, SAMPLE_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for SAMPLE")
            return


    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

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
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """

        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        result = None

        current_state = self._protocol_fsm.get_current_state()
        log.debug("///////////////////// in handler_unknown_discover: current state is ",current_state)
        
        if current_state == ProtocolState.AUTOSAMPLE:
            result = ResourceAgentState.STREAMING

        elif current_state == ProtocolState.COMMAND:
            result = ResourceAgentState.IDLE

        elif current_state == ProtocolState.UNKNOWN:

            # Wakeup the device with timeout if passed.

            delay = 0.5
            log.debug("############## TIMEOUT = " + str(timeout))
            prompt = self._wakeup(timeout=timeout, delay=delay)
            prompt = self._wakeup(timeout)

        logging = self._is_logging(timeout=timeout)

        if logging == True:
            next_state = ProtocolState.AUTOSAMPLE
            result = ResourceAgentState.STREAMING
        elif logging == False:
            next_state = ProtocolState.COMMAND
            result = ResourceAgentState.IDLE
        else:
            raise InstrumentStateException('Unknown state.')

        print "//////////////////// on exit from handler_unknown_discover: next_state is ",next_state
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
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        next_state = None
        result = None


        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

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
