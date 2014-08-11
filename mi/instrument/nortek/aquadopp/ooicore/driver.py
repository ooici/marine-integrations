"""
@package mi.instrument.nortek.aquadopp.ooicore.driver
@author Rachel Manoni, Ronald Ronquillo
@brief Driver for the ooicore
Release notes:

Driver for Aquadopp DW
"""
__author__ = 'Rachel Manoni, Ronald Ronquillo'
__license__ = 'Apache 2.0'

import re
import base64

from mi.core.common import BaseEnum

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.nortek.driver import NortekInstrumentProtocol, InstrumentPrompts, NortekProtocolParameterDict
from mi.instrument.nortek.driver import Parameter, NortekInstrumentDriver, NEWLINE, ParameterUnits
from mi.instrument.nortek.driver import NortekHardwareConfigDataParticle, NortekHeadConfigDataParticle, NortekUserConfigDataParticle\
    , NortekEngBatteryDataParticle, NortekEngIdDataParticle, NortekEngClockDataParticle

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

VELOCITY_DATA_LEN = 42
VELOCITY_DATA_SYNC_BYTES = '\xa5\x01\x15\x00'

VELOCITY_DATA_PATTERN = r'%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})' \
                        r'(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)


class NortekDataParticleType(BaseEnum):
    """
    List of data particles.  Names match those in the IOS, need to overwrite enum defined in base class
    """
    VELOCITY = 'velpt_velocity_data'
    HARDWARE_CONFIG = 'velpt_hardware_configuration'
    HEAD_CONFIG = 'velpt_head_configuration'
    USER_CONFIG = 'velpt_user_configuration'
    CLOCK = 'velpt_clock_data'
    BATTERY = 'velpt_battery_voltage'
    ID_STRING = 'velpt_identification_string'


