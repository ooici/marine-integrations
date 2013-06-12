"""
@package mi.instrument.nortek.driver
@file mi/instrument/nortek/driver.py
@author Bill Bollenbacher
@author Steve Foley
@brief Base class for Nortek instruments
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import re
import time
import copy
import base64

from mi.core.log import get_logger ; log = get_logger()

from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.instrument.instrument_protocol import InstrumentProtocol
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import RegexParameter

from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import ReadOnlyException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException

from mi.core.time import get_timestamp_delayed
from mi.core.common import InstErrorCode, BaseEnum

# newline.
NEWLINE = '\n\r'

# default timeout.
TIMEOUT = 10
# set up the 'structure' lengths (in bytes) and sync/id/size constants   
USER_CONFIG_LEN = 512
USER_CONFIG_SYNC_BYTES = '\xa5\x00\x00\x01'
HW_CONFIG_LEN = 48
HW_CONFIG_SYNC_BYTES   = '\xa5\x05\x18\x00'
HEAD_CONFIG_LEN = 224
HEAD_CONFIG_SYNC_BYTES = '\xa5\x04\x70\x00'
CHECK_SUM_SEED = 0xb58c
FAT_LENGTH = 512

HARDWARE_CONFIG_DATA_PATTERN = r'%s(.{14})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{12})(.{4})(.{2})' % HW_CONFIG_SYNC_BYTES
HARDWARE_CONFIG_DATA_REGEX = re.compile(HARDWARE_CONFIG_DATA_PATTERN, re.DOTALL)
HEAD_CONFIG_DATA_PATTERN = r'%s(.{2})(.{2})(.{2})(.{12})(.{176})(.{22})(.{2})(.{2})' % HEAD_CONFIG_SYNC_BYTES
HEAD_CONFIG_DATA_REGEX = re.compile(HEAD_CONFIG_DATA_PATTERN, re.DOTALL)
USER_CONFIG_DATA_PATTERN = r'%s(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{6})(.{2})(.{6})(.{4})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{180})(.{180})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{2})(.{30})(.{16})(.{2})' % USER_CONFIG_SYNC_BYTES
USER_CONFIG_DATA_REGEX = re.compile(USER_CONFIG_DATA_PATTERN, re.DOTALL)

NORTEK_COMMON_SAMPLE_STRUCTS = [[USER_CONFIG_SYNC_BYTES, USER_CONFIG_LEN],
                                [HW_CONFIG_SYNC_BYTES, HW_CONFIG_LEN],
                                [HEAD_CONFIG_SYNC_BYTES, HEAD_CONFIG_LEN]]
# Device prompts.
class InstrumentPrompts(BaseEnum):
    """
    vector prompts.
    """
    COMMAND_MODE  = 'Command mode'
    CONFIRMATION  = 'Confirm:'
    Z_ACK         = '\x06\x06'  # attach a 'Z' to the front of these two items to force them to the end of the list
    Z_NACK        = '\x15\x15'  # so the other responses will have priority to be detected if they are present

    
class InstrumentCmds(BaseEnum):
    CONFIGURE_INSTRUMENT               = 'CC'        # sets the user configuration
    SOFT_BREAK_FIRST_HALF              = '@@@@@@'
    SOFT_BREAK_SECOND_HALF             = 'K1W%!Q'
    READ_REAL_TIME_CLOCK               = 'RC'        
    SET_REAL_TIME_CLOCK                = 'SC'
    CMD_WHAT_MODE                      = 'II'        # to determine the mode of the instrument
    READ_USER_CONFIGURATION            = 'GC'
    READ_HW_CONFIGURATION              = 'GP'
    READ_HEAD_CONFIGURATION            = 'GH'
    POWER_DOWN                         = 'PD'     
    READ_BATTERY_VOLTAGE               = 'BV'
    READ_ID                            = 'ID'
    START_MEASUREMENT_AT_SPECIFIC_TIME = 'SD'
    START_MEASUREMENT_IMMEDIATE        = 'SR'
    START_MEASUREMENT_WITHOUT_RECORDER = 'ST'
    ACQUIRE_DATA                       = 'AD'
    CONFIRMATION                       = 'MC'        # confirm a break request
    READ_FAT                           = 'RF'
    # SAMPLE_AVG_TIME                    = 'A'
    # SAMPLE_INTERVAL_TIME               = 'M'
    # GET_ALL_CONFIGURATIONS             = 'GA'
    # GET_USER_CONFIGURATION             = 'GC'
    # SAMPLE_WHAT_MODE                   = 'I'   

class InstrumentModes(BaseEnum):
    FIRMWARE_UPGRADE = '\x00\x00\x06\x06'
    MEASUREMENT      = '\x01\x00\x06\x06'
    COMMAND          = '\x02\x00\x06\x06'
    DATA_RETRIEVAL   = '\x04\x00\x06\x06'
    CONFIRMATION     = '\x05\x00\x06\x06'
    

class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ExportedInstrumentCommand(BaseEnum):
    SET_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_SET_CONFIGURATION"
    READ_CLOCK = "EXPORTED_INSTRUMENT_CMD_READ_CLOCK"
    READ_MODE = "EXPORTED_INSTRUMENT_CMD_READ_MODE"
    POWER_DOWN = "EXPORTED_INSTRUMENT_CMD_POWER_DOWN"
    READ_BATTERY_VOLTAGE = "EXPORTED_INSTRUMENT_CMD_READ_BATTERY_VOLTAGE"
    READ_ID = "EXPORTED_INSTRUMENT_CMD_READ_ID"
    GET_HW_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HW_CONFIGURATION"
    GET_HEAD_CONFIGURATION = "EXPORTED_INSTRUMENT_CMD_GET_HEAD_CONFIGURATION"
    START_MEASUREMENT_AT_SPECIFIC_TIME = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_AT_SPECIFIC_TIME"
    START_MEASUREMENT_IMMEDIATE = "EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_IMMEDIATE"
    READ_FAT = "EXPORTED_INSTRUMENT_CMD_READ_FAT"

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    # common events from base class
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    
    # instrument specific events
    SET_CONFIGURATION = ExportedInstrumentCommand.SET_CONFIGURATION
    READ_CLOCK = ExportedInstrumentCommand.READ_CLOCK
    READ_MODE = ExportedInstrumentCommand.READ_MODE
    POWER_DOWN = ExportedInstrumentCommand.POWER_DOWN
    READ_BATTERY_VOLTAGE = ExportedInstrumentCommand.READ_BATTERY_VOLTAGE
    READ_ID = ExportedInstrumentCommand.READ_ID
    GET_HW_CONFIGURATION = ExportedInstrumentCommand.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ExportedInstrumentCommand.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ExportedInstrumentCommand.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATE = ExportedInstrumentCommand.START_MEASUREMENT_IMMEDIATE
    READ_FAT = ExportedInstrumentCommand.READ_FAT

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    SET_CONFIGURATION = ProtocolEvent.SET_CONFIGURATION
    READ_CLOCK = ProtocolEvent.READ_CLOCK
    READ_MODE = ProtocolEvent.READ_MODE
    POWER_DOWN = ProtocolEvent.POWER_DOWN
    READ_BATTERY_VOLTAGE = ProtocolEvent.READ_BATTERY_VOLTAGE
    READ_ID = ProtocolEvent.READ_ID
    GET_HW_CONFIGURATION = ProtocolEvent.GET_HW_CONFIGURATION
    GET_HEAD_CONFIGURATION = ProtocolEvent.GET_HEAD_CONFIGURATION
    START_MEASUREMENT_AT_SPECIFIC_TIME = ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME
    START_MEASUREMENT_IMMEDIATE = ProtocolEvent.START_MEASUREMENT_IMMEDIATE
    READ_FAT = ProtocolEvent.READ_FAT

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """
    """
    # these are read only and not included for now
    # hardware configuration
    HW_SERIAL_NUMBER = "HardwareSerialNumber"
    HW_CONFIG = "HardwareConfig"
    HW_FREQUENCY = "HardwareFrequency"
    PIC_VERSION = "HardwarePicCodeVerNumber"
    HW_REVISION = "HardwareRevision"
    REC_SIZE = "HardwareRecorderSize"
    STATUS = "HardwareStatus"
    HW_SPARE = 'HardwareSpare'
    FW_VERSION = "HardwareFirmwareVersion"
    
    # head configuration
    HEAD_CONFIG = "HeadConfig"
    HEAD_FREQUENCY = "HeadFrequency"
    HEAD_TYPE = "HeadType"
    HEAD_SERIAL_NUMBER = "HeadSerialNumber"
    HEAD_SYSTEM = 'HeadSystemData'
    HEAD_SPARE = 'HeadSpare'
    HEAD_NUMBER_BEAMS = "HeadNumberOfBeams"

    REAL_TIME_CLOCK = "RealTimeClock"
    BATTERY_VOLTAGE = "BatteryVoltage"
    IDENTIFICATION_STRING = "IdentificationString"
    """
    
    # user configuration
    TRANSMIT_PULSE_LENGTH = "TransmitPulseLength"                # T1
    BLANKING_DISTANCE = "BlankingDistance"                       # T2
    RECEIVE_LENGTH = "ReceiveLength"                             # T3
    TIME_BETWEEN_PINGS = "TimeBetweenPings"                      # T4
    TIME_BETWEEN_BURST_SEQUENCES = "TimeBetweenBurstSequences"   # T5 
    NUMBER_PINGS = "NumberPings"     # number of beam sequences per burst
    AVG_INTERVAL = "AvgInterval"
    USER_NUMBER_BEAMS = "UserNumberOfBeams" 
    TIMING_CONTROL_REGISTER = "TimingControlRegister"
    POWER_CONTROL_REGISTER = "PowerControlRegister"
    A1_1_SPARE = 'A1_1Spare'
    B0_1_SPARE = 'B0_1Spare'
    B1_1_SPARE = 'B1_1Spare'
    COMPASS_UPDATE_RATE ="CompassUpdateRate"  
    COORDINATE_SYSTEM = "CoordinateSystem"
    NUMBER_BINS = "NumberOfBins"      # number of cells
    BIN_LENGTH = "BinLength"          # cell size
    MEASUREMENT_INTERVAL = "MeasurementInterval"
    DEPLOYMENT_NAME = "DeploymentName"
    WRAP_MODE = "WrapMode"
    CLOCK_DEPLOY = "ClockDeploy"      # deployment start time
    DIAGNOSTIC_INTERVAL = "DiagnosticInterval"
    MODE = "Mode"
    ADJUSTMENT_SOUND_SPEED = 'AdjustmentSoundSpeed'
    NUMBER_SAMPLES_DIAGNOSTIC = 'NumberSamplesInDiagMode'
    NUMBER_BEAMS_CELL_DIAGNOSTIC = 'NumberBeamsPerCellInDiagMode'
    NUMBER_PINGS_DIAGNOSTIC = 'NumberPingsInDiagMode'
    MODE_TEST = 'ModeTest'
    ANALOG_INPUT_ADDR = 'AnalogInputAddress'
    SW_VERSION = 'SwVersion'
    USER_1_SPARE = 'User1Spare'
    VELOCITY_ADJ_TABLE = 'VelocityAdjTable'
    COMMENTS = 'Comments'
    WAVE_MEASUREMENT_MODE = 'WaveMeasurementMode'
    DYN_PERCENTAGE_POSITION = 'PercentageForCellPositioning'
    WAVE_TRANSMIT_PULSE = 'WaveTransmitPulse'
    WAVE_BLANKING_DISTANCE = 'WaveBlankingDistance'
    WAVE_CELL_SIZE = 'WaveCellSize'
    NUMBER_DIAG_SAMPLES = 'NumberDiagnosticSamples'
    A1_2_SPARE = 'A1_2Spare'
    B0_2_SPARE = 'B0_2Spare'
    NUMBER_SAMPLES_PER_BURST = 'NumberSamplesPerBurst'
    USER_2_SPARE = 'User2Spare'
    ANALOG_OUTPUT_SCALE = 'AnalogOutputScale'
    CORRELATION_THRESHOLD = 'CorrelationThreshold'
    USER_3_SPARE = 'User3Spare'
    TRANSMIT_PULSE_LENGTH_SECOND_LAG = 'TransmitPulseLengthSecondLag'
    USER_4_SPARE = 'User4Spare'
    QUAL_CONSTANTS = 'StageMatchFilterConstants'
    
    
