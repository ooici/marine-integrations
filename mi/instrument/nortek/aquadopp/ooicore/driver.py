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

from mi.core.common import BaseEnum

from mi.core.exceptions import SampleException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.instrument.nortek.driver import NortekInstrumentProtocol, InstrumentPrompts, NortekProtocolParameterDict
from mi.instrument.nortek.driver import NortekParameterDictVal, Parameter, NortekInstrumentDriver, NEWLINE

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType

VELOCITY_DATA_LEN = 42
VELOCITY_DATA_SYNC_BYTES = '\xa5\x01\x15\x00'

VELOCITY_DATA_PATTERN = r'%s(.{6})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{1})(.{1})(.{2})(.{2})' \
                        r'(.{2})(.{2})(.{2})(.{1})(.{1})(.{1})(.{3})' % VELOCITY_DATA_SYNC_BYTES
VELOCITY_DATA_REGEX = re.compile(VELOCITY_DATA_PATTERN, re.DOTALL)

AQUADOPP_SAMPLE_REGEX = [VELOCITY_DATA_REGEX]


class DataParticleType(BaseEnum):
    """
    List of data particles.  Names match those in the IOS, so need to overwrite definition in base class
    """
    VELOCITY = 'velocity'

###############################################################################
# Data particles
###############################################################################
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

    def _build_parsed_values(self):
        """
        Take the velocity data sample and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
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
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        super(Protocol, self).__init__(prompts, newline, driver_event)

        self.velocity_data_regex.extend(AQUADOPP_SAMPLE_REGEX)
        self.velocity_sync_bytes = VELOCITY_DATA_SYNC_BYTES

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
        #TODO - THIS WILL NEED TO BE UPDATED ONCE THE IOS IS FINISHED!
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
                                   display_name="number samples per burst"))