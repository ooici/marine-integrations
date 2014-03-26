"""
@package mi.instrument.noaa.iris.ooicore.driver
@file marine-integrations/mi/instrument/noaa/iris/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for IRIS TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time

import ntplib

from mi.core.log import get_logger


log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0a'
IRIS_STRING = 'IRIS,'
IRIS_COMMAND_STRING = '*9900XY'
IRIS_DATA_ON = 'C2'  # turns on continuous data
IRIS_DATA_OFF = 'C-OFF'  # turns off continuous data
IRIS_DUMP_01 = '-DUMP-SETTINGS'  # outputs current settings
IRIS_DUMP_02 = '-DUMP2'  # outputs current extended settings

# default timeout.
TIMEOUT = 10


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class ExportedInstrumentCommand(BaseEnum):
    DUMP_01 = "EXPORTED_INSTRUMENT_DUMP_SETTINGS"
    DUMP_02 = "EXPORTED_INSTRUMENT_DUMP_EXTENDED_SETTINGS"


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    DISCOVER = DriverEvent.DISCOVER
    DUMP_01 = ExportedInstrumentCommand.DUMP_01
    DUMP_02 = ExportedInstrumentCommand.DUMP_02
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    DUMP_01 = ProtocolEvent.DUMP_01
    DUMP_02 = ProtocolEvent.DUMP_02
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """


###############################################################################
# Command Response (not a particle but uses regex and chunker to parse command
# responses rather than the normal get_response() method)
###############################################################################

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_ON  # turns on continuous data
    DATA_OFF = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_OFF  # turns off continuous data
    DUMP_SETTINGS_01 = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP_01  # outputs current settings
    DUMP_SETTINGS_02 = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP_02  # outputs current extended settings


class IRISCommandResponse():
    _compiled_regex = None

    def __init__(self, raw_data):
        """ 
        Construct a IRISCommandResponse object
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data
        self.iris_command_response = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'IRIS,'  # pattern starts with IRIS '
        pattern += r'(.*),'  # group 1: time
        pattern += r'\*9900XY'  # generic part of IRIS command
        pattern += r'(.*)'  # group 2: echoed command
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if IRISCommandResponse._compiled_regex is None:
            IRISCommandResponse._compiled_regex = re.compile(IRISCommandResponse.regex())
        return IRISCommandResponse._compiled_regex

    def check_command_response(self, expected_response):
        """
        Generic command response method; the expected response
        is passed in as a parameter; that is used to check 
        whether the response from the sensor is valid (positive)
        or not.
        """
        return_value = False

        match = IRISCommandResponse.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of command response: [%s]" %
                                  self.raw_data)
        try:
            self.iris_command_response = match.group(2)
            if expected_response is not None:
                if self.iris_command_response == expected_response:
                    return_value = True
            else:
                return_value = True

        except ValueError:
            raise SampleException("check_command_response: ValueError" +
                                  " while converting data: [%s]" %
                                  self.raw_data)

        return return_value


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    IRIS_PARSED = 'botpt_iris_sample'
    IRIS_STATUS1 = 'botpt_iris_status1'
    IRIS_STATUS2 = 'botpt_iris_status2'


class IRISDataParticleKey(BaseEnum):
    TIME = "iris_time"
    X_TILT = "iris_x_tilt"
    Y_TILT = "iris_y_tilt"
    TEMP = "temperature"
    SN = "serial_number"


class IRISDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642
       IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642       
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = IRIS
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = x.xxxx (float degrees)
        Y_TILT = y.yyyy (float degrees)
        Temp = tt.tt (float degrees C)
        Serial Number = sn
    """
    _data_particle_type = DataParticleType.IRIS_PARSED
    _compiled_regex = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'IRIS,'  # pattern starts with IRIS '
        pattern += r'(.*),'  # 1 time
        pattern += r'( -*[.0-9]+),'  # 2 x-tilt
        pattern += r'( -*[.0-9]+),'  # 3 y-tilt
        pattern += r'(.*),'  # 4 temp
        pattern += r'(.*)'  # 5 serial number
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if IRISDataParticle._compiled_regex is None:
            IRISDataParticle._compiled_regex = re.compile(IRISDataParticle.regex())
        return IRISDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = IRISDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            iris_time = match.group(1)
            timestamp = time.strptime(iris_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            temperature = float(match.group(4))
            sn = str(match.group(5))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" % self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.SN,
             DataParticleKey.VALUE: sn}
        ]

        return result


