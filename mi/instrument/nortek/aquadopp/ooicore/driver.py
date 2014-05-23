"""
@package mi.instrument.nortek.aquadopp.ooicore.driver
@author Rachel Manoni, Ronald Ronquillo
@brief Driver for the ooicore
Release notes:

Driver for Aquadopp DW
"""
import base64

__author__ = 'Rachel Manoni, Ronald Ronquillo'
__license__ = 'Apache 2.0'

import re

from mi.core.common import BaseEnum

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.nortek.driver import NortekInstrumentProtocol, InstrumentPrompts, NortekProtocolParameterDict, \
    NEWLINE, ParameterUnits
from mi.instrument.nortek.driver import NortekParameterDictVal, Parameter, NortekInstrumentDriver

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

VELOCITY_DATA_LEN = 42
VELOCITY_DATA_SYNC_BYTES = '\xa5\x01\x15\x00'

VELOCITY_DATA_PATTERN = r'%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})' \
                        r'(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)

AQUADOPP_SAMPLE_REGEX = [VELOCITY_DATA_REGEX]


class NortekDataParticleType(BaseEnum):
    """
    List of data particles.  Names match those in the IOS, need to overwrite enum defined in base class
    """
    VELOCITY = 'velpt_velocity_data'
    HARDWARE_CONFIG = 'velpt_hardware_configuration'
    HEAD_CONFIG = 'velpt_head_configuration'
    USER_CONFIG = 'velpt_user_configuration'
    CLOCK = 'vept_clock_data'
    BATTERY = 'velpt_battery_voltage'
    ID_STRING = 'velpt_identification_string'

    
