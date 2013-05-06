"""
@package mi.instrument.nortek.vector.ooicore.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/vector/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the ooicore
Release notes:

Driver for vector
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import time
import string
import re
import copy
import base64
#from ordereddict import OrderedDict

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               InstrumentStateException, \
                               SampleException, \
                               ReadOnlyException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterValue
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType

from mi.instrument.nortek.driver import NortekInstrumentDriver
from mi.instrument.nortek.driver import NortekProtocol
from mi.instrument.nortek.driver import NortekProtocolParameterDict
from mi.instrument.nortek.driver import NEWLINE, TIMEOUT, CHECK_SUM_SEED, FAT_LENGTH
from mi.instrument.nortek.driver import USER_CONFIG_LEN, USER_CONFIG_SYNC_BYTES
from mi.instrument.nortek.driver import HEAD_CONFIG_LEN, HEAD_CONFIG_SYNC_BYTES
from mi.instrument.nortek.driver import HW_CONFIG_LEN, HW_CONFIG_SYNC_BYTES

from mi.core.common import InstErrorCode

from mi.core.log import get_logger ; log = get_logger()

VELOCITY_DATA_LEN = 24
VELOCITY_DATA_SYNC_BYTES = '\xa5\x10'
SYSTEM_DATA_LEN = 28
SYSTEM_DATA_SYNC_BYTES = '\xa5\x11\x0e\x00'
VELOCITY_HEADER_DATA_LEN = 42
VELOCITY_HEADER_DATA_SYNC_BYTES = '\xa5\x12\x15\x00'
PROBE_CHECK_SIZE_OFFSET = 2
PROBE_CHECK_SYNC_BYTES = '\xa5\x07'

sample_structures = [[VELOCITY_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                     [SYSTEM_DATA_SYNC_BYTES, SYSTEM_DATA_LEN],
                     [VELOCITY_HEADER_DATA_SYNC_BYTES, VELOCITY_HEADER_DATA_LEN],
                     [PROBE_CHECK_SYNC_BYTES, PROBE_CHECK_SIZE_OFFSET]]

VELOCITY_DATA_PATTERN = r'^%s(.{1})(.{1})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{1})(.{1})(.{1}).{2}' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)
SYSTEM_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2}).{2}' % SYSTEM_DATA_SYNC_BYTES
SYSTEM_DATA_REGEX = re.compile(SYSTEM_DATA_PATTERN, re.DOTALL)
VELOCITY_HEADER_DATA_PATTERN = r'^%s(.{6})(.{2})(.{1})(.{1})(.{1}).{1}(.{1})(.{1})(.{1}).{23}' % VELOCITY_HEADER_DATA_SYNC_BYTES
VELOCITY_HEADER_DATA_REGEX = re.compile(VELOCITY_HEADER_DATA_PATTERN, re.DOTALL)
PROBE_CHECK_DATA_PATTERN = r'^%s' % PROBE_CHECK_SYNC_BYTES
PROBE_CHECK_DATA_REGEX = re.compile(PROBE_CHECK_DATA_PATTERN, re.DOTALL)

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PARSED = 'parsed'
    VELOCITY = 'velocity'
    VELOCITY_HEADER = 'velocity_header'
    PROBE_CHECK = 'probe_check'
    SYSTEM = 'system'
    
            

###############################################################################
# Driver
###############################################################################

class InstrumentDriver(NortekInstrumentDriver):

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)
        

###############################################################################
# Data particles
###############################################################################

class VectorVelocityDataParticleKey(BaseEnum):
    ANALOG_INPUT2 = "analog_input2"
    COUNT = "count"
    PRESSURE = "pressure"
    ANALOG_INPUT1 = "analog_input1"
    VELOCITY_BEAM1 = "velocity_beam1"
    VELOCITY_BEAM2 = "velocity_beam2"
    VELOCITY_BEAM3 = "velocity_beam3"
    AMPLITUDE_BEAM1 = "amplitude_beam1"
    AMPLITUDE_BEAM2 = "amplitude_beam2"
    AMPLITUDE_BEAM3 = "amplitude_beam3"
    CORRELATION_BEAM1 = "correlation_beam1"
    CORRELATION_BEAM2 = "correlation_beam2"
    CORRELATION_BEAM3 = "correlation_beam3"
    
            
class VectorVelocityDataParticle(DataParticle):
    """
    Routine for parsing velocity data into a data particle structure for the Vector sensor. 
    """
    _data_particle_type = DataParticleType.VELOCITY

    def _build_parsed_values(self):
        """
        Take something in the velocity data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = VELOCITY_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorVelocityDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        analog_input2 = ord(match.group(1))
        count = ord(match.group(2))
        pressure = ord(match.group(3)) * 0x10000
        analog_input2 += ord(match.group(4)) * 0x100
        pressure += NortekProtocolParameterDict.convert_word_to_int(match.group(5))
        analog_input1 = NortekProtocolParameterDict.convert_word_to_int(match.group(6))
        velocity_beam1 = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        velocity_beam2 = NortekProtocolParameterDict.convert_word_to_int(match.group(8))
        velocity_beam3 = NortekProtocolParameterDict.convert_word_to_int(match.group(9))
        amplitude_beam1 = ord(match.group(10))
        amplitude_beam2 = ord(match.group(11))
        amplitude_beam3 = ord(match.group(12))
        correlation_beam1 = ord(match.group(13))
        correlation_beam2 = ord(match.group(14))
        correlation_beam3 = ord(match.group(15))
        
        if None == analog_input2:
            raise SampleException("No analog_input2 value parsed")
        if None == count:
            raise SampleException("No count value parsed")
        if None == pressure:
            raise SampleException("No pressure value parsed")
        if None == analog_input1:
            raise SampleException("No analog_input1 value parsed")
        if None == velocity_beam1:
            raise SampleException("No velocity_beam1 value parsed")
        if None == velocity_beam2:
            raise SampleException("No velocity_beam2 value parsed")
        if None == velocity_beam3:
            raise SampleException("No velocity_beam3 value parsed")
        if None == amplitude_beam1:
            raise SampleException("No amplitude_beam1 value parsed")
        if None == amplitude_beam2:
            raise SampleException("No amplitude_beam2 value parsed")
        if None == amplitude_beam3:
            raise SampleException("No amplitude_beam3 value parsed")
        if None == correlation_beam1:
            raise SampleException("No correlation_beam1 value parsed")
        if None == correlation_beam2:
            raise SampleException("No correlation_beam2 value parsed")
        if None == correlation_beam3:
            raise SampleException("No correlation_beam3 value parsed")
        
        result = [{DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT2,
                   DataParticleKey.VALUE: analog_input2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.COUNT,
                   DataParticleKey.VALUE: count},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT1,
                   DataParticleKey.VALUE: analog_input1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM1,
                   DataParticleKey.VALUE: velocity_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM2,
                   DataParticleKey.VALUE: velocity_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM3,
                   DataParticleKey.VALUE: velocity_beam3},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM1,
                   DataParticleKey.VALUE: amplitude_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM2,
                   DataParticleKey.VALUE: amplitude_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM3,
                   DataParticleKey.VALUE: amplitude_beam3},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM1,
                   DataParticleKey.VALUE: correlation_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM2,
                   DataParticleKey.VALUE: correlation_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM3,
                   DataParticleKey.VALUE: correlation_beam3}]
 
        log.debug('VectorVelocityDataParticle: particle=%s' %result)
        return result
    
class VectorVelocityHeaderDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"
    NUMBER_OF_RECORDS = "number_of_records"
    NOISE1 = "noise1"
    NOISE2 = "noise2"
    NOISE3 = "noise3"
    CORRELATION1 = "correlation1"
    CORRELATION2 = "correlation2"
    CORRELATION3 = "correlation3"
        
class VectorVelocityHeaderDataParticle(DataParticle):
    """
    Routine for parsing velocity header data into a data particle structure for the Vector sensor. 
    """
    _data_particle_type = DataParticleType.VELOCITY_HEADER

    def _build_parsed_values(self):
        """
        Take something in the velocity header data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = VELOCITY_HEADER_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorVelocityHeaderDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('VectorVelocityHeaderDataParticle: particle=%s' %result)
        return result
            
    def _build_particle(self, match):
        timestamp = NortekProtocolParameterDict.convert_time(match.group(1))
        py_timestamp = time.strptime(timestamp, "%d/%m/%Y %H:%M:%S")
        self.set_internal_timestamp(unix_time=time.mktime(py_timestamp))
        number_of_records = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        noise1 = ord(match.group(3))
        noise2 = ord(match.group(4))
        noise3 = ord(match.group(5))
        correlation1 = ord(match.group(6))
        correlation2 = ord(match.group(7))
        correlation3 = ord(match.group(8))
        
        if None == timestamp:
            raise SampleException("No timestamp parsed")
        if None == number_of_records:
            raise SampleException("No number_of_records value parsed")
        if None == noise1:
            raise SampleException("No noise1 value parsed")
        if None == noise2:
            raise SampleException("No noise2 value parsed")
        if None == noise3:
            raise SampleException("No noise3 value parsed")
        if None == correlation1:
            raise SampleException("No correlation1 value parsed")
        if None == correlation2:
            raise SampleException("No correlation2 value parsed")
        if None == correlation3:
            raise SampleException("No correlation3 value parsed")
        
        result = [{DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NUMBER_OF_RECORDS,
                   DataParticleKey.VALUE: number_of_records},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE1,
                   DataParticleKey.VALUE: noise1},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE2,
                   DataParticleKey.VALUE: noise2},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE3,
                   DataParticleKey.VALUE: noise3},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION1,
                   DataParticleKey.VALUE: correlation1},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION2,
                   DataParticleKey.VALUE: correlation2},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION3,
                   DataParticleKey.VALUE: correlation3}]
 
        return result

class VectorSystemDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"
    BATTERY = "battery"
    SOUND_SPEED = "sound_speed"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    TEMPERATURE = "temperature"
    ERROR = "error"
    STATUS = "status"
    ANALOG_INPUT = "analog_input"
        
class VectorSystemDataParticle(DataParticle):
    """
    Routine for parsing system data into a data particle structure for the Vector sensor. 
    """
    _data_particle_type = DataParticleType.SYSTEM

    def _build_parsed_values(self):
        """
        Take something in the system data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = SYSTEM_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorSystemDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('VectorSystemDataParticle: particle=%s' %result)
        return result
            
    def _build_particle(self, match):
        timestamp = NortekProtocolParameterDict.convert_time(match.group(1))
        py_timestamp = time.strptime(timestamp, "%d/%m/%Y %H:%M:%S")
        self.set_internal_timestamp(unix_time=time.mktime(py_timestamp))
        battery = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        sound_speed = NortekProtocolParameterDict.convert_word_to_int(match.group(3))
        heading = NortekProtocolParameterDict.convert_word_to_int(match.group(4))
        pitch = NortekProtocolParameterDict.convert_word_to_int(match.group(5))
        roll = NortekProtocolParameterDict.convert_word_to_int(match.group(6))
        temperature = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        error = ord(match.group(8))
        status = ord(match.group(9))
        analog_input = NortekProtocolParameterDict.convert_word_to_int(match.group(10))
        
        if None == timestamp:
            raise SampleException("No timestamp parsed")
        if None == battery:
            raise SampleException("No battery value parsed")
        if None == sound_speed:
            raise SampleException("No sound_speed value parsed")
        if None == heading:
            raise SampleException("No heading value parsed")
        if None == pitch:
            raise SampleException("No pitch value parsed")
        if None == roll:
            raise SampleException("No roll value parsed")
        if None == temperature:
            raise SampleException("No temperature value parsed")
        if None == error:
            raise SampleException("No error value parsed")
        if None == status:
            raise SampleException("No status value parsed")
        if None == analog_input:
            raise SampleException("No analog_input value parsed")
        
        result = [{DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.BATTERY,
                   DataParticleKey.VALUE: battery},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.SOUND_SPEED,
                   DataParticleKey.VALUE: sound_speed},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.HEADING,
                   DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ERROR,
                   DataParticleKey.VALUE: error},                   
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.STATUS,
                   DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ANALOG_INPUT,
                   DataParticleKey.VALUE: analog_input}]
 
        return result
            