class IRISStatus01ParticleKey(BaseEnum):
    TIME = "iris_time"
    MODEL = "iris_model"
    FIRMWARE_VERSION = "iris_firmware_version"
    SERIAL_NUMBER = "iris_serial_number"
    ID_NUMBER = "iris_id_number"
    VBIAS = "iris_vbias"
    VGAIN = "iris_vgain"
    VMIN = "iris_vmin"
    VMAX = "iris_vmax"
    AVALS = "iris_avals"
    TCOEFS = "iris_tcoefs"
    N_SAMP = "iris_n_samp"
    XZERO = "iris_xzero"
    YZERO = "iris_yzero"
    REST = "iris_rest"


###############################################################################
# Status Particles
###############################################################################
class IRISStatus01Particle(DataParticle):
    _data_particle_type = DataParticleType.IRIS_STATUS1
    _compiled_basic_regex = None
    _compiled_complete_regex = None
    iris_status_response = "No response found."

    @staticmethod
    def basic_regex():
        """
        Example of output from DUMP-SETTINGS command:
        
        IRIS,2013/06/19 21:26:20,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01
        IRIS,2013/06/19 21:26:20,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
        IRIS,2013/06/19 21:26:20,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
        IRIS,2013/06/19 21:26:21,*01: Vmin:  -2.50  -2.50   2.50   2.50
        IRIS,2013/06/19 21:26:21,*01: Vmax:   2.50   2.50   2.50   2.50
        IRIS,2013/06/19 21:26:21,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/19 21:26:21,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/19 21:26:21, -49.297,  31.254,193.84, 25.98,11.96,N9655
        IRIS,2013/06/19 21:26:21,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/19 21:26:21,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/19 21:26:21,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
        NANO,V,2013/06/19 21:26:21.000,13.987252,24.991366335
        IRIS,2013/06/19 21:26:21,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
        IRIS,2013/06/19 21:26:21,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00
        IRIS,2013/06/19 21:26:21,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-   
        """
        pattern = 'IRIS,.*\*APPLIED GEOMECHANICS.*baud FV-'
        return pattern

    @staticmethod
    def complete_regex():
        iris_date_time = r'IRIS,\d+/\d+/\d+ \d+:\d+:\d+'
        floating_point_num = r'(-?\d+\.\d+)'
        four_floats = r'\s+?'.join([floating_point_num] * 4)
        six_floats = r'\s+?'.join([floating_point_num] * 6)
        pattern = [
            '(%(iris_date_time)s),\*APPLIED GEOMECHANICS Model %(word)s Firmware %(word)s %(word)s %(word)s',
            '%(iris_date_time)s,\*01: Vbias=\s+%(four_fp)s',
            '%(iris_date_time)s,\*01: Vgain=\s+%(four_fp)s',
            '%(iris_date_time)s,\*01: Vmin:\s+%(four_fp)s',
            '%(iris_date_time)s,\*01: Vmax:\s+%(four_fp)s',
            '%(iris_date_time)s,\*01: a0=\s+%(six_fp)s',
            '%(iris_date_time)s,\*01: a1=\s+%(six_fp)s',
            '%(iris_date_time)s,\*01: a2=\s+%(six_fp)s',
            '%(iris_date_time)s,\*01: a3=\s+%(six_fp)s',
            '%(iris_date_time)s,\*01: Tcoef 0: Ks=\s+%(int)s\s+Kz=\s+%(int)s\s+Tcal=\s+%(int)s',
            '%(iris_date_time)s,\*01: Tcoef 1: Ks=\s+%(int)s\s+Kz=\s+%(int)s\s+Tcal=\s+%(int)s',
            '%(iris_date_time)s,\*01: N_SAMP=\s*%(int)s\s*Xzero=\s*%(float)s\s*Yzero=\s*%(float)s',
            '%(iris_date_time)s,\*01: (TR.*FV-)'
        ]
        pattern = '.*'.join(pattern) % {
            'iris_date_time': iris_date_time,
            'float': floating_point_num,
            'four_fp': four_floats,
            'six_fp': six_floats,
            'int': '(-?\d+)',
            'word': '(\S+)'}
        return pattern

    @staticmethod
    def basic_regex_compiled():
        if IRISStatus01Particle._compiled_basic_regex is None:
            IRISStatus01Particle._compiled_basic_regex = re.compile(IRISStatus01Particle.basic_regex(), re.DOTALL)
        return IRISStatus01Particle._compiled_basic_regex

    @staticmethod
    def complete_regex_compiled():
        if IRISStatus01Particle._compiled_complete_regex is None:
            IRISStatus01Particle._compiled_complete_regex = re.compile(IRISStatus01Particle.complete_regex(), re.DOTALL)
        return IRISStatus01Particle._compiled_complete_regex

    def _build_parsed_values(self):
        """
        Parse the values from the dump settings command
        """
        match = self.complete_regex_compiled().match(self.raw_data)
        log.warning(match.groups())
        if not match:
            raise SampleException('No regex match of parsed status data: [%s]' % self.raw_data)

        try:
            iris_time = match.group(1)
            timestamp = time.strptime(iris_time, "IRIS,%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            model = match.group(2)
            firmware_version = match.group(3)
            serial_number = match.group(4)
            id_num = match.group(5)
            vbias = [float(match.group(x)) for x in range(6, 10)]
            vgain = [float(match.group(x)) for x in range(10, 14)]
            vmin = [float(match.group(x)) for x in range(14, 18)]
            vmax = [float(match.group(x)) for x in range(18, 22)]
            avals = [float(match.group(x)) for x in range(22, 46)]
            tcoefs = [int(match.group(x)) for x in range(46, 52)]
            n_samp = int(match.group(52))
            xzero = float(match.group(53))
            yzero = float(match.group(54))
            rest = match.group(55)
        except ValueError:
            raise SampleException('Exception parsing status data: [%s]' % self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.MODEL,
             DataParticleKey.VALUE: model},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.FIRMWARE_VERSION,
             DataParticleKey.VALUE: firmware_version},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.SERIAL_NUMBER,
             DataParticleKey.VALUE: serial_number},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.ID_NUMBER,
             DataParticleKey.VALUE: id_num},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.VBIAS,
             DataParticleKey.VALUE: vbias},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.VGAIN,
             DataParticleKey.VALUE: vgain},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.VMIN,
             DataParticleKey.VALUE: vmin},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.VMAX,
             DataParticleKey.VALUE: vmax},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.AVALS,
             DataParticleKey.VALUE: avals},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.TCOEFS,
             DataParticleKey.VALUE: tcoefs},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.N_SAMP,
             DataParticleKey.VALUE: n_samp},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.XZERO,
             DataParticleKey.VALUE: xzero},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.YZERO,
             DataParticleKey.VALUE: yzero},
            {DataParticleKey.VALUE_ID: IRISStatus01ParticleKey.REST,
             DataParticleKey.VALUE: rest},
        ]
        return result

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the iris_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The iris_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.iris_status_response = NEWLINE.join([line for line in self.raw_data.split(NEWLINE)
                                                  if line.startswith(IRIS_STRING)])