class NortekHardwareConfigDataParticleKey(BaseEnum):
    SERIAL_NUM = 'instmt_type_serial_number'
    RECORDER_INSTALLED = 'recorder_installed'
    COMPASS_INSTALLED = 'compass_installed'
    BOARD_FREQUENCY = 'board_frequency'
    PIC_VERSION = 'pic_version'
    HW_REVISION = 'hardware_revision'
    RECORDER_SIZE = 'recorder_size'
    VELOCITY_RANGE = 'velocity_range'
    FW_VERSION = 'firmware_version'
        
class NortekHardwareConfigDataParticle(DataParticle):
    """
    Routine for parsing hardware config data into a data particle structure for the Vector sensor. 
    """    

    def _build_parsed_values(self):
        """
        Take something in the hardware config data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = HARDWARE_CONFIG_DATA_REGEX.match(self.raw_data)
        log.debug("match: %s, compared to: %s", match, HARDWARE_CONFIG_DATA_REGEX.match(self.raw_data))
        
        if not match:
            raise SampleException("VectorHardwareConfigDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        # Calculate values ### FIXME
        serial_num = NortekProtocolParameterDict.convert_bytes_to_string(match.group(1))
        bit_field = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(2))
        recorder_installed = bit_field[-1]
        compass_installed = bit_field[-2]
        board_frequency = NortekProtocolParameterDict.convert_word_to_int(match.group(3))
        pic_version = NortekProtocolParameterDict.convert_word_to_int(match.group(4))
        hw_revision = NortekProtocolParameterDict.convert_word_to_int(match.group(5))
        recorder_size = NortekProtocolParameterDict.convert_word_to_int(match.group(6))
        velocity_range = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(7))[-1]
        fw_version = NortekProtocolParameterDict.convert_bytes_to_string(match.group(9))
        checksum = NortekProtocolParameterDict.convert_word_to_int(match.group(10))

        
        #number_of_samples_per_beam = NortekProtocolParameterDict.convert_word_to_int(self.raw_data[self.SAMPLES_PER_BEAM_OFFSET:self.SAMPLES_PER_BEAM_OFFSET+2])
        #log.debug("VectorHardwareConfigDataParticle: samples per beam = %d", number_of_samples_per_beam)
        #first_sample_number = NortekProtocolParameterDict.convert_word_to_int(self.raw_data[self.FIRST_SAMPLE_NUMBER_OFFSET:self.FIRST_SAMPLE_NUMBER_OFFSET+2])
        
        if None == serial_num:
            raise SampleException("No serial number value parsed")
        if None == recorder_installed:
            raise SampleException("No recorder installation value parsed")
        if None == compass_installed:
            raise SampleException("No compass installation value parsed")
        if None == board_frequency:
            raise SampleException("No board frequency value parsed")
        if None == pic_version:
            raise SampleException("No PIC version value parsed")
        if None == hw_revision:
            raise SampleException("No hardware revision value parsed")
        if None == recorder_size:
            raise SampleException("No recorder size value parsed")
        if None == velocity_range:
            raise SampleException("No velocity range value parsed")
        if None == fw_version:
            raise SampleException("No firmware version value parsed")
        
        # report values
        result = [{DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.SERIAL_NUM,
                   DataParticleKey.VALUE: serial_num},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.RECORDER_INSTALLED,
                   DataParticleKey.VALUE: recorder_installed},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.COMPASS_INSTALLED,
                   DataParticleKey.VALUE: compass_installed},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.BOARD_FREQUENCY,
                   DataParticleKey.VALUE: board_frequency},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.PIC_VERSION,
                   DataParticleKey.VALUE: pic_version},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.HW_REVISION,
                   DataParticleKey.VALUE: hw_revision},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.RECORDER_SIZE,
                   DataParticleKey.VALUE: recorder_size},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.VELOCITY_RANGE,
                   DataParticleKey.VALUE: velocity_range},
                  {DataParticleKey.VALUE_ID: NortekHardwareConfigDataParticleKey.FW_VERSION,
                   DataParticleKey.VALUE: fw_version}
                  ]
        
        calculated_checksum = NortekProtocolParameterDict.calculate_checksum(match.group())
        if (checksum != calculated_checksum):
            log.warn("Calculated checksum: %s did not match packet checksum: %s",
                     calculated_checksum, checksum)
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED

        log.debug('VectorHardwareConfigDataParticle: particle=%s' %result)
        return result
            
class NortekHeadConfigDataParticleKey(BaseEnum):
    PRESSURE_SENSOR = 'pressure_sensor'
    MAG_SENSOR = 'magnetometer_sensor'
    TILT_SENSOR = 'tilt_sensor'
    TILT_SENSOR_MOUNT = 'tilt_sensor_mounting'
    HEAD_FREQ = 'head_frequency'
    HEAD_TYPE = 'head_type'
    HEAD_SERIAL = 'head_serial_number'
    SYSTEM_DATA = 'system_data'
    NUM_BEAMS = 'number_beams'

class NortekHeadConfigDataParticle(DataParticle):
    """
    Routine for parsing head config data into a data particle structure for the Vector sensor. 
    """    

    def _build_parsed_values(self):
        """
        Take something in the probe check data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = HEAD_CONFIG_DATA_REGEX.match(self.raw_data)
                
        if not match:
            raise SampleException("VectorHeadConfigDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        # Calculate values ### FIXME
        sensor_bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(1))
        pres_sensor = sensor_bitfield[-1]
        mag_sensor = sensor_bitfield[-2]
        tilt_sensor = sensor_bitfield[-3]
        tilt_sensor_mount = sensor_bitfield[-4]
        head_freq = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        head_type = NortekProtocolParameterDict.convert_word_to_int(match.group(3))
        head_sn = NortekProtocolParameterDict.convert_bytes_to_string(match.group(4))
        system_data = base64.b64encode(match.group(5))
        num_beams = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        checksum = NortekProtocolParameterDict.convert_word_to_int(match.group(8))
                            
        if None == pres_sensor:
            raise SampleException("No pressure sensor value parsed")
        if None == mag_sensor:
            raise SampleException("No magnetometer sensor value parsed")
        if None == tilt_sensor:
            raise SampleException("No tilt sensor value parsed")
        if None == tilt_sensor_mount:
            raise SampleException("No tilt sensor mounting value parsed")
        if None == head_freq:
            raise SampleException("No head frequency value parsed")
        if None == head_type:
            raise SampleException("No head type value parsed")
        if None == head_sn:
            raise SampleException("No head serial number value parsed")
        if None == system_data:
            raise SampleException("No system data value parsed")
        if None == num_beams:
            raise SampleException("No beam number value parsed")
        
        # report values
        result = [{DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.PRESSURE_SENSOR,
                   DataParticleKey.VALUE: pres_sensor},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.MAG_SENSOR,
                   DataParticleKey.VALUE: mag_sensor},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.TILT_SENSOR,
                   DataParticleKey.VALUE: tilt_sensor},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.TILT_SENSOR_MOUNT,
                   DataParticleKey.VALUE: tilt_sensor_mount},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_FREQ,
                   DataParticleKey.VALUE: head_freq},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_TYPE,
                   DataParticleKey.VALUE: head_type},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.HEAD_SERIAL,
                   DataParticleKey.VALUE: head_sn},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.SYSTEM_DATA,
                   DataParticleKey.VALUE: system_data,
                   DataParticleKey.BINARY: True},
                  {DataParticleKey.VALUE_ID: NortekHeadConfigDataParticleKey.NUM_BEAMS,
                   DataParticleKey.VALUE: num_beams}
                  ]
        
        calculated_checksum = NortekProtocolParameterDict.calculate_checksum(match.group())
        if (checksum != calculated_checksum):
            log.warn("Calculated checksum: %s did not match packet checksum: %s",
                     calculated_checksum, checksum)
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED
            
        log.debug('VectorHeadConfigDataParticle: particle=%s' %result)
        return result

