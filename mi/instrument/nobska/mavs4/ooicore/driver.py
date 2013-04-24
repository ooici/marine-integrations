"""
@package mi.instrument.nobska.mavs4.ooicore.driver
@file /marine-integrations/mi/instrument/nobska/mavs4/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the mavs4
Release notes:

initial release
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'


import time
import re
import ntplib

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.driver_dict import DriverDict, DriverDictKey

from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               SampleException, \
                               InstrumentStateException
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import RegexParameter
from mi.core.common import InstErrorCode
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, CommonDataParticleType
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger
log = get_logger()

SAMPLE_DATA_PATTERN = (r'(\d+\s+\d+\s+\d+)' +    # date
                       '\s+(\d+\s+\d+\s+\d+)' +  # time
                       '\.(\d+)' +               # fractional second
                       '\s+(\w+)' +              # vector A
                       '\s+(\w+)' +              # vector B
                       '\s+(\w+)' +              # vector C
                       '\s+(\w+)' +              # vector D
                       '\s+(-*\d+\.\d+)' +       # east
                       '\s+(-*\d+\.\d+)' +       # north
                       '\s+(-*\d+\.\d+)' +       # west
                       '\s+(-*\d+\.\d+)' +       # temperature
                       '\s+(-*\d+\.\d+)' +       # MX
                       '\s+(-*\d+\.\d+)' +       # MY
                       '\s+(-*\d+\.\d+)' +       # pitch
                       '\s+(-*\d+\.\d+)\s+')     # roll

SAMPLE_DATA_REGEX = re.compile(SAMPLE_DATA_PATTERN)


INSTRUMENT_NEWLINE = '\r\n'
WRITE_DELAY = 0
YES = 'y'
NO = 'n'

# default timeout.
INSTRUMENT_TIMEOUT = 5

class ScheduledJob(BaseEnum):
    CLOCK_SYNC = 'clock_sync'
    
class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    SAMPLE = 'vel3d_b_sample'
    STATUS = 'vel3d_b_engineering'

# Device prompts.
class InstrumentPrompts(BaseEnum):
    """
    MAVS-4 prompts.
    The main menu prompt has 2 bells and the sub menu prompts have one; the
    PicoDOS prompt has none.
    """
    MAIN_MENU                     = '\a\b ? \a\b'
    SUB_MENU                      = '\a\b'
    PICO_DOS                      = 'Enter command >> '
    SLEEPING                      = 'Sleeping . . .'
    SLEEP_WAKEUP                  = 'Enter <CTRL>-<C> now to wake up?'
    DEPLOY_WAKEUP                 = '>>> <CTRL>-<C> to terminate deployment <<<'
    SET_DONE                      = 'New parameters accepted.'
    SET_FAILED                    = 'Invalid entry'
    SET_TIME                      = '] ? \a\b'
    GET_TIME                      = 'Enter correct time ['
    CHANGE_TIME                   = 'Change time & date (Yes/No) [N] ?\a\b'
    NOTE_INPUT                    = '> '
    DEPLOY_MENU                   = 'G| Go (<CTRL>-<G> skips checks)\r\n\r\n'
    SELECTION                     = 'Selection  ?'
    VELOCITY_FRAME                = ' <3> Earth Frame (E, N, W)'
    MONITOR                       = 'Enable Data Monitor (Yes/No) ['
    LOG_DISPLAY                   = 'with each sample (Yes/No) [Y] ?'
    VELOCITY_FORMAT               = 'Set acoustic axis velocity format (HDS) [S] ?'
    QUERY                         = 'Enable Query Mode (Yes/No) ['
    FREQUENCY                     = 'Enter Measurement Frequency [Hz] (0.01 to 50.0) ?'
    MEAS_PER_SAMPLE               = 'Enter number of measurements per sample (1 to 10000) ?'
    SAMPLE_PERIOD                 = 'Enter Sample Period [sec] (0.02 to   10000) ?'
    SAMPLES_PER_BURST             = 'Enter number of samples per burst (1 to 100000) ?'
    BURST_INTERVAL_DAYS           = 'Days     (  0 to   366) ?'
    BURST_INTERVAL_HOURS          = 'Hours    (  0 to    23) ?'
    BURST_INTERVAL_MINUTES        = 'Minutes  (  0 to    59) ?'
    BURST_INTERVAL_SECONDS        = 'Seconds  (  0 to    59) ?'
    BEGIN_MEASUREMENT             = 'Beginning measurement cycle now.'
    SYSTEM_CONFIGURATION_MENU     = '<X> Save Changes and Exit'
    SYSTEM_CONFIGURATION_PASSWORD = 'Password:'
    SI_CONVERSION                 = 'Enter binary to SI velocity conversion (0.0010000 to 0.0200000) ?'
    WARM_UP_INTERVAL              = '[F]ast or [S]low sensor warm up interval [F] ?'
    THREE_AXIS_COMPASS            = '3-Axis compass enabled (Yes/No) ['
    SOLID_STATE_TILT              = 'Solid state tilt enabled (Yes/No) ['
    LOAD_DEFAULT_TILT             = 'Load default tilt coefficients (Yes/No) ['
    THERMISTOR                    = 'Thermistor enabled (Yes/No) ['
    THERMISTOR_OFFSET             = 'Set thermistor offset to 0.0 (default) (Yes/No) [N] ?'
    PRESSURE                      = 'Pressure enabled (Yes/No) ['
    AUXILIARY                     = 'Auxiliary * enabled (Yes/No) ['
    SENSOR_ORIENTATION            = '<7> Horizontal/Bent Up'
    CALIBRATION_MENU              = '<X> Save Constants and Exit'
    VELOCITY_OFFSETS              = 'Velocity Offsets:'
    VELOCITY_OFFSETS_SET          = 'Current path offsets:'
    COMPASS_OFFSETS               = 'Compass Offsets:'
    COMPASS_OFFSETS_SET           = 'Current compass offsets:'
    COMPASS_SCALE_FACTORS         = 'Compass Scale Factors:'
    COMPASS_SCALE_FACTORS_SET     = 'Current compass scale factors:'
    TILT_OFFSETS                  = 'Tilt Offsets:'
    TILT_OFFSETS_SET              = 'Current tilt offsets:'
    SOLID_STATE_TILT_NOT_ENABLED  = 'Solid State Tilt is not currently enabled.'
        
class InstrumentCmds(BaseEnum):   # these all must be unique for the fsm and dictionaries to work correctly
    CONTROL_C                                  = '\x03'   # CTRL-C (end of text)
    DEPLOY_GO                                  = '\a'     # CTRL-G (bell)
    SET_TIME                                   = '1'
    ENTER_TIME                                 = 'enter_time'
    DEPLOY_MENU                                = '6'
    SET_NOTE                                   = 'set_note'
    ENTER_NOTE                                 = 'enter_note'
    SET_VELOCITY_FRAME                         = 'F'
    ENTER_VELOCITY_FRAME                       = 'enter_velocity_frame'
    SET_MONITOR                                = 'M'
    ENTER_MONITOR                              = 'enter_monitor'
    ENTER_LOG_DISPLAY_TIME                     = 'enter_log_display_time'
    ENTER_LOG_DISPLAY_FRACTIONAL_SECOND        = 'enter_log_display_fractional_second'
    ENTER_LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES = 'enter_log_display_acoustic_axis_velocities'
    ENTER_ACOUSTIC_AXIS_VELOCITY_FORMAT        = 'enter_log_display_acoustic_axis_velocity_format'
    SET_QUERY                                  = 'Q'
    ENTER_QUERY                                = 'enter_query'
    SET_FREQUENCY                              = '4'
    ENTER_FREQUENCY                            = 'enter_frequency'
    SET_MEAS_PER_SAMPLE                        = '5'
    ENTER_MEAS_PER_SAMPLE                      = 'enter_measurements_per_sample'
    SET_SAMPLE_PERIOD                          = ' 6'                         # make different from DEPLOY_MENU with leading space
    ENTER_SAMPLE_PERIOD                        = 'enter_sample_period'
    SET_SAMPLES_PER_BURST                      = '7'
    ENTER_SAMPLES_PER_BURST                    = 'enter_samples_per_burst'
    SET_BURST_INTERVAL_DAYS                    = '8'
    ENTER_BURST_INTERVAL_DAYS                  = 'enter_burst_interval_days'
    ENTER_BURST_INTERVAL_HOURS                 = 'enter_burst_interval_hours'
    ENTER_BURST_INTERVAL_MINUTES               = 'enter_burst_interval_minutes'
    ENTER_BURST_INTERVAL_SECONDS               = 'enter_burst_interval_seconds'
    SYSTEM_CONFIGURATION_MENU                  = 's'                          # intentionally lower case to differentiate it from other commands
    SYSTEM_CONFIGURATION_PASSWORD              = 'whipr'
    SYSTEM_CONFIGURATION_EXIT                  = 'x'
    SET_SI_CONVERSION                          = 'C\nn'
    ENTER_SI_CONVERSION                        = 'enter_si_conversion'
    SET_WARM_UP_INTERVAL                       = 'W'
    ENTER_WARM_UP_INTERVAL                     = 'enter_warm_up_interval'
    SET_THREE_AXIS_COMPASS                     = ' 1'                          # make different from SET_TIME with leading space
    ENTER_THREE_AXIS_COMPASS                   = 'enter_3_axis_compass'
    SET_SOLID_STATE_TILT                       = '2'                                          
    ENTER_SOLID_STATE_TILT                     = 'enter_solid_state_tilt'
    ANSWER_SOLID_STATE_TILT_YES                = YES
    SET_THERMISTOR                             = ' 3'                          # make different from CALIBRATION_MENU with leading space                 
    ENTER_THERMISTOR                           = 'enter_thermistor'
    ANSWER_THERMISTOR_NO                       = NO
    ANSWER_THERMISTOR_YES                      = YES
    SET_PRESSURE                               = ' 4'                          # make different from SET_FREQUENCY with leading space                         
    ENTER_PRESSURE                             = 'enter_pressure'
    SET_AUXILIARY                              = 'set_auxiliary'                          
    ENTER_AUXILIARY                            = 'enter_auxiliary'
    SET_SENSOR_ORIENTATION                     = 'o'                          
    ENTER_SENSOR_ORIENTATION                   = 'enter_sensor_orientation'
    CALIBRATION_MENU                           = '3'  
    VELOCITY_OFFSETS                           = 'V'                       
    VELOCITY_OFFSETS_SET                       = 'S'                           # intentionally upper case to differentiate it from other commands                
    COMPASS_OFFSETS                            = 'C'                       
    COMPASS_OFFSETS_SET                        = ' S'                          # make different from VELOCITY_OFFSETS_SET with leading space                
    COMPASS_SCALE_FACTORS                      = ' F'                          # make different from SET_VEL_FRAME with leading space
    COMPASS_SCALE_FACTORS_SET                  = '  S'                         # make different from COMPASS_OFFSETS_SET with 2 leading spaces                
    TILT_OFFSETS                               = 'T'                       
    TILT_OFFSETS_SET                           = '   S'                        # make different from COMPASS_SCALE_FACTORS_SET with 3 leading spaces                
    

class ProtocolStates(BaseEnum):
    """
    Protocol states for MAVS-4. Cherry picked from DriverProtocolState enum.
    """
    UNKNOWN       = DriverProtocolState.UNKNOWN
    COMMAND       = DriverProtocolState.COMMAND
    AUTOSAMPLE    = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ProtocolEvent(BaseEnum):
    """
    Protocol events for MAVS-4. Cherry picked from DriverEvent enum.
    """
    ENTER                = DriverEvent.ENTER
    EXIT                 = DriverEvent.EXIT
    GET                  = DriverEvent.GET
    SET                  = DriverEvent.SET
    DISCOVER             = DriverEvent.DISCOVER
    START_AUTOSAMPLE     = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE      = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT       = DriverEvent.EXECUTE_DIRECT
    START_DIRECT         = DriverEvent.START_DIRECT
    STOP_DIRECT          = DriverEvent.STOP_DIRECT
    CLOCK_SYNC           = DriverEvent.CLOCK_SYNC
    SCHEDULED_CLOCK_SYNC = DriverEvent.SCHEDULED_CLOCK_SYNC
    ACQUIRE_STATUS       = DriverEvent.ACQUIRE_STATUS


class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET              = ProtocolEvent.GET
    SET              = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC       = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS   = ProtocolEvent.ACQUIRE_STATUS         

# Device specific parameters.
class InstrumentParameters(DriverParameter):
    """
    Device parameters for MAVS-4.
    """
    # main menu parameters
    SYS_CLOCK                            = 'sys_clock'
    
    # deploy menu parameters
    NOTE1                                = 'note1'
    NOTE2                                = 'note2'
    NOTE3                                = 'note3'
    VELOCITY_FRAME                       = 'velocity_frame'
    MONITOR                              = 'monitor'
    LOG_DISPLAY_TIME                     = 'log/display_time'
    LOG_DISPLAY_FRACTIONAL_SECOND        = 'log/display_fractional_second'
    LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES = 'log/display_acoustic_axis_velocities'
    QUERY_MODE                           = 'query_mode'
    FREQUENCY                            = 'frequency'
    MEASUREMENTS_PER_SAMPLE              = 'measurements_per_sample'
    SAMPLE_PERIOD                        = 'sample_period'
    SAMPLES_PER_BURST                    = 'samples_per_burst'
    BURST_INTERVAL_DAYS                  = 'burst_interval_days'
    BURST_INTERVAL_HOURS                 = 'burst_interval_hours'
    BURST_INTERVAL_MINUTES               = 'burst_interval_minutes'
    BURST_INTERVAL_SECONDS               = 'burst_interval_seconds'
    
    # system configuration menu parameters
    SI_CONVERSION                        = 'si_conversion'
    WARM_UP_INTERVAL                     = 'warm_up_interval'
    THREE_AXIS_COMPASS                   = '3_axis_compass'
    SOLID_STATE_TILT                     = 'solid_state_tilt'
    THERMISTOR                           = 'thermistor'
    PRESSURE                             = 'pressure'
    AUXILIARY_1                          = 'auxiliary_1'
    AUXILIARY_2                          = 'auxiliary_2'
    AUXILIARY_3                          = 'auxiliary_3'
    SENSOR_ORIENTATION                   = 'sensor_orientation'
    SERIAL_NUMBER                        = 'serial_number'
    
    # calibration menu parameters
    VELOCITY_OFFSET_PATH_A               = 'velocity_offset_path_a'
    VELOCITY_OFFSET_PATH_B               = 'velocity_offset_path_b'
    VELOCITY_OFFSET_PATH_C               = 'velocity_offset_path_c'
    VELOCITY_OFFSET_PATH_D               = 'velocity_offset_path_d'
    COMPASS_OFFSET_0                     = 'comapss_offset_0'
    COMPASS_OFFSET_1                     = 'comapss_offset_1'
    COMPASS_OFFSET_2                     = 'comapss_offset_2'
    COMPASS_SCALE_FACTORS_0              = 'comapss_scale_factors_0'
    COMPASS_SCALE_FACTORS_1              = 'comapss_scale_factors_1'
    COMPASS_SCALE_FACTORS_2              = 'comapss_scale_factors_2'
    TILT_PITCH_OFFSET                    = 'tilt_pitch_offset'
    TILT_ROLL_OFFSET                     = 'tilt_roll_offset'
    
class DeployMenuParameters(BaseEnum):
    NOTE1                                = InstrumentParameters.NOTE1
    NOTE2                                = InstrumentParameters.NOTE2
    NOTE3                                = InstrumentParameters.NOTE3
    VELOCITY_FRAME                       = InstrumentParameters.VELOCITY_FRAME
    MONITOR                              = InstrumentParameters.MONITOR
    LOG_DISPLAY_TIME                     = InstrumentParameters.LOG_DISPLAY_TIME
    LOG_DISPLAY_FRACTIONAL_SECOND        = InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND
    LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES = InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES
    QUERY_MODE                           = InstrumentParameters.QUERY_MODE
    FREQUENCY                            = InstrumentParameters.FREQUENCY
    MEASUREMENTS_PER_SAMPLE              = InstrumentParameters.MEASUREMENTS_PER_SAMPLE
    SAMPLE_PERIOD                        = InstrumentParameters.SAMPLE_PERIOD
    SAMPLES_PER_BURST                    = InstrumentParameters.SAMPLES_PER_BURST
    BURST_INTERVAL_DAYS                  = InstrumentParameters.BURST_INTERVAL_DAYS
    BURST_INTERVAL_HOURS                 = InstrumentParameters.BURST_INTERVAL_HOURS
    BURST_INTERVAL_MINUTES               = InstrumentParameters.BURST_INTERVAL_MINUTES
    BURST_INTERVAL_SECONDS               = InstrumentParameters.BURST_INTERVAL_SECONDS
    
class SystemConfigurationMenuParameters(BaseEnum):
    SI_CONVERSION      = InstrumentParameters.SI_CONVERSION
    WARM_UP_INTERVAL   = InstrumentParameters.WARM_UP_INTERVAL
    THREE_AXIS_COMPASS = InstrumentParameters.THREE_AXIS_COMPASS
    SOLID_STATE_TILT   = InstrumentParameters.SOLID_STATE_TILT
    THERMISTOR         = InstrumentParameters.THERMISTOR
    PRESSURE           = InstrumentParameters.PRESSURE
    AUXILIARY_1        = InstrumentParameters.AUXILIARY_1
    AUXILIARY_2        = InstrumentParameters.AUXILIARY_2
    AUXILIARY_3        = InstrumentParameters.AUXILIARY_3
    SENSOR_ORIENTATION = InstrumentParameters.SENSOR_ORIENTATION
    SERIAL_NUMBER      = InstrumentParameters.SERIAL_NUMBER

class VelocityOffsetParameters(BaseEnum):
    VELOCITY_OFFSET_PATH_A = InstrumentParameters.VELOCITY_OFFSET_PATH_A
    VELOCITY_OFFSET_PATH_B = InstrumentParameters.VELOCITY_OFFSET_PATH_B
    VELOCITY_OFFSET_PATH_C = InstrumentParameters.VELOCITY_OFFSET_PATH_C
    VELOCITY_OFFSET_PATH_D = InstrumentParameters.VELOCITY_OFFSET_PATH_D

class CompassOffsetParameters(BaseEnum):
    COMPASS_OFFSET_0 = InstrumentParameters.COMPASS_OFFSET_0
    COMPASS_OFFSET_1 = InstrumentParameters.COMPASS_OFFSET_1
    COMPASS_OFFSET_2 = InstrumentParameters.COMPASS_OFFSET_2

class CompassScaleFactorsParameters(BaseEnum):
    COMPASS_SCALE_FACTORS_0 = InstrumentParameters.COMPASS_SCALE_FACTORS_0
    COMPASS_SCALE_FACTORS_1 = InstrumentParameters.COMPASS_SCALE_FACTORS_1
    COMPASS_SCALE_FACTORS_2 = InstrumentParameters.COMPASS_SCALE_FACTORS_2

class TiltOffsetParameters(BaseEnum):
    TILT_PITCH_OFFSET = InstrumentParameters.TILT_PITCH_OFFSET
    TILT_ROLL_OFFSET = InstrumentParameters.TILT_ROLL_OFFSET

class SubMenues(BaseEnum):
    ROOT          = 'root_menu'
    SET_TIME      = 'set_time'
    FLASH_CARD    = 'flash_card'
    CALIBRATION   = 'calibration'
    SLEEP         = 'sleep'
    BENCH_TESTS   = 'bench_tests'
    DEPLOY        = 'deploy'
    OFFLOAD       = 'offload'
    CONFIGURATION = 'configuration'
    PICO_DOS      = 'pico_dos'
    DUMMY         = 'dummy'

class Mavs4ProtocolParameterDict(ProtocolParameterDict):
          
    def update(self, name, response):
        #log.debug('Mavs4ProtocolParameterDict.update(): set %s from \n%s',
        # name, response)
        response = self._param_dict[name].update(response)
        return response
        
###
#   Driver for mavs4
###
class mavs4InstrumentDriver(SingleConnectionInstrumentDriver):

    """
    Instrument driver class for MAVS-4 driver.
    Uses CommandResponseInstrumentProtocol to communicate with the device
    """

    def __init__(self, evt_callback):
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
        # replace the driver's discover handler with one that applies the startup values after discovery
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED, 
                                         DriverEvent.DISCOVER, 
                                         self._handler_connected_discover)
    
    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params after we discover. 
        # For this instrument the driver puts the instrument into command mode during discover.
        log.debug("*** Handing discover from connected state, event: %s...", event)
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        log.debug("*** Applying startup params.")
        self.apply_startup_params()
        log.debug("*** Applied startup params.")
        return result

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = mavs4InstrumentProtocol(InstrumentPrompts,
                                                 INSTRUMENT_NEWLINE,
                                                 self._driver_event)
        
###############################################################################
# Data particles
###############################################################################

class Mavs4SampleDataParticleKey(BaseEnum):
    TIMESTAMP                = "timestamp"
    FRACTIONAL_SECOND        = 'fractional_second'
    ACOUSTIC_AXIS_VELOCITY_A = 'acoustic_axis_velocity_a'
    ACOUSTIC_AXIS_VELOCITY_B = 'acoustic_axis_velocity_b'
    ACOUSTIC_AXIS_VELOCITY_C = 'acoustic_axis_velocity_c'
    ACOUSTIC_AXIS_VELOCITY_D = 'acoustic_axis_velocity_d'
    VELOCITY_FRAME_EAST      = 'velocity_frame_east'
    VELOCITY_FRAME_NORTH     = 'velocity_frame_north'
    VELOCITY_FRAME_WEST      = 'velocity_frame_west'
    TEMPERATURE              = 'temperature'
    COMPASS_MX               = 'compass_mx'
    COMPASS_MY               = 'compass_my'
    PITCH                    = 'pitch'
    ROLL                     = 'roll'
                
class Mavs4SampleDataParticle(DataParticle):
    """
    Class for parsing sample data into a data particle structure for the MAVS-4 sensor. 
    """
    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the data sample format and parse it into
        values with appropriate tags.
        @throws SampleException If there is a problem with sample creation
        """
        match = SAMPLE_DATA_REGEX.match(self.raw_data)
        
        if not match:
            raise SampleException("Mavs4SampleDataParticle: No regex match of \
                                  parsed sample data: [%s]", self.raw_data)
        
        #log.debug('_build_parsed_values: match=%s', match.group(0))
                
        try:
            datetime = match.group(1) + ' ' + match.group(2)
            timestamp = time.strptime(datetime, "%m %d %Y %H %M %S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            fractional_second = int(match.group(3))
            acoustic_axis_velocity_a = int(match.group(4), 16)
            acoustic_axis_velocity_b = int(match.group(5), 16)
            acoustic_axis_velocity_c = int(match.group(6), 16)
            acoustic_axis_velocity_d = int(match.group(7), 16)
            velocity_frame_east = float(match.group(8))
            velocity_frame_north = float(match.group(9))
            velocity_frame_west = float(match.group(10))
            temperature = float(match.group(11))
            compass_mx = float(match.group(12))
            compass_my = float(match.group(13))
            pitch = float(match.group(14))
            roll = float(match.group(15))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))
                     
        result = [{DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: ntp_timestamp},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.FRACTIONAL_SECOND,
                   DataParticleKey.VALUE: fractional_second},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_A,
                   DataParticleKey.VALUE: acoustic_axis_velocity_a},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_B,
                   DataParticleKey.VALUE: acoustic_axis_velocity_b},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_C,
                   DataParticleKey.VALUE: acoustic_axis_velocity_c},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_D,
                   DataParticleKey.VALUE: acoustic_axis_velocity_d},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.VELOCITY_FRAME_EAST,
                   DataParticleKey.VALUE: velocity_frame_east},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.VELOCITY_FRAME_NORTH,
                   DataParticleKey.VALUE: velocity_frame_north},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.VELOCITY_FRAME_WEST,
                   DataParticleKey.VALUE: velocity_frame_west},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.COMPASS_MX,
                   DataParticleKey.VALUE: compass_mx},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.COMPASS_MY,
                   DataParticleKey.VALUE: compass_my},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: Mavs4SampleDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll}]
 
        log.debug('Mavs4SampleDataParticle: particle=%s', result)
        return result
    
