"""
@package mi.instrument.nortek.aquadopp.ooicore.driver
@author Rachel Manoni
@brief Driver for the ooicore
Release notes:

Driver for Aquadopp DW
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

import re

from mi.core.common import BaseEnum

from mi.core.exceptions import SampleException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.instrument.nortek.driver import NortekInstrumentProtocol, InstrumentPrompts, NortekProtocolParameterDict, \
    USER_CONFIG_DATA_REGEX, HARDWARE_CONFIG_DATA_REGEX, HEAD_CONFIG_DATA_REGEX, NEWLINE, log_method, \
    ACQUIRE_STATUS_REGEX, EngineeringParameter, BATTERY_DATA_REGEX, CLOCK_DATA_REGEX, ID_DATA_REGEX, \
    NortekEngBatteryDataParticle, NortekEngClockDataParticle, NortekEngIdDataParticle
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticle
from mi.instrument.nortek.driver import NortekHeadConfigDataParticle
from mi.instrument.nortek.driver import NortekUserConfigDataParticle, NortekParameterDictVal, Parameter, \
    RUN_CLOCK_SYNC_REGEX, NortekInstrumentDriver
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

VELOCITY_DATA_LEN = 42
VELOCITY_DATA_SYNC_BYTES = '\xa5\x01\x15\x00'
DIAGNOSTIC_DATA_HEADER_LEN = 36
DIAGNOSTIC_DATA_HEADER_SYNC_BYTES = '\xa5\x06\x12\x00'
DIAGNOSTIC_DATA_LEN = 42
DIAGNOSTIC_DATA_SYNC_BYTES = '\xa5\x80\x15\x00'

VECTOR_SAMPLE_STRUCTURES = [[VELOCITY_DATA_SYNC_BYTES, VELOCITY_DATA_LEN],
                            [DIAGNOSTIC_DATA_HEADER_SYNC_BYTES, DIAGNOSTIC_DATA_HEADER_LEN],
                            [DIAGNOSTIC_DATA_SYNC_BYTES, DIAGNOSTIC_DATA_LEN]]

VELOCITY_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})' \
                        r'(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)
DIAGNOSTIC_DATA_HEADER_PATTERN = r'^%s(.{2})(.{2})(.{1})(.{1})(.{1})(.{1})(.{2})(.{2})(.{2})(.{2})(.{2})' \
                                 r'(.{2})(.{2})(.{2})(.{8})' % DIAGNOSTIC_DATA_HEADER_SYNC_BYTES
DIAGNOSTIC_DATA_HEADER_REGEX = re.compile(DIAGNOSTIC_DATA_HEADER_PATTERN, re.DOTALL)
DIAGNOSTIC_DATA_PATTERN = r'^%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})(.{2})' \
                          r'(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % DIAGNOSTIC_DATA_SYNC_BYTES
DIAGNOSTIC_DATA_REGEX = re.compile(DIAGNOSTIC_DATA_PATTERN, re.DOTALL)


class DataParticleType(BaseEnum):
    VELOCITY = 'velocity'
    DIAGNOSTIC = 'diagnostic'
    DIAGNOSTIC_HEADER = 'diagnostic_header'


###############################################################################
# Data particles
###############################################################################
class AquadoppDwDiagnosticHeaderDataParticleKey(BaseEnum):
    RECORDS = "records"
    CELL = "cell"
    NOISE1 = "noise1"
    NOISE2 = "noise2"
    NOISE3 = "noise3"
    NOISE4 = "noise4"
    PROCESSING_MAGNITUDE_BEAM1 = "processing_magnitude_beam1"
    PROCESSING_MAGNITUDE_BEAM2 = "processing_magnitude_beam2"
    PROCESSING_MAGNITUDE_BEAM3 = "processing_magnitude_beam3"
    PROCESSING_MAGNITUDE_BEAM4 = "processing_magnitude_beam4"
    DISTANCE1 = "distance1"
    DISTANCE2 = "distance2"
    DISTANCE3 = "distance3"
    DISTANCE4 = "distance4"


class AquadoppDwDiagnosticHeaderDataParticle(DataParticle):
    """
    Routine for parsing diagnostic data header into a data particle structure for the Aquadopp DW sensor.
    """
    _data_particle_type = DataParticleType.DIAGNOSTIC_HEADER

    @log_method
    def _build_parsed_values(self):
        """
        Take something in the diagnostic data header sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = DIAGNOSTIC_DATA_HEADER_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("AquadoppDwDiagnosticHeaderDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        records = NortekProtocolParameterDict.convert_word_to_int(match.group(1))
        cell = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        noise1 = ord(match.group(3))
        noise2 = ord(match.group(4))
        noise3 = ord(match.group(5))
        noise4 = ord(match.group(6))
        proc_magn_beam1 = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        proc_magn_beam2 = NortekProtocolParameterDict.convert_word_to_int(match.group(8))
        proc_magn_beam3 = NortekProtocolParameterDict.convert_word_to_int(match.group(9))
        proc_magn_beam4 = NortekProtocolParameterDict.convert_word_to_int(match.group(10))
        distance1 = NortekProtocolParameterDict.convert_word_to_int(match.group(11))
        distance2 = NortekProtocolParameterDict.convert_word_to_int(match.group(12))
        distance3 = NortekProtocolParameterDict.convert_word_to_int(match.group(13))
        distance4 = NortekProtocolParameterDict.convert_word_to_int(match.group(14))

        if None == records:
            raise SampleException("No records value parsed")
        if None == cell:
            raise SampleException("No cell value parsed")
        if None == noise1:
            raise SampleException("No noise1 value parsed")
        if None == noise2:
            raise SampleException("No noise2 value parsed")
        if None == noise3:
            raise SampleException("No noise3 value parsed")
        if None == noise4:
            raise SampleException("No noise4 value parsed")
        if None == proc_magn_beam1:
            raise SampleException("No proc_magn_beam1 value parsed")
        if None == proc_magn_beam2:
            raise SampleException("No proc_magn_beam2 value parsed")
        if None == proc_magn_beam3:
            raise SampleException("No proc_magn_beam3 value parsed")
        if None == proc_magn_beam4:
            raise SampleException("No proc_magn_beam4 value parsed")
        if None == distance1:
            raise SampleException("No distance1 value parsed")
        if None == distance2:
            raise SampleException("No distance2 value parsed")
        if None == distance3:
            raise SampleException("No distance3 value parsed")
        if None == distance4:
            raise SampleException("No distance4 value parsed")

        result = [{DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.RECORDS,
                   DataParticleKey.VALUE: records},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.CELL,
                   DataParticleKey.VALUE: cell},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE1,
                   DataParticleKey.VALUE: noise1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE2,
                   DataParticleKey.VALUE: noise2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE3,
                   DataParticleKey.VALUE: noise3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.NOISE4,
                   DataParticleKey.VALUE: noise4},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM1,
                   DataParticleKey.VALUE: proc_magn_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM2,
                   DataParticleKey.VALUE: proc_magn_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM3,
                   DataParticleKey.VALUE: proc_magn_beam3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.PROCESSING_MAGNITUDE_BEAM4,
                   DataParticleKey.VALUE: proc_magn_beam4},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE1,
                   DataParticleKey.VALUE: distance1},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE2,
                   DataParticleKey.VALUE: distance2},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE3,
                   DataParticleKey.VALUE: distance3},
                  {DataParticleKey.VALUE_ID: AquadoppDwDiagnosticHeaderDataParticleKey.DISTANCE4,
                   DataParticleKey.VALUE: distance4}]

        return result


class AquadoppDwVelocityDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"
    ERROR = "error"
    ANALOG1 = "analog1"
    BATTERY_VOLTAGE = "battery_voltage"
    SOUND_SPEED_ANALOG2 = "sound_speed_analog2"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    PRESSURE = "pressure"
    STATUS = "status"
    TEMPERATURE = "temperature"
    VELOCITY_BEAM1 = "velocity_beam1"
    VELOCITY_BEAM2 = "velocity_beam2"
    VELOCITY_BEAM3 = "velocity_beam3"
    AMPLITUDE_BEAM1 = "amplitude_beam1"
    AMPLITUDE_BEAM2 = "amplitude_beam2"
    AMPLITUDE_BEAM3 = "amplitude_beam3"


class AquadoppDwVelocityDataParticle(DataParticle):
    """
    Routine for parsing velocity data into a data particle structure for the Aquadopp DW sensor.
    """
    _data_particle_type = DataParticleType.VELOCITY

    @log_method
    def _build_parsed_values(self):
        """
        Take something in the velocity data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = VELOCITY_DATA_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("AquadoppDwVelocityDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        result = self._build_particle(match)
        return result

    def _build_particle(self, match):
        timestamp = NortekProtocolParameterDict.convert_time(match.group(1))
        error = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        analog1 = NortekProtocolParameterDict.convert_word_to_int(match.group(3))
        battery_voltage = NortekProtocolParameterDict.convert_word_to_int(match.group(4))
        sound_speed = NortekProtocolParameterDict.convert_word_to_int(match.group(5))
        heading = NortekProtocolParameterDict.convert_word_to_int(match.group(6))
        pitch = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        roll = NortekProtocolParameterDict.convert_word_to_int(match.group(8))
        pressure = ord(match.group(9)) * 0x10000
        status = ord(match.group(10))
        pressure += NortekProtocolParameterDict.convert_word_to_int(match.group(11))
        temperature = NortekProtocolParameterDict.convert_word_to_int(match.group(12))
        velocity_beam1 = NortekProtocolParameterDict.convert_word_to_int(match.group(13))
        velocity_beam2 = NortekProtocolParameterDict.convert_word_to_int(match.group(14))
        velocity_beam3 = NortekProtocolParameterDict.convert_word_to_int(match.group(15))
        amplitude_beam1 = ord(match.group(16))
        amplitude_beam2 = ord(match.group(17))
        amplitude_beam3 = ord(match.group(18))

        if None == timestamp:
            raise SampleException("No timestamp parsed")
        if None == error:
            raise SampleException("No error value parsed")
        if None == analog1:
            raise SampleException("No analog1 value parsed")
        if None == battery_voltage:
            raise SampleException("No battery_voltage value parsed")
        if None == sound_speed:
            raise SampleException("No sound_speed value parsed")
        if None == heading:
            raise SampleException("No heading value parsed")
        if None == pitch:
            raise SampleException("No pitch value parsed")
        if None == roll:
            raise SampleException("No roll value parsed")
        if None == status:
            raise SampleException("No status value parsed")
        if None == pressure:
            raise SampleException("No pressure value parsed")
        if None == temperature:
            raise SampleException("No temperature value parsed")
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

        result = [{DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ERROR,
                   DataParticleKey.VALUE: error},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ANALOG1,
                   DataParticleKey.VALUE: analog1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.BATTERY_VOLTAGE,
                   DataParticleKey.VALUE: battery_voltage},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.SOUND_SPEED_ANALOG2,
                   DataParticleKey.VALUE: sound_speed},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.HEADING,
                   DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.STATUS,
                   DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM1,
                   DataParticleKey.VALUE: velocity_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM2,
                   DataParticleKey.VALUE: velocity_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM3,
                   DataParticleKey.VALUE: velocity_beam3},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM1,
                   DataParticleKey.VALUE: amplitude_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM2,
                   DataParticleKey.VALUE: amplitude_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM3,
                   DataParticleKey.VALUE: amplitude_beam3}]

        return result




class AquadoppDwDiagnosticDataParticle(AquadoppDwVelocityDataParticle):
    """
    Routine for parsing diagnostic data into a data particle structure for the Aquadopp DW sensor.
    This structure is the same as the velocity data, so particle is built with the same method
    """
    _data_particle_type = DataParticleType.DIAGNOSTIC

    @log_method
    def _build_parsed_values(self):
        """
        Take something in the diagnostic data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = DIAGNOSTIC_DATA_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("AquadoppDwDiagnosticDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        result = self._build_particle(match)
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
    @log_method
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
    @log_method
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

    @log_method
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        NortekInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(Protocol.chunker_sieve_function)    # This can be moved to base class if VECTOR_SAMPLE_STRUCTURES can be initialized

    ########################################################################
    # overridden superclass methods
    ########################################################################
    @staticmethod
    @log_method
    def chunker_sieve_function(raw_data, add_structs=[]):
        return NortekInstrumentProtocol.chunker_sieve_function(raw_data,
                                                               VECTOR_SAMPLE_STRUCTURES)

    @log_method
    def _got_chunk(self, structure, timestamp):
        """
        The base class got_data has gotten a structure from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(AquadoppDwVelocityDataParticle, VELOCITY_DATA_REGEX, structure, timestamp)
        self._extract_sample(AquadoppDwDiagnosticDataParticle, DIAGNOSTIC_DATA_REGEX, structure, timestamp)
        self._extract_sample(AquadoppDwDiagnosticHeaderDataParticle, DIAGNOSTIC_DATA_HEADER_REGEX, structure, timestamp)

        self._got_chunk_base(structure, timestamp)

    def _helper_get_data_key(self):
        # override to pass the correct velocity data key per instrument

        # TODO change this to a init value that the base class can use
        return VELOCITY_DATA_SYNC_BYTES

    @log_method
    def _build_param_dict(self):
        """
        Overwrite base classes method.
        Creates base class's param dictionary, then sets parameter values for those specific to this instrument.
        """

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

        # self._param_dict.set_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
        #                            self._param_dict.get_default_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL))
        # self._param_dict.set_value(EngineeringParameter.CLOCK_SYNC_INTERVAL,
        #                            self._param_dict.get_default_value(EngineeringParameter.CLOCK_SYNC_INTERVAL))