class IRISStatus02ParticleKey(BaseEnum):
    TIME = 'iris_time'
    TBIAS = 'iris_tbias'
    ABOVE = 'iris_above'
    BELOW = 'iris_below'
    ADC_DELAY = 'iris_adc_delay'
    PCA_MODEL = 'iris_pca_model'
    FIRMWARE_REV = 'iris_firmware_rev'
    XCHAN_GAIN = 'iris_xchan_gain'
    YCHAN_GAIN = 'iris_ychan_gain'
    TEMP_GAIN = 'iris_temp_gain'
    OUTPUT_MODE = 'iris_output_mode'
    CAL_MODE = 'iris_cal_mode'
    CONTROL = 'iris_control'
    RS232 = 'iris_rs232'
    RTC_INSTALLED = 'iris_rtc_installed'
    RTC_TIMING = 'iris_rtc_timing'
    EXT_FLASH = 'iris_external_flash'
    XPOS_RELAY_THRESHOLD = 'iris_xpos_relay_threshold'
    XNEG_RELAY_THRESHOLD = 'iris_xneg_relay_threshold'
    YPOS_RELAY_THRESHOLD = 'iris_ypos_relay_threshold'
    YNEG_RELAY_THRESHOLD = 'iris_yneg_relay_threshold'
    RELAY_HYSTERESIS = 'iris_relay_hysteresis'
    CAL_METHOD = 'iris_calibration_method'
    POS_LIMIT = 'iris_positive_limit'
    NEG_LIMIT = 'iris_negative_limit'
    NUM_CAL_POINTS = 'iris_calibration_points'
    CAL_POINTS_X = 'iris_cal_points_x'
    CAL_POINTS_Y = 'iris_cal_points_y'
    BIAXIAL_SENSOR_TYPE = 'iris_biaxial sensor_type'
    ADC_TYPE = 'iris_adc_type'
    DAC_SCALE_FACTOR = 'iris_dac_output_scale_factor'
    DAC_SCALE_UNITS = 'iris_dac_output_scale_units'
    SAMPLE_STORAGE_CAPACITY = 'iris_sample_storage_capacity'
    BAE_SCALE_FACTOR = 'iris_bae_scale_factor'