class Mavs4StatusDataParticleKey(BaseEnum):
    VELOCITY_OFFSET_PATH_A  = InstrumentParameters.VELOCITY_OFFSET_PATH_A
    VELOCITY_OFFSET_PATH_B  = InstrumentParameters.VELOCITY_OFFSET_PATH_B
    VELOCITY_OFFSET_PATH_C  = InstrumentParameters.VELOCITY_OFFSET_PATH_C
    VELOCITY_OFFSET_PATH_D  = InstrumentParameters.VELOCITY_OFFSET_PATH_D
    COMPASS_OFFSET_0        = InstrumentParameters.COMPASS_OFFSET_0
    COMPASS_OFFSET_1        = InstrumentParameters.COMPASS_OFFSET_1
    COMPASS_OFFSET_2        = InstrumentParameters.COMPASS_OFFSET_2
    COMPASS_SCALE_FACTORS_0 = InstrumentParameters.COMPASS_SCALE_FACTORS_0
    COMPASS_SCALE_FACTORS_1 = InstrumentParameters.COMPASS_SCALE_FACTORS_1
    COMPASS_SCALE_FACTORS_2 = InstrumentParameters.COMPASS_SCALE_FACTORS_2
    TILT_PITCH_OFFSET       = InstrumentParameters.TILT_PITCH_OFFSET
    TILT_ROLL_OFFSET        = InstrumentParameters.TILT_ROLL_OFFSET
    SAMPLE_PERIOD           = InstrumentParameters.SAMPLE_PERIOD
    SAMPLES_PER_BURST       = InstrumentParameters.SAMPLES_PER_BURST
    BURST_INTERVAL_DAYS     = InstrumentParameters.BURST_INTERVAL_DAYS
    BURST_INTERVAL_HOURS    = InstrumentParameters.BURST_INTERVAL_HOURS
    BURST_INTERVAL_MINUTES  = InstrumentParameters.BURST_INTERVAL_MINUTES
    BURST_INTERVAL_SECONDS  = InstrumentParameters.BURST_INTERVAL_SECONDS
    SI_CONVERSION           = InstrumentParameters.SI_CONVERSION
                