class NortekUserConfigDataParticleKey(BaseEnum):
    TX_LENGTH = 'transmit_pulse_length'
    BLANK_DIST = 'blanking_distance'
    RX_LENGTH = 'receive_length'
    TIME_BETWEEN_PINGS = 'time_between_pings'
    TIME_BETWEEN_BURSTS = 'time_between_bursts'
    NUM_PINGS = 'number_pings'
    AVG_INTERVAL = 'average_interval'
    NUM_BEAMS = 'number_beams'
    PROFILE_TYPE = 'profile_type'
    MODE_TYPE = 'mode_type'
    POWER_TCM1 = 'power_level_tcm1'
    POWER_TCM2 = 'power_level_tcm2'
    SYNC_OUT_POSITION = 'sync_out_position'
    SAMPLE_ON_SYNC = 'sample_on_sync'
    START_ON_SYNC = 'start_on_sync'
    POWER_PCR1 = 'power_level_pcr1'
    POWER_PCR2 = 'power_level_pcr2'
    COMPASS_UPDATE_RATE = 'compass_update_rate'
    COORDINATE_SYSTEM = 'coordinate_system'
    NUM_CELLS = 'number_cells'
    CELL_SIZE = 'cell_size'
    MEASUREMENT_INTERVAL = 'measurement_interval'
    DEPLOYMENT_NAME = 'deployment_name'
    WRAP_MODE = 'wrap_moder'
    DEPLOY_START_TIME = 'deployment_start_time'
    DIAG_INTERVAL = 'diagnostics_interval'
    USE_SPEC_SOUND_SPEED = 'use_specified_sound_speed'
    DIAG_MODE_ON = 'diagnostics_mode_enable'
    ANALOG_OUTPUT_ON = 'analog_output_enable'
    OUTPUT_FORMAT = 'output_format_nortek'
    SCALING = 'scaling'
    SERIAL_OUT_ON = 'serial_output_enable'
    STAGE_ON = 'stage_enable'
    ANALOG_POWER_OUTPUT = 'analog_power_output'
    SOUND_SPEED_ADJUST = 'sound_speed_adjust_factor'
    NUM_DIAG_SAMPLES = 'number_diagnostics_samples'
    NUM_BEAMS_PER_CELL = 'number_beams_per_cell'
    NUM_PINGS_DIAG = 'number_pings_diagnostic'
    USE_DSP_FILTER = 'use_dsp_filter'
    FILTER_DATA_OUTPUT = 'filter_data_output'
    ANALOG_INPUT_ADDR = 'analog_input_address'
    SW_VER = 'software_version'
    VELOCITY_ADJ_FACTOR = 'velocity_adjustment_factor'
    FILE_COMMENTS = 'file_comments'
    WAVE_DATA_RATE = 'wave_data_rate'
    WAVE_CELL_POS = 'wave_cell_pos'
    DYNAMIC_POS_TYPE = 'dynamic_position_type'
    PERCENT_WAVE_CELL_POS = 'percent_wave_cell_position'
    WAVE_TX_PULSE = 'wave_transmit_pulse'
    FIX_WAVE_BLANK_DIST = 'fixed_wave_blanking_distance'
    WAVE_CELL_SIZE = 'wave_measurement_cell_size'
    NUM_DIAG_PER_WAVE = 'number_diagnostics_per_wave'
    NUM_SAMPLE_PER_BURST = 'number_samples_per_burst'
    ANALOG_SCALE_FACTOR = 'analog_scale_factor'
    CORRELATION_THRS = 'correlation_threshold'
    TX_PULSE_LEN_2ND = 'transmit_pulse_length_2nd'
    FILTER_CONSTANTS = 'filter_constants'

