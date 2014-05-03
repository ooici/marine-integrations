"""
@package mi.instrument.nortek.vector.ooicore.driver
@file mi/instrument/nortek/vector/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the ooicore
Release notes:

Driver for vector
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import time
import re

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.nortek.driver import NortekParameterDictVal
from mi.instrument.nortek.driver import NortekDataParticleType
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticle
from mi.instrument.nortek.driver import NortekHeadConfigDataParticle
from mi.instrument.nortek.driver import NortekUserConfigDataParticle
from mi.instrument.nortek.driver import NortekEngBatteryDataParticle
from mi.instrument.nortek.driver import NortekEngClockDataParticle
from mi.instrument.nortek.driver import NortekEngIdDataParticle
from mi.instrument.nortek.driver import NortekInstrumentDriver
from mi.instrument.nortek.driver import NortekInstrumentProtocol
from mi.instrument.nortek.driver import NortekProtocolParameterDict
from mi.instrument.nortek.driver import Parameter, InstrumentCmds, InstrumentPrompts
from mi.instrument.nortek.driver import NEWLINE
from mi.instrument.nortek.driver import HARDWARE_CONFIG_DATA_REGEX
from mi.instrument.nortek.driver import HEAD_CONFIG_DATA_REGEX
from mi.instrument.nortek.driver import USER_CONFIG_DATA_REGEX
from mi.instrument.nortek.driver import BATTERY_DATA_REGEX
from mi.instrument.nortek.driver import CLOCK_DATA_REGEX
from mi.instrument.nortek.driver import ID_DATA_REGEX

from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger ; log = get_logger()

RESOURCE_FILE = 'mi/instrument/nortek/vector/ooicore/resource/strings.yml'
VELOCITY_DATA_LEN = 24
VELOCITY_DATA_SYNC_BYTES = '\xa5\x10'
SYSTEM_DATA_LEN = 28
SYSTEM_DATA_SYNC_BYTES = '\xa5\x11\x0e\x00'
VELOCITY_HEADER_DATA_LEN = 42
VELOCITY_HEADER_DATA_SYNC_BYTES = '\xa5\x12\x15\x00'

VECTOR_SAMPLE_STRUCTURES = [[VELOCITY_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                            [SYSTEM_DATA_SYNC_BYTES, SYSTEM_DATA_LEN],
                            [VELOCITY_HEADER_DATA_SYNC_BYTES, VELOCITY_HEADER_DATA_LEN]
                           ]

VELOCITY_DATA_PATTERN = r'^%s(.{1})(.{1})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{1})(.{1})(.{1}).{2}' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)
SYSTEM_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2}).{2}' % SYSTEM_DATA_SYNC_BYTES
SYSTEM_DATA_REGEX = re.compile(SYSTEM_DATA_PATTERN, re.DOTALL)
VELOCITY_HEADER_DATA_PATTERN = r'^%s(.{6})(.{2})(.{1})(.{1})(.{1}).{1}(.{1})(.{1})(.{1}).{23}' % VELOCITY_HEADER_DATA_SYNC_BYTES
VELOCITY_HEADER_DATA_REGEX = re.compile(VELOCITY_HEADER_DATA_PATTERN, re.DOTALL)

VECTOR_SAMPLE_REGEX = [VELOCITY_DATA_REGEX, SYSTEM_DATA_REGEX, VELOCITY_HEADER_DATA_REGEX]

class DataParticleType(NortekDataParticleType):
    VELOCITY = 'vel3d_cd_velocity_data'
    VELOCITY_HEADER = 'vel3d_cd_data_header'
    SYSTEM = 'vel3d_cd_system_data'

    
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

class VectorHardwareConfigDataParticle(NortekHardwareConfigDataParticle):
    _data_particle_type = DataParticleType.HARDWARE_CONFIG

    def _build_parsed_values(self):
        return NortekHardwareConfigDataParticle._build_parsed_values(self)

class VectorUserConfigDataParticle(NortekUserConfigDataParticle):
    _data_particle_type = DataParticleType.USER_CONFIG

    def _build_parsed_values(self):
        return NortekUserConfigDataParticle._build_parsed_values(self)

class VectorHeadConfigDataParticle(NortekHeadConfigDataParticle):
    _data_particle_type = DataParticleType.HEAD_CONFIG

    def _build_parsed_values(self):
        return NortekHeadConfigDataParticle._build_parsed_values(self)

class VectorVelocityDataParticleKey(BaseEnum):
    ANALOG_INPUT2 = "analog_input2"
    COUNT = "ensemble_counter"
    PRESSURE = "seawater_pressure"
    ANALOG_INPUT1 = "analog_input1"
    VELOCITY_BEAM1 = "turbulent_velocity_east"
    VELOCITY_BEAM2 = "turbulent_velocity_north"
    VELOCITY_BEAM3 = "turbulent_velocity_vertical"
    AMPLITUDE_BEAM1 = "amplitude_beam_1"
    AMPLITUDE_BEAM2 = "amplitude_beam_2"
    AMPLITUDE_BEAM3 = "amplitude_beam_3"
    CORRELATION_BEAM1 = "correlation_beam_1"
    CORRELATION_BEAM2 = "correlation_beam_2"
    CORRELATION_BEAM3 = "correlation_beam_3"
    
            
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
    TIMESTAMP = "date_time_string"
    NUMBER_OF_RECORDS = "number_velocity_records"
    NOISE1 = "noise_amp_beam1"
    NOISE2 = "noise_amp_beam2"
    NOISE3 = "noise_amp_beam3"
    CORRELATION1 = "noise_correlation_beam1"
    CORRELATION2 = "noise_correlation_beam2"
    CORRELATION3 = "noise_correlation_beam3"
        
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
    TIMESTAMP = "date_time_string"
    BATTERY = "battery_voltage"
    SOUND_SPEED = "speed_of_sound"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    TEMPERATURE = "temperature"
    ERROR = "error_code"
    STATUS = "status_code"
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
    
    
    def __init__(self, prompts, newline, driver_event):
        NortekInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        
        # create chunker for processing instrument samples.
        self._chunker = StringChunker(Protocol.chunker_sieve_function)
        
    @staticmethod
    def chunker_sieve_function(raw_data):
        return NortekInstrumentProtocol.chunker_sieve_function(raw_data,
                                                               VECTOR_SAMPLE_STRUCTURES)

    # @staticmethod
    # def sieve_function(raw_data):
    #     return NortekInstrumentProtocol.sieve_function(raw_data,
    #                                                            VECTOR_SAMPLE_REGEX)

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

        self._got_chunk_child(structure, timestamp)

            
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
        result = self._do_cmd_resp(InstrumentCmds.ACQUIRE_DATA, expected_prompt=VELOCITY_HEADER_DATA_SYNC_BYTES, timeout=15, *args, **kwargs)

        return (next_state, (next_agent_state, result))


    ########################################################################
    # Private helpers.
    ########################################################################
    def _build_param_dict(self):
        NortekInstrumentProtocol._build_param_dict(self)

        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_SAMPLES_PER_BURST,
                                   r'^.{%s}(.{2}).*' % str(452),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   expiration=None,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="number samples per burst"
                                   ))
        self._param_dict.load_strings(RESOURCE_FILE)

    def _build_cmd_dict(self):
        NortekInstrumentProtocol._build_cmd_dict(self)
        self._cmd_dict.load_strings(RESOURCE_FILE)