# noinspection PyMethodMayBeStatic
class IRISStatus02Particle(DataParticle):
    _data_particle_type = DataParticleType.IRIS_STATUS2
    _compiled_basic_regex = None
    _compiled_complete_regex = None
    iris_status_response = "No response found."

    @staticmethod
    def basic_regex():
        """
        Example of output from DUMP2 command:
        IRIS,2013/06/12 23:55:09,*01: TBias: 8.85 
        IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        IRIS,2013/06/12 18:04:01,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
        IRIS,2013/06/12 18:04:01,*01: ADCDelay:  310 
        IRIS,2013/06/12 18:04:01,*01: PCA Model: 90009-01
        IRIS,2013/06/12 18:04:01,*01: Firmware Version: 5.2 Rev N
        LILY,2013/06/12 18:04:01,-330.000,-247.647,290.73, 24.50,11.88,N9656
        IRIS,2013/06/12 18:04:01,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
        IRIS,2013/06/12 18:04:01,*01: Output Mode: Degrees
        IRIS,2013/06/12 18:04:01,*01: Calibration performed in Degrees
        IRIS,2013/06/12 18:04:01,*01: Control: Off
        IRIS,2013/06/12 18:04:01,*01: Using RS232
        IRIS,2013/06/12 18:04:01,*01: Real Time Clock: Not Installed
        IRIS,2013/06/12 18:04:01,*01: Use RTC for Timing: No
        IRIS,2013/06/12 18:04:01,*01: External Flash Capacity: 0 Bytes(Not Installed)
        IRIS,2013/06/12 18:04:01,*01: Relay Thresholds:
        IRIS,2013/06/12 18:04:01,*01:   Xpositive= 1.0000   Xnegative=-1.0000
        IRIS,2013/06/12 18:04:01,*01:   Ypositive= 1.0000   Ynegative=-1.0000
        IRIS,2013/06/12 18:04:01,*01: Relay Hysteresis:
        IRIS,2013/06/12 18:04:01,*01:   Hysteresis= 0.0000
        IRIS,2013/06/12 18:04:01,*01: Calibration method: Dynamic 
        IRIS,2013/06/12 18:04:01,*01: Positive Limit=26.25   Negative Limit=-26.25 
        IRIS,2013/06/12 18:04:02,*01: Calibration Points:025  X: Disabled  Y: Disabled
        IRIS,2013/06/12 18:04:02,*01: Biaxial Sensor Type (0)
        IRIS,2013/06/12 18:04:02,*01: ADC: 12-bit (internal)
        IRIS,2013/06/12 18:04:02,*01: DAC Output Scale Factor: 0.10 Volts/Degree
        HEAT,2013/06/12 18:04:02,-001,0001,0024
        IRIS,2013/06/12 18:04:02,*01: Total Sample Storage Capacity: 372
        IRIS,2013/06/12 18:04:02,*01: BAE Scale Factor:  2.88388 (arcseconds/bit)
        """
        pattern = r'IRIS,.*\*01: TBias.*\(arcseconds/bit\)'
        return pattern

    @staticmethod
    def complete_regex():
        """
        More complete regex for parsing all fields from the status message
        """
        pattern = [r'(%(iris_date_time)s),\*01: TBias: %(fp)s',
                   r'%(iris_date_time)s,\*Above %(fp)s\(KZMinTemp\): kz\[0\]=\s+%(int)s, kz\[1\]=\s+%(int)s',
                   r'%(iris_date_time)s,\*Below %(fp)s\(KZMinTemp\): kz\[2\]=\s+%(int)s, kz\[3\]=\s+%(int)s',
                   r'%(iris_date_time)s,\*01: ADCDelay:\s+%(int)s',
                   r'%(iris_date_time)s,\*01: PCA Model: %(word)s',
                   r'%(iris_date_time)s,\*01: Firmware Version: %(to_eol)s',
                   r'%(iris_date_time)s,\*01: X Ch Gain= %(fp)s, Y Ch Gain= %(fp)s, Temperature Gain= %(fp)s',
                   r'%(iris_date_time)s,\*01: Output Mode: %(word)s',
                   r'%(iris_date_time)s,\*01: Calibration performed in %(word)s',
                   r'%(iris_date_time)s,\*01: Control: %(word)s',
                   r'%(iris_date_time)s,\*01: Using %(word)s',
                   r'%(iris_date_time)s,\*01: Real Time Clock: %(to_eol)s',
                   r'%(iris_date_time)s,\*01: Use RTC for Timing: %(word)s',
                   r'%(iris_date_time)s,\*01: External Flash Capacity: %(to_eol)s',
                   r'%(iris_date_time)s,\*01: Relay Thresholds:',
                   r'%(iris_date_time)s,\*01:   Xpositive=\s*%(fp)s\s+Xnegative=\s*%(fp)s',
                   r'%(iris_date_time)s,\*01:   Ypositive=\s*%(fp)s\s+Ynegative=\s*%(fp)s',
                   r'%(iris_date_time)s,\*01: Relay Hysteresis:',
                   r'%(iris_date_time)s,\*01:   Hysteresis= %(fp)s',
                   r'%(iris_date_time)s,\*01: Calibration method: %(word)s',
                   r'%(iris_date_time)s,\*01: Positive Limit=%(fp)s\s+Negative Limit=\s*%(fp)s',
                   r'%(iris_date_time)s,\*01: Calibration Points:%(int)s\s+X:\s*%(word)s\s*Y:\s*%(word)s',
                   r'%(iris_date_time)s,\*01: Biaxial Sensor Type \(%(int)s\)',
                   r'%(iris_date_time)s,\*01: ADC: %(to_eol)s',
                   r'%(iris_date_time)s,\*01: DAC Output Scale Factor: %(fp)s %(word)s',
                   r'%(iris_date_time)s,\*01: Total Sample Storage Capacity: %(int)s',
                   r'%(iris_date_time)s,\*01: BAE Scale Factor:  %(fp)s \(arcseconds/bit\)']
        pattern = '.*'.join(pattern) % {'iris_date_time': r'IRIS,\d+/\d+/\d+ \d+:\d+:\d+',
                                        'fp': r'(-?\d+\.\d+)',
                                        'int': r'(-?\d+)',
                                        'word': '(\S+)',
                                        'to_eol': '(.+?)$'}
        return pattern

    @staticmethod
    def basic_regex_compiled():
        if IRISStatus02Particle._compiled_basic_regex is None:
            IRISStatus02Particle._compiled_basic_regex = re.compile(IRISStatus02Particle.basic_regex(), re.DOTALL)
        return IRISStatus02Particle._compiled_basic_regex

    @staticmethod
    def complete_regex_compiled():
        if IRISStatus02Particle._compiled_complete_regex is None:
            IRISStatus02Particle._compiled_complete_regex = re.compile(IRISStatus02Particle.complete_regex(),
                                                                       re.DOTALL | re.MULTILINE)
        return IRISStatus02Particle._compiled_complete_regex

    def encoders(self):
        return {}

    def _build_parsed_values(self):
        match = self.complete_regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException('No regex match of parsed status data: [%s]' % self.raw_data)

        try:
            iris_time = match.group(1)
            timestamp = time.strptime(iris_time, "IRIS,%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            tbias = float(match.group(2))
            above = [float(match.group(3)), int(match.group(4)), int(match.group(5))]
            below = [float(match.group(6)), int(match.group(7)), int(match.group(8))]
            adc_delay = int(match.group(9))
            pca_model = match.group(10)
            firmware_version = match.group(11)
            xchan_gain = float(match.group(12))
            ychan_gain = float(match.group(13))
            temp_gain = float(match.group(14))
            output_mode = match.group(15)
            cal_mode = match.group(16)
            control = match.group(17)
            using = match.group(18)
            rtc_installed = match.group(19)
            rtc_timing = match.group(20)
            ext_flash_capacity = match.group(21)
            xpos_thresh = float(match.group(22))
            xneg_thresh = float(match.group(23))
            ypos_thresh = float(match.group(24))
            yneg_thresh = float(match.group(25))
            hysteresis = float(match.group(26))
            cal_method = match.group(27)
            pos_limit = float(match.group(28))
            neg_limit = float(match.group(29))
            cal_points = int(match.group(30))
            cal_x = match.group(31)
            cal_y = match.group(32)
            biaxial_type = int(match.group(33))
            adc_type = match.group(34)
            dac_scale = float(match.group(35))
            dac_units = match.group(36)
            storage_cap = int(match.group(37))
            bae_scale = float(match.group(38))

        except ValueError:
            raise SampleException('Exception parsing status data: [%s]' % self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.TBIAS,
             DataParticleKey.VALUE: tbias},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.ABOVE,
             DataParticleKey.VALUE: above},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.BELOW,
             DataParticleKey.VALUE: below},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.ADC_DELAY,
             DataParticleKey.VALUE: adc_delay},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.PCA_MODEL,
             DataParticleKey.VALUE: pca_model},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.FIRMWARE_REV,
             DataParticleKey.VALUE: firmware_version},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.XCHAN_GAIN,
             DataParticleKey.VALUE: xchan_gain},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.YCHAN_GAIN,
             DataParticleKey.VALUE: ychan_gain},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.TEMP_GAIN,
             DataParticleKey.VALUE: temp_gain},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.OUTPUT_MODE,
             DataParticleKey.VALUE: output_mode},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.CAL_MODE,
             DataParticleKey.VALUE: cal_mode},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.CONTROL,
             DataParticleKey.VALUE: control},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.RS232,
             DataParticleKey.VALUE: using},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.RTC_INSTALLED,
             DataParticleKey.VALUE: rtc_installed},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.RTC_TIMING,
             DataParticleKey.VALUE: rtc_timing},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.EXT_FLASH,
             DataParticleKey.VALUE: ext_flash_capacity},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.XPOS_RELAY_THRESHOLD,
             DataParticleKey.VALUE: xpos_thresh},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.XNEG_RELAY_THRESHOLD,
             DataParticleKey.VALUE: xneg_thresh},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.YPOS_RELAY_THRESHOLD,
             DataParticleKey.VALUE: ypos_thresh},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.YNEG_RELAY_THRESHOLD,
             DataParticleKey.VALUE: yneg_thresh},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.RELAY_HYSTERESIS,
             DataParticleKey.VALUE: hysteresis},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.CAL_METHOD,
             DataParticleKey.VALUE: cal_method},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.POS_LIMIT,
             DataParticleKey.VALUE: pos_limit},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.NEG_LIMIT,
             DataParticleKey.VALUE: neg_limit},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.NUM_CAL_POINTS,
             DataParticleKey.VALUE: cal_points},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.CAL_POINTS_X,
             DataParticleKey.VALUE: cal_x},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.CAL_POINTS_Y,
             DataParticleKey.VALUE: cal_y},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.BIAXIAL_SENSOR_TYPE,
             DataParticleKey.VALUE: biaxial_type},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.ADC_TYPE,
             DataParticleKey.VALUE: adc_type},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.DAC_SCALE_FACTOR,
             DataParticleKey.VALUE: dac_scale},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.DAC_SCALE_UNITS,
             DataParticleKey.VALUE: dac_units},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.SAMPLE_STORAGE_CAPACITY,
             DataParticleKey.VALUE: storage_cap},
            {DataParticleKey.VALUE_ID: IRISStatus02ParticleKey.BAE_SCALE_FACTOR,
             DataParticleKey.VALUE: bae_scale},
        ]
        return result

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the iris_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The iris_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.iris_status_response = NEWLINE.join([line for line in self.raw_data.split(NEWLINE)
                                                  if line.startswith(IRIS_STRING)])


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
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
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyMethodMayBeStatic, PyUnusedLocal
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
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
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01),
                (ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01),
                (ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Add event handlers for protocol state machine.

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_build_handler(command, self._build_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_01, self._parse_status_01_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_02, self._parse_status_02_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = IRISDataParticle.regex_compiled()
        self.cmd_rsp_regex = IRISCommandResponse.regex_compiled()
        self.status_01_regex = IRISStatus01Particle.basic_regex_compiled()
        self.status_02_regex = IRISStatus02Particle.basic_regex_compiled()
        self._last_data_timestamp = 0

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []
        matchers.append(IRISDataParticle.regex_compiled())
        matchers.append(IRISStatus01Particle.basic_regex_compiled())
        matchers.append(IRISStatus02Particle.basic_regex_compiled())
        matchers.append(IRISCommandResponse.regex_compiled())
        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_cmd_dict(self):
        """
        Populate the command dictionary with NOAA IRIS Driver metadata information. 
        Currently IRIS only supports DATA_ON and DATA_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        pass

    def add_to_buffer(self, data):
        """
        Overridden because most of the data coming to this driver
        isn't meant for it.  I'm only adding to the buffer when
        a chunk arrives (see my_add_to_buffer, below), so this
        method does nothing.

        @param data: bytes to add to the buffer
        """
        pass

    def _my_add_to_buffer(self, data):
        """
        Replaces add_to_buffer. Most data coming to this driver isn't meant
        for it.  I'm only adding to the buffer when data meant for this 
        driver arrives.  That is accomplished using the chunker mechanism. This
        method would normally collect any data fragments that are then search by
        the get_response method in the context of a synchronous command sent
        from the observatory.  However, because so much data arrives here that
        is not applicable, the add_to_buffer method has been overridden to do
        nothing.
        
        @param data: bytes to add to the buffer
        """

        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._last_data_timestamp = time.time()

    def _got_chunk(self, chunk, timestamp):
        """
        The base class has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, or pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """

        log.debug("_got_chunk_: %r", chunk)

        if self.data_regex.match(chunk):
            self._extract_sample(IRISDataParticle, self.data_regex, chunk, timestamp)
        elif self.status_01_regex.match(chunk):
            self._my_add_to_buffer(chunk)
            self._extract_sample(IRISStatus01Particle, self.status_01_regex, chunk, timestamp)
        elif self.status_02_regex.match(chunk):
            self._my_add_to_buffer(chunk)
            self._extract_sample(IRISStatus02Particle, self.status_02_regex, chunk, timestamp)
        elif self.cmd_rsp_regex.match(chunk):
            self._my_add_to_buffer(chunk)
        else:
            raise InstrumentProtocolException("Unhandled chunk")

    def _build_command(self, cmd, *args, **kwargs):
        command = cmd + NEWLINE
        log.debug("_build_command: command is: %r", command)
        return command

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %r", response, prompt)
        return response.iris_command_response

    def _parse_status_01_resp(self, response, prompt):
        log.debug("_parse_status_01_resp: response: %r; prompt: %r", response, prompt)
        return response.iris_status_response

    def _parse_status_02_resp(self, response, prompt):
        log.debug("_parse_status_02_resp: response: %r; prompt: %r", response, prompt)
        return response.iris_status_response

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    def _get_response(self, timeout=10, expected_prompt=None, expected_regex=None):
        """
        Overriding _get_response: this one uses regex on chunks
        that have already been filtered by the chunker.  An improvement
        to the chunker could be metadata labeling the chunk so that we
        don't have to do another match, although I don't think it is that
        expensive once the chunk has been pulled out to match again
        
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolException on timeout
        """
        # Grab time for timeout and wait for response

        starttime = time.time()

        # Spin around for <timeout> looking for the response to arrive
        continuing = True
        response = "no response"
        while continuing:
            if self.cmd_rsp_regex.match(self._promptbuf):
                response = IRISCommandResponse(self._promptbuf)
                log.debug("_get_response() matched CommandResponse")
                response.check_command_response(expected_prompt)
                continuing = False
            elif self.status_01_regex.match(self._promptbuf):
                response = IRISStatus01Particle(self._promptbuf)
                log.debug("_get_response() matched Status_01_Response")
                response.build_response()
                continuing = False
            elif self.status_02_regex.search(self._promptbuf):
                response = IRISStatus02Particle(self._promptbuf)
                log.debug("_get_response() matched Status_02_Response")
                response.build_response()
                continuing = False
            else:
                self._promptbuf = ''
                time.sleep(.1)

            if timeout and time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in BOTPT IRIS driver._get_response()")

        return 'IRIS_RESPONSE', response

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

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        result = self._do_cmd_resp(InstrumentCommand.DATA_OFF, expected_prompt=IRIS_DATA_OFF)

        return ProtocolState.COMMAND, ResourceAgentState.IDLE

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
        Exit command state.
        """
        pass

    def _handler_autosample_stop_autosample(self):
        """
        Turn the iris data off
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        result = self._do_cmd_resp(InstrumentCommand.DATA_OFF, expected_prompt=IRIS_DATA_OFF)

        return next_state, (next_agent_state, result)

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
        next_agent_state = None

        # Only allow direct access to IRIS
        commands = data.split(NEWLINE)
        commands = [x for x in commands if x.startswith(IRIS_STRING)]
        for command in commands:
            self._do_cmd_direct(command)

            # add sent command to list for 'echo' filtering in callback
            self._sent_cmds.append(command)

        return next_state, (next_agent_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)

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
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """

        next_state = None
        result = {}

        return next_state, result

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        params = args[0]

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the iris data on
        """
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        # call _do_cmd_resp, passing our IRIS_DATA_ON as the expected_prompt
        result = self._do_cmd_resp(InstrumentCommand.DATA_ON, expected_prompt=IRIS_DATA_ON)

        return next_state, (next_agent_state, result)

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        Turn the iris data on
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None

        return next_state, (next_agent_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_acquire_status")
        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01)
        log.debug("DUMP_SETTINGS_01 response: %r", result)
        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_02)
        log.debug("DUMP_SETTINGS_02 response: %r", result)

        return next_state, (next_agent_state, result)

    def _handler_command_autosample_dump01(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_dump01")

        timeout = kwargs.get('timeout')

        if timeout is not None:
            result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01, timeout=timeout)
        else:
            result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_01)

        log.debug("DUMP_SETTINGS_01 response: %r", result)

        return next_state, (next_agent_state, result)

    def _handler_command_autosample_dump02(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_autosample_dump02")

        result = self._do_cmd_resp(InstrumentCommand.DUMP_SETTINGS_02)

        log.debug("DUMP_SETTINGS_02 response: %r", result)

        return next_state, (next_agent_state, result)