class NortekUserConfigDataParticle(DataParticle):
    """
    Routine for parsing head config data into a data particle structure for the Vector sensor. 
    """    

    def _build_parsed_values(self):
        """
        Take something in the probe check data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = USER_CONFIG_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("VectorHeadConfigDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        # Calculate values ### FIXME
        working_value = {}
        working_value["tx_length"] = NortekProtocolParameterDict.convert_word_to_int(match.group(1))
        working_value["blank_dist"] = NortekProtocolParameterDict.convert_word_to_int(match.group(2))
        working_value["rx_length"] = NortekProtocolParameterDict.convert_word_to_int(match.group(3))
        working_value["time_between_pings"] = NortekProtocolParameterDict.convert_word_to_int(match.group(4))
        working_value["time_between_bursts"] = NortekProtocolParameterDict.convert_word_to_int(match.group(5))
        working_value["num_pings"] = NortekProtocolParameterDict.convert_word_to_int(match.group(6))
        working_value["avg_interval"] = NortekProtocolParameterDict.convert_word_to_int(match.group(7))
        working_value["num_beams"] = NortekProtocolParameterDict.convert_word_to_int(match.group(8))
        bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(9))
        working_value["profile_type"] = bitfield[-2]
        working_value["mode_type"] = bitfield[-3]
        working_value["power_tcm1"] = bitfield[-6]
        working_value["power_tcm2"] = bitfield[-7]
        working_value["sync_out_position"] = bitfield[-8]
        working_value["sample_on_sync"] = bitfield[-9]
        working_value["start_on_sync"] = bitfield[-10]
        bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(10))        
        working_value["power_pcr1"] = bitfield[-6]
        working_value["power_pcr2"] = bitfield[-7]
        working_value["compass_update_rate"] = NortekProtocolParameterDict.convert_word_to_int(match.group(14))
        working_value["coordinate_system"] = NortekProtocolParameterDict.convert_word_to_int(match.group(15))
        working_value["num_cells"] = NortekProtocolParameterDict.convert_word_to_int(match.group(16))
        working_value["cell_size"] = NortekProtocolParameterDict.convert_word_to_int(match.group(17))
        working_value["measurement_interval"] = NortekProtocolParameterDict.convert_word_to_int(match.group(18))
        working_value["deployment_name"] = NortekProtocolParameterDict.convert_bytes_to_string(match.group(19))
        working_value["wrap_mode"] = NortekProtocolParameterDict.convert_word_to_int(match.group(20))
        working_value["deploy_start_time"] = NortekProtocolParameterDict.convert_words_to_datetime(match.group(21))
        working_value["diag_interval"] = NortekProtocolParameterDict.convert_double_word_to_int(match.group(22))
        bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(23))
        working_value["use_spec_sound_speed"] = bool(bitfield[-1])
        working_value["diag_mode_on"] = bool(bitfield[-2])
        working_value["analog_output_on"] = bool(bitfield[-3])
        working_value["output_format"] = bitfield[-4]
        working_value["scaling"] = bitfield[-5]
        working_value["serial_out_on"] = bool(bitfield[-6])
        working_value["stage_on"] = bool(bitfield[-8])
        working_value["analog_power_output"] = bool(bitfield[-9])
        working_value["sound_speed_adjust"] = NortekProtocolParameterDict.convert_word_to_int(match.group(24))
        working_value["num_diag_samples"] = NortekProtocolParameterDict.convert_word_to_int(match.group(25))
        working_value["num_beams_per_cell"] = NortekProtocolParameterDict.convert_word_to_int(match.group(26))
        working_value["num_pings_diag"] = NortekProtocolParameterDict.convert_word_to_int(match.group(27))
        bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(28))
        working_value["use_dsp_filter"] = bool(bitfield[-1])
        working_value["filter_data_output"] = bitfield[-2]
        working_value["analog_input_addr"] = NortekProtocolParameterDict.convert_word_to_int(match.group(29))
        working_value["sw_ver"] = NortekProtocolParameterDict.convert_word_to_int(match.group(30))
        working_value["velocity_adj_factor"] = base64.b64encode(match.group(32))
        working_value["file_comments"] = NortekProtocolParameterDict.convert_bytes_to_string(match.group(33))
        bitfield = NortekProtocolParameterDict.convert_bytes_to_bit_field(match.group(34))
        working_value["wave_data_rate"] = bitfield[-1]
        working_value["wave_cell_pos"] = bitfield[-2]
        working_value["dynamic_pos_type"] = bitfield[-3]
        working_value["percent_wave_cell_pos"] = NortekProtocolParameterDict.convert_word_to_int(match.group(35))
        working_value["wave_tx_pulse"] = NortekProtocolParameterDict.convert_word_to_int(match.group(36))
        working_value["fix_wave_blank_dist"] = NortekProtocolParameterDict.convert_word_to_int(match.group(37))
        working_value["wave_cell_size"] = NortekProtocolParameterDict.convert_word_to_int(match.group(38))
        working_value["num_diag_per_wave"] = NortekProtocolParameterDict.convert_word_to_int(match.group(39))
        working_value["num_sample_per_burst"] = NortekProtocolParameterDict.convert_word_to_int(match.group(42))
        working_value["analog_scale_factor"] = NortekProtocolParameterDict.convert_word_to_int(match.group(44))
        working_value["correlation_thrs"] = NortekProtocolParameterDict.convert_word_to_int(match.group(45))
        working_value["tx_pulse_len_2nd"] = NortekProtocolParameterDict.convert_word_to_int(match.group(47))
        working_value["filter_constants"] = base64.b64encode(match.group(49))
        checksum = NortekProtocolParameterDict.convert_word_to_int(match.group(50))

        for key in working_value.keys():
            if None == working_value[key]:
                raise SampleException("No %s value parsed", key)
                
        # report values
        result = [{DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TX_LENGTH,
                   DataParticleKey.VALUE: working_value["tx_length"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.BLANK_DIST,
                   DataParticleKey.VALUE: working_value["blank_dist"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.RX_LENGTH,
                   DataParticleKey.VALUE: working_value["rx_length"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TIME_BETWEEN_PINGS,
                   DataParticleKey.VALUE: working_value["time_between_pings"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TIME_BETWEEN_BURSTS,
                   DataParticleKey.VALUE: working_value["time_between_bursts"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_PINGS,
                   DataParticleKey.VALUE: working_value["num_pings"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.AVG_INTERVAL,
                   DataParticleKey.VALUE: working_value["avg_interval"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_BEAMS,
                   DataParticleKey.VALUE: working_value["num_beams"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.PROFILE_TYPE,
                   DataParticleKey.VALUE: working_value["profile_type"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.MODE_TYPE,
                   DataParticleKey.VALUE: working_value["mode_type"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_TCM1,
                   DataParticleKey.VALUE: working_value["power_tcm1"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_TCM2,
                   DataParticleKey.VALUE: working_value["power_tcm2"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SYNC_OUT_POSITION,
                   DataParticleKey.VALUE: working_value["sync_out_position"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SAMPLE_ON_SYNC,
                   DataParticleKey.VALUE: working_value["sample_on_sync"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.START_ON_SYNC,
                   DataParticleKey.VALUE: working_value["start_on_sync"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_PCR1,
                   DataParticleKey.VALUE: working_value["power_pcr1"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.POWER_PCR2,
                   DataParticleKey.VALUE: working_value["power_pcr2"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.COMPASS_UPDATE_RATE,
                   DataParticleKey.VALUE: working_value["compass_update_rate"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.COORDINATE_SYSTEM,
                   DataParticleKey.VALUE: working_value["coordinate_system"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_CELLS,
                   DataParticleKey.VALUE: working_value["num_cells"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.CELL_SIZE,
                   DataParticleKey.VALUE: working_value["cell_size"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.MEASUREMENT_INTERVAL,
                   DataParticleKey.VALUE: working_value["measurement_interval"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DEPLOYMENT_NAME,
                   DataParticleKey.VALUE: working_value["deployment_name"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WRAP_MODE,
                   DataParticleKey.VALUE: working_value["wrap_mode"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DEPLOY_START_TIME,
                   DataParticleKey.VALUE: working_value["deploy_start_time"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DIAG_INTERVAL,
                   DataParticleKey.VALUE: working_value["diag_interval"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.USE_SPEC_SOUND_SPEED,
                   DataParticleKey.VALUE: working_value["use_spec_sound_speed"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DIAG_MODE_ON,
                   DataParticleKey.VALUE: working_value["diag_mode_on"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_OUTPUT_ON,
                   DataParticleKey.VALUE: working_value["analog_output_on"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.OUTPUT_FORMAT,
                   DataParticleKey.VALUE: working_value["output_format"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SCALING,
                   DataParticleKey.VALUE: working_value["scaling"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SERIAL_OUT_ON,
                   DataParticleKey.VALUE: working_value["serial_out_on"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.STAGE_ON,
                   DataParticleKey.VALUE: working_value["stage_on"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_POWER_OUTPUT,
                   DataParticleKey.VALUE: working_value["analog_power_output"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SOUND_SPEED_ADJUST,
                   DataParticleKey.VALUE: working_value["sound_speed_adjust"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_DIAG_SAMPLES,
                   DataParticleKey.VALUE: working_value["num_diag_samples"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_BEAMS_PER_CELL,
                   DataParticleKey.VALUE: working_value["num_beams_per_cell"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_PINGS_DIAG,
                   DataParticleKey.VALUE: working_value["num_pings_diag"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.USE_DSP_FILTER,
                   DataParticleKey.VALUE: working_value["use_dsp_filter"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILTER_DATA_OUTPUT,
                   DataParticleKey.VALUE: working_value["filter_data_output"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_INPUT_ADDR,
                   DataParticleKey.VALUE: working_value["analog_input_addr"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.SW_VER,
                   DataParticleKey.VALUE: working_value["sw_ver"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.VELOCITY_ADJ_FACTOR,
                   DataParticleKey.VALUE: working_value["velocity_adj_factor"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILE_COMMENTS,
                   DataParticleKey.VALUE: working_value["file_comments"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_DATA_RATE,
                   DataParticleKey.VALUE: working_value["wave_data_rate"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_CELL_POS,
                   DataParticleKey.VALUE: working_value["wave_cell_pos"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.DYNAMIC_POS_TYPE,
                   DataParticleKey.VALUE: working_value["dynamic_pos_type"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.PERCENT_WAVE_CELL_POS,
                   DataParticleKey.VALUE: working_value["percent_wave_cell_pos"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_TX_PULSE,
                   DataParticleKey.VALUE: working_value["wave_tx_pulse"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FIX_WAVE_BLANK_DIST,
                   DataParticleKey.VALUE: working_value["fix_wave_blank_dist"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.WAVE_CELL_SIZE,
                   DataParticleKey.VALUE: working_value["wave_cell_size"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_DIAG_PER_WAVE,
                   DataParticleKey.VALUE: working_value["num_diag_per_wave"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.NUM_SAMPLE_PER_BURST,
                   DataParticleKey.VALUE: working_value["num_sample_per_burst"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.ANALOG_SCALE_FACTOR,
                   DataParticleKey.VALUE: working_value["analog_scale_factor"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.CORRELATION_THRS,
                   DataParticleKey.VALUE: working_value["correlation_thrs"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.TX_PULSE_LEN_2ND,
                   DataParticleKey.VALUE: working_value["tx_pulse_len_2nd"]},
                  {DataParticleKey.VALUE_ID: NortekUserConfigDataParticleKey.FILTER_CONSTANTS,
                   DataParticleKey.VALUE: working_value["filter_constants"]},
                  ]
        
        calculated_checksum = NortekProtocolParameterDict.calculate_checksum(match.group())
        if (checksum != calculated_checksum):
            log.warn("Calculated checksum: %s did not match packet checksum: %s",
                     calculated_checksum, checksum)
            self.contents[DataParticleKey.QUALITY_FLAG] = DataParticleValue.CHECKSUM_FAILED

        log.debug('VectorUserConfigDataParticle: particle=%s' %result)
        return result    
    
###############################################################################
# Paramdict stuff
###############################################################################
class NortekParameterDictVal(RegexParameter):
    
    def update(self, input, **kwargs):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        init_value = kwargs.get('init_value', False)
        match = self.regex.match(input)
        if match:
            log.debug('NortekDictVal.update(): match=<%s>, init_value=%s', match.group(1).encode('hex'), init_value)
            value = self.f_getval(match)
            if init_value:
                self.init_value = value
            else:
                self.value = value
            if isinstance(value, int):
                log.debug('NortekParameterDictVal.update(): updated parameter %s=<%d>', self.name, value)
            else:
                log.debug('NortekParameterDictVal.update(): updated parameter %s=\"%s\" <%s>', self.name, 
                          value, str(self.value).encode('hex'))
            return True
        else:
            log.debug('NortekParameterDictVal.update(): failed to update parameter %s', self.name)
            log.debug('input=%s' %input.encode('hex'))
            log.debug('regex=%s' %str(self.regex))
            return False

class NortekProtocolParameterDict(ProtocolParameterDict):   
        
    def update(self, input, target_params=None, **kwargs):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update a parameter. Only updates the first
        match encountered. If we pass in a target params list then will will
        only iterate through those allowing us to limit upstate to only specific
        parameters.
        @param input A string to match to a dictionary object.
        @param target_params a name, or list of names to limit the scope of
        the update.
        @retval The name that was successfully updated, None if not updated
        @raise InstrumentParameterException on invalid target prams
        @raise KeyError on invalid parameter name
        """
        log.debug("update input: %s", input)
        found = False

        if(target_params and isinstance(target_params, str)):
            params = [target_params]
        elif(target_params and isinstance(target_params, list)):
            params = target_params
        elif(target_params == None):
            params = self._param_dict.keys()
        else:
            raise InstrumentParameterException("invalid target_params, must be name or list")

        for name in params:
            log.trace("update param dict name: %s", name)
            val = self._param_dict[name]
            if val.update(input, **kwargs):
                found = True
        return found
    
    def get_config(self):
        """
        Retrieve the configuration (all key values not ending in 'Spare').
        """
        config = {}
        for (key, val) in self._param_dict.iteritems():
            if not key.endswith('Spare'):
                config[key] = val.get_value()
        return config
    
    def set_from_value(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        log.debug("NortekProtocolParameterDict.set_from_value(): name=%s, value=%s",
                  name, value)
        
        if not name in self._param_dict:
            raise InstrumentParameterException('Unable to set parameter %s to %s: parameter %s not an dictionary' %(name, value, name))
            
        if ((self._param_dict[name].value.f_format == NortekProtocolParameterDict.word_to_string) or
            (self._param_dict[name].value.f_format == NortekProtocolParameterDict.double_word_to_string)):
            if not isinstance(value, int):
                raise InstrumentParameterException('Unable to set parameter %s to %s: value not an integer' %(name, value))
        else:
            if not isinstance(value, str):
                raise InstrumentParameterException('Unable to set parameter %s to %s: value not a string' %(name, value))
        
        if self._param_dict[name].description.visibility == ParameterDictVisibility.READ_ONLY:
            raise ReadOnlyException('Unable to set parameter %s to %s: parameter %s is read only' %(name, value, name))
                
        self._param_dict[name].value.set_value(value)
        
    def get_keys(self):
        """
        Return list of device parameters available.  These are a subset of all the parameters
        """
        list = []
        for param in self._param_dict.keys():
            if not param.endswith('Spare'):
                list.append(param) 
        log.debug('get_keys: list=%s' %list)
        return list
    
    def set_params_to_read_write(self):
        for (name, val) in self._param_dict.iteritems():
            val.description.visibility = ParameterDictVisibility.READ_WRITE

    @staticmethod
    def word_to_string(value):
        if len(value) != 2:
            raise SampleException("Invalid number of bytes in word input! Found %s" % len(value))

        low_byte = value & 0xff
        high_byte = (value & 0xff00) >> 8
        return chr(low_byte) + chr(high_byte)
        
    @staticmethod
    def convert_word_to_int(word):
        if len(word) != 2:
            raise SampleException("Invalid number of bytes in word input! Found %s" % len(word))

        low_byte = ord(word[0])
        high_byte = 0x100 * ord(word[1])
        #log.debug('w=%s, l=%d, h=%d, v=%d' %(word.encode('hex'), low_byte, high_byte, low_byte + high_byte))
        return low_byte + high_byte
            
    @staticmethod
    def double_word_to_string(value):
        if len(value) != 4:
            raise SampleException("Invalid number of bytes in double word input! Found %s" % len(value))
        result = NortekProtocolParameterDict.word_to_string(value & 0xffff)
        result += NortekProtocolParameterDict.word_to_string((value & 0xffff0000) >> 16)
        return result
        
    @staticmethod
    def convert_double_word_to_int(dword):
        if len(dword) != 4:
            raise SampleException("Invalid number of bytes in double word input! Found %s" % len(dword))
        low_word = NortekProtocolParameterDict.convert_word_to_int(dword[0:2])
        high_word = NortekProtocolParameterDict.convert_word_to_int(dword[2:4])
        #log.debug('dw=%s, lw=%d, hw=%d, v=%d' %(dword.encode('hex'), low_word, high_word, low_word + (0x10000 * high_word)))
        return low_word + (0x10000 * high_word)
    
    @staticmethod
    def convert_bytes_to_bit_field(bytes):
        """
        Convert bytes to a bit field, reversing bytes in the process.
        ie ['\x05', '\x01'] becomes [0, 0, 0, 1, 0, 1, 0, 1]
        @param bytes an array of string literal bytes.
        @retval an list of 1 or 0 in order 
        """
        byte_list = list(bytes)
        byte_list.reverse()
        result = []
        for byte in byte_list:
            bin_string = bin(ord(byte))[2:].rjust(8, '0')
            result.extend([int(x) for x in list(bin_string)])
        log.trace("Returning a bitfield of %s for input string: [%s]", result, bytes)
        return result

    @staticmethod
    def convert_words_to_datetime(bytes):
        """
        Convert block of 6 words into a date/time structure for the
        instrument family
        @param bytes 6 bytes
        @retval An array of 6 ints corresponding to the date/time structure
        @raise SampleException If the date/time cannot be found
        """
        log.debug("Converting date/time bytes (ord values): %s", map(ord, bytes))
        if len(bytes) != 6:
            raise SampleException("Invalid number of bytes in input! Found %s" % len(bytes))

        list = NortekProtocolParameterDict.convert_to_array(bytes, 1)
        for i in range(0, len(list)):
            list[i] = int(list[i].encode("hex"))
            
        return list

    @staticmethod
    def convert_to_array(bytes, item_size):
        """
        Convert the byte stream into a array with each element being
        item_size bytes. ie '\x01\x02\x03\x04' with item_size 2 becomes
        ['\x01\x02', '\x03\x04'] 
        @param item_size the size in bytes to make each element
        @retval An array with elements of the correct size
        @raise SampleException if there are problems unpacking the bytes or
        fitting them all in evenly.
        """
        length = len(bytes)
        if length % item_size != 0:
            raise SampleException("Uneven number of bytes for size %s" % item_size)
        l = list(bytes)
        result = []
        for i in range(0, length, item_size):
            result.append("".join(l[i:i+item_size]))
        return result

    @staticmethod
    def calculate_checksum(input, length=None):
        #log.debug("calculate_checksum: input=%s, length=%d", input.encode('hex'), length)
        calculated_checksum = CHECK_SUM_SEED
        if length == None:
            length = len(input)
        for word_index in range(0, length-2, 2):
            word_value = NortekProtocolParameterDict.convert_word_to_int(input[word_index:word_index+2])
            calculated_checksum = (calculated_checksum + word_value) % 0x10000
            #log.trace('w_i=%d, c_c=%d', word_index, calculated_checksum)
        return calculated_checksum

    @staticmethod
    def convert_bytes_to_string(bytes_in):
        """
        Convert a list of bytes into a string, remove trailing nulls
        ie. ['\x65', '\x66'] turns into "ef"
        @param bytes_in The byte list to take in
        @retval The string to return
        """
        ba = bytearray(bytes_in)
        return str(ba).split('\x00', 1)[0]
        
    @staticmethod
    def convert_time(response):
        t = str(response[2].encode('hex'))  # get day
        t += '/' + str(response[5].encode('hex'))  # get month   
        t += '/20' + str(response[4].encode('hex'))  # get year   
        t += ' ' + str(response[3].encode('hex'))  # get hours   
        t += ':' + str(response[0].encode('hex'))  # get minutes   
        t += ':' + str(response[1].encode('hex'))  # get seconds   
        return t
    
###############################################################################
# Driver
###############################################################################

class NortekInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    Base class for all seabird instrument drivers.
    """

    def apply_startup_params(self):
        """
        Over-ridden to add the 'NotUserRequested' keyed parameter to allow writing to read-only params
        Apply the startup values previously stored in the protocol to
        the running config of the live instrument. The startup values are the
        values that are (1) marked as startup parameters and are (2) the "best"
        value to use at startup. Preference is given to the previously-set init
        value, then the default value, then the currently used value.
        
        This default method assumes a dict of parameter name and value for
        the configuration.
        @raise InstrumentParameterException If the config cannot be applied
        """
        config = self._protocol.get_startup_config()
        
        if not isinstance(config, dict):
            raise InstrumentParameterException("Incompatible initialization parameters")
        
        self.set_resource(config, NotUserRequested=True)

    def restore_direct_access_params(self, config):
        """
        Over-ridden to add the 'NotUserRequested' keyed parameter to allow writing to read-only params
        Restore the correct values out of the full config that is given when
        returning from direct access. By default, this takes a simple dict of
        param name and value. Override this class as needed as it makes some
        simple assumptions about how your instrument sets things.
        
        @param config The configuration that was previously saved (presumably
        to disk somewhere by the driver that is working with this protocol)
        """
        vals = {}
        # for each parameter that is read only, restore
        da_params = self._protocol.get_direct_access_params()        
        for param in da_params:
            vals[param] = config[param]
            
        self.set_resource(vals, NotUserRequested=True)


###############################################################################
# Protocol
###############################################################################

class NortekInstrumentProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for seabird driver.
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
        self._protocol_fsm = InstrumentFSM(ProtocolState, 
                                           ProtocolEvent,
                                           ProtocolEvent.ENTER, 
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET_CONFIGURATION, self._handler_command_set_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_CLOCK, self._handler_command_read_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_MODE, self._handler_command_read_mode)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.POWER_DOWN, self._handler_command_power_down)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_BATTERY_VOLTAGE, self._handler_command_read_battery_voltage)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_ID, self._handler_command_read_id)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HW_CONFIGURATION, self._handler_command_get_hw_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HEAD_CONFIGURATION, self._handler_command_get_head_config)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME, self._handler_command_start_measurement_specific_time)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_MEASUREMENT_IMMEDIATE, self._handler_command_start_measurement_immediate)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.READ_FAT, self._handler_command_read_fat)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.CONFIGURE_INSTRUMENT, self._build_set_configutation_command)
        self._add_build_handler(InstrumentCmds.SET_REAL_TIME_CLOCK, self._build_set_real_time_clock_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.READ_REAL_TIME_CLOCK, self._parse_read_clock_response)
        self._add_response_handler(InstrumentCmds.CMD_WHAT_MODE, self._parse_what_mode_response)
        self._add_response_handler(InstrumentCmds.READ_BATTERY_VOLTAGE, self._parse_read_battery_voltage_response)
        self._add_response_handler(InstrumentCmds.READ_ID, self._parse_read_id)
        self._add_response_handler(InstrumentCmds.READ_HW_CONFIGURATION, self._parse_read_hw_config)
        self._add_response_handler(InstrumentCmds.READ_HEAD_CONFIGURATION, self._parse_read_head_config)
        self._add_response_handler(InstrumentCmds.READ_FAT, self._parse_read_fat)

        # Construct the parameter dictionary containing device parameters, current parameter values, and set formatting functions.
        self._build_param_dict()

    ########################################################################
    # overridden superclass methods
    ########################################################################    

    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def set_init_params(self, config):
        """
        over-ridden to handle binary block configuration
        Set the initialization parameters to the given values in the protocol
        parameter dictionary. 
        @param config The parameter_name/value to set in the initialization
            fields of the parameter dictionary
        @raise InstrumentParameterException If the config cannot be set
        """
        log.debug("set_init_params: config=%s", config)
        if not isinstance(config, dict):
            raise InstrumentParameterException("Invalid init config format")
                
        if DriverParameter.ALL in config:
            binary_config = base64.b64decode(config[DriverParameter.ALL])
            # make the configuration string look like it came from instrument to get all the methods to be happy
            binary_config += InstrumentPrompts.Z_ACK    
            log.debug("config len=%d, config=%s",
                      len(binary_config), binary_config.encode('hex'))
            
            if len(binary_config) == USER_CONFIG_LEN+2:
                if self._check_configuration(binary_config, USER_CONFIG_SYNC_BYTES, USER_CONFIG_LEN):                    
                    self._param_dict.update(binary_config, init_value=True)
                else:
                    raise InstrumentParameterException("bad configuration")
            else:
                raise InstrumentParameterException("configuration not the correct length")
        else:
            for name in config.keys():
                self._param_dict.set_init_value(name, config[name])

    def _get_response(self, timeout=5, expected_prompt=None):
        """
        Get a response from the instrument
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.
        starttime = time.time()
                
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            assert isinstance(expected_prompt, str)
            prompt_list = [expected_prompt]   
        while True:
            for item in prompt_list:
                if item in self._promptbuf:
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)
            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """
        
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', 5)
        expected_prompt = kwargs.get('expected_prompt', InstrumentPrompts.Z_ACK)
                            
        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if build_handler:
            cmd_line = build_handler(cmd, *args, **kwargs)
        else:
            cmd_line = cmd

        # Send command.
        log.debug('_do_cmd_resp: %s(%s), timeout=%s, expected_prompt=%s (%s),' 
                  % (repr(cmd_line), repr(cmd_line.encode("hex")), timeout, expected_prompt, expected_prompt.encode("hex")))
        self._connection.send(cmd_line)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout,
                                              expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)
        
        return resp_result

    ########################################################################
    # Common handlers
    ########################################################################
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

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state of instrument; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result)
        """
        next_state = None
        result = None

        # try to discover the device mode using timeout if passed.
        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._get_mode(timeout)
        if prompt == InstrumentPrompts.COMMAND_MODE:
            next_state = ProtocolState.COMMAND
            result = ResourceAgentState.IDLE
        elif prompt == InstrumentPrompts.CONFIRMATION:    
            next_state = ProtocolState.AUTOSAMPLE
            result = ResourceAgentState.STREAMING
        elif prompt == InstrumentPrompts.Z_ACK:
            log.debug('_handler_unknown_discover: promptbuf=%s (%s)' %(self._promptbuf, self._promptbuf.encode("hex")))
            if InstrumentModes.COMMAND in self._promptbuf:
                next_state = ProtocolState.COMMAND
                result = ResourceAgentState.IDLE
            elif (InstrumentModes.MEASUREMENT in self._promptbuf or 
                 InstrumentModes.CONFIRMATION in self._promptbuf):
                next_state = ProtocolState.AUTOSAMPLE
                result = ResourceAgentState.STREAMING
            else:
                raise InstrumentStateException('Unknown state.')
        else:
            raise InstrumentStateException('Unknown state.')

        log.debug('_handler_unknown_discover: state=%s', next_state)
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
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None

        not_user_requested = kwargs.get('NotUserRequested', False)

        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.
        try:
            params_to_set = args[0]           
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        else:
            if not isinstance(params_to_set, dict):
                raise InstrumentParameterException('Set parameters not a dict.')
        
        parameters = copy.copy(self._param_dict)    # get copy of parameters to modify
        
        # if internal set from apply_startup_params() or restore_direct_access_params()
        # over-ride read-only parameters
        if not_user_requested:
            parameters.set_params_to_read_write()
        
        # For each key, value in the params_to_set list set the value in parameters copy.
        try:
            for (name, value) in params_to_set.iteritems():
                log.debug('_handler_command_set: setting %s to %s' %(name, value))
                parameters.set_from_value(name, value)
        except Exception as ex:
            raise InstrumentParameterException('Unable to set parameter %s to %s: %s' %(name, value, ex))
        
        output = self._create_set_output(parameters)
        
        log.debug('_handler_command_set: writing instrument configuration to instrument')
        self._connection.send(InstrumentCmds.CONFIGURE_INSTRUMENT)
        self._connection.send(output)

        # Clear the prompt buffer.
        self._promptbuf = ''
        self._get_response(timeout=5, expected_prompt=InstrumentPrompts.Z_ACK)

        self._update_params()
            
        return (next_state, result)
    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_IMMEDIATE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)
                
        next_state = ProtocolState.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        next_state = ProtocolState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_set_configuration(self, *args, **kwargs):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue set user configuration command.
        result = self._do_cmd_resp(InstrumentCmds.CONFIGURE_INSTRUMENT, 
                                   expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_clock(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_REAL_TIME_CLOCK, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_mode(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.CMD_WHAT_MODE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_power_down(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.POWER_DOWN, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_battery_voltage(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_BATTERY_VOLTAGE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_id(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_ID, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_hw_config(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HW_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_head_config(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_HEAD_CONFIGURATION, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_read_fat(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.READ_FAT, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_measurement_specific_time(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_AT_SPECIFIC_TIME, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)
        # TODO: what state should the driver/IA go to? Should this command even be exported?

        return (next_state, (next_agent_state, result))

    def _handler_command_start_measurement_immediate(self):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        # Issue read clock command.
        result = self._do_cmd_resp(InstrumentCmds.START_MEASUREMENT_IMMEDIATE, 
                                   expected_prompt = InstrumentPrompts.Z_ACK)
        # TODO: what state should the driver/IA go to? Should this command even be exported?

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        str_time = get_timestamp_delayed("%M %S %d %H %y %m")
        byte_time = ''
        for v in str_time.split():
            byte_time += chr(int('0x'+v, base=16))
        values = str_time.split()
        log.info("_handler_command_clock_sync: time set to %s:m %s:s %s:d %s:h %s:y %s:M (%s)" %(values[0], values[1], values[2], values[3], values[4], values[5], byte_time.encode('hex'))) 
        self._do_cmd_resp(InstrumentCmds.SET_REAL_TIME_CLOCK, byte_time, **kwargs)

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

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # send soft break
        self._connection.send(InstrumentCmds.SOFT_BREAK_FIRST_HALF)
        time.sleep(.1)
        self._do_cmd_resp(InstrumentCmds.SOFT_BREAK_SECOND_HALF,
                          expected_prompt = InstrumentPrompts.CONFIRMATION, *args, **kwargs)
        
        # Issue the confirmation command.
        self._do_cmd_resp(InstrumentCmds.CONFIRMATION, 
                          expected_prompt = InstrumentPrompts.Z_ACK, *args, **kwargs)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

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

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, result)

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
    # Common handlers.
    ########################################################################

    def _handler_get(self, *args, **kwargs):
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
        # Retrieve each key in the list, raise if any are invalid.
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
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        
        # The parameter dictionary.
        self._param_dict = NortekProtocolParameterDict()

        # Add parameter handlers to parameter dict.
        
        # user config
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(4),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(6),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.RECEIVE_LENGTH,
                             r'^.{%s}(.{2}).*' % str(8),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
                             r'^.{%s}(.{2}).*' % str(10),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.TIME_BETWEEN_BURST_SEQUENCES,
                             r'^.{%s}(.{2}).*' % str(12),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_PINGS,
                             r'^.{%s}(.{2}).*' % str(14),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.AVG_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(16),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             init_value=60,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.USER_NUMBER_BEAMS,
                             r'^.{%s}(.{2}).*' % str(18),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.TIMING_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(20),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.POWER_CONTROL_REGISTER,
                             r'^.{%s}(.{2}).*' % str(22),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.A1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(24),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.B0_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(26),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.B1_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(28),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.COMPASS_UPDATE_RATE,
                             r'^.{%s}(.{2}).*' % str(30),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             init_value=2,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.COORDINATE_SYSTEM,
                             r'^.{%s}(.{2}).*' % str(32),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             init_value=1,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_BINS,
                             r'^.{%s}(.{2}).*' % str(34),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.BIN_LENGTH,
                             r'^.{%s}(.{2}).*' % str(36),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.MEASUREMENT_INTERVAL,
                             r'^.{%s}(.{2}).*' % str(38),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             init_value=3600,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
                             r'^.{%s}(.{6}).*' % str(40),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.WRAP_MODE,
                             r'^.{%s}(.{2}).*' % str(46),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.CLOCK_DEPLOY,
                             r'^.{%s}(.{6}).*' % str(48),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.DIAGNOSTIC_INTERVAL,
                             r'^.{%s}(.{4}).*' % str(54),
                             lambda match : NortekProtocolParameterDict.convert_double_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.double_word_to_string,
                             init_value=43200,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.MODE,
                             r'^.{%s}(.{2}).*' % str(58),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.ADJUSTMENT_SOUND_SPEED,
                             r'^.{%s}(.{2}).*' % str(60),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(62),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             init_value=20,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(64),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_PINGS_DIAGNOSTIC,
                             r'^.{%s}(.{2}).*' % str(66),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.MODE_TEST,
                             r'^.{%s}(.{2}).*' % str(68),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.ANALOG_INPUT_ADDR,
                             r'^.{%s}(.{2}).*' % str(70),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.SW_VERSION,
                             r'^.{%s}(.{2}).*' % str(72),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.USER_1_SPARE,
                             r'^.{%s}(.{2}).*' % str(74),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.VELOCITY_ADJ_TABLE,
                             r'^.{%s}(.{180}).*' % str(76),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.COMMENTS,
                             r'^.{%s}(.{180}).*' % str(256),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.WAVE_MEASUREMENT_MODE,
                             r'^.{%s}(.{2}).*' % str(436),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.DYN_PERCENTAGE_POSITION,
                             r'^.{%s}(.{2}).*' % str(438),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.WAVE_TRANSMIT_PULSE,
                             r'^.{%s}(.{2}).*' % str(440),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.WAVE_BLANKING_DISTANCE,
                             r'^.{%s}(.{2}).*' % str(442),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.WAVE_CELL_SIZE,
                             r'^.{%s}(.{2}).*' % str(444),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.NUMBER_DIAG_SAMPLES,
                             r'^.{%s}(.{2}).*' % str(446),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.A1_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(448),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.B0_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(450),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.USER_2_SPARE,
                             r'^.{%s}(.{2}).*' % str(454),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.ANALOG_OUTPUT_SCALE,
                             r'^.{%s}(.{2}).*' % str(456),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
                             r'^.{%s}(.{2}).*' % str(458),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                             r'^.{%s}(.{2}).*' % str(462),
                             lambda match : NortekProtocolParameterDict.convert_word_to_int(match.group(1)),
                             NortekProtocolParameterDict.word_to_string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.USER_4_SPARE,
                             r'^.{%s}(.{30}).*' % str(464),
                             lambda match : match.group(1),
                             lambda string : string,
                             regex_flags=re.DOTALL)
        self._param_dict.add(Parameter.QUAL_CONSTANTS,
                             r'^.{%s}(.{16}).*' % str(494),
                             lambda match : match.group(1),
                             lambda string : string,
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
        
        log.debug("_get_mode: timeout = %d", timeout)
        
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
        self._extract_sample(VectorEngClockDataParticle, CLOCK_DATA_REGEX, response, timestamp)
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
        
        self._extract_sample(VectorEngBatteryDataParticle, BATTERY_DATA_REGEX, response, timestamp)
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
        self._extract_sample(VectorEngIdDataParticle, ID_DATA_REGEX, response, timestamp)
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
        self._extract_sample(VectorHardwareConfigDataParticle, HARDWARE_CONFIG_DATA_REGEX, response, timestamp)
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
        self._extract_sample(VectorHeadConfigDataParticle, HEAD_CONFIG_DATA_REGEX, response, timestamp)
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
            parsed_record = {'FileNumber': record_number, 
                             'FileName': record[0:6].rstrip(chr(0x00)), 
                             'SequenceNumber': ord(record[6:7]), 
                             'Status': record[7:8], 
                             'StartAddr': record[8:12].encode('hex'), 
                             'StopAddr': record[12:record_length].encode('hex')}
            ###
            parsed.append(sorted(parsed_record.items(), key=lambda i: i[0]))  
        return parsed