NortekHardwareConfigDataParticle._data_particle_type = NortekDataParticleType.HARDWARE_CONFIG
NortekHeadConfigDataParticle._data_particle_type = NortekDataParticleType.HEAD_CONFIG
NortekUserConfigDataParticle._data_particle_type = NortekDataParticleType.USER_CONFIG
NortekEngBatteryDataParticle._data_particle_type = NortekDataParticleType.BATTERY
NortekEngIdDataParticle._data_particle_type = NortekDataParticleType.ID_STRING
NortekEngClockDataParticle._data_particle_type = NortekDataParticleType.CLOCK


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
        Take the velocity data sample and parse it into values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        log.debug('AquadoppDwVelocityDataParticle: raw data =%r', self.raw_data)
        match = VELOCITY_DATA_REGEX.match(self.raw_data)

        if not match:
            raise SampleException("AquadoppDwVelocityDataParticle: No regex match of parsed sample data: [%s]" % self.raw_data)

        result = self._build_particle(match)
        log.debug('AquadoppDwVelocityDataParticle: particle=%s', result)
        return result

    def _build_particle(self, match):
        """
        Build a particle.  Used for parsing Velocity
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
    NortekInstrumentProtocol.velocity_data_regex.append(VELOCITY_DATA_REGEX)
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
        log.debug("_got_chunk: structure: %r", structure)

        self._extract_sample(AquadoppDwVelocityDataParticle, VELOCITY_DATA_REGEX, structure, timestamp)
        self._got_chunk_base(structure, timestamp)

    def _build_param_dict(self):
        """
        Overwrite base classes method.
        Creates base class's param dictionary, then sets parameter values for those specific to this instrument.
        """
        NortekInstrumentProtocol._build_param_dict(self)

        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(4),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Transmit Pulse Length",
                                   default_value=125,
                                   units=ParameterUnits.CENTIMETERS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                                   r'^.{%s}(.{2}).*' % str(6),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Blanking Distance",
                                   default_value=49,
                                   units=ParameterUnits.CENTIMETERS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(8),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Receive Length",
                                   default_value=32,
                                   units=ParameterUnits.CENTIMETERS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                                   r'^.{%s}(.{2}).*' % str(10),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Time Between Pings",
                                   units=ParameterUnits.CENTIMETERS,
                                   default_value=437,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                                   r'^.{%s}(.{2}).*' % str(12),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Time Between Burst Sequences",
                                   default_value=512,
                                   units=None,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_PINGS,
                                   r'^.{%s}(.{2}).*' % str(14),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Pings",
                                   default_value=1,
                                   units=ParameterUnits.HERTZ,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                                   r'^.{%s}(.{2}).*' % str(16),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Average Interval",
                                   default_value=60,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                                   r'^.{%s}(.{2}).*' % str(18),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="User Number Beams",
                                   direct_access=True,
                                   value=3)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                                   r'^.{%s}(.{2}).*' % str(20),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Timing Control Register",
                                   direct_access=True,
                                   value=130)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                                   r'^.{%s}(.{2}).*' % str(22),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Power Control Register",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.A1_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(24),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="A1 1 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.B0_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(26),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="B0 1 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.B1_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(28),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="B1 1 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                                   r'^.{%s}(.{2}).*' % str(30),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Compass Update Rate",
                                   default_value=1,
                                   units=ParameterUnits.HERTZ,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                                   r'^.{%s}(.{2}).*' % str(32),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Coordinate System",
                                   description='Coordinate System (0=ENU, 1=XYZ, 2=BEAM)',
                                   default_value=2,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_BINS,
                                   r'^.{%s}(.{2}).*' % str(34),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Bins",
                                   default_value=1,
                                   units=ParameterUnits.METERS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.BIN_LENGTH,
                                   r'^.{%s}(.{2}).*' % str(36),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Bin Length",
                                   default_value=7,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                                   r'^.{%s}(.{2}).*' % str(38),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Measurement Interval",
                                   default_value=60,
                                   units=ParameterUnits.SECONDS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                                   r'^.{%s}(.{6}).*' % str(40),
                                   lambda match: NortekProtocolParameterDict.convert_bytes_to_string(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Deployment Name",
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.WRAP_MODE,
                                   r'^.{%s}(.{2}).*' % str(46),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Wrap Mode",
                                   description='Recorder wrap mode (0=NO WRAP, 1=WRAP WHEN FULL)',
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                                   r'^.{%s}(.{6}).*' % str(48),
                                   lambda match: NortekProtocolParameterDict.convert_words_to_datetime(match.group(1)),
                                   NortekProtocolParameterDict.convert_datetime_to_words,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.LIST,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Clock Deploy",
                                   description='Deployment start time.',
                                   default_value=[0, 0, 0, 0, 0, 0],
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                                   r'^.{%s}(.{4}).*' % str(54),
                                   lambda match: NortekProtocolParameterDict.convert_double_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.double_word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Diagnostic Interval",
                                   description='Number of seconds between diagnostics measurements.',
                                   default_value=11250,
                                   startup_param=True,
                                   units=ParameterUnits.SECONDS,
                                   direct_access=True)
        self._param_dict.add(Parameter.MODE,
                                   r'^.{%s}(.{2}).*' % str(58),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Mode",
                                   default_value=48,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                                   r'^.{%s}(.{2}).*' % str(60),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Adjustment Sound Speed",
                                   description='User input sound speed adjustment factor.',
                                   units=ParameterUnits.METERS_PER_SECOND,
                                   default_value=1525,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(62),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Samples Diagnostic",
                                   description='Samples in diagnostics mode.',
                                   default_value=20,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(64),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Beams Cell Diagnostic",
                                   description='Beams/cell number to measure in diagnostics mode',
                                   default_value=1,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                                   r'^.{%s}(.{2}).*' % str(66),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Pings Diagnostic",
                                   description='Pings in diagnostics/wave mode.',
                                   default_value=1,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.MODE_TEST,
                                   r'^.{%s}(.{2}).*' % str(68),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Mode Test",
                                   default_value=4,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                                   r'^.{%s}(.{2}).*' % str(70),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Analog Input Address",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.SW_VERSION,
                                   r'^.{%s}(.{2}).*' % str(72),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Software Version",
                                   default_value=13902,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.USER_1_SPARE,
                                   r'^.{%s}(.{2}).*' % str(74),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="User 1 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                                   r'^.{%s}(.{180}).*' % str(76),
                                   lambda match: base64.b64encode(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_WRITE,
                                   display_name="Velocity Adj Table",
                                   units=ParameterUnits.PARTS_PER_TRILLION,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.COMMENTS,
                                   r'^.{%s}(.{180}).*' % str(256),
                                   lambda match: NortekProtocolParameterDict.convert_bytes_to_string(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Comments",
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                                   r'^.{%s}(.{2}).*' % str(436),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Wave Measurement Mode",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                                   r'^.{%s}(.{2}).*' % str(438),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Dyn Percentage Position",
                                   description='Percentage for wave cell positioning.',
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                                   r'^.{%s}(.{2}).*' % str(440),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Wave Transmit Pulse",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                                   r'^.{%s}(.{2}).*' % str(442),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Fixed Wave Blanking Distance",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                                   r'^.{%s}(.{2}).*' % str(444),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Wave Measurement Cell Size",
                                   default_value=0,
                                   units=ParameterUnits.METERS,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                                   r'^.{%s}(.{2}).*' % str(446),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number Diag Samples",
                                   description='Number of diagnostics/wave samples.',
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.A1_2_SPARE,
                                   r'^.{%s}(.{2}).*' % str(448),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="A1 2 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.B0_2_SPARE,
                                   r'^.{%s}(.{2}).*' % str(450),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="B0 2 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.NUMBER_SAMPLES_PER_BURST,
                                   r'^.{%s}(.{2}).*' % str(452),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   expiration=None,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Number of Samples per Burst",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.USER_2_SPARE,
                                   r'^.{%s}(.{2}).*' % str(454),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="User 2 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                                   r'^.{%s}(.{2}).*' % str(456),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Analog Output Scale Factor",
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
                                   r'^.{%s}(.{2}).*' % str(458),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Correlation Threshold",
                                   description='Correlation threshold for resolving ambiguities.',
                                   default_value=0,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.USER_3_SPARE,
                                   r'^.{%s}(.{2}).*' % str(460),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="User 3 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                                   r'^.{%s}(.{2}).*' % str(462),
                                   lambda match: NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                                   NortekProtocolParameterDict.word_to_string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.INT,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Transmit Pulse Length Second Lag",
                                   default_value=2,
                                   startup_param=True,
                                   direct_access=True)
        self._param_dict.add(Parameter.USER_4_SPARE,
                                   r'^.{%s}(.{30}).*' % str(464),
                                   lambda match: match.group(1).encode('hex'),
                                   lambda string: string.decode('hex'),
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.READ_ONLY,
                                   display_name="User 4 Spare",
                                   description='Not used.')
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                                   r'^.{%s}(.{16}).*' % str(494),
                                   lambda match: base64.b64encode(match.group(1)),
                                   lambda string: string,
                                   regex_flags=re.DOTALL,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Qual Constants",
                                   description='Stage match filter constants.',
                                   startup_param=True,
                                   direct_access=True)