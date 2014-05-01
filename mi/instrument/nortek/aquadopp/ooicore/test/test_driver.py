"""
@package mi.instrument.nortek.aquadopp.ooicore.test.test_driver
@author Rachel Manoni
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a QUAL
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import unittest
import re
import time
import datetime
import base64

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.instrument_driver import DriverConnectionState, ResourceAgentEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import SampleException

from mi.instrument.nortek.aquadopp.ooicore.driver import DataParticleType
from mi.instrument.nortek.aquadopp.ooicore.driver import Protocol
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticHeaderDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticHeaderDataParticleKey
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticleKey
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticDataParticle

from interface.objects import AgentCommand
from interface.objects import CapabilityType

from mi.instrument.nortek.test.test_driver import NortekUnitTest, NortekIntTest, NortekQualTest
from mi.instrument.nortek.driver import Parameter, ProtocolState, ProtocolEvent, ID_DATA_PATTERN

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.aquadopp.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='nortek_aquadopp_dw_ooicore',
    instrument_agent_name='nortek_aquadopp_dw_ooicore_agent',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={Parameter.TRANSMIT_PULSE_LENGTH: 0x7d})

params_dict = {
    Parameter.TRANSMIT_PULSE_LENGTH: int,
    Parameter.BLANKING_DISTANCE: int,
    Parameter.RECEIVE_LENGTH: int,
    Parameter.TIME_BETWEEN_PINGS: int,
    Parameter.TIME_BETWEEN_BURST_SEQUENCES: int,
    Parameter.NUMBER_PINGS: int,
    Parameter.AVG_INTERVAL: int,
    Parameter.USER_NUMBER_BEAMS: int,
    Parameter.TIMING_CONTROL_REGISTER: int,
    Parameter.POWER_CONTROL_REGISTER: int,
    Parameter.COMPASS_UPDATE_RATE: int,
    Parameter.COORDINATE_SYSTEM: int,
    Parameter.NUMBER_BINS: int,
    Parameter.BIN_LENGTH: int,
    Parameter.MEASUREMENT_INTERVAL: int,
    Parameter.DEPLOYMENT_NAME: str,
    Parameter.WRAP_MODE: int,
    Parameter.CLOCK_DEPLOY: str,
    Parameter.DIAGNOSTIC_INTERVAL: int,
    Parameter.MODE: int,
    Parameter.ADJUSTMENT_SOUND_SPEED: int,
    Parameter.NUMBER_SAMPLES_DIAGNOSTIC: int,
    Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC: int,
    Parameter.NUMBER_PINGS_DIAGNOSTIC: int,
    Parameter.MODE_TEST: int,
    Parameter.ANALOG_INPUT_ADDR: int,
    Parameter.SW_VERSION: int,
    Parameter.VELOCITY_ADJ_TABLE: str,
    Parameter.COMMENTS: str,
    Parameter.WAVE_MEASUREMENT_MODE: int,
    Parameter.DYN_PERCENTAGE_POSITION: int,
    Parameter.WAVE_TRANSMIT_PULSE: int,
    Parameter.WAVE_BLANKING_DISTANCE: int,
    Parameter.WAVE_CELL_SIZE: int,
    Parameter.NUMBER_DIAG_SAMPLES: int,
    Parameter.ANALOG_OUTPUT_SCALE: int,
    Parameter.CORRELATION_THRESHOLD: int,
    Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG: int,
    Parameter.QUAL_CONSTANTS: str}


def user_config1():
    # CompassUpdateRate = 600, MeasurementInterval = 600
    user_config_values = "A5 00 00 01 7D 00 37 00 20 00 B5 01 00 02 01 00 \
                          3C 00 03 00 00 00 00 00 00 00 00 00 00 00 58 02 \
                          00 00 01 00 20 00 58 02 00 00 00 00 00 00 00 00 \
                          59 12 03 14 12 08 C0 A8 00 00 20 00 11 41 14 00 \
                          01 00 14 00 04 00 00 00 00 00 5E 01 02 3D 1E 3D \
                          39 3D 53 3D 6E 3D 88 3D A2 3D BB 3D D4 3D ED 3D \
                          06 3E 1E 3E 36 3E 4E 3E 65 3E 7D 3E 93 3E AA 3E \
                          C0 3E D6 3E EC 3E 02 3F 17 3F 2C 3F 41 3F 55 3F \
                          69 3F 7D 3F 91 3F A4 3F B8 3F CA 3F DD 3F F0 3F \
                          02 40 14 40 26 40 37 40 49 40 5A 40 6B 40 7C 40 \
                          8C 40 9C 40 AC 40 BC 40 CC 40 DB 40 EA 40 F9 40 \
                          08 41 17 41 25 41 33 41 42 41 4F 41 5D 41 6A 41 \
                          78 41 85 41 92 41 9E 41 AB 41 B7 41 C3 41 CF 41 \
                          DB 41 E7 41 F2 41 FD 41 08 42 13 42 1E 42 28 42 \
                          33 42 3D 42 47 42 51 42 5B 42 64 42 6E 42 77 42 \
                          80 42 89 42 91 42 9A 42 A2 42 AA 42 B2 42 BA 42 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 1E 00 5A 00 5A 00 BC 02 \
                          32 00 00 00 00 00 00 00 07 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 1E 00 00 00 00 00 2A 00 00 00 \
                          02 00 14 00 EA 01 14 00 EA 01 0A 00 05 00 00 00 \
                          40 00 40 00 02 00 0F 00 5A 00 00 00 01 00 C8 00 \
                          00 00 00 00 0F 00 EA 01 EA 01 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 06 00 \
                          14 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \
                          00 00 00 00 00 00 00 00 00 00 00 00 00 00 0A FF \
                          CD FF 8B 00 E5 00 EE 00 0B 00 84 FF 3D FF 82 8E"
    user_config = ''
    for value in user_config_values.split():
        user_config += chr(int(value, 16))
    return user_config


def user_config2():
    # CompassUpdateRate = 2, MeasurementInterval = 3600
    user_config_values = [0xa5, 0x00, 0x00, 0x01, 0x7d, 0x00, 0x37, 0x00, 0x20, 0x00, 0xb5, 0x01, 0x00, 0x02, 0x01, 0x00, 
                          0x3c, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 
                          0x01, 0x00, 0x01, 0x00, 0x20, 0x00, 0x10, 0x0e, 0x74, 0x65, 0x73, 0x74, 0x00, 0x00, 0x01, 0x00, 
                          0x56, 0x07, 0x08, 0x10, 0x12, 0x08, 0xc0, 0xa8, 0x00, 0x00, 0x22, 0x00, 0x11, 0x41, 0x14, 0x00, 
                          0x01, 0x00, 0x14, 0x00, 0x04, 0x00, 0x00, 0x00, 0xe8, 0x35, 0x5e, 0x01, 0x02, 0x3d, 0x1e, 0x3d, 
                          0x39, 0x3d, 0x53, 0x3d, 0x6e, 0x3d, 0x88, 0x3d, 0xa2, 0x3d, 0xbb, 0x3d, 0xd4, 0x3d, 0xed, 0x3d, 
                          0x06, 0x3e, 0x1e, 0x3e, 0x36, 0x3e, 0x4e, 0x3e, 0x65, 0x3e, 0x7d, 0x3e, 0x93, 0x3e, 0xaa, 0x3e, 
                          0xc0, 0x3e, 0xd6, 0x3e, 0xec, 0x3e, 0x02, 0x3f, 0x17, 0x3f, 0x2c, 0x3f, 0x41, 0x3f, 0x55, 0x3f, 
                          0x69, 0x3f, 0x7d, 0x3f, 0x91, 0x3f, 0xa4, 0x3f, 0xb8, 0x3f, 0xca, 0x3f, 0xdd, 0x3f, 0xf0, 0x3f, 
                          0x02, 0x40, 0x14, 0x40, 0x26, 0x40, 0x37, 0x40, 0x49, 0x40, 0x5a, 0x40, 0x6b, 0x40, 0x7c, 0x40, 
                          0x8c, 0x40, 0x9c, 0x40, 0xac, 0x40, 0xbc, 0x40, 0xcc, 0x40, 0xdb, 0x40, 0xea, 0x40, 0xf9, 0x40, 
                          0x08, 0x41, 0x17, 0x41, 0x25, 0x41, 0x33, 0x41, 0x42, 0x41, 0x4f, 0x41, 0x5d, 0x41, 0x6a, 0x41, 
                          0x78, 0x41, 0x85, 0x41, 0x92, 0x41, 0x9e, 0x41, 0xab, 0x41, 0xb7, 0x41, 0xc3, 0x41, 0xcf, 0x41, 
                          0xdb, 0x41, 0xe7, 0x41, 0xf2, 0x41, 0xfd, 0x41, 0x08, 0x42, 0x13, 0x42, 0x1e, 0x42, 0x28, 0x42, 
                          0x33, 0x42, 0x3d, 0x42, 0x47, 0x42, 0x51, 0x42, 0x5b, 0x42, 0x64, 0x42, 0x6e, 0x42, 0x77, 0x42, 
                          0x80, 0x42, 0x89, 0x42, 0x91, 0x42, 0x9a, 0x42, 0xa2, 0x42, 0xaa, 0x42, 0xb2, 0x42, 0xba, 0x42, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x5a, 0x00, 0x5a, 0x00, 0xbc, 0x02, 
                          0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2a, 0x00, 0x00, 0x00, 
                          0x02, 0x00, 0x14, 0x00, 0xea, 0x01, 0x14, 0x00, 0xea, 0x01, 0x0a, 0x00, 0x05, 0x00, 0x00, 0x00, 
                          0x40, 0x00, 0x40, 0x00, 0x02, 0x00, 0x0f, 0x00, 0x5a, 0x00, 0x00, 0x00, 0x01, 0x00, 0xc8, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x0f, 0x00, 0xea, 0x01, 0xea, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 
                          0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0xff, 
                          0xcd, 0xff, 0x8b, 0x00, 0xe5, 0x00, 0xee, 0x00, 0x0b, 0x00, 0x84, 0xff, 0x3d, 0xff, 0xa8, 0x98]
    user_config = ''
    for value in user_config_values:
        user_config += chr(value)
    return user_config


# velocity data particle & sample 
def velocity_sample():
    sample_as_hex = "a5011500101926221211000000009300f83b810628017f01002d0000e3094c0122ff9afe1e1416006093"
    return sample_as_hex.decode('hex')

velocity_particle = [{'value_id': 'timestamp', 'value': '26/11/2012 22:10:19'}, 
                     {'value_id': 'error', 'value': 0}, 
                     {'value_id': 'analog1', 'value': 0}, 
                     {'value_id': 'battery_voltage', 'value': 147}, 
                     {'value_id': 'sound_speed_analog2', 'value': 15352}, 
                     {'value_id': 'heading', 'value': 1665}, 
                     {'value_id': 'pitch', 'value': 296}, 
                     {'value_id': 'roll', 'value': 383}, 
                     {'value_id': 'status', 'value': 45}, 
                     {'value_id': 'pressure', 'value': 0}, 
                     {'value_id': 'temperature', 'value': 2531}, 
                     {'value_id': 'velocity_beam1', 'value': 332}, 
                     {'value_id': 'velocity_beam2', 'value': 65314}, 
                     {'value_id': 'velocity_beam3', 'value': 65178}, 
                     {'value_id': 'amplitude_beam1', 'value': 30}, 
                     {'value_id': 'amplitude_beam2', 'value': 20}, 
                     {'value_id': 'amplitude_beam3', 'value': 22}]


# diagnostic header data particle & sample 
def diagnostic_header_sample():
    sample_as_hex = "a5061200140001000000000011192622121100000000000000000000000000000000a108"
    return sample_as_hex.decode('hex')

diagnostic_header_particle = [{'value_id': 'records', 'value': 20}, 
                              {'value_id': 'cell', 'value': 1}, 
                              {'value_id': 'noise1', 'value': 0}, 
                              {'value_id': 'noise2', 'value': 0}, 
                              {'value_id': 'noise3', 'value': 0}, 
                              {'value_id': 'noise4', 'value': 0}, 
                              {'value_id': 'processing_magnitude_beam1', 'value': 6417}, 
                              {'value_id': 'processing_magnitude_beam2', 'value': 8742}, 
                              {'value_id': 'processing_magnitude_beam3', 'value': 4370}, 
                              {'value_id': 'processing_magnitude_beam4', 'value': 0}, 
                              {'value_id': 'distance1', 'value': 0}, 
                              {'value_id': 'distance2', 'value': 0}, 
                              {'value_id': 'distance3', 'value': 0}, 
                              {'value_id': 'distance4', 'value': 0}]


# diagnostic data particle & sample 
def diagnostic_sample():
    sample_as_hex = "a5801500112026221211000000009300f83ba0065c0189fe002c0000e40904ffd8ffbdfa18131500490f"
    return sample_as_hex.decode('hex')

diagnostic_particle = [{'value_id': 'timestamp', 'value': '26/11/2012 22:11:20'}, 
                       {'value_id': 'error', 'value': 0}, 
                       {'value_id': 'analog1', 'value': 0}, 
                       {'value_id': 'battery_voltage', 'value': 147}, 
                       {'value_id': 'sound_speed_analog2', 'value': 15352}, 
                       {'value_id': 'heading', 'value': 1696}, 
                       {'value_id': 'pitch', 'value': 348}, 
                       {'value_id': 'roll', 'value': 65161}, 
                       {'value_id': 'status', 'value': 44}, 
                       {'value_id': 'pressure', 'value': 0}, 
                       {'value_id': 'temperature', 'value': 2532}, 
                       {'value_id': 'velocity_beam1', 'value': 65284}, 
                       {'value_id': 'velocity_beam2', 'value': 65496}, 
                       {'value_id': 'velocity_beam3', 'value': 64189}, 
                       {'value_id': 'amplitude_beam1', 'value': 24},                        
                       {'value_id': 'amplitude_beam2', 'value': 19}, 
                       {'value_id': 'amplitude_beam3', 'value': 21}]


#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################
###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(NortekUnitTest):
    def setUp(self):
        NortekUnitTest.setUp(self)

    def test_driver_enums(self):
        """
        Verify driver specific enums have no duplicates
        Base unit test driver will test enums specific for the base class.
        """
        self.assert_enum_has_no_duplicates(DataParticleType())

    def test_diagnostic_header_sample_format(self):
        """
        Verify driver can get diagnostic_header sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
        """
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.DIAGNOSTIC_HEADER,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: diagnostic_header_particle}
        
        self.compare_parsed_data_particle(AquadoppDwDiagnosticHeaderDataParticle,
                                          diagnostic_header_sample(),
                                          expected_particle)

    def test_diagnostic_sample_format(self):
        """
        Verify driver can get diagnostic sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
        """
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.DIAGNOSTIC,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: diagnostic_particle}
        
        self.compare_parsed_data_particle(AquadoppDwDiagnosticDataParticle,
                                          diagnostic_sample(),
                                          expected_particle)

    def test_velocity_sample_format(self):
        """
        Verify driver can get velocity sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
        """
        
        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.VELOCITY,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: velocity_particle}
        
        self.compare_parsed_data_particle(AquadoppDwVelocityDataParticle,
                                          velocity_sample(),
                                          expected_particle)

    def test_chunker(self):
        """
        Verify the chunker can parse each sample type
        1. complete data structure
        2. fragmented data structure
        3. combined data structure
        4. data structure with noise
        """
        chunker = StringChunker(Protocol.chunker_sieve_function)

        # test complete data structures
        self.assert_chunker_sample(chunker, velocity_sample())
        self.assert_chunker_sample(chunker, diagnostic_sample())
        self.assert_chunker_sample(chunker, diagnostic_header_sample())

        # test fragmented data structures
        self.assert_chunker_fragmented_sample(chunker, velocity_sample())
        self.assert_chunker_fragmented_sample(chunker, diagnostic_sample())
        self.assert_chunker_fragmented_sample(chunker, diagnostic_header_sample())

        # test combined data structures
        self.assert_chunker_combined_sample(chunker, velocity_sample())
        self.assert_chunker_combined_sample(chunker, diagnostic_sample())
        self.assert_chunker_combined_sample(chunker, diagnostic_header_sample())

        # test data structures with noise
        self.assert_chunker_sample_with_noise(chunker, velocity_sample())
        self.assert_chunker_sample_with_noise(chunker, diagnostic_sample())
        self.assert_chunker_sample_with_noise(chunker, diagnostic_header_sample())

    def test_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, an exception is raised
        """
        particle = AquadoppDwDiagnosticHeaderDataParticle(diagnostic_header_sample().replace(chr(0), chr(1), 1),
                        port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
        particle = AquadoppDwDiagnosticDataParticle(diagnostic_sample().replace(chr(0), chr(1), 1),
                        port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
        particle = AquadoppDwVelocityDataParticle(velocity_sample().replace(chr(0), chr(1), 1),
                        port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

 
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(NortekIntTest):
    
    def setUp(self):
        NortekIntTest.setUp(self)


    def test_instrument_read_id(self):
        """
        Test for reading ID, need to be implemented int the child class because each ID is unique to the
        instrument.
        """
        self.assert_initialize_driver()

        # command the instrument to read the ID.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_ID)

        log.debug("read ID returned: %s", response)
        self.assertTrue(re.search(r'AQD 8493.*', response[1]))

        self.assert_driver_command(ProtocolEvent.READ_ID, regex=ID_DATA_PATTERN)
 
    def test_set_init_params(self):
        """
        @brief Test for set_init_params()
        """
        self.assert_initialize_driver()

        values_before = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)        
        #print("vb=%s" %values_before)
        
        self.driver_client.cmd_dvr('set_init_params', {DriverParameter.ALL: base64.b64encode(user_config1())})
        self.driver_client.cmd_dvr("apply_startup_params") 

        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)
        #print("va=%s" %values_after)
        
        # check to see if startup config got set in instrument
        self.assertEquals(values_after[Parameter.MEASUREMENT_INTERVAL], 600)
        self.assertEquals(values_after[Parameter.COMPASS_UPDATE_RATE], 600)

        self.driver_client.cmd_dvr('set_resource', values_before)
        values_reset = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertEquals(values_reset, values_before)

    def test_startup_configuration(self):
        """
        Test that the startup configuration is applied correctly
        """
        self.put_driver_in_command_mode()

        value_before = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])
    
        self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])

        self.assertEquals(reply, {Parameter.TRANSMIT_PULSE_LENGTH: 0x7d})

        reply = self.driver_client.cmd_dvr('set_resource', value_before)

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.TRANSMIT_PULSE_LENGTH])

        self.assertEquals(reply, value_before)

    def test_instrument_set_configuration(self):
        """
        @brief Test for setting instrument configuration
        """
        
        self.put_driver_in_command_mode()
        
        # command the instrument to set the user configuration.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SET_CONFIGURATION, user_configuration=base64.b64encode(user_config2()))
        
        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)
        #print("va=%s" %values_after)
        
        # check to see if config got set in instrument
        self.assertEquals(values_after[Parameter.MEASUREMENT_INTERVAL], 3600)
        self.assertEquals(values_after[Parameter.COMPASS_UPDATE_RATE], 2)

    def test_instrument_set(self):
        """
        @brief Test for setting instrument parameter
        """
        self.put_driver_in_command_mode()

        # Get all device parameters. Confirm all expected keys are retrieved
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDictionariesEqual(reply, params_dict, True)

        # Grab a subset of parameters.
        params = [
            Parameter.WRAP_MODE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        #self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        new_wrap_mode = 1 if orig_params[Parameter.WRAP_MODE]==0 else 0
        log.debug('old=%d, new=%d' %(orig_params[Parameter.WRAP_MODE], new_wrap_mode))
        new_params = {
            Parameter.WRAP_MODE : new_wrap_mode
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(new_params[Parameter.WRAP_MODE], reply[Parameter.WRAP_MODE])

        # Reset parameter to original value and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(orig_params[Parameter.WRAP_MODE], reply[Parameter.WRAP_MODE])

        # set wrap_mode to 1 to leave instrument with wrap mode enabled
        new_params = {
            Parameter.WRAP_MODE : 1,
            Parameter.AVG_INTERVAL : 60,
            Parameter.DIAGNOSTIC_INTERVAL : 43200
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.WRAP_MODE, Parameter.AVG_INTERVAL, Parameter.DIAGNOSTIC_INTERVAL])
        self.assertEqual(new_params, reply)
        
    def test_instrument_acquire_sample(self):
        """
        Test acquire sample command and events.
        """

        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # wait for some samples to be generated
        gevent.sleep(100)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d', len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 4)
               
    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        with self.assertRaises(InstrumentCommandException):
            self.driver_client.cmd_dvr('bogus_command')

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = 'not a config dict'            
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG.pop('addr')
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG['addr'] = ''
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
        
        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
                
        self.driver_client.cmd_dvr('discover_state')

        try:
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)
        except:
            self.assertEqual(self.protocol_state, ProtocolState.AUTOSAMPLE)
            # Put the driver in command mode
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('connect')
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.ADJUSTMENT_SOUND_SPEED]
            self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name': 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.ADJUSTMENT_SOUND_SPEED: 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(NortekQualTest):
    def setUp(self):
        NortekQualTest.setUp(self)
    
    def assert_execute_resource(self, command):
        """
        @brief send an execute_resource command and ensure no exceptions are raised
        """
        
        # send command to the instrument 
        cmd = AgentCommand(command=ResourceAgentEvent.EXECUTE_RESOURCE,
                           args=[command])
        try:            
            return self.instrument_agent_client.execute_agent(cmd)
        except:
            self.fail('assert_execute_resource: execute_resource command failed for %s' %command)

    def assert_resource_capabilities(self, capabilities):

        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @return res_cmds, res_pars
            '''
            res_cmds = []
            res_pars = []

            if(not capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)):
                capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)):
                capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

            res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
            res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            return res_cmds, res_pars

        retval = self.instrument_agent_client.get_capabilities()
        res_cmds, res_pars = sort_capabilities(retval)

        log.debug("Resource Commands: %s " % sorted(res_cmds))
        log.debug("Expected Resource Commands: %s " % sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)))
        
        log.debug("Resource Parameters: %s " % sorted(res_pars))
        log.debug("Expected Resource Parameters: %s " % sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)))

        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)), sorted(res_cmds), "commands don't match")
        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)), sorted(res_pars), "parameters don't match")

    def assert_sample_polled(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test observatory polling function.

        Verifies the acquire_status command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        ###
        # Poll for a sample
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        log.debug("Acquire Sample")
        self.data_subscribers.clear_sample_queue(sampleQueue)

        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Watch the parsed data queue and return once a sample
        # has been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sampleQueue, 4, timeout = timeout)
        self.assertGreaterEqual(len(samples), 4)
        log.error("SAMPLE: %s" % samples)

        # Verify
        for sample in samples:
            sampleDataAssert(sample)

        self.assert_reset()
        self.doCleanups()

    def assertSampleDataParticle(self, sample):
        log.debug('assertSampleDataParticle: sample=%s' %sample)
        self.assertTrue(sample[DataParticleKey.STREAM_NAME],
            DataParticleType.PARSED)
        self.assertTrue(sample[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample.get(DataParticleKey.PREFERRED_TIMESTAMP))
        
        values = sample['values']
        value_ids = []
        for value in values:
            value_ids.append(value['value_id'])
        if AquadoppDwVelocityDataParticleKey.TIMESTAMP in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwVelocityDataParticle/AquadoppDwDiagnosticDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwVelocityDataParticleKey.list()))
            for value in values:
                if value['value_id'] == AquadoppDwVelocityDataParticleKey.TIMESTAMP:
                    self.assertTrue(isinstance(value['value'], str))
                else:
                    self.assertTrue(isinstance(value['value'], int))
        elif AquadoppDwDiagnosticHeaderDataParticleKey.RECORDS in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwDiagnosticHeaderDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwDiagnosticHeaderDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value['value'], int))
        else:
            self.fail('Unknown data particle')



    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        #OVERRIDEN THE BASE CLASSES BECAUSE EXCPET IS DIFFERENT!!!!
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("K1W%!Q")
        self.tcp_client.expect("DW-AQUADOPP")

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        poll for a single sample
        '''

        self.assert_sample_polled(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_get_set_parameters(self):
        '''
        verify that parameters can be get set properly
        '''
        self.assert_enter_command_mode()
        
        value_before_set = self.get_parameter(Parameter.BLANKING_DISTANCE)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 40)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, value_before_set)

        value_before_set = self.get_parameter(Parameter.AVG_INTERVAL)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, 4)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, value_before_set)

        self.assert_reset()