class AquadoppDwVelocityDataParticleKey(BaseEnum):
    """
    Velocity Data particle
    """
    TIMESTAMP = "date_time_string"
    ERROR = "error_code"
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
    _data_particle_type = NortekDataParticleType.VELOCITY

    def _build_parsed_values(self):
        """
        Take the diagnostic data sample and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        log.debug('AquadoppDwVelocityDataParticle: raw data =%r', self.raw_data)
        match = VELOCITY_DATA_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("AquadoppDwVelocityDataParticle: No regex match of parsed sample data: [%s]" % self.raw_data)

        result = self._build_particle(match)
        return result

    def _build_particle(self, match):
        """
        Build a particle.  Used for parsing Velocity and Diagnostic data
        """
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

        result = [{DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TIMESTAMP, DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ERROR, DataParticleKey.VALUE: error},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ANALOG1, DataParticleKey.VALUE: analog1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.BATTERY_VOLTAGE, DataParticleKey.VALUE: battery_voltage},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.SOUND_SPEED_ANALOG2, DataParticleKey.VALUE: sound_speed},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.HEADING, DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PITCH, DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.ROLL, DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.STATUS, DataParticleKey.VALUE: status},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.PRESSURE, DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.TEMPERATURE, DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM1, DataParticleKey.VALUE: velocity_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM2, DataParticleKey.VALUE: velocity_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.VELOCITY_BEAM3, DataParticleKey.VALUE: velocity_beam3},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM1, DataParticleKey.VALUE: amplitude_beam1},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM2, DataParticleKey.VALUE: amplitude_beam2},
                  {DataParticleKey.VALUE_ID: AquadoppDwVelocityDataParticleKey.AMPLITUDE_BEAM3, DataParticleKey.VALUE: amplitude_beam3}]

        log.debug('AquadoppDwVelocityDataParticle: particle=%s', result)
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
    NortekInstrumentProtocol.velocity_data_regex.extend(AQUADOPP_SAMPLE_REGEX)
    NortekInstrumentProtocol.velocity_sync_bytes = VELOCITY_DATA_SYNC_BYTES

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        super(Protocol, self).__init__(prompts, newline, driver_event)

    ########################################################################
    # overridden superclass methods
    ########################################################################
    def _got_chunk(self, structure, timestamp):
        """
        The base class got_data has gotten a structure from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(AquadoppDwVelocityDataParticle, VELOCITY_DATA_REGEX, structure, timestamp)
        self._got_chunk_base(structure, timestamp)

    def _build_param_dict(self):
        """
        Overwrite base classes method.
        Creates base class's param dictionary, then sets parameter values for those specific to this instrument.
        """
        NortekInstrumentProtocol._build_param_dict(self)

        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TRANSMIT_PULSE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(4),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="transmit pulse length",
                                   default_value=125,
                                   units=ParameterUnits.CENTIMETERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.BLANKING_DISTANCE,
                                   r'^.{%s}(.{2}).*' % str(6),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="blanking distance",
                                   default_value=49,
                                   units=ParameterUnits.CENTIMETERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.RECEIVE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(8),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="receive length",
                                   default_value=32,
                                   units=ParameterUnits.CENTIMETERS,
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
                                   units=ParameterUnits.CENTIMETERS,
                                   default_value=437,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                                   r'^.{%s}(.{2}).*' % str(12),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="time between burst sequences",
                                   default_value=512,
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
                                   default_value=1,
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
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="avg interval",
                                   default_value=60,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_NUMBER_BEAMS,
                                   r'^.{%s}(.{2}).*' % str(18),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="user number beams",
                                   direct_access=True,
                                   value=3))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TIMING_CONTROL_REGISTER,
                                   r'^.{%s}(.{2}).*' % str(20),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="timing control register",
                                   direct_access=True,
                                   value=130))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.POWER_CONTROL_REGISTER,
                                   r'^.{%s}(.{2}).*' % str(22),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="power control register",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.A1_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(24),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="a1 1 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.B0_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(26),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="b0 1 spare",
                                   default_value=None))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.B1_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(28),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="b1 1 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.COMPASS_UPDATE_RATE,
                                   r'^.{%s}(.{2}).*' % str(30),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="compass update rate",
                                   default_value=1,
                                   units=ParameterUnits.HERTZ,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.COORDINATE_SYSTEM,
                                   r'^.{%s}(.{2}).*' % str(32),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="coordinate system",
                                   default_value=2,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_BINS,
                                   r'^.{%s}(.{2}).*' % str(34),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number bins",
                                   default_value=1,
                                   units=ParameterUnits.METERS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.BIN_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(36),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="bin length",
                                   default_value=7,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.MEASUREMENT_INTERVAL,
                                   r'^.{%s}(.{2}).*' % str(38),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="measurement interval",
                                   default_value=60,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.DEPLOYMENT_NAME,
                                   r'^.{%s}(.{6}).*' % str(40),
                                   lambda match: NortekProtocolParameterDict.convert_bytes_to_string(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="deployment name",
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
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.CLOCK_DEPLOY,
                                   r'^.{%s}(.{6}).*' % str(48),
                                   lambda match: NortekProtocolParameterDict.convert_words_to_datetime(match.group(1)),
                                   NortekProtocolParameterDict.convert_datetime_to_words,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.LIST,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="clock deploy",
                                   default_value=[0, 0, 0, 0, 0, 0],
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.DIAGNOSTIC_INTERVAL,
                                   r'^.{%s}(.{4}).*' % str(54),
                                   lambda match: NortekProtocolParameterDict.convert_double_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.double_word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="diagnostic interval",
                                   default_value=11250,
                                   startup_param=True,
                                   units=ParameterUnits.SECONDS,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.MODE,
                                   r'^.{%s}(.{2}).*' % str(58),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="mode",
                                   default_value=48,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.ADJUSTMENT_SOUND_SPEED,
                                   r'^.{%s}(.{2}).*' % str(60),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="adjustment sound speed",
                                   units=ParameterUnits.METERS_PER_SECOND,
                                   default_value=1525,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(62),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number samples diagnostic",
                                   default_value=20,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(64),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number beams cell diagnostic",
                                   default_value=1,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(66),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number pings diagnostic",
                                   default_value=1,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.MODE_TEST,
                                   r'^.{%s}(.{2}).*' % str(68),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="mode test",
                                   default_value=4,
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
                                   default_value=0,
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
                                   default_value=13902,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(74),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="user 1 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.VELOCITY_ADJ_TABLE,
                                   r'^.{%s}(.{180}).*' % str(76),
                                   lambda match: base64.b64encode(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="velocity adj table",
                                   units=ParameterUnits.PARTS_PER_TRILLION,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.COMMENTS,
                                   r'^.{%s}(.{180}).*' % str(256),
                                   lambda match: NortekProtocolParameterDict.convert_bytes_to_string(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="comments",
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.WAVE_MEASUREMENT_MODE,
                                   r'^.{%s}(.{2}).*' % str(436),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="wave measurement mode",
                                   default_value=0,
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
                                   default_value=0,
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
                                   default_value=0,
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
                                   default_value=0,
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
                                   default_value=0,
                                   units=ParameterUnits.METERS,
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
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.A1_2_SPARE,
                                   r'^.{%s}(.{2}).*' % str(448),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="a1 2 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.B0_2_SPARE,
                                   r'^.{%s}(.{2}).*' % str(450),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="b0 2 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.NUMBER_SAMPLES_PER_BURST,
                                   r'^.{%s}(.{2}).*' % str(452),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   expiration=None,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="number of samples per burst",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.ANALOG_OUTPUT_SCALE,
                                   r'^.{%s}(.{2}).*' % str(456),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="analog output scale",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_2_SPARE,  # for Vector this is 'SAMPLE_RATE'
                                   r'^.{%s}(.{2}).*' % str(454),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="user 2 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.CORRELATION_THRESHOLD,
                                   r'^.{%s}(.{2}).*' % str(458),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="correlation threshold",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_3_SPARE,
                                   r'^.{%s}(.{2}).*' % str(460),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="user 3 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                                   r'^.{%s}(.{2}).*' % str(462),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="transmit pulse length second lag",
                                   default_value=2,
                                   startup_param=True,
                                   direct_access=True))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.USER_4_SPARE,
                                   r'^.{%s}(.{30}).*' % str(464),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="user 4 spare"))
        self._param_dict.add_parameter(
            NortekParameterDictVal(Parameter.QUAL_CONSTANTS,
                                   r'^.{%s}(.{16}).*' % str(494),
                                   lambda match: base64.b64encode(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="qual constants",
                                   startup_param=True,
                                   direct_access=True))