class VectorProbeCheckDataParticleKey(BaseEnum):
    NUMBER_OF_SAMPLES_PER_BEAM = "number_of_samples_per_beam"
    FIRST_SAMPLE_NUMBER = "first_sample_number"
    BEAM_1_AMPLITUDES = "beam_1_amplitudes"
    BEAM_2_AMPLITUDES = "beam_2_amplitudes"
    BEAM_3_AMPLITUDES = "beam_3_amplitudes"
        
class VectorProbeCheckDataParticle(DataParticle):
    """
    Routine for parsing probe check data into a data particle structure for the Vector sensor. 
    """
    _data_particle_type = DataParticleType.PROBE_CHECK
    
    SAMPLES_PER_BEAM_OFFSET = 4
    FIRST_SAMPLE_NUMBER_OFFSET = 6
    START_OF_SAMPLES_OFFSET = 8

    def _build_parsed_values(self):
        """
        Take something in the probe check data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = PROBE_CHECK_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorProbeCheckDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        
        number_of_samples_per_beam = NortekProtocolParameterDict.convert_word_to_int(self.raw_data[self.SAMPLES_PER_BEAM_OFFSET:self.SAMPLES_PER_BEAM_OFFSET+2])
        log.debug("VectorProbeCheckDataParticle: samples per beam = %d" %number_of_samples_per_beam)
        first_sample_number = NortekProtocolParameterDict.convert_word_to_int(self.raw_data[self.FIRST_SAMPLE_NUMBER_OFFSET:self.FIRST_SAMPLE_NUMBER_OFFSET+2])
        
        index = self.START_OF_SAMPLES_OFFSET
        for beam_number in range(1, 4):
            beam_amplitudes = []
            for sample in range(0, number_of_samples_per_beam):
                beam_amplitudes.append(ord(self.raw_data[index]))
                index += 1
            if beam_number == 1:
                beam_1_amplitudes = beam_amplitudes
            elif beam_number == 2:
                beam_2_amplitudes = beam_amplitudes
            elif beam_number == 3:
                beam_3_amplitudes = beam_amplitudes
            
        
        result = [{DataParticleKey.VALUE_ID: VectorProbeCheckDataParticleKey.NUMBER_OF_SAMPLES_PER_BEAM,
                   DataParticleKey.VALUE: number_of_samples_per_beam},
                  {DataParticleKey.VALUE_ID: VectorProbeCheckDataParticleKey.FIRST_SAMPLE_NUMBER,
                   DataParticleKey.VALUE: first_sample_number},
                  {DataParticleKey.VALUE_ID: VectorProbeCheckDataParticleKey.BEAM_1_AMPLITUDES,
                   DataParticleKey.VALUE: beam_1_amplitudes},
                  {DataParticleKey.VALUE_ID: VectorProbeCheckDataParticleKey.BEAM_2_AMPLITUDES,
                   DataParticleKey.VALUE: beam_2_amplitudes},
                  {DataParticleKey.VALUE_ID: VectorProbeCheckDataParticleKey.BEAM_3_AMPLITUDES,
                   DataParticleKey.VALUE: beam_3_amplitudes},
                  ]
        
        log.debug('VectorProbeCheckDataParticle: particle=%s' %result)
        return result
            

###############################################################################
# Protocol
################################################################################

class Protocol(NortekInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    
    UserParameters = [
        # user configuration
        Parameter.TRANSMIT_PULSE_LENGTH,
        Parameter.BLANKING_DISTANCE,
        Parameter.RECEIVE_LENGTH,
        Parameter.TIME_BETWEEN_PINGS,
        Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
        Parameter.NUMBER_PINGS,
        Parameter.AVG_INTERVAL,
        Parameter.USER_NUMBER_BEAMS, 
        Parameter.TIMING_CONTROL_REGISTER,
        Parameter.POWER_CONTROL_REGISTER,
        Parameter.A1_1_SPARE,
        Parameter.B0_1_SPARE,
        Parameter.B1_1_SPARE,
        Parameter.COMPASS_UPDATE_RATE,  
        Parameter.COORDINATE_SYSTEM,
        Parameter.NUMBER_BINS,
        Parameter.BIN_LENGTH,
        Parameter.MEASUREMENT_INTERVAL,
        Parameter.DEPLOYMENT_NAME,
        Parameter.WRAP_MODE,
        Parameter.CLOCK_DEPLOY,
        Parameter.DIAGNOSTIC_INTERVAL,
        Parameter.MODE,
        Parameter.ADJUSTMENT_SOUND_SPEED,
        Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
        Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
        Parameter.NUMBER_PINGS_DIAGNOSTIC,
        Parameter.MODE_TEST,
        Parameter.ANALOG_INPUT_ADDR,
        Parameter.SW_VERSION,
        Parameter.USER_1_SPARE,
        Parameter.VELOCITY_ADJ_TABLE,
        Parameter.COMMENTS,
        Parameter.WAVE_MEASUREMENT_MODE,
        Parameter.DYN_PERCENTAGE_POSITION,
        Parameter.WAVE_TRANSMIT_PULSE,
        Parameter.WAVE_BLANKING_DISTANCE,
        Parameter.WAVE_CELL_SIZE,
        Parameter.NUMBER_DIAG_SAMPLES,
        Parameter.A1_2_SPARE,
        Parameter.B0_2_SPARE,
        Parameter.NUMBER_SAMPLES_PER_BURST,
        Parameter.USER_2_SPARE,
        Parameter.ANALOG_OUTPUT_SCALE,
        Parameter.CORRELATION_THRESHOLD,
        Parameter.USER_3_SPARE,
        Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
        Parameter.USER_4_SPARE,
        Parameter.QUAL_CONSTANTS,
        ]
    
    

    @staticmethod
    def chunker_sieve_function(raw_data):
        """ The method that detects data sample structures from instrument
        """
        return_list = []
        
        for structure_sync, structure_len in sample_structures:
            start = raw_data.find(structure_sync)
            if start != -1:    # found a sync pattern
                if structure_sync == PROBE_CHECK_SYNC_BYTES:
                    # must extract size of variable length structure
                    if start+structure_len+1 <= len(raw_data):    # only extract the size if the first 4 bytes have arrived
                        structure_len = NortekProtocolParameterDict.convert_word_to_int(raw_data[start+structure_len:start+structure_len+2]) * 2
                        log.debug('chunker_sieve_function: probe_check record size = %d' %structure_len)
                if start+structure_len <= len(raw_data):    # only check the CRC if all of the structure has arrived
                    calculated_checksum = NortekProtocolParameterDict.calculate_checksum(raw_data[start:start+structure_len], structure_len)
                    log.debug('chunker_sieve_function: calculated checksum = %s' % calculated_checksum)
                    sent_checksum = NortekProtocolParameterDict.convert_word_to_int(raw_data[start+structure_len-2:start+structure_len])
                    if sent_checksum == calculated_checksum:
                        return_list.append((start, start+structure_len))        
                        log.debug("chunker_sieve_function: found %s", raw_data[start:start+structure_len].encode('hex'))
                
        return return_list
    

    ########################################################################
    # overridden superclass methods
    ########################################################################    
                
    
    def _got_chunk(self, structure, timestamp):
        """
        The base class got_data has gotten a structure from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        log.debug("_got_chunk: detected structure = %s", structure.encode('hex'))
        self._extract_sample(VectorVelocityDataParticle, VELOCITY_DATA_REGEX, structure, timestamp)
        self._extract_sample(VectorSystemDataParticle, SYSTEM_DATA_REGEX, structure, timestamp)
        self._extract_sample(VectorVelocityHeaderDataParticle, VELOCITY_HEADER_DATA_REGEX, structure, timestamp)
        self._extract_sample(VectorProbeCheckDataParticle, PROBE_CHECK_DATA_REGEX, structure, timestamp)

            
    ########################################################################
    # Command handlers.
    ########################################################################
    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from vector.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).        
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # the vector doesn't respond with ACKs for this command, so look for start of velocity data header structure
        result = self._do_cmd_resp(InstrumentCmds.ACQUIRE_DATA, 
                                   expected_prompt = VELOCITY_HEADER_DATA_SYNC_BYTES, *args, **kwargs)
        
        return (next_state, (next_agent_state, result))


    ########################################################################
    # Private helpers.
    ########################################################################
    def _build_param_dict(self):
        NortekInstrumentProtocol._build_param_dict(self)

        self._param_dict.add(Parameter.NUMBER_SAMPLES_PER_BURST,
                     r'^.{%s}(.{2}).*' % str(452),
                     lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                     NortekProtocolParameterDict.word_to_string,
                     regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.USER_3_SPARE,
                             r'^.{%s}(.{2}).*' % str(460),
                             lambda match : match.group(1),
                             lambda string : string,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             regex_flags=re.DOTALL)

        
    def _dump_config(self, input):
        # dump config block
        dump = ''
        for byte_index in range(0, len(input)):
            if byte_index % 0x10 == 0:
                if byte_index != 0:
                    dump += '\n'   # no linefeed on first line
                dump += '{:03x}  '.format(byte_index)
            #dump += '0x{:02x}, '.format(ord(input[byte_index]))
            dump += '{:02x} '.format(ord(input[byte_index]))
        #log.debug("dump = %s", dump)
        return dump
    
    def _check_configuration(self, input, sync, length):        
        log.debug('_check_configuration: config=')
        print self._dump_config(input)
        if len(input) != length+2:
            log.debug('_check_configuration: wrong length, expected length %d != %d' %(length+2, len(input)))
            return False
        
        # check for ACK bytes
        if input[length:length+2] != InstrumentPrompts.Z_ACK:
            log.debug('_check_configuration: ACK bytes in error %s != %s' 
                      %(input[length:length+2].encode('hex'), InstrumentPrompts.Z_ACK.encode('hex')))
            return False
        
        # check the sync bytes 
        if input[0:4] != sync:
            log.debug('_check_configuration: sync bytes in error %s != %s' 
                      %(input[0:4], sync))
            return False
        
        # check checksum
        calculated_checksum = NortekProtocolParameterDict.calculate_checksum(input, length)
        log.debug('_check_configuration: user c_c = %s' % calculated_checksum)
        sent_checksum = NortekProtocolParameterDict.convert_word_to_int(input[length-2:length])
        if sent_checksum != calculated_checksum:
            log.debug('_check_configuration: user checksum in error %s != %s' 
                      %(calculated_checksum, sent_checksum))
            return False       
        
        return True

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and values saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolState.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        # get user_configuration params from the instrument
        # Grab time for timeout.
        starttime = time.time()
        timeout = 6

        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''

            log.debug('Sending get_user_configuration command to the instrument.')
            # Send get_user_cofig command to attempt to get user configuration.
            self._connection.send(InstrumentCmds.READ_USER_CONFIGURATION)
            for i in range(20):   # loop for 2 seconds waiting for response to complete
                if len(self._promptbuf) == USER_CONFIG_LEN+2:
                    if self._check_configuration(self._promptbuf, USER_CONFIG_SYNC_BYTES, USER_CONFIG_LEN):                    
                        self._param_dict.update(self._promptbuf)
                        new_config = self._param_dict.get_config()
                        if new_config != old_config:
                            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                        return
                    break
                time.sleep(.1)
            log.debug('_update_params: get_user_configuration command response length %d not right, %s' % (len(self._promptbuf), self._promptbuf.encode("hex")))

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()
            
            continue
        
    def  _get_mode(self, timeout, delay=1):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        self._promptbuf = ''
        
        # Grab time for timeout.
        starttime = time.time()
        
        log.debug("_get_mode: timeout = %d" %timeout)
        
        while True:
            log.debug('Sending what_mode command to get a response from the instrument.')
            # Send what_mode command to attempt to get a response.
            self._connection.send(InstrumentCmds.CMD_WHAT_MODE)
            time.sleep(delay)
            
            for item in self._prompts.list():
                if item in self._promptbuf:
                    if item != InstrumentPrompts.Z_NACK:
                        log.debug('get_mode got prompt: %s' % repr(item))
                        return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _create_set_output(self, parameters):
        # load buffer with sync byte (A5), ID byte (0), and size word (# of words in little-endian form)
        # 'user' configuration is 512 bytes, 256 words long, so size is 0x100
        output = '\xa5\x00\x00\x01'
        for name in self.UserParameters:
            log.debug('_create_set_output: adding %s to list' %name)
            output += parameters.format(name)
        
        checksum = CHECK_SUM_SEED
        for word_index in range(0, len(output), 2):
            word_value = NortekProtocolParameterDict.convert_word_to_int(output[word_index:word_index+2])
            checksum = (checksum + word_value) % 0x10000
            #log.debug('w_i=%d, c_c=%d' %(word_index, calculated_checksum))
        log.debug('_create_set_output: user checksum = %s' % checksum)

        output += NortekProtocolParameterDict.word_to_string(checksum)
        self._dump_config(output)                      
        
        return output
    
    def _build_set_configutation_command(self, cmd, *args, **kwargs):
        user_configuration = kwargs.get('user_configuration', None)
        if not user_configuration:
            raise InstrumentParameterException('set_configuration command missing user_configuration parameter.')
        if not isinstance(user_configuration, str):
            raise InstrumentParameterException('set_configuration command requires a string user_configuration parameter.')
        user_configuration = base64.b64decode(user_configuration)
        self._dump_config(user_configuration)        
            
        cmd_line = cmd + user_configuration
        return cmd_line


    def _build_set_real_time_clock_command(self, cmd, time, **kwargs):
        return cmd + time


    def _parse_read_clock_response(self, response, prompt):
        """ Parse the response from the instrument for a read clock command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        # packed BCD format, so convert binary to hex to get value
        # should be the 6 byte response ending with two ACKs
        if (len(response) != 8):
            log.warn("_parse_read_clock_response: Bad read clock response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read clock response. (%s)", response.encode('hex'))
        log.debug("_parse_read_clock_response: response=%s", response.encode('hex')) 
        time = NortekProtocolParameterDict.convert_time(response)   
        return time

    def _parse_what_mode_response(self, response, prompt):
        """ Parse the response from the instrument for a 'what mode' command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 4):
            log.warn("_parse_what_mode_response: Bad what mode response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid what mode response. (%s)", response.encode('hex'))
        log.debug("_parse_what_mode_response: response=%s", response.encode('hex')) 
        return NortekProtocolParameterDict.convert_word_to_int(response[0:2])
        

    def _parse_read_battery_voltage_response(self, response, prompt):
        """ Parse the response from the instrument for a read battery voltage command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 4):
            log.warn("_parse_read_battery_voltage_response: Bad read battery voltage response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read battery voltage response. (%s)", response.encode('hex'))
        log.debug("_parse_read_battery_voltage_response: response=%s", response.encode('hex')) 
        return NortekProtocolParameterDict.convert_word_to_int(response[0:2])
        
    def _parse_read_id(self, response, prompt):
        """ Parse the response from the instrument for a read ID command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if (len(response) != 10):
            log.warn("_handler_command_read_id: Bad read ID response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read ID response. (%s)", response.encode('hex'))
        log.debug("_handler_command_read_id: response=%s", response.encode('hex')) 
        return response[0:8]
        
    def _parse_read_hw_config(self, response, prompt):
        """ Parse the response from the instrument for a read hw config command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not self._check_configuration(self._promptbuf, HW_CONFIG_SYNC_BYTES, HW_CONFIG_LEN):                    
            log.warn("_parse_read_hw_config: Bad read hw response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read hw response. (%s)", response.encode('hex'))
        log.debug("_parse_read_hw_config: response=%s", response.encode('hex'))
        parsed = {} 
        parsed['SerialNo'] = response[4:18]  
        parsed['Config'] = NortekProtocolParameterDict.convert_word_to_int(response[18:20])  
        parsed['Frequency'] = NortekProtocolParameterDict.convert_word_to_int(response[20:22])  
        parsed['PICversion'] = NortekProtocolParameterDict.convert_word_to_int(response[22:24])  
        parsed['HWrevision'] = NortekProtocolParameterDict.convert_word_to_int(response[24:26])  
        parsed['RecSize'] = NortekProtocolParameterDict.convert_word_to_int(response[26:28])  
        parsed['Status'] = NortekProtocolParameterDict.convert_word_to_int(response[28:30])  
        parsed['FWversion'] = response[42:46] 
        return parsed
        
    def _parse_read_head_config(self, response, prompt):
        """ Parse the response from the instrument for a read head command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not self._check_configuration(self._promptbuf, HEAD_CONFIG_SYNC_BYTES, HEAD_CONFIG_LEN):                    
            log.warn("_parse_read_head_config: Bad read head response from instrument (%s)", response.encode('hex'))
            raise InstrumentProtocolException("Invalid read head response. (%s)", response.encode('hex'))
        log.debug("_parse_read_head_config: response=%s", response.encode('hex')) 
        parsed = {} 
        parsed['Config'] = NortekProtocolParameterDict.convert_word_to_int(response[4:6])  
        parsed['Frequency'] = NortekProtocolParameterDict.convert_word_to_int(response[6:8])  
        parsed['Type'] = NortekProtocolParameterDict.convert_word_to_int(response[8:10])  
        parsed['SerialNo'] = response[10:22]  
        #parsed['System'] = self._dump_config(response[22:198])
        parsed['System'] = base64.b64encode(response[22:198])
        parsed['NBeams'] = NortekProtocolParameterDict.convert_word_to_int(response[220:222])  
        return parsed
    
    def _parse_read_fat(self, response, prompt):
        """ Parse the response from the instrument for a read fat command.
        
        @param response The response string from the instrument
        @param prompt The prompt received from the instrument
        @retval return The time as a string
        @raise InstrumentProtocolException When a bad response is encountered
        """
        if not len(response) == FAT_LENGTH + 2:
            raise InstrumentProtocolException("Read FAT response length %d wrong, should be %d", len(response), FAT_LENGTH + 2)
        
        FAT = response[:-2]    
        print self._dump_config(FAT)

        parsed = []
         
        record_length = 16
        for index in range(0, FAT_LENGTH-record_length, record_length):
            record = FAT[index:index+record_length]
            record_number = index / record_length
### Introduced a new dependency.  Needs to be reviewed when finalizing driver
#            parsed_record = OrderedDict([('FileNumber', record_number), 
#                                         ('FileName', record[0:6].rstrip(chr(0x00))), 
#                                         ('SequenceNumber', ord(record[6:7])), 
#                                         ('Status', record[7:8]), 
#                                         ('StartAddr', record[8:12].encode('hex')), 
#                                         ('StopAddr', record[12:record_length].encode('hex'))])
            parsed.append(parsed_record)  
        return parsed