class Mavs4StatusDataParticle(DataParticle):
    """
    Class for constructing status data into a status particle structure for
    the MAVS-4 sensor. The raw_data variable in the DataParticle base class
    needs to be initialized to a reference to a dictionary that contains the
    status parameters.
    """
    _data_particle_type = DataParticleType.STATUS

    def _build_parsed_values(self):
        """
        Build the status particle from a dictionary of parameters adding the
        appropriate tags.
        NOTE: raw_data references a dictionary with the status parameters, not
        a line of input
        @throws SampleException If there is a problem with particle creation
        """
                
        if not isinstance(self.raw_data, dict):
            raise SampleException("Error: raw_data is not a dictionary")
                     
        log.debug('Mavs4StatusDataParticle: raw_data=%s', self.raw_data)

        result = []
        for key, value in self.raw_data.items():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})
             
        log.debug('Mavs4StatusDataParticle: particle=%s', result)
        return result
    
###
#   Protocol for mavs4
###
class mavs4InstrumentProtocol(MenuInstrumentProtocol):
    """
    This protocol implements a simple command-response interaction for the
    menu based MAVs-4 instrument. It utilizes a dictionary that holds info on
    the more complex commands as well as command builders and response handles
    that can dynamically create and process the instrument interactions.
    """
    
    monitor_sub_parameters = (InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES, 
                              InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND, 
                              InstrumentParameters.LOG_DISPLAY_TIME)
    
    burst_interval_parameters = (InstrumentParameters.BURST_INTERVAL_DAYS,
                                 InstrumentParameters.BURST_INTERVAL_HOURS,
                                 InstrumentParameters.BURST_INTERVAL_MINUTES,
                                 InstrumentParameters.BURST_INTERVAL_SECONDS)
    
    # Lookup dictionary which contains the response, the next command, and the
    # possible parameter name for a given instrument command if it is needed.
    # The value None for the next command means there is no next command (the
    # interaction is complete). Commands that decide how to construct the
    # command or any of these values dynamically have there own build handlers
    # and are not in this table.
    Command_Response = {InstrumentCmds.SET_TIME : 
                            [InstrumentPrompts.SET_TIME, None, None],
                        InstrumentCmds.ENTER_TIME : 
                            [InstrumentPrompts.SET_TIME, None, None],
                        InstrumentCmds.ENTER_NOTE : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],
                        InstrumentCmds.SET_VELOCITY_FRAME : 
                            [InstrumentPrompts.VELOCITY_FRAME,
                             InstrumentCmds.ENTER_VELOCITY_FRAME,
                             None],
                        InstrumentCmds.ENTER_VELOCITY_FRAME : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],
                        InstrumentCmds.SET_MONITOR : 
                            [InstrumentPrompts.MONITOR,
                             InstrumentCmds.ENTER_MONITOR,
                             None],
                        InstrumentCmds.ENTER_LOG_DISPLAY_TIME : 
                            [InstrumentPrompts.LOG_DISPLAY, 
                             InstrumentCmds.ENTER_LOG_DISPLAY_FRACTIONAL_SECOND, 
                             InstrumentParameters.LOG_DISPLAY_TIME],
                        InstrumentCmds.ENTER_LOG_DISPLAY_FRACTIONAL_SECOND : 
                            [InstrumentPrompts.LOG_DISPLAY, 
                             InstrumentCmds.ENTER_LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES, 
                             InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND],
                        InstrumentCmds.SET_QUERY : 
                            [InstrumentPrompts.QUERY,
                             InstrumentCmds.ENTER_QUERY,
                             None],
                        InstrumentCmds.ENTER_QUERY : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],
                        InstrumentCmds.SET_FREQUENCY : 
                            [InstrumentPrompts.FREQUENCY,
                             InstrumentCmds.ENTER_FREQUENCY,
                             None],
                        InstrumentCmds.ENTER_FREQUENCY : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],                        
                        InstrumentCmds.SET_MEAS_PER_SAMPLE : 
                            [InstrumentPrompts.MEAS_PER_SAMPLE,
                             InstrumentCmds.ENTER_MEAS_PER_SAMPLE,
                             None],
                        InstrumentCmds.ENTER_MEAS_PER_SAMPLE : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],                        
                        InstrumentCmds.SET_SAMPLE_PERIOD : 
                            [InstrumentPrompts.SAMPLE_PERIOD,
                             InstrumentCmds.ENTER_SAMPLE_PERIOD,
                             None],
                        InstrumentCmds.ENTER_SAMPLE_PERIOD : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],                        
                        InstrumentCmds.SET_SAMPLES_PER_BURST : 
                            [InstrumentPrompts.SAMPLES_PER_BURST,
                             InstrumentCmds.ENTER_SAMPLES_PER_BURST,
                             None],
                        InstrumentCmds.ENTER_SAMPLES_PER_BURST : 
                            [InstrumentPrompts.DEPLOY_MENU, None, None],                        
                        InstrumentCmds.SET_BURST_INTERVAL_DAYS : 
                            [InstrumentPrompts.BURST_INTERVAL_DAYS,
                             InstrumentCmds.ENTER_BURST_INTERVAL_DAYS,
                             None],                        
                        InstrumentCmds.ENTER_BURST_INTERVAL_DAYS : 
                            [InstrumentPrompts.BURST_INTERVAL_HOURS, 
                             InstrumentCmds.ENTER_BURST_INTERVAL_HOURS, 
                             InstrumentParameters.BURST_INTERVAL_DAYS],                        
                        InstrumentCmds.ENTER_BURST_INTERVAL_HOURS : 
                            [InstrumentPrompts.BURST_INTERVAL_MINUTES, 
                             InstrumentCmds.ENTER_BURST_INTERVAL_MINUTES, 
                             InstrumentParameters.BURST_INTERVAL_HOURS],                        
                        InstrumentCmds.ENTER_BURST_INTERVAL_MINUTES : 
                            [InstrumentPrompts.BURST_INTERVAL_SECONDS, 
                             InstrumentCmds.ENTER_BURST_INTERVAL_SECONDS, 
                             InstrumentParameters.BURST_INTERVAL_MINUTES],                        
                        InstrumentCmds.ENTER_BURST_INTERVAL_SECONDS : 
                            [InstrumentPrompts.DEPLOY_MENU,
                             None,
                             InstrumentParameters.BURST_INTERVAL_SECONDS],                        
                        InstrumentCmds.DEPLOY_GO : 
                            [InstrumentPrompts.BEGIN_MEASUREMENT, None, None],                        
                        InstrumentCmds.SET_SI_CONVERSION : 
                            [InstrumentPrompts.SI_CONVERSION,
                             InstrumentCmds.ENTER_SI_CONVERSION,
                             None],                        
                        InstrumentCmds.ENTER_SI_CONVERSION : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.SYSTEM_CONFIGURATION_EXIT : 
                            [InstrumentPrompts.MAIN_MENU, None, None],                        
                        InstrumentCmds.SET_WARM_UP_INTERVAL : 
                            [InstrumentPrompts.WARM_UP_INTERVAL,
                             InstrumentCmds.ENTER_WARM_UP_INTERVAL,
                             None],                        
                        InstrumentCmds.SET_THREE_AXIS_COMPASS : 
                            [InstrumentPrompts.THREE_AXIS_COMPASS,
                             InstrumentCmds.ENTER_THREE_AXIS_COMPASS,
                             None],                        
                        InstrumentCmds.ENTER_THREE_AXIS_COMPASS : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.SET_SOLID_STATE_TILT : 
                            [InstrumentPrompts.SOLID_STATE_TILT,
                             InstrumentCmds.ENTER_SOLID_STATE_TILT,
                             None],                        
                        InstrumentCmds.ANSWER_SOLID_STATE_TILT_YES : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.SET_THERMISTOR : 
                            [InstrumentPrompts.THERMISTOR,
                             InstrumentCmds.ENTER_THERMISTOR,
                             None],                        
                        InstrumentCmds.ANSWER_THERMISTOR_NO : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.SET_PRESSURE : 
                            [InstrumentPrompts.PRESSURE,
                             InstrumentCmds.ENTER_PRESSURE,
                             None],                        
                        InstrumentCmds.ENTER_PRESSURE : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.SET_SENSOR_ORIENTATION : 
                            [InstrumentPrompts.SENSOR_ORIENTATION,
                             InstrumentCmds.ENTER_SENSOR_ORIENTATION,
                             None],                        
                        InstrumentCmds.ENTER_SENSOR_ORIENTATION : 
                            [InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                             InstrumentCmds.SYSTEM_CONFIGURATION_EXIT,
                             None],                        
                        InstrumentCmds.VELOCITY_OFFSETS : 
                            [InstrumentPrompts.VELOCITY_OFFSETS,
                             InstrumentCmds.VELOCITY_OFFSETS_SET,
                             None],                        
                        InstrumentCmds.VELOCITY_OFFSETS_SET: 
                            [InstrumentPrompts.VELOCITY_OFFSETS_SET, None, None],                        
                        InstrumentCmds.COMPASS_OFFSETS : 
                            [InstrumentPrompts.COMPASS_OFFSETS,
                             InstrumentCmds.COMPASS_OFFSETS_SET, None],                        
                        InstrumentCmds.COMPASS_OFFSETS_SET: 
                            [InstrumentPrompts.COMPASS_OFFSETS_SET, None, None],                        
                        InstrumentCmds.COMPASS_SCALE_FACTORS : 
                            [InstrumentPrompts.COMPASS_SCALE_FACTORS,
                             InstrumentCmds.COMPASS_SCALE_FACTORS_SET,
                             None],                        
                        InstrumentCmds.COMPASS_SCALE_FACTORS_SET: 
                            [InstrumentPrompts.COMPASS_SCALE_FACTORS_SET,
                             None,
                             None],                        
                        InstrumentCmds.TILT_OFFSETS : 
                            [InstrumentPrompts.TILT_OFFSETS,
                             InstrumentCmds.TILT_OFFSETS_SET,
                             None],                        
                        InstrumentCmds.TILT_OFFSETS_SET: 
                            [InstrumentPrompts.TILT_OFFSETS_SET, None, None],                        
                        }
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = INSTRUMENT_NEWLINE
        
        # create short alias for Directions class
        Directions = MenuInstrumentProtocol.MenuTree.Directions
        
        # create MenuTree object for navigating to sub-menus
        menu = MenuInstrumentProtocol.MenuTree({
            SubMenues.ROOT          : [],
            SubMenues.SET_TIME      : [Directions(InstrumentCmds.SET_TIME,
                                                  InstrumentPrompts.SET_TIME)],
            SubMenues.DEPLOY        : [Directions(InstrumentCmds.DEPLOY_MENU,
                                                  InstrumentPrompts.DEPLOY_MENU,
                                                  20)],
            SubMenues.CONFIGURATION : [Directions(InstrumentCmds.SYSTEM_CONFIGURATION_MENU,
                                                  InstrumentPrompts.SYSTEM_CONFIGURATION_PASSWORD),
                                       Directions(InstrumentCmds.SYSTEM_CONFIGURATION_PASSWORD,
                                                  InstrumentPrompts.SYSTEM_CONFIGURATION_MENU)],
            SubMenues.CALIBRATION   : [Directions(InstrumentCmds.CALIBRATION_MENU,
                                                  InstrumentPrompts.CALIBRATION_MENU)],
            })
        
        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)
                
        self._protocol_fsm = InstrumentFSM(ProtocolStates, 
                                           ProtocolEvent, 
                                           ProtocolEvent.ENTER,
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Set state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolStates.UNKNOWN)

        self._build_command_handlers()
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_cmd_dict()
        self._build_driver_dict()

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(mavs4InstrumentProtocol.chunker_sieve_function)

        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)


    @staticmethod
    def chunker_sieve_function(raw_data):
        # The method that detects data sample structures from instrument
 
        return_list = []
        
        for match in SAMPLE_DATA_REGEX.finditer(raw_data):
            return_list.append((match.start(), match.end()))
                
        return return_list
    
    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _got_chunk(self, structure, timestamp):
        """
        The base class got_data has gotten a structure from the chunker.
        Pass it to extract_sample with the appropriate particle objects and
        REGEXes. 
        """
        log.debug("_got_chunk: detected structure = <%s>", structure)
        self._extract_sample(Mavs4SampleDataParticle, SAMPLE_DATA_REGEX,
                             structure, timestamp)


    ########################################################################
    # overridden superclass methods
    ########################################################################

    def _get_response(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument, and do not ignore white space as in
        base class method.
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
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        while True:
            for item in prompt_list:
                if item in self._promptbuf:
                    return (item, self._linebuf)

            if time.time() > starttime + timeout:
                log.debug("_get_response: promptbuf=%s (%s), prompt_list: %s",
                          self._promptbuf, self._promptbuf.encode("hex"), prompt_list)
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

            time.sleep(.1)

    def _navigate_and_execute(self, cmd, **kwargs):
        """
        Navigate to a sub-menu and execute a list of commands instead of just
        one command as in the base class.  
        @param cmds The list of commands to execute.
        @param expected_prompt optional kwarg passed through to do_cmd_resp.
        @param timeout=timeout optional wakeup and command timeout.
        @param write_delay optional kwarg passed through to do_cmd_resp.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # go to root menu.
        got_prompt = False
        for i in range(10):
            try:
                self._go_to_root_menu()
                got_prompt = True
                break
            except:
                pass
            
        if not got_prompt:                
            raise InstrumentTimeoutException()
                                    
        # Get dest_submenu 
        dest_submenu = kwargs.pop('dest_submenu', None)
        if dest_submenu == None:
            raise InstrumentParameterException('_navigate_and_execute(): dest_submenu parameter missing')

        # save timeout and expected_prompt for the execution of the actual command after any traversing of the menu
        cmd_timeout = kwargs.pop('timeout', None)
        cmd_expected_prompt = kwargs.pop('expected_prompt', None)

        # iterate through the menu traversing directions 
        directions_list = self._menu.get_directions(dest_submenu)
        for directions in directions_list:
            log.debug('_navigate_and_execute: directions: %s', directions)
            command = directions.get_command()
            response = directions.get_response()
            timeout = directions.get_timeout()
            self._do_cmd_resp(command, expected_prompt = response, timeout = timeout, **kwargs)

        # restore timeout and expected_prompt for the execution of the actual command 
        kwargs['timeout'] = cmd_timeout
        kwargs['expected_prompt'] = cmd_expected_prompt
        command = cmd
        while command != None:
            log.debug('_navigate_and_execute: sending cmd:%s, kwargs: %s to _do_cmd_resp.', 
                      command, kwargs)
            command = self._do_cmd_resp(command, **kwargs)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device. 
        Send commands a character at a time to spoon feed instrument so it
        doesn't drop characters!
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and final response.
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('_do_cmd_resp: Cannot build command: %s' % cmd)
        
        (cmd_line, expected_response, next_cmd) = build_handler(command=cmd, **kwargs)
        if expected_prompt == None:
            expected_prompt = expected_response
            
        # Send command.
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: <%s> (%s), timeout=%s, expected_prompt=%s, expected_prompt(hex)=%s,', 
                  cmd_line, cmd_line.encode("hex"), timeout, expected_prompt, 
                    expected_prompt.encode("hex") if expected_prompt != None else '')
        for char in cmd_line:       
            self._linebuf = ''      # Clear line and prompt buffers for result.
            self._promptbuf = ''
            log.debug('mavs4InstrumentProtocol._do_cmd_resp: sending char <%s>', char)
            self._connection.send(char)
            # Wait for the character to be echoed, timeout exception
            self._get_response(timeout, expected_prompt='%s'%char)
        self._connection.send(INSTRUMENT_NEWLINE)
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: command sent, looking for response')
        (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get(cmd, None)
        if resp_handler:
            resp_result = resp_handler(result, prompt, **kwargs)
        else:
            resp_result = None
        if next_cmd == None:
            next_cmd = resp_result
        return next_cmd
   
    def _float_to_string(self, v):
        """
        Write a float value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific
        formatting.
        
        @param v A float val.
        @retval a float string formatted for "generic" set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return str(v)
                
    def _build_keypress_command(self, **kwargs):
        """
        Builder for simple, non-EOLN-terminated commands
        over-ridden to return dictionary expected by this classes
        _do_cmd_resp() method

        @param cmd The command to build
        @param args Unused arguments
        @retval list with:
            The command to be sent to the device,
            The response expected from the device (set to None to indicate not
            specified),
            The next command to be sent to device (set to None to indicate not
            specified)
        """
        cmd = kwargs.get('command', None)
        if cmd == None:
            raise InstrumentParameterException('_build_keypress_command: command not specified.')
        return ("%s" %(cmd), None, None)
    

    ########################################################################
    # implement virtual methods from base class.
    ########################################################################

    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @todo: This feels odd.  It feels like some of this logic should
               be handled by the state machine.  It's a pattern that we
               may want to review.  I say this because this command
               needs to be run from autosample or command mode.
        @raise: InstrumentProtocolException if not in command or streaming
        """

        log.debug("apply_startup_params: CURRENT STATE = %s",
                  self.get_current_state())
        if (self.get_current_state() != ProtocolStates.COMMAND):
            raise InstrumentProtocolException("Not in command state. Unable to apply startup parameters")

        # If our configuration on the instrument matches what we think it should be then 
        # we don't need to do anything.
        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s", startup_params)
        instrument_configured = True
        for param in startup_params:
            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                instrument_configured = False
                break
        if instrument_configured:
            log.debug("*** configured already")
            return
        
        log.debug("*** fetching startup parameters again")
        config = self.get_startup_config()
        log.debug("*** got startup config: %s", config)
        self._handler_command_set(config, startup=True)


    ########################################################################
    # State Unknown handlers.
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
        Discover current state; can be COMMAND or AUTOSAMPLE.  If the
        instrument is sleeping consider that to be in command state.
        @retval (next_state, result), (ProtocolStates.COMMAND or
        ProtocolStates.AUTOSAMPLE, None) if successful.
        """
        log.debug("*** Discovering from unknown state...")
        next_state = None
        result = None
        
        # try to get root menu prompt from the device using timeout if passed.
        # NOTE: this driver always tries to put instrument into command mode
        # so that parameters can be initialized
        try:
            self._go_to_root_menu()
            log.debug("*** got to root menu...")
        except InstrumentTimeoutException:
            # didn't get root menu prompt, so indicate that there is trouble
            # with the instrument
            raise InstrumentStateException('Unknown state.')
        else:
            # got root menu prompt, so device is in command mode           
            next_state = ProtocolStates.COMMAND
            result = ResourceAgentState.IDLE
            
        log.debug("*** returning next_state: %s, result: %s", next_state, result)
        return (next_state, result)


    ########################################################################
    # State Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not
        recognized.
        """
        # Command device to update parameters and send a config change event.
        self._update_params()
        
        log.debug("parameters values are: %s", str(self._param_dict.get_config()))

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
            
    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass
    
    def _set_query_mode_parameter(self, params_to_set):
        """
        Set the query mode parameter early since the burst interval parameters
        depend on it.
        @param params_to_set the parameters to set
        """
        
        
    def _set_parameter_sub_parameters(self, params_to_set):
        
        # handle monitor sub-parameters as a block to reduce I/O with instrument
        parameters_dict = dict([(x, params_to_set[x]) for x in self.monitor_sub_parameters if x in params_to_set])
        if parameters_dict:
            # set the parameter values so they can be gotten in the command builders
            for (key, value) in parameters_dict.iteritems():
                self._param_dict.set_value(key, value)
            if params_to_set.get(InstrumentParameters.MONITOR, NO) != YES:
                # if there isn't a set for enabling the monitor parameter then force a set so sub-parameters will be set
                dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.MONITOR)
                command = self._param_dict.get_submenu_write(InstrumentParameters.MONITOR)
                self._navigate_and_execute(command, name=key, value=YES,
                                           dest_submenu=dest_submenu, timeout=5)
                # check to see if the monitor parameter needs to be reset from the 'enabled' value
                monitor = self._param_dict.get(InstrumentParameters.MONITOR)
                if monitor != YES:
                    dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.MONITOR)
                    command = self._param_dict.get_submenu_write(InstrumentParameters.MONITOR)
                    self._navigate_and_execute(command, name=key, value=monitor,
                                               dest_submenu=dest_submenu, timeout=5)
            # remove the sub-parameters from the params_to_set dictionary
            for parameter in parameters_dict:
                del params_to_set[parameter]
        
        # handle burst interval parameters as a block to reduce I/O with instrument
        # ...but set the query mode first
        if InstrumentParameters.QUERY_MODE in params_to_set:
            dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.QUERY_MODE)
            command = self._param_dict.get_submenu_write(InstrumentParameters.QUERY_MODE)
            self._navigate_and_execute(command, name=InstrumentParameters.QUERY_MODE,
                                       value=params_to_set[InstrumentParameters.QUERY_MODE],
                                       dest_submenu=dest_submenu, timeout=5)
            del params_to_set[InstrumentParameters.QUERY_MODE]
        
        parameters_dict = dict([(x, params_to_set[x]) for x in self.burst_interval_parameters if x in params_to_set])
        if parameters_dict:
            # set the parameter values so they can be gotten in the command builders
            for (key, value) in parameters_dict.iteritems():
                self._param_dict.set_value(key, value)
            dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.BURST_INTERVAL_DAYS)
            command = self._param_dict.get_submenu_write(InstrumentParameters.BURST_INTERVAL_DAYS)
            self._navigate_and_execute(command, name=key,
                                       dest_submenu=dest_submenu, timeout=5)
            # remove the sub-parameters from the params_to_set dictionary
            for parameter in parameters_dict:
                del params_to_set[parameter]

    def _check_deployment_params(self, params):
        """
        Verify that some of the deployment params are either not all set at the
        same time or, if they are, all are set to correct values. This includes
        the measurement/samples, measurement frequency, and sample period.
        It also includes a check for validity of the burst and query mode
        relationship.
        
        @param params A dict of parameter names and values
        @retval A list of keys to set. Must have these values in the correct
        order to not hose things later.
        @throws InstrumentParameterException if the parameters conflict or one
        is missing
        """
        if (params == None):
            return list(params)
        if (not isinstance(params, dict)):
            raise InstrumentParameterException("Checking invalid deployment params")        

        return_list = list(params)

        # query mode / burst check
        query = (InstrumentParameters.QUERY_MODE in params)            
        burst = (InstrumentParameters.BURST_INTERVAL_DAYS in params)
            
        log.debug("*** query: %s, burst: %s", query, burst)
        if (query):
            log.debug("*** params query: %s",
                      params[InstrumentParameters.QUERY_MODE])
        
        if (query and burst) and (params[InstrumentParameters.QUERY_MODE] == YES):
            raise InstrumentParameterException("Cannot set burst interval when in query mode!")
        if (not query and burst) and (self._param_dict.get(InstrumentParameters.QUERY_MODE) == YES):
            raise InstrumentParameterException("Cannot set burst interval when in query mode!")

        # samples/freq/period relationship check
        target = {}
        if InstrumentParameters.FREQUENCY in params:
            target[InstrumentParameters.FREQUENCY] = \
            params[InstrumentParameters.FREQUENCY]
        
        if InstrumentParameters.MEASUREMENTS_PER_SAMPLE in params:
            target[InstrumentParameters.MEASUREMENTS_PER_SAMPLE] = \
            params[InstrumentParameters.MEASUREMENTS_PER_SAMPLE]
            
        if InstrumentParameters.SAMPLE_PERIOD in params:
            target[InstrumentParameters.SAMPLE_PERIOD] = \
            params[InstrumentParameters.SAMPLE_PERIOD]

        if (len(target) <= 1):
            return list(params)

        if ((len(target) == 2) and ((InstrumentParameters.FREQUENCY in target) and \
                                    (InstrumentParameters.MEASUREMENTS_PER_SAMPLE in target))):
            return_list.remove(InstrumentParameters.FREQUENCY)
            return_list.remove(InstrumentParameters.MEASUREMENTS_PER_SAMPLE)
            return_list.extend([InstrumentParameters.FREQUENCY,
                                InstrumentParameters.MEASUREMENTS_PER_SAMPLE])
            return return_list
                
        if ((len(target) == 3) and (target[InstrumentParameters.SAMPLE_PERIOD] * \
                                    target[InstrumentParameters.FREQUENCY] == \
                                    target[InstrumentParameters.MEASUREMENTS_PER_SAMPLE])):
            return_list.remove(InstrumentParameters.FREQUENCY)
            return_list.remove(InstrumentParameters.MEASUREMENTS_PER_SAMPLE)
            return_list.remove(InstrumentParameters.SAMPLE_PERIOD)
            return_list.extend([InstrumentParameters.FREQUENCY,
                                InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                                InstrumentParameters.SAMPLE_PERIOD])
            return return_list
        
        # if we made it this far, it cant be good)
        raise InstrumentParameterException("Invalid deployment parameter configuration! %s" %
                                           target)
        

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict configuration
        @param kwargs['startup'] startup boolean: True if we are starting up,
            false otherwise
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set
        parameters not ALL and not a dict, or if paramter can't be properly
        formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set
        command.
        @throws InstrumentProtocolException if set command could not be built
        or misunderstood.
        @throws InstrumentParameterException if the parameter configuration
        doesnt make sense for some reason (maybe invalid parameters or
        combinations of them)
        """
        next_state = None
        result = None

        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.
        try:
            params_to_set = args[0]           
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        else:
            if not isinstance(params_to_set, dict):
                raise InstrumentParameterException('Set parameters not a dict.')
                
        startup = kwargs.get('startup', False)
        if not startup:
            readonly = self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)
            #log.trace("Read only keys during non startup: %s", readonly)

            for (key, val) in params_to_set.iteritems():
                if key in readonly:
                    raise InstrumentParameterException("Attempt to set read only parameter (%s)" % key)
        log.debug("*** Params to set 1: %s", params_to_set)
        ordered_keys_to_set = self._check_deployment_params(params_to_set)
        log.debug("*** Params to set 2: %s", params_to_set)              
        self._set_parameter_sub_parameters(params_to_set)
        log.debug("*** Keys to set: %s", ordered_keys_to_set)

        #for (key, val) in params_to_set.iteritems():
        for key in ordered_keys_to_set:
            if key in params_to_set:
                dest_submenu = self._param_dict.get_menu_path_write(key)
                command = self._param_dict.get_submenu_write(key)
                self._navigate_and_execute(command, name=key, value=params_to_set[key],
                                           dest_submenu=dest_submenu, timeout=5)
        
        self._update_params()
            
        return (next_state, result)

    def _handler_command_get(self, *args, **kwargs):
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
        # Retireve each key in the list, raise if any are invalid.
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

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolStates.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        self._navigate_and_execute(InstrumentCmds.DEPLOY_GO, 
                                   dest_submenu=SubMenues.DEPLOY, 
                                   timeout=20, 
                                   *args, **kwargs)
                
        next_state = ProtocolStates.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (ProtocolStates.TEST, None).
        """
        next_state = None
        result = None

        next_state = ProtocolStates.TEST
        
        return (next_state, result)

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolStates.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        
        return (next_state, (next_agent_state, result))

    def _clock_sync(self):
        """
        Logic for syncing the clock
        """
        str_time = get_timestamp_delayed("%m/%d/%Y %H:%M:%S")
        log.trace("_clock_sync: time set to %s" %str_time)
        dest_submenu = self._param_dict.get_menu_path_write(InstrumentParameters.SYS_CLOCK)
        command = self._param_dict.get_submenu_write(InstrumentParameters.SYS_CLOCK)
        self._navigate_and_execute(command,
                                   name=InstrumentParameters.SYS_CLOCK,
                                   value=str_time,
                                   dest_submenu=dest_submenu,
                                   timeout=5)
        
    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or
        misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None
        self._clock_sync()
        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        
        self._generate_status_event()
    
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
    
    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolStates.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Issue stop command and switch to command if successful.
        got_root_prompt = False
        for i in range(2):
            try:
                self._go_to_root_menu()
                got_root_prompt = True
                break
            except:
                pass
            
        if not got_root_prompt:                
            raise InstrumentTimeoutException()
        
        next_state = ProtocolStates.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))
        
    def _handler_autosample_clock_sync(self, *args, **kwargs):
        """
        Execute a clock sync from autosample mode.
        For this command we have to move the instrument
        into command mode, do the clock sync, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)
            next_state = ProtocolStates.COMMAND
            next_agent_state = ResourceAgentState.COMMAND

            # Sync the clock
            self._clock_sync()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging(*args, **kwargs)
            next_state = None
            next_agent_state = None

        if(error):
            raise error

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

        self._do_cmd_direct(data)
                        
        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolStates.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _generate_status_event(self):
        if not self._driver_event:
            # can't send events, so don't bother creating the particle
            return
        
        # update parameters so param_dict values used for status are latest
        # and greatest.
        self._update_params()

        # build a dictionary of the parameters that are to be returned in the
        # status data particle
        status_params = {}
        for name in Mavs4StatusDataParticleKey.list():
            status_params[name] = self._param_dict.get(name)
            
        # Create status data particle, but pass in a reference to the
        # dictionary just created as first parameter instead of the 'line'.
        # The status data particle class will use the 'raw_data' variable as a
        # reference to a dictionary object to get access to parameter values
        # (see the Mavs4StatusDataParticle class).
        particle = Mavs4StatusDataParticle(status_params,
                                           preferred_timestamp=DataParticleKey.DRIVER_TIMESTAMP)
        status = particle.generate()

        # send particle as an event
        self._driver_event(DriverAsyncEvent.SAMPLE, status)
    
    def _send_control_c(self, count):
        # spoon feed the control-c characters so instrument doesn't drop them
        # if they are sent too fast
        for n in range(count):
            self._connection.send(InstrumentCmds.CONTROL_C)
            time.sleep(.1)            
    
    def _go_to_root_menu(self):
        # try to get root menu presuming the instrument is not sleeping by
        # sending single control-c
        for attempt in range(0,2):
            self._linebuf = ''
            self._promptbuf = ''
            self._connection.send(InstrumentCmds.CONTROL_C)
            try:
                (prompt, result) = self._get_response(timeout= 4,
                                                      expected_prompt=[InstrumentPrompts.MAIN_MENU,
                                                                       InstrumentPrompts.SLEEPING])
            except:
                log.trace('_go_to_root_menu: TIMED_OUT WAITING FOR ROOT MENU FROM ONE CONTROL-C !')
                pass
            else:
                if prompt == InstrumentPrompts.MAIN_MENU:
                    log.trace("_go_to_root_menu: got root menu prompt")
                    return
                if prompt == InstrumentPrompts.SLEEPING:
                    # instrument says it is sleeping, so try to wake it up
                    log.trace("_go_to_root_menu: GOT SLEEPING PROMPT !")
                    break
        # instrument acts like it's asleep, so try to wake it up and get to root menu
        count = 3   # send 3 control-c characters to get the instruments attention
        for attempt in range(0,5):
            self._linebuf = ''
            self._promptbuf = ''
            prompt = 'no prompt received'
            log.debug("_go_to_root_menu: sending %d control-c characters to wake up sleeping instrument", count)
            self._send_control_c(count)
            try:
                (prompt, result) = self._get_response(timeout= 4,
                                                      expected_prompt=[InstrumentPrompts.MAIN_MENU,
                                                                       InstrumentPrompts.SLEEP_WAKEUP,
                                                                       InstrumentPrompts.SLEEPING])
            except:
                log.debug('_go_to_root_menu: TIMED_OUT WAITING FOR PROMPT FROM 3 CONTROL-Cs !')
                pass
            log.debug("_go_to_root_menu: prompt after sending %d control-c characters = <%s>",
                      count, prompt)
            if prompt == InstrumentPrompts.MAIN_MENU:
                return
            if prompt == InstrumentPrompts.SLEEP_WAKEUP:
                count = 1    # send 1 control=c to get the root menu
            if prompt == InstrumentPrompts.SLEEPING:
                count = 3    # send 3 control-c chars to get the instruments attention
        log.debug("_go_to_root_menu: failed to get to root menu, prompt=%s (%s)",
                  prompt, prompt.encode("hex"))
        raise InstrumentTimeoutException("failed to get to root menu.")
                
    def _parse_sensor_orientation(self, sensor_orientation):
        #log.debug('_parse_sensor_orientation: vf=%s (%s)',
        #   sensor_orientation, sensor_orientation.encode('hex'))
        if 'Vertical/Down' in sensor_orientation:
            return '1'
        if 'Vertical/Up' in sensor_orientation:
            return '2'
        if 'Horizontal/Straight' in sensor_orientation:
            return '3'
        if 'Horizontal/Bent Left' in sensor_orientation:
            return '4'
        if 'Horizontal/Bent Right' in sensor_orientation:
            return '5'
        if 'Horizontal/Bent Down' in sensor_orientation:
            return '6'
        if 'Horizontal/Bent Up' in sensor_orientation:
            return '7'
        else:
            return ''
    
    def _parse_velocity_frame(self, velocity_frame):
        #log.debug('_parse_velocity_frame: vf=%s (%s)',
        #   velocity_frame, velocity_frame.encode('hex'))
        if 'No Velocity Frame' in velocity_frame:
            return '1'
        if '(U, V, W)' in velocity_frame:
            return '2'
        if '(E, N, W)' in velocity_frame:
            return '3'
        if '(S, \xE9, W)' in velocity_frame:
            return '4'
        else:
            return '0'
    
    def _parse_enable_disable(self, input):
        #log.debug('_parse_enable_disable: input=%s (%s)', input, input.encode('hex'))
        if 'Enabled' in input:
            return YES
        if 'Disabled' in input:
            return NO
        else:
            return 'unknown_state'
    
    def _parse_on_off(self, input):
        #log.debug('_parse_on_off: input=%s (%s)', input, input.encode('hex'))
        if 'Off' in input:
            return NO
        if 'On' in input:
            return YES
        else:
            # handle ENTER_LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES parameter case when not off
            return input
    
    def _build_driver_dict(self):
        """
        Populate the driver dictionary with MAVS4 metadata information.
        """
        self._driver_dict = DriverDict()
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)
    
    def _build_cmd_dict(self):
        """
        Populate the command dictionary with MAVS4 metadata information. Empty
        for the MAVS4 instrument as no additional commands are supported.
        """
        self._cmd_dict = ProtocolCommandDict()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with MAVS4 parameters.
        For each parameter key add value formatting function for set commands.
        """
        
        # The parameter dictionary.
        self._param_dict = Mavs4ProtocolParameterDict()
        
        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SYS_CLOCK,
                           r'.*\[(.*)\].*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.ROOT,
                           submenu_read=InstrumentCmds.SET_TIME,
                           menu_path_write=SubMenues.SET_TIME,
                           submenu_write=InstrumentCmds.ENTER_TIME,
                           description="System clock",
                           type="string",
                           value_description="A time between 1970 and 2038, formatted as 'MM/DD/YY HH:MM:SS'"))
    
        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.NOTE1,
                           r'.*Notes 1\| (.*?)\r\n.*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_NOTE,
                           description="Deployment note line 1",
                           display_name="Note line 1",
                           type="string",
                           value_description="Line of a note describing the deployment"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.NOTE2,
                           r'.*2\| (.*?)\r\n.*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_NOTE,
                           description="Deployment note line 2",
                           display_name="Note line 2",
                           type="string",
                           value_description="Line of a note describing the deployment"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.NOTE3,
                           r'.*3\| (.*?)\r\n.*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_NOTE,
                           description="Deployment note line 3",
                           display_name="Note line 3",
                           type="string",
                           value_description="Line of a note describing the deployment"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.VELOCITY_FRAME,
                           r'.*Data  F\| Velocity Frame (.*?) TTag FSec Axes.*', 
                           lambda match : self._parse_velocity_frame(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           default_value='3',
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_VELOCITY_FRAME,
                           description="Velocity frame",
                           type="enum",
                           value_description="No velocity frame,  MAVS4 frame (U, V, W), Earth frame (E, N, W), or Earth Frame(S, ?, W)"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.MONITOR,
                           r'.*M\| Monitor\s+(\w+).*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           value='',
                           default_value=YES,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_MONITOR,
                           description="Data monitor enabled",
                           display_name="Data monitor",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
	    RegexParameter(InstrumentParameters.LOG_DISPLAY_TIME,
                           r'.*M\| Monitor\s+\w+\s+(\w+).*', 
                           lambda match : self._parse_on_off(match.group(1)),
                           lambda string : str(string),
                           visibility=ParameterDictVisibility.READ_ONLY,
                           regex_flags=re.DOTALL,
                           default_value=YES,
                           value='',
                           description="Log/display time with each sample while monitoring",
                           display_name="Log display time",
                           type="bool",
                           value_description="Time logging on or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND,
                           r'.*M\| Monitor\s+\w+\s+\w+\s+(\w+).*', 
                           lambda match : self._parse_on_off(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           default_value=YES,
                           value='',
                           description="Log/display time with fractional seconds",
                           display_name="Display fractional seconds",
                           type="bool",
                           value_description="Fractional seconds on or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES,
                           r'.*M\| Monitor\s+\w+\s+\w+\s+\w+\s+(\w+).*', 
                           lambda match : self._parse_on_off(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           value='',
                           description="Log/display acoustic axis velocities",
                           display_name="Display acoustic axis velocities",
                           type="bool",
                           value_description="Acoustic axis velocities on or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.QUERY_MODE,
                           r'.*Q\| Query Mode\s+(\w+).*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=NO,
                           startup_param=True,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_QUERY,
                           description="Enable or disable query mode",
                           display_name="Query mode",
                           type="bool",
                           value_description="Query mode on or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.FREQUENCY,
                           r'.*4\| Measurement Frequency\s+(\d+.\d+)\s+\[Hz\].*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           default_value=1.0,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_FREQUENCY,
                           description="The rate at which measurements are taken to form a sample (applies to all enabled sensors)",
                           display_name="Measurement frequency",
                           type="float",
                           units="Hz",
                           value_description="0.01 to 50.0"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                           r'.*5\| Measurements/Sample\s+(\d+)\s+\[M/S\].*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           default_value=1,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_MEAS_PER_SAMPLE,
                           description="The number of individual measurements that are averaged to form a sample (applies to all enabled sensors)",
                           display_name="Measurements per sample",
                           type="int",
                           value_description="1 to 10000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SAMPLE_PERIOD,
                            '.*6\| Sample Period\s+(\d+.\d+)\s+\[sec\].*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_SAMPLE_PERIOD,
                           description="The interval between samples",
                           display_name="Sample period",
                           type="float",
                           units="seconds",
                           value_description="0.02 to 10000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SAMPLES_PER_BURST,
                           r'.*7\| Samples/Burst\s+(\d+)\s+\[S/B\].*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_SAMPLES_PER_BURST,
                           description="The number of samples (single data records) in a burst. Each sample is displayed if the data monitor is enabled and logged if flash card logging is enabled.",
                           display_name="Samples per burst",
                           type="int",
                           value_description="1 to 100000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.BURST_INTERVAL_DAYS,
                           r'.*8\| Burst Interval\s+(\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           default_value=0,
                           menu_path_read=SubMenues.DEPLOY,
                           submenu_read=None,
                           menu_path_write=SubMenues.DEPLOY,
                           submenu_write=InstrumentCmds.SET_BURST_INTERVAL_DAYS,
                           description="The days value in the interval between bursts. Set to 0 for continuous sampling. Burst interval is disabled when query mode is enabled.",
                           display_name="Burst interval days",
                           type="int",
                           units="days",
                           value_description="0 to 366"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.BURST_INTERVAL_HOURS,
                           r'.*8\| Burst Interval\s+\d+\s+(\d+):.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           default_value=0,
                           description="The hours value in the interval between bursts. Set to 0 for continuous sampling. Burst interval is disabled when query mode is enabled.",
                           display_name="Burst interval hours",
                           type="int",
                           units="hours",
                           value_description="0 to 23"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.BURST_INTERVAL_MINUTES,
                           r'.*8\| Burst Interval\s+\d+\s+\d+:(\d+):.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           default_value=0,
                           description="The minutes value in the interval between bursts. Set to 0 for continuous sampling. Burst interval is disabled when query mode is enabled.",
                           display_name="Burst interval minutes",
                           type="int",
                           units="minutes",
                           value_description="0 to 59"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.BURST_INTERVAL_SECONDS,
                           r'.*8\| Burst Interval\s+\d+\s+\d+:\d+:(\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           default_value=0,
                           description="The seconds value in the interval between bursts. Set to 0 for continuous sampling. Burst interval is disabled when query mode is enabled.",
                           display_name="Burst interval seconds",
                           type="int",
                           units="seconds",
                           value_description="0 to 59"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SI_CONVERSION,
                           r'.*<C> Binary to SI Conversion\s+(\d+.\d+)\s+.*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_SI_CONVERSION,
                           description="Coefficient to use during conversion from binary to SI",
                           display_name="SI conversion coefficient",
                           type="float",
                           value_description="0.0010000 to 0.0200000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.WARM_UP_INTERVAL,
                           r'.*<W> Warm up interval\s+(\w)\w*\s+.*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           startup_param=True,
                           default_value='f',
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_WARM_UP_INTERVAL,
                           description="Adjusts warm up time to allow for working with auxiliary sensors that have slower response times to get the required accuracy",
                           display_name="Warm up interval for sensors",
                           type="enum",
                           value_description="Fast or slow"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.THREE_AXIS_COMPASS,
                           r'.*<1> 3-Axis Compass\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=YES,
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,                             
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_THREE_AXIS_COMPASS,
                           description="Enable the 3-axis compass sensor",
                           display_name="3-axis compass enabled",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SOLID_STATE_TILT,
                           r'.*<2> Solid State Tilt\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=YES,
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,                             
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_SOLID_STATE_TILT,
                           description="Enable the solid state tilt sensor",
                           display_name="Solid state tilt sensor",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.THERMISTOR,
                           r'.*<3> Thermistor\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=YES,
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_THERMISTOR,
                           description="Enable the thermister sensor",
                           display_name="Thermistor sensor",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.PRESSURE,
                           r'.*<4> Pressure\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=NO,            # this parameter can only be set to NO (meaning disabled)
                                                         # support for setting it to YES has not been implemented
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_PRESSURE,
                           description="Enable the pressure sensor",
                           display_name="Pressure sensor",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.AUXILIARY_1,
                           r'.*<5> Auxiliary 1\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=NO,            # this parameter can only be set to NO (meaning disabled)
                                                         # support for setting it to YES has not been implemented
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_AUXILIARY,
                           description="Enable auxiliary sensor #1",
                           display_name="Aux sensor 1",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.AUXILIARY_2,
                           r'.*<6> Auxiliary 2\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=NO,            # this parameter can only be set to NO (meaning disabled)
                                                         # support for setting it to YES has not been implemented
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_AUXILIARY,
                           description="Enable auxiliary sensor #2",
                           display_name="Aux sensor 2",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.AUXILIARY_3,
                           r'.*<7> Auxiliary 3\s+(\w+)\s+.*', 
                           lambda match : self._parse_enable_disable(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value=NO,            # this parameter can only be set to NO (meaning disabled)
                                                         # support for setting it to YES has not been implemented
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_AUXILIARY,
                           description="Enable auxiliary sensor #3",
                           display_name="Aux sensor 3",
                           type="bool",
                           value_description="On or off"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SENSOR_ORIENTATION,
                           r'.*<O> Sensor Orientation\s+(.*)\n.*', 
                           lambda match : self._parse_sensor_orientation(match.group(1)),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           default_value='2',
                           startup_param=True,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=SubMenues.CONFIGURATION,
                           submenu_write=InstrumentCmds.SET_SENSOR_ORIENTATION,
                           description="Sensor orientation",
                           type="enum",
                           value_description="One of: Veritcal/Down, Vertical/Up, Horizontal/Straight, Horizontal/Bent Left, Horizontal/Bent Right, Horizontal/Bent Down, Horizontal/Bent Up"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.SERIAL_NUMBER,
                           r'.*<S> Serial Number\s+(\w+)\s+.*', 
                           lambda match : match.group(1),
                           lambda string : str(string),
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CONFIGURATION,
                           submenu_read=None,
                           menu_path_write=None,
                           submenu_write=None,
                           description="The instrument serial number",
                           display_name="Serial number",
                           type="int",
                           value_description="10000 to 20000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.VELOCITY_OFFSET_PATH_A,
                           r'.*Current path offsets:\s+(\w+)\s+.*', 
                           lambda match : int(match.group(1), 16),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="The velocity offset value for path A",
                           display_name="Velocity offset path A",
                           type="string",
                           units="",
                           value_description="A hex value from F300 to 0D00"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.VELOCITY_OFFSET_PATH_B,
                           r'.*Current path offsets:\s+\w+\s+(\w+)\s+.*', 
                           lambda match : int(match.group(1), 16),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="The velocity offset value for path B",
                           display_name="Velocity offset path B",
                           type="string",
                           units="",
                           value_description="A hex value from F300 to 0D00"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.VELOCITY_OFFSET_PATH_C,
                           r'.*Current path offsets:\s+\w+\s+\w+\s+(\w+)\s+.*', 
                           lambda match : int(match.group(1), 16),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="The velocity offset value for path B",
                           display_name="Velocity offset path B",
                           type="string",
                           units="",
                           value_description="A hex value from F300 to 0D00"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.VELOCITY_OFFSET_PATH_D,
                           r'.*Current path offsets:\s+\w+\s+\w+\s+\w+\s+(\w+)\s+.*', 
                           lambda match : int(match.group(1), 16),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.VELOCITY_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="The velocity offset value for path C",
                           display_name="Velocity offset path C",
                           type="string",
                           units="",
                           value_description="A hex value from F300 to 0D00"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_OFFSET_0,
                           r'.*Current compass offsets:\s+([-+]?\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass offset 0",
                           type="int",
                           value_description="-400 to 400"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_OFFSET_1,
                           r'.*Current compass offsets:\s+[-+]?\d+\s+([-+]?\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass offset 1",
                           type="int",
                           value_description="-400 to 400"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_OFFSET_2,
                           r'.*Current compass offsets:\s+[-+]?\d+\s+[-+]?\d+\s+([-+]?\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass offset 2",
                           type="int",
                           value_description="-400 to 400"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_SCALE_FACTORS_0,
                           r'.*Current compass scale factors:\s+(\d+.\d+)\s+.*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass scale factor 0",
                           type="float",
                           value_description="0.200 to 5.000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_SCALE_FACTORS_1,
                           r'.*Current compass scale factors:\s+\d+.\d+\s+(\d+.\d+)\s+.*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass scale factor 1",
                           type="float",
                           value_description="0.200 to 5.000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.COMPASS_SCALE_FACTORS_2,
                           r'.*Current compass scale factors:\s+\d+.\d+\s+\d+.\d+\s+(\d+.\d+)\s+.*', 
                           lambda match : float(match.group(1)),
                           self._float_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.COMPASS_SCALE_FACTORS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Compass scale factor 2",
                           type="float",
                           value_description="0.200 to 5.000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.TILT_PITCH_OFFSET,
                           r'.*Current tilt offsets:\s+(\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           value=-1,     # to indicate that the parameter has not been read from the instrument
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.TILT_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Tilt offset for pitch axis",
                           display_name="Tilt offset (pitch)",
                           type="int",
                           value_description="0 to 30000"))

        self._param_dict.add_parameter(
            RegexParameter(InstrumentParameters.TILT_ROLL_OFFSET,
                           r'.*Current tilt offsets:\s+\d+\s+(\d+)\s+.*', 
                           lambda match : int(match.group(1)),
                           self._int_to_string,
                           value=-1,     # to indicate that the parameter has not been read from the instrument
                           regex_flags=re.DOTALL,
                           visibility=ParameterDictVisibility.READ_ONLY,
                           menu_path_read=SubMenues.CALIBRATION,
                           submenu_read=InstrumentCmds.TILT_OFFSETS,
                           menu_path_write=None,
                           submenu_write=None,
                           description="Tilt offset for roll axis",
                           display_name="Tilt offset (roll)",
                           type="int",
                           value_description="0 to 30000"))

    def _build_command_handlers(self):
        # these build handlers will be called by the base class during the navigate_and_execute sequence.        
        self._add_build_handler(InstrumentCmds.TILT_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TILT_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_SCALE_FACTORS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_SCALE_FACTORS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COMPASS_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.VELOCITY_OFFSETS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.VELOCITY_OFFSETS_SET, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SENSOR_ORIENTATION, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SENSOR_ORIENTATION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_AUXILIARY, self._build_enter_auxiliary_command)
        self._add_build_handler(InstrumentCmds.SET_AUXILIARY, self._build_set_auxiliary_command)
        self._add_build_handler(InstrumentCmds.ENTER_PRESSURE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_PRESSURE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ANSWER_THERMISTOR_NO, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ANSWER_THERMISTOR_YES, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_THERMISTOR, self._build_enter_thermistor_command)
        self._add_build_handler(InstrumentCmds.SET_THERMISTOR, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ANSWER_SOLID_STATE_TILT_YES, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SOLID_STATE_TILT, self._build_enter_solid_state_tilt_command)
        self._add_build_handler(InstrumentCmds.SET_SOLID_STATE_TILT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_THREE_AXIS_COMPASS, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_THREE_AXIS_COMPASS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_WARM_UP_INTERVAL, self._build_enter_warm_up_interval_command)
        self._add_build_handler(InstrumentCmds.SET_WARM_UP_INTERVAL, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SI_CONVERSION, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SI_CONVERSION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_SECONDS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_MINUTES, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_HOURS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_BURST_INTERVAL_DAYS, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.SET_BURST_INTERVAL_DAYS, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SAMPLES_PER_BURST, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SAMPLES_PER_BURST, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_SAMPLE_PERIOD, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_SAMPLE_PERIOD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_MEAS_PER_SAMPLE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_MEAS_PER_SAMPLE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_FREQUENCY, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_FREQUENCY, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_QUERY, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_QUERY, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_ACOUSTIC_AXIS_VELOCITY_FORMAT, self._build_enter_log_display_acoustic_axis_velocity_format_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES, self._build_enter_log_display_acoustic_axis_velocities_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_FRACTIONAL_SECOND, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_LOG_DISPLAY_TIME, self._build_simple_sub_parameter_enter_command)
        self._add_build_handler(InstrumentCmds.ENTER_MONITOR, self._build_enter_monitor_command)
        self._add_build_handler(InstrumentCmds.SET_MONITOR, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_VELOCITY_FRAME, self._build_enter_velocity_frame_command)
        self._add_build_handler(InstrumentCmds.SET_VELOCITY_FRAME, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENTER_NOTE, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_NOTE, self._build_set_note_command)
        self._add_build_handler(InstrumentCmds.ENTER_TIME, self._build_simple_enter_command)
        self._add_build_handler(InstrumentCmds.SET_TIME, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_PASSWORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SYSTEM_CONFIGURATION_EXIT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CALIBRATION_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_GO, self._build_simple_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SET_TIME,
                                   self._parse_time_response)
        self._add_response_handler(InstrumentCmds.DEPLOY_MENU,
                                   self._parse_deploy_menu_response)
        self._add_response_handler(InstrumentCmds.SYSTEM_CONFIGURATION_PASSWORD,
                                   self._parse_system_configuration_menu_response)
        self._add_response_handler(InstrumentCmds.VELOCITY_OFFSETS_SET,
                                   self._parse_velocity_offset_set_response)
        self._add_response_handler(InstrumentCmds.COMPASS_OFFSETS_SET,
                                   self._parse_compass_offset_set_response)
        self._add_response_handler(InstrumentCmds.COMPASS_SCALE_FACTORS_SET,
                                   self._parse_compass_scale_factors_set_response)
        self._add_response_handler(InstrumentCmds.TILT_OFFSETS_SET,
                                   self._parse_tilt_offset_set_response)
   
    def _build_enter_auxiliary_command(self, **kwargs):
        """
        Build handler for auxiliary enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('auxiliary enter command requires a name.')
        # THIS PARAMETER ONLY SUPPORTS THE NO VALUE IN THIS IMPLEMENTATION
        # THE YES VALUE WOULD REQUIRE MORE DIALOG WITH INSTRUMENT
        cmd = "%s" %(self._param_dict.format(name, NO))
        log.debug("_build_enter_auxiliary_command: cmd=%s", cmd)
        return (cmd, InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                InstrumentCmds.SYSTEM_CONFIGURATION_EXIT)

    def _build_set_auxiliary_command(self, **kwargs):
        """
        Build handler for auxiliary set command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('set auxiliary command requires a name.')
        cmd = "%s" %(int(name[-1]) + 4)
        response = InstrumentPrompts.AUXILIARY.replace("*", name[-1])
        log.debug("_build_set_auxiliary_command: cmd=%s", cmd)
        return (cmd, response, InstrumentCmds.ENTER_AUXILIARY)

    def _build_enter_solid_state_tilt_command(self, **kwargs):
        """
        Build handler for solid state tilt enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('solid state tilt enter command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('solid state tilt  enter command requires a value.')
        cmd = "%s" %(self._param_dict.format(name, value)[0])
        log.debug("_build_enter_solid_state_tilt_command: cmd=%s", cmd)
        if cmd != InstrumentCmds.ANSWER_SOLID_STATE_TILT_YES:
            return (cmd, InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                    InstrumentCmds.SYSTEM_CONFIGURATION_EXIT)
        else:
            return (cmd, InstrumentPrompts.LOAD_DEFAULT_TILT,
                    InstrumentCmds.ANSWER_SOLID_STATE_TILT_YES)

    def _build_enter_thermistor_command(self, **kwargs):
        """
        Build handler for thermistor enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('thermistor enter command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('thermistor enter command requires a value.')
        cmd = "%s" %(self._param_dict.format(name, value)[0])
        log.debug("_build_enter_thermistor_command: cmd=%s", cmd)
        if cmd == InstrumentCmds.ANSWER_THERMISTOR_NO:
            return (cmd, InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                    InstrumentCmds.SYSTEM_CONFIGURATION_EXIT)
        else:
            return (InstrumentCmds.ANSWER_THERMISTOR_YES,
                    InstrumentPrompts.THERMISTOR_OFFSET,
                    InstrumentCmds.ANSWER_THERMISTOR_NO)

    def _build_enter_warm_up_interval_command(self, **kwargs):
        """
        Build handler for warm up interval enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('warm up interval enter command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('warm up interval enter command requires a value.')
        cmd = "%s" %(self._param_dict.format(name, value)[0])
        return (cmd, InstrumentPrompts.SYSTEM_CONFIGURATION_MENU,
                InstrumentCmds.SYSTEM_CONFIGURATION_EXIT)

    def _build_enter_log_display_acoustic_axis_velocity_format_command(self, **kwargs):
        """
        Build handler for log display acoustic axis velocity format enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one) 
        """
        cmd = "%s" %(self._param_dict.get(InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES)[0])
        log.debug("_build_enter_log_display_acoustic_axis_velocity_format_command: cmd=%s", cmd)
        return (cmd, InstrumentPrompts.DEPLOY_MENU, None)

    def _build_enter_log_display_acoustic_axis_velocities_command(self, **kwargs):
        """
        Build handler for log display acoustic axis velocities enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one for the NO cmd) 
        """
        cmd = self._param_dict.get(InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES)
        log.debug("_build_enter_log_display_acoustic_axis_velocities_command: cmd=%s", cmd)
        if cmd == NO:
            return (cmd, InstrumentPrompts.DEPLOY_MENU, None)
        return (YES, InstrumentPrompts.VELOCITY_FORMAT,
                InstrumentCmds.ENTER_ACOUSTIC_AXIS_VELOCITY_FORMAT)

    def _build_simple_sub_parameter_enter_command(self, **kwargs):
        """
        Build handler for simple sub parameter enter command 
        String cmd constructed by param dict formatting function.
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device
        """
        cmd_name = kwargs.get('command', None)
        if cmd_name == None:
            raise InstrumentParameterException('simple sub parameter enter command requires a command.')
        parameter_name = self.Command_Response[cmd_name][2]
        if parameter_name == None:
            raise InstrumentParameterException('simple sub parameter enter command requires a parameter name.')
        cmd = self._param_dict.format(parameter_name)
        response = self.Command_Response[cmd_name][0]
        next_cmd = self.Command_Response[cmd_name][1]
        log.debug("_build_simple_sub_parameter_enter_command: cmd=%s", cmd)
        return (cmd, response, next_cmd)

    def _build_enter_monitor_command(self, **kwargs):
        """
        Build handler for monitor enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('enter monitor command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('enter monitor command requires a value.')
        cmd = self._param_dict.format(name, value)
        log.debug("_build_enter_monitor_command: cmd=%s", cmd)
        if value == NO:
            return (cmd, InstrumentPrompts.DEPLOY_MENU, None)            
        return (cmd, InstrumentPrompts.LOG_DISPLAY, InstrumentCmds.ENTER_LOG_DISPLAY_TIME)

    def _build_enter_velocity_frame_command(self, **kwargs):
        """
        Build handler for velocity frame enter command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one)
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('enter velocity frame command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('enter velocity frame command requires a value.')
        cmd = self._param_dict.format(name, value)
        log.debug("_build_enter_velocity_frame_command: cmd=%s", cmd)
        if value == 1:
            return (cmd, InstrumentPrompts.DISPLAY_FORMAT, None)            
        return (cmd, InstrumentPrompts.SELECTION, None)

    def _build_set_note_command(self, **kwargs):
        """
        Build handler for note set command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('set note command requires a name.')
        cmd = "%s" %(name[-1])
        log.debug("_build_set_note_command: cmd=%s", cmd)
        return (cmd, InstrumentPrompts.NOTE_INPUT, InstrumentCmds.ENTER_NOTE)

    def _build_simple_enter_command(self, **kwargs):
        """
        Build handler for simple enter command 
        String cmd constructed by param dict formatting function.
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device
        """
        cmd_name = kwargs.get('command', None)
        if cmd_name == None:
            raise InstrumentParameterException('simple enter command requires a command.')
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('simple enter command requires a name.')
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('simple enter command requires a value.')
        cmd = self._param_dict.format(name, value)
        response = self.Command_Response[cmd_name][0]
        next_cmd = self.Command_Response[cmd_name][1]
        log.debug("_build_simple_enter_command: cmd=%s", cmd)
        return (cmd, response, next_cmd)

    def _build_simple_command(self, **kwargs):
        """
        Build handler for simple set command 
        @retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device
        """
        cmd_name = kwargs.get('command', None)
        if cmd_name == None:
            raise InstrumentParameterException('simple command requires a command.')
        cmd = cmd_name
        if cmd_name in self.Command_Response:
            response = self.Command_Response[cmd_name][0]
            next_cmd = self.Command_Response[cmd_name][1]
        else:
            response = None
            next_cmd = None
        log.debug("_build_simple_command: cmd=%s", cmd)
        return (cmd, response, next_cmd)

    def _parse_time_response(self, response, prompt, **kwargs):
        """
        Parse handler for time command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.GET_TIME in response:
            raise InstrumentProtocolException('get time command not recognized by instrument: %s.' % response)
        
        log.debug("_parse_time_response: response=%s", response)

        if not self._param_dict.update(InstrumentParameters.SYS_CLOCK, response.splitlines()[-1]):
            log.debug('_parse_time_response: Failed to parse %s', InstrumentParameters.SYS_CLOCK)
        return None
              
    def _parse_deploy_menu_response(self, response, prompt, **kwargs):
        """
        Parse handler for deploy menu command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.DEPLOY_MENU in response:
            raise InstrumentProtocolException('deploy menu command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in DeployMenuParameters.list():
            #log.debug('_parse_deploy_menu_response: name=%s, response=%s', parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_deploy_menu_response: Failed to parse %s', parameter)
        return None
              
    def _parse_system_configuration_menu_response(self, response, prompt, **kwargs):
        """
        Parse handler for system configuration menu command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.SYSTEM_CONFIGURATION_MENU in response:
            raise InstrumentProtocolException('system configuration menu command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in SystemConfigurationMenuParameters.list():
            #log.debug('_parse_system_configuration_menu_response: name=%s, response=%s'
            #   parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_system_configuration_menu_response: Failed to parse %s', parameter)
        return None
              
    def _parse_velocity_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for velocity offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.VELOCITY_OFFSETS_SET in response:
            raise InstrumentProtocolException('velocity offset set command not recognized by instrument: %s.', response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in VelocityOffsetParameters.list():
            #log.debug('_parse_velocity_offset_set_response: name=%s, response=%s', parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_velocity_offset_set_response: Failed to parse %s', parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_compass_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for compass offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.COMPASS_OFFSETS_SET in response:
            raise InstrumentProtocolException('compass offset set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in CompassOffsetParameters.list():
            #log.debug('_parse_compass_offset_set_response: name=%s, response=%s', parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_compass_offset_set_response: Failed to parse %s' %parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_compass_scale_factors_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for compass scale factors set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.COMPASS_SCALE_FACTORS_SET in response:
            raise InstrumentProtocolException('compass scale factors set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in CompassScaleFactorsParameters.list():
            #log.debug('_parse_compass_scale_factors_set_response: name=%s, response=%s',
            #   parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_compass_scale_factors_set_response: Failed to parse %s', parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def _parse_tilt_offset_set_response(self, response, prompt, **kwargs):
        """
        Parse handler for tilt offset set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.TILT_OFFSETS_SET in response:
            raise InstrumentProtocolException('tilt offset set command not recognized by instrument: %s.' %response)
        
        name = kwargs.get('name', None)
        if name != InstrumentParameters.ALL:
            # only get the parameter values if called from _update_params()
            return None
        for parameter in TiltOffsetParameters.list():
            #log.debug('_parse_tilt_offset_set_response: name=%s, response=%s', parameter, response)
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_tilt_offset_set_response: Failed to parse %s', parameter)
        # don't leave instrument in calibration menu because it doesn't wakeup from sleeping correctly
        self._go_to_root_menu()
        return None
              
    def  _get_prompt(self, timeout=8, delay=4):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  There is no 
        'wakeup' for this instrument when it is in 'deployed' mode,
        so the best that can be done is to see if it responds or not.
        
        Clear buffers and send some CRs to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Grab time for timeout.
        starttime = time.time()
        
        # get longest prompt to match by sorting the prompts longest to shortest
        prompts = self._sorted_longest_to_shortest(self._prompts.list())
        log.debug("prompts=%s", prompts)
        
        while True:
            # Clear the prompt buffer.
            self._promptbuf = ''
        
            # Send a line return and wait a 4 sec.
            log.debug('Sending newline to get a response from the instrument.')
            self._connection.send(INSTRUMENT_NEWLINE)
            time.sleep(delay)
            
            for item in prompts:
                if item in self._promptbuf:
                    log.debug('_get_prompt got prompt: %s', repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """        
        if self.get_current_state() != ProtocolStates.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        deploy_menu_prameters_parsed = False
        system_configuration_menu_prameters_parsed = False
        velocity_offset_set_prameters_parsed = False
        compass_offset_set_prameters_parsed = False
        compass_scale_factors_set_prameters_parsed = False
        tilt_offset_set_prameters_parsed = False
        
        # sort the list so that the solid_state_tilt parameter will be updated
        # and accurate before the tilt_offset parameters are updated, so that
        # the check of the solid_state_tilt param value reflects what's on the
        # instrument
        for key in sorted(InstrumentParameters.list()):
            if key == InstrumentParameters.ALL:
                # this is not the name of any parameter
                continue
            dest_submenu = self._param_dict.get_menu_path_read(key)
            command = self._param_dict.get_submenu_read(key)

            if key in DeployMenuParameters.list():
                # only screen scrape the deploy menu once for efficiency
                if deploy_menu_prameters_parsed == True:
                    continue
                else:
                    deploy_menu_prameters_parsed = True
                    # set name to ALL so _parse_deploy_menu_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in SystemConfigurationMenuParameters.list():
                # only screen scrape the system configuration menu once for efficiency
                if system_configuration_menu_prameters_parsed == True:
                    continue
                else:
                    system_configuration_menu_prameters_parsed = True
                    # set name to ALL so _parse_system_configuration_menu_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in VelocityOffsetParameters.list():
                # only screen scrape the velocity offset set response once for efficiency
                if velocity_offset_set_prameters_parsed == True:
                    continue
                else:
                    velocity_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_velocity_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL

            elif key in CompassOffsetParameters.list():
                # only screen scrape the compass offset set response once for efficiency
                if compass_offset_set_prameters_parsed == True:
                    continue
                else:
                    compass_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_compass_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            elif key in CompassScaleFactorsParameters.list():
                # only screen scrape the compass scale factors set response once for efficiency
                if compass_scale_factors_set_prameters_parsed == True:
                    continue
                else:
                    compass_scale_factors_set_prameters_parsed = True
                    # set name to ALL so _parse_compass_scale_factors_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            elif key in TiltOffsetParameters.list():
                # only screen scrape the tilt offset set response once for efficiency
                if tilt_offset_set_prameters_parsed == True:
                    continue
                elif self._param_dict.get(InstrumentParameters.SOLID_STATE_TILT) == NO:
                    # don't get the tilt offset parameters if the solid state tilt is disabled
                    self._param_dict.set_value(InstrumentParameters.TILT_PITCH_OFFSET, -1)
                    self._param_dict.set_value(InstrumentParameters.TILT_ROLL_OFFSET, -1)
                    tilt_offset_set_prameters_parsed = True               
                    continue
                else:
                    tilt_offset_set_prameters_parsed = True
                    # set name to ALL so _parse_tilt_offset_set_response() knows to get all values
                    key = InstrumentParameters.ALL
                                                        
            self._navigate_and_execute(command, name=key, dest_submenu=dest_submenu, timeout=10)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            
    def _sorted_longest_to_shortest(self, list):
        sorted_list = sorted(list, key=len, reverse=True)
        #log.debug("list=%s \nsorted=%s", list, sorted_list)
        return sorted_list
