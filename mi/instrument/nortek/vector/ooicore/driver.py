"""
@package mi.instrument.nortek.vector.ooicore.driver
@file mi/instrument/nortek/vector/ooicore/driver.py
@author Rachel Manoni
@brief Driver for the ooicore
Release notes:

Driver for vector
"""
from mi.core.instrument.protocol_param_dict import ParameterDictType, ParameterDictVisibility

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

import time
import re

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.nortek.driver import NortekDataParticleType, NortekParameterDictVal, Parameter, ParameterUnits
from mi.instrument.nortek.driver import NortekInstrumentDriver
from mi.instrument.nortek.driver import NortekInstrumentProtocol
from mi.instrument.nortek.driver import NortekProtocolParameterDict
from mi.instrument.nortek.driver import InstrumentPrompts
from mi.instrument.nortek.driver import NEWLINE

from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger
log = get_logger()

VELOCITY_DATA_LEN = 24
VELOCITY_DATA_SYNC_BYTES = '\xa5\x10'
SYSTEM_DATA_LEN = 28
SYSTEM_DATA_SYNC_BYTES = '\xa5\x11\x0e\x00'
VELOCITY_HEADER_DATA_LEN = 42
VELOCITY_HEADER_DATA_SYNC_BYTES = '\xa5\x12\x15\x00'

VECTOR_SAMPLE_STRUCTURES = [[VELOCITY_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                            [SYSTEM_DATA_SYNC_BYTES, SYSTEM_DATA_LEN],
                            [VELOCITY_HEADER_DATA_SYNC_BYTES, VELOCITY_HEADER_DATA_LEN]]

VELOCITY_DATA_PATTERN = r'^%s(.{1})(.{1})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{1})(.{1})(.{1}).{2}' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)
SYSTEM_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2}).{2}' % SYSTEM_DATA_SYNC_BYTES
SYSTEM_DATA_REGEX = re.compile(SYSTEM_DATA_PATTERN, re.DOTALL)
VELOCITY_HEADER_DATA_PATTERN = r'^%s(.{6})(.{2})(.{1})(.{1})(.{1}).{1}(.{1})(.{1})(.{1}).{23}' % VELOCITY_HEADER_DATA_SYNC_BYTES
VELOCITY_HEADER_DATA_REGEX = re.compile(VELOCITY_HEADER_DATA_PATTERN, re.DOTALL)

VECTOR_SAMPLE_REGEX = [VELOCITY_DATA_REGEX, SYSTEM_DATA_REGEX, VELOCITY_HEADER_DATA_REGEX]


class DataParticleType(NortekDataParticleType):
    """
    List of data particles to collect
    """
    VELOCITY = 'vel3d_cd_velocity_data'
    VELOCITY_HEADER = 'vel3d_cd_data_header'
    SYSTEM = 'vel3d_cd_system_data'


class VectorVelocityDataParticleKey(BaseEnum):
    """
    Velocity Data Paticles
    """
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
        Take the velocity data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        log.debug('VectorVelocityDataParticle: raw data =%r', self.raw_data)
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
        
        result = [{DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT2, DataParticleKey.VALUE: analog_input2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.COUNT, DataParticleKey.VALUE: count},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.PRESSURE, DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.ANALOG_INPUT1, DataParticleKey.VALUE: analog_input1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM1, DataParticleKey.VALUE: velocity_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM2, DataParticleKey.VALUE: velocity_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.VELOCITY_BEAM3, DataParticleKey.VALUE: velocity_beam3},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM1, DataParticleKey.VALUE: amplitude_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM2, DataParticleKey.VALUE: amplitude_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.AMPLITUDE_BEAM3, DataParticleKey.VALUE: amplitude_beam3},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM1, DataParticleKey.VALUE: correlation_beam1},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM2, DataParticleKey.VALUE: correlation_beam2},
                  {DataParticleKey.VALUE_ID: VectorVelocityDataParticleKey.CORRELATION_BEAM3, DataParticleKey.VALUE: correlation_beam3}]
 
        log.debug('VectorVelocityDataParticle: particle=%s', result)
        return result


class VectorVelocityHeaderDataParticleKey(BaseEnum):
    """
    Velocity Header data particles
    """
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
        Take the velocity header data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        log.debug('VectorVelocityHeaderDataParticle: raw data =%r', self.raw_data)
        match = VELOCITY_HEADER_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorVelocityHeaderDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('VectorVelocityHeaderDataParticle: particle=%s', result)
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
        
        result = [{DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NUMBER_OF_RECORDS, DataParticleKey.VALUE: number_of_records},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE1, DataParticleKey.VALUE: noise1},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE2, DataParticleKey.VALUE: noise2},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.NOISE3, DataParticleKey.VALUE: noise3},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION1, DataParticleKey.VALUE: correlation1},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION2, DataParticleKey.VALUE: correlation2},
                  {DataParticleKey.VALUE_ID: VectorVelocityHeaderDataParticleKey.CORRELATION3, DataParticleKey.VALUE: correlation3}]
 
        return result


class VectorSystemDataParticleKey(BaseEnum):
    """
    System data particles
    """
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
        Take the system data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        log.debug('VectorSystemDataParticle: raw data =%r', self.raw_data)
        match = SYSTEM_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorSystemDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = self._build_particle(match)
        log.debug('VectorSystemDataParticle: particle=%s', result)
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
        
        result = [{DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.BATTERY, DataParticleKey.VALUE: battery},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.SOUND_SPEED, DataParticleKey.VALUE: sound_speed},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.HEADING, DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.PITCH, DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ROLL, DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.TEMPERATURE, DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ERROR, DataParticleKey.VALUE: error},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.STATUS, DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: VectorSystemDataParticleKey.ANALOG_INPUT, DataParticleKey.VALUE: analog_input}]
 
        return result


###############################################################################
# Driver
###############################################################################
class InstrumentDriver(NortekInstrumentDriver):
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
        NortekInstrumentDriver.__init__(self, evt_callback)
    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)


###############################################################################
# Protocol
################################################################################
class Protocol(NortekInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses NortekInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        NortekInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(Protocol.chunker_sieve_function)
        
    @staticmethod
    def chunker_sieve_function(raw_data, add_structs=[]):
        return NortekInstrumentProtocol.chunker_sieve_function(raw_data, VECTOR_SAMPLE_STRUCTURES)

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

        self._got_chunk_base(structure, timestamp)

    def _helper_get_data_key(self):
        # override to pass the correct velocity data key per instrument

        # TODO change this to a init value that the base class can use
        return VELOCITY_DATA_SYNC_BYTES

    ########################################################################
    # Private helpers.
    ########################################################################
    def _build_param_dict(self):
        NortekInstrumentProtocol._build_param_dict(self)

        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TRANSMIT_PULSE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(4),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="transmit pulse length",
                                   default_value=2,
                                   units=ParameterUnits.MILLIMETERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.BLANKING_DISTANCE,
                                   r'^.{%s}(.{2}).*' % str(6),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="blanking distance",
                                   default_value=16,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.RECEIVE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(8),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="receive length",
                                   default_value=7,
                                   units=ParameterUnits.MILLIMETERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TIME_BETWEEN_PINGS,
                                   r'^.{%s}(.{2}).*' % str(10),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="time between pings",
                                   default_value=None,
                                   units=ParameterUnits.METERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                                   r'^.{%s}(.{2}).*' % str(12),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="time between burst sequences",
                                   default_value=0,
                                   units=None,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_PINGS,
                                   r'^.{%s}(.{2}).*' % str(14),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number pings",
                                   default_value=0,
                                   units=ParameterUnits.HERTZ,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.AVG_INTERVAL,
                                   r'^.{%s}(.{2}).*' % str(16),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="avg interval",
                                   default_value=32,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.POWER_CONTROL_REGISTER,
                                   r'^.{%s}(.{2}).*' % str(22),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="power control register",
                                   direct_access=True,
                                   value=0))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.COMPASS_UPDATE_RATE,
                                   r'^.{%s}(.{2}).*' % str(30),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="compass update rate",
                                   default_value=1,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.BIN_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(36),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="bin length",
                                   default_value=7,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.MEASUREMENT_INTERVAL,
                                   r'^.{%s}(.{2}).*' % str(38),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="measurement interval",
                                   default_value=3600,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WRAP_MODE,
                                   r'^.{%s}(.{2}).*' % str(46),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="wrap mode",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.CLOCK_DEPLOY,
                                   r'^.{%s}(.{6}).*' % str(48),
                                   lambda match: NortekProtocolParameterDict.convert_words_to_datetime(match.group(1)),
                                   lambda string : string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="clock deploy",
                                   default_value='000000',
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.ANALOG_INPUT_ADDR,
                                    r'^.{%s}(.{2}).*' % str(70),
                                    lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                    NortekProtocolParameterDict.word_to_string,
                                    regex_flags=re.DOTALL,
                                    type=ParameterDictType.STRING,
                                    visibility=ParameterDictVisibility.IMMUTABLE,
                                    display_name="analog input addr",
                                    startup_param=True,
                                    direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.SW_VERSION,
                                   r'^.{%s}(.{2}).*' % str(72),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="sw version",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WAVE_MEASUREMENT_MODE,
                                   r'^.{%s}(.{2}).*' % str(436),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="wave measurement mode",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.DYN_PERCENTAGE_POSITION,
                                   r'^.{%s}(.{2}).*' % str(438),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="dyn percentage position",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WAVE_TRANSMIT_PULSE,
                                   r'^.{%s}(.{2}).*' % str(440),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="wave transmit pulse",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WAVE_BLANKING_DISTANCE,
                                   r'^.{%s}(.{2}).*' % str(442),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="wave blanking distance",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WAVE_CELL_SIZE,
                                   r'^.{%s}(.{2}).*' % str(444),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="wave cell size",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_DIAG_SAMPLES,
                                   r'^.{%s}(.{2}).*' % str(446),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number diag samples",
                                   startup_param=True,
                                   direct_access=True))

        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_SAMPLES_PER_BURST,
                                   r'^.{%s}(.{2}).*' % str(452),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="number samples per burst",
                                   direct_access=True,
                                   value=0))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.ANALOG_OUTPUT_SCALE,
                                    r'^.{%s}(.{2}).*' % str(456),
                                    lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                    NortekProtocolParameterDict.word_to_string,
                                    regex_flags=re.DOTALL,
                                    type=ParameterDictType.INT,
                                    visibility=ParameterDictVisibility.IMMUTABLE,
                                    display_name="analog output scale",
                                    startup_param=True,
                                    direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_2_SPARE,# for Vector this is 'SAMPLE_RATE'
                                    r'^.{%s}(.{2}).*' % str(454),
                                    lambda match: match.group(1).encode('hex'),
                                    lambda string: string.decode('hex'),
                                    regex_flags=re.DOTALL,
                                    type=ParameterDictType.STRING,
                                    visibility=ParameterDictVisibility.READ_WRITE,
                                    display_name="sample rate",
                                    direct_access=True,
                                    value='8'))