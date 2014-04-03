"""
@package mi.instrument.noaa.driver
@file marine-integrations/mi/instrument/noaa/driver.py
@author David Everett, Pete Cable
@brief Common items for BOTPT
Release notes:
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
from mi.core.instrument.instrument_driver import DriverEvent, DriverAsyncEvent, ResourceAgentState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import SampleException, NotImplementedException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0a'

# default timeout.
TIMEOUT = 10

# default max promptbuf/linebuf length
MAX_BUFFER_LENGTH = 10


class BotptProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class BotptExportedInstrumentCommand(BaseEnum):
    DUMP_01 = "EXPORTED_INSTRUMENT_DUMP_SETTINGS"
    DUMP_02 = "EXPORTED_INSTRUMENT_DUMP_EXTENDED_SETTINGS"


class BotptProtocolEvent(BaseEnum):
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
    DUMP_01 = BotptExportedInstrumentCommand.DUMP_01
    DUMP_02 = BotptExportedInstrumentCommand.DUMP_02
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class BotptCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = BotptProtocolEvent.GET
    SET = BotptProtocolEvent.SET
    START_AUTOSAMPLE = BotptProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = BotptProtocolEvent.STOP_AUTOSAMPLE
    DUMP_01 = BotptProtocolEvent.DUMP_01
    DUMP_02 = BotptProtocolEvent.DUMP_02
    ACQUIRE_STATUS = BotptProtocolEvent.ACQUIRE_STATUS


class BotptStatusParticleKey(BaseEnum):
    TIME = "botpt_time"


class BotptStatus01ParticleKey(BotptStatusParticleKey):
    MODEL = "botpt_model"
    FIRMWARE_VERSION = "botpt_firmware_version"
    SERIAL_NUMBER = "botpt_serial_number"
    ID_NUMBER = "botpt_id_number"
    VBIAS = "botpt_vbias"
    VGAIN = "botpt_vgain"
    VMIN = "botpt_vmin"
    VMAX = "botpt_vmax"
    AVALS_0 = "botpt_avals_0"
    AVALS_1 = "botpt_avals_1"
    AVALS_2 = "botpt_avals_2"
    AVALS_3 = "botpt_avals_3"
    TCOEF0_KS = "botpt_tcoef0_ks"
    TCOEF0_KZ = 'botpt_tcoef0_kz'
    TCOEF0_TCAL = 'botpt_tcoef0_tcal'
    TCOEF1_KS = "botpt_tcoef1_ks"
    TCOEF1_KZ = 'botpt_tcoef1_kz'
    TCOEF1_TCAL = 'botpt_tcoef1_tcal'
    N_SAMP = "botpt_n_samp"
    XZERO = "botpt_xzero"
    YZERO = "botpt_yzero"
    BAUD = "botpt_baud"


class BotptDataParticleType(BaseEnum):
    BOTPT_STATUS_01 = 'botpt_status_01'
    BOTPT_STATUS_02 = 'botpt_status_02'


###############################################################################
# Status Particles
###############################################################################

class BotptStatusParticle(DataParticle):
    _DEFAULT_ENCODER_KEY = float
    botpt_date_time = r',(\d+/\d+/\d+ \d+:\d+:\d+),'
    floating_point_num = r'(-?\d+\.\d+)'
    four_floats = r'\s+?'.join([floating_point_num] * 4)
    six_floats = r'\s+?'.join([floating_point_num] * 6)
    integer = r'(-?\d+)'
    word = r'(\S+)'

    def _regex_multiline_compiled(self):
        """
        return a dictionary containing compiled regex used to match patterns
        in SBE multiline results.
        @return: dictionary of compiled regexes
        """
        result = {}
        for key, regex in self._regex_multiline().iteritems():
            if key not in result:
                result[key] = re.compile(regex)
        return result

    def _build_parsed_values(self):
        """
        Run the status output through our regex dictionary, returning a data particle.
        """
        log.debug('BOTPT Status Particle _build_parsed_values')
        try:
            results = self._get_multiline_values()
        except ValueError as e:
            raise SampleException("ValueError while decoding status: [%s]" % e)

        self.set_internal_timestamp(unix_time=0)
        for r in results:
            if BotptStatusParticleKey.TIME in r:
                self.set_internal_timestamp(r[BotptStatusParticleKey.TIME])

        return results

    def _get_encoder(self, key):
        return self._encoders.get(key, self._DEFAULT_ENCODER_KEY)

    def _get_multiline_values(self):
        """
        return a dictionary containing keys and found values from a
        multiline sample using the multiline regex
        @param: split_fun - function to which splits sample into lines
        @return: dictionary of compiled regexes
        """
        result = []

        for key, matcher in self._regex_multiline_compiled().items():
            match = matcher.search(self.raw_data)
            if match:
                groups = match.groups()
                encoder = self._get_encoder(key)
                value = [encoder(v) for v in groups]
                if len(value) == 1:
                    value = value[0]
                log.trace('multiline match %s = [%r]', key, value)
                result.append({
                    DataParticleKey.VALUE_ID: key,
                    DataParticleKey.VALUE: value
                })
            else:
                log.debug('multiline match -- no match found for matcher: %s %r', key, matcher.pattern)
        log.trace('BOTPT Status particle: [%r]', result)
        return result

    @staticmethod
    def timestamp_to_ntp(tstamp):
        timestamp = time.strptime(tstamp, "%Y/%m/%d %H:%M:%S")
        return ntplib.system_to_ntp_time(time.mktime(timestamp))


class BotptStatus01Particle(BotptStatusParticle):
    # Example of output from DUMP-SETTINGS command:

    # IRIS:

    # IRIS,2013/06/19 21:26:20,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01
    # IRIS,2013/06/19 21:26:20,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
    # IRIS,2013/06/19 21:26:20,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
    # IRIS,2013/06/19 21:26:21,*01: Vmin:  -2.50  -2.50   2.50   2.50
    # IRIS,2013/06/19 21:26:21,*01: Vmax:   2.50   2.50   2.50   2.50
    # IRIS,2013/06/19 21:26:21,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # IRIS,2013/06/19 21:26:21,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # IRIS,2013/06/19 21:26:21,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # IRIS,2013/06/19 21:26:21,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # IRIS,2013/06/19 21:26:21,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
    # IRIS,2013/06/19 21:26:21,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
    # IRIS,2013/06/19 21:26:21,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00
    # IRIS,2013/06/19 21:26:21,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-

    # LILY:

    # LILY,2013/06/24 23:35:41,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9655 ID01
    # LILY,2013/06/24 23:35:41,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
    # LILY,2013/06/24 23:35:41,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
    # LILY,2013/06/24 23:35:41,*01: Vmin:  -2.50  -2.50   2.50   2.50
    # LILY,2013/06/24 23:35:41,*01: Vmax:   2.50   2.50   2.50   2.50
    # LILY,2013/06/24 23:35:41,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # LILY,2013/06/24 23:35:41,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # LILY,2013/06/24 23:35:41,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # LILY,2013/06/24 23:35:41,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
    # LILY,2013/06/24 23:35:41,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
    # LILY,2013/06/24 23:35:41,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
    # LILY,2013/06/24 23:35:41,*01: N_SAMP= 360 Xzero=  0.00 Yzero=  0.00
    # LILY,2013/06/24 23:35:41,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-

    _data_particle_type = BotptDataParticleType.BOTPT_STATUS_01
    _encoders = {
        BotptStatus01ParticleKey.MODEL: str,
        BotptStatus01ParticleKey.FIRMWARE_VERSION: str,
        BotptStatus01ParticleKey.SERIAL_NUMBER: str,
        BotptStatus01ParticleKey.TIME: BotptStatusParticle.timestamp_to_ntp,
        BotptStatus01ParticleKey.ID_NUMBER: str,
        BotptStatus01ParticleKey.TCOEF0_KS: int,
        BotptStatus01ParticleKey.TCOEF0_KZ: int,
        BotptStatus01ParticleKey.TCOEF0_TCAL: int,
        BotptStatus01ParticleKey.TCOEF1_KS: int,
        BotptStatus01ParticleKey.TCOEF1_KZ: int,
        BotptStatus01ParticleKey.TCOEF1_TCAL: int,
        BotptStatus01ParticleKey.N_SAMP: int,
        BotptStatus01ParticleKey.BAUD: int,
    }

    @staticmethod
    def regex():
        pattern = '(?:IRIS|LILY),.*\*APPLIED GEOMECHANICS.*baud FV-'
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(BotptStatus01Particle.regex(), re.DOTALL)

    @classmethod
    def _regex_multiline(cls):
        sub_dict = {
            'float': cls.floating_point_num,
            'four_floats': cls.four_floats,
            'six_floats': cls.six_floats,
            'int': cls.integer,
        }

        return {
            BotptStatus01ParticleKey.TIME: cls.botpt_date_time,
            BotptStatus01ParticleKey.MODEL: r'APPLIED GEOMECHANICS (.*?) Firmware',
            BotptStatus01ParticleKey.FIRMWARE_VERSION: r'Firmware (\S+)',
            BotptStatus01ParticleKey.SERIAL_NUMBER: r'Firmware \S+ (\S+)',
            BotptStatus01ParticleKey.ID_NUMBER: r'Firmware \S+ \S+ (\S+)',
            BotptStatus01ParticleKey.VBIAS: r'Vbias=\s+%(four_floats)s' % sub_dict,
            BotptStatus01ParticleKey.VGAIN: r'Vgain=\s+%(four_floats)s' % sub_dict,
            BotptStatus01ParticleKey.VMIN: r'Vmin:\s+%(four_floats)s' % sub_dict,
            BotptStatus01ParticleKey.VMAX: r'Vmax:\s+%(four_floats)s' % sub_dict,
            BotptStatus01ParticleKey.AVALS_0: r'a0=\s+%(six_floats)s' % sub_dict,
            BotptStatus01ParticleKey.AVALS_1: r'a1=\s+%(six_floats)s' % sub_dict,
            BotptStatus01ParticleKey.AVALS_2: r'a2=\s+%(six_floats)s' % sub_dict,
            BotptStatus01ParticleKey.AVALS_3: r'a3=\s+%(six_floats)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF0_KS: r'Tcoef 0:.*Ks=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF0_KZ: r'Tcoef 0:.*Kz=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF0_TCAL: r'Tcoef 0:.*Tcal=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF1_KS: r'Tcoef 1:.*Ks=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF1_KZ: r'Tcoef 1:.*Kz=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.TCOEF1_TCAL: r'Tcoef 1:.*Tcal=\s+%(int)s' % sub_dict,
            BotptStatus01ParticleKey.N_SAMP: r'N_SAMP=\s*%(int)s' % sub_dict,
            BotptStatus01ParticleKey.XZERO: r'Xzero=\s*%(float)s' % sub_dict,
            BotptStatus01ParticleKey.YZERO: r'Yzero=\s*%(float)s' % sub_dict,
            BotptStatus01ParticleKey.BAUD: r'%(int)s baud' % sub_dict,
        }


class BotptStatus02ParticleKey(BotptStatusParticleKey):
    TBIAS = 'botpt_tbias'
    ABOVE = 'botpt_kzmintemp_above'
    BELOW = 'botpt_kzmintemp_below'
    KZVALS = 'botpt_kzvals'
    ADC_DELAY = 'botpt_adc_delay'
    PCA_MODEL = 'botpt_pca_model'
    FIRMWARE_REV = 'botpt_firmware_rev'
    XCHAN_GAIN = 'botpt_xchan_gain'
    YCHAN_GAIN = 'botpt_ychan_gain'
    TEMP_GAIN = 'botpt_temp_gain'
    RS232 = 'botpt_rs232'
    RTC_INSTALLED = 'botpt_rtc_installed'
    RTC_TIMING = 'botpt_rtc_timing'
    CAL_METHOD = 'botpt_calibration_method'
    POS_LIMIT = 'botpt_positive_limit'
    NEG_LIMIT = 'botpt_negative_limit'
    NUM_CAL_POINTS = 'botpt_calibration_points'
    CAL_POINTS_X = 'botpt_cal_points_x'
    CAL_POINTS_Y = 'botpt_cal_points_y'
    ADC_TYPE = 'botpt_adc_type'
    OUTPUT_MODE = 'botpt_output_mode'
    CAL_MODE = 'botpt_cal_mode'
    EXT_FLASH_CAPACITY = 'botpt_external_flash_capacity_bytes'
    SENSOR_TYPE = 'botpt_sensor_type'

    # CONTROL = 'iris_control'
    # XPOS_RELAY_THRESHOLD = 'iris_xpos_relay_threshold'
    # XNEG_RELAY_THRESHOLD = 'iris_xneg_relay_threshold'
    # YPOS_RELAY_THRESHOLD = 'iris_ypos_relay_threshold'
    # YNEG_RELAY_THRESHOLD = 'iris_yneg_relay_threshold'
    # RELAY_HYSTERESIS = 'iris_relay_hysteresis'
    #
    # DAC_SCALE_FACTOR = 'iris_dac_output_scale_factor'
    # DAC_SCALE_UNITS = 'iris_dac_output_scale_units'
    # SAMPLE_STORAGE_CAPACITY = 'iris_sample_storage_capacity'
    # BAE_SCALE_FACTOR = 'iris_bae_scale_factor'


# noinspection PyMethodMayBeStatic
class BotptStatus02Particle(BotptStatusParticle):
    _data_particle_type = BotptDataParticleType.BOTPT_STATUS_02
    _encoders = {
        BotptStatus02ParticleKey.TIME: BotptStatusParticle.timestamp_to_ntp,
        BotptStatus02ParticleKey.KZVALS: int,
        BotptStatus02ParticleKey.ADC_DELAY: int,
        BotptStatus02ParticleKey.PCA_MODEL: str,
        BotptStatus02ParticleKey.FIRMWARE_REV: str,
        BotptStatus02ParticleKey.RS232: str,
        BotptStatus02ParticleKey.RTC_INSTALLED: str,
        BotptStatus02ParticleKey.RTC_TIMING: str,
        BotptStatus02ParticleKey.CAL_METHOD: str,
        BotptStatus02ParticleKey.CAL_POINTS_X: str,
        BotptStatus02ParticleKey.CAL_POINTS_Y: str,
        BotptStatus02ParticleKey.ADC_TYPE: str,
        BotptStatus02ParticleKey.OUTPUT_MODE: str,
        BotptStatus02ParticleKey.CAL_MODE: str,
        BotptStatus02ParticleKey.EXT_FLASH_CAPACITY: int,
        BotptStatus02ParticleKey.SENSOR_TYPE: str,
        BotptStatus02ParticleKey.NUM_CAL_POINTS: int,
    }

    @staticmethod
    def regex():
        # IRIS and LILY Common items:

        # IRIS,2013/06/12 23:55:09,*01: TBias: 8.85
        # IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        # IRIS,2013/06/12 18:04:01,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
        # IRIS,2013/06/12 18:04:01,*01: ADCDelay:  310
        # IRIS,2013/06/12 18:04:01,*01: PCA Model: 90009-01
        # IRIS,2013/06/12 18:04:01,*01: Firmware Version: 5.2 Rev N
        # IRIS,2013/06/12 18:04:01,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
        # IRIS,2013/06/12 18:04:01,*01: Using RS232
        # IRIS,2013/06/12 18:04:01,*01: Real Time Clock: Not Installed
        # IRIS,2013/06/12 18:04:01,*01: Use RTC for Timing: No
        # IRIS,2013/06/12 18:04:01,*01: Calibration method: Dynamic
        # IRIS,2013/06/12 18:04:01,*01: Positive Limit=26.25   Negative Limit=-26.25
        # IRIS,2013/06/12 18:04:02,*01: Calibration Points:025  X: Disabled  Y: Disabled
        # IRIS,2013/06/12 18:04:02,*01: ADC: 12-bit (internal)

        # IRIS and LILY Similar items:

        # IRIS,2013/06/12 18:04:01,*01: Output Mode: Degrees
        # IRIS,2013/06/12 18:04:01,*01: Calibration performed in Degrees
        # IRIS,2013/06/12 18:04:01,*01: External Flash Capacity: 0 Bytes(Not Installed)
        # LILY,2014/03/31 23:18:49,*01: Calibrated in uRadian, Current Output Mode: uRadian
        # LILY,2014/03/31 23:18:49,*01: External Flash: 2162688 Bytes Installed

        # IRIS and LILY Unique items (not handled here):

        # IRIS,2013/06/12 18:04:01,*01: Control: Off
        # IRIS,2013/06/12 18:04:01,*01: Relay Thresholds:
        # IRIS,2013/06/12 18:04:01,*01:   Xpositive= 1.0000   Xnegative=-1.0000
        # IRIS,2013/06/12 18:04:01,*01:   Ypositive= 1.0000   Ynegative=-1.0000
        # IRIS,2013/06/12 18:04:01,*01: Relay Hysteresis:
        # IRIS,2013/06/12 18:04:01,*01:   Hysteresis= 0.0000
        # IRIS,2013/06/12 18:04:02,*01: Biaxial Sensor Type (0)
        # IRIS,2013/06/12 18:04:02,*01: DAC Output Scale Factor: 0.10 Volts/Degree
        # IRIS,2013/06/12 18:04:02,*01: Total Sample Storage Capacity: 372
        # IRIS,2013/06/12 18:04:02,*01: BAE Scale Factor:  2.88388 (arcseconds/bit)

        # LILY,2014/03/31 23:18:49,*01: Flash Status (in Samples) (Used/Total): (107/55424)
        # LILY,2014/03/31 23:18:49,*01: Low Power Logger Data Rate: -1 Seconds per Sample
        # LILY,2014/03/31 23:18:49,*01: Uniaxial (x2) Sensor Type (1)
        # LILY,2014/03/31 23:18:49,*01: Compass: Installed   Magnetic Declination: 0.000000
        # LILY,2014/03/31 23:18:49,*01: Compass: Xoffset:  124, Yoffset:  196, Xrange: 1349, Yrange: 1364
        # LILY,2014/03/31 23:18:49,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
        # LILY,2014/03/31 23:18:49,*01: Motor I_limit: 90.0mA
        # LILY,2014/03/31 23:18:49,*01: Current Time: 10/03/00 05:48:02
        # LILY,2014/03/31 23:18:49,*01: Supply Voltage: 11.87 Volts
        # LILY,2014/03/31 23:18:49,*01: Memory Save Mode: Off
        # LILY,2014/03/31 23:18:49,*01: Outputting Data: No
        # LILY,2014/03/31 23:18:49,*01: Auto Power-Off Recovery Mode: On
        # LILY,2014/03/31 23:18:49,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No
        return r'(?:IRIS|LILY),.*\*01: TBias.*(?:\(arcseconds/bit\)|XY-MEMD: \S+)'

    @staticmethod
    def regex_compiled():
        return re.compile(BotptStatus02Particle.regex(), re.DOTALL)

    @classmethod
    def _regex_multiline(cls):
        sub_dict = {
            'float': cls.floating_point_num,
            'four_floats': cls.four_floats,
            'six_floats': cls.six_floats,
            'int': cls.integer,
            'word': cls.word,
            'newline': NEWLINE,
        }
        return {
            BotptStatus02ParticleKey.TIME: cls.botpt_date_time,
            BotptStatus02ParticleKey.TBIAS: r'TBias:\s*%(float)s' % sub_dict,
            BotptStatus02ParticleKey.ABOVE: r'Above %(float)s' % sub_dict,
            BotptStatus02ParticleKey.BELOW: r'Below %(float)s' % sub_dict,
            BotptStatus02ParticleKey.KZVALS: (r'kz\[0\]=.*?%(int)s' +
                                              r'.*kz\[1\]=.*?%(int)s.*%(newline)s' +
                                              r'.*kz\[2\]=.*?%(int)s' +
                                              r'.*kz\[3\]=\s+%(int)s') % sub_dict,
            BotptStatus02ParticleKey.ADC_DELAY: r'ADCDelay:\s*%(int)s' % sub_dict,
            BotptStatus02ParticleKey.PCA_MODEL: r'PCA Model: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.FIRMWARE_REV: r'Firmware Version: (.*)' % sub_dict,
            BotptStatus02ParticleKey.XCHAN_GAIN: r'X Ch Gain=\s*%(float)s' % sub_dict,
            BotptStatus02ParticleKey.YCHAN_GAIN: r'Y Ch Gain=\s*%(float)s' % sub_dict,
            BotptStatus02ParticleKey.TEMP_GAIN: r'Temperature Gain=\s*%(float)s' % sub_dict,
            BotptStatus02ParticleKey.RS232: r': Using %(word)s' % sub_dict,
            BotptStatus02ParticleKey.RTC_INSTALLED: r'Real Time Clock: (.*)',
            BotptStatus02ParticleKey.RTC_TIMING: r'Use RTC for Timing: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.CAL_METHOD: r'Calibration method: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.POS_LIMIT: r'Positive Limit=%(float)s' % sub_dict,
            BotptStatus02ParticleKey.NEG_LIMIT: r'Negative Limit=%(float)s' % sub_dict,
            BotptStatus02ParticleKey.NUM_CAL_POINTS: r'Calibration Points:%(int)s' % sub_dict,
            BotptStatus02ParticleKey.CAL_POINTS_X: r'Calibration Points.*X: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.CAL_POINTS_Y: r'Calibration Points.*Y: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.ADC_TYPE: r'ADC: (.*)',
            BotptStatus02ParticleKey.OUTPUT_MODE: r'Output Mode: %(word)s' % sub_dict,
            BotptStatus02ParticleKey.CAL_MODE: r'Calibrat.*in ([a-zA-Z]+)' % sub_dict,
            BotptStatus02ParticleKey.EXT_FLASH_CAPACITY: r'External Flash.*?%(int)s\s*Bytes' % sub_dict,
            BotptStatus02ParticleKey.SENSOR_TYPE: r'(\S+axial.*?Sensor Type.*)',
        }


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal,PyMethodMayBeStatic
class BotptProtocol(CommandResponseInstrumentProtocol):
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
        self._filter_string = None
        self._chunker = None
        self._last_data_timestamp = 0
        self._sent_cmds = []

    def _got_chunk(self, chunk, timestamp):
        raise NotImplementedException('_got_chunk not implemented')

    def _handler_command_generic(self, command, next_state, next_agent_state, timeout, expected_prompt=None):
        """
        Generic method to command the instrument
        """
        log.debug('_handler_command: %s %s %s %s', command, next_state, next_agent_state, timeout)

        if timeout is None:
            result = self._do_cmd_resp(command, expected_prompt=expected_prompt)
        else:
            result = self._do_cmd_resp(command, expected_prompt=expected_prompt, timeout=timeout)

        log.debug('%s response: %s', command, result)
        return next_state, (next_agent_state, result)

    def got_raw(self, port_agent_packet):
        """
        Overridden, BOTPT drivers shall not generate raw particles, unless further overridden
        """
        pass

    def _filter_raw(self, data):
        """
        BOTPT puts out lots of data not destined for LILY.  Filter it out.
        """
        if self._filter_string is None:
            return data
        my_filter = lambda s: (s.startswith(self._filter_string) or len(s) == 0)
        lines = data.split(NEWLINE)
        lines = filter(my_filter, lines)
        return NEWLINE.join(lines)

    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """
        data_length = port_agent_packet.get_data_length()
        data = self._filter_raw(port_agent_packet.get_data())
        timestamp = port_agent_packet.get_timestamp()

        log.debug("Got Data: %s" % data)
        log.debug("Add Port Agent Timestamp: %s" % timestamp)

        if data_length > 0:
            if self.get_current_state() == DriverProtocolState.DIRECT_ACCESS:
                self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)

            self.add_to_buffer(data)

            self._chunker.add_chunk(data, timestamp)
            timestamp, chunk = self._chunker.get_next_data()
            while chunk:
                self._got_chunk(chunk, timestamp)
                timestamp, chunk = self._chunker.get_next_data()

    def _clean_buffer(self, my_buffer):
        return NEWLINE.join(my_buffer.split(NEWLINE)[-MAX_BUFFER_LENGTH:])

    def add_to_buffer(self, data):
        """
        Add a chunk of data to the internal data buffers, filtering out data not for this sensor.
        Limit buffer length to MAX_BUFFER_LENGTH lines
        @param data: bytes to add to the buffer
        """
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._linebuf = self._clean_buffer(self._linebuf)
        self._promptbuf = self._clean_buffer(self._promptbuf)
        self._last_data_timestamp = time.time()

        log.debug("LINE BUF: %s", self._linebuf)
        log.debug("PROMPT BUF: %s", self._promptbuf)

    def _build_command(self, cmd, *args, **kwargs):
        command = cmd + NEWLINE
        log.debug("_build_command: command is: %s", command)
        return command

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        log.debug("_handler_unknown_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        log.debug("_handler_unknown_exit")

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        log.debug("_handler_autosample_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        log.debug("_handler_autosample_exit")

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        log.debug("_handler_command_enter")

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

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        log.debug("_handler_command_exit")

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = DriverProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
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

        # Filter commands if _filter_string is specified
        if self._filter_string is None:
            commands = [data]
        else:
            commands = data.split(NEWLINE)
            commands = [x for x in commands if x.startswith(self._filter_string)]

        for command in commands:
            self._do_cmd_direct(command)

            # add sent command to list for 'echo' filtering in callback
            self._sent_cmds.append(command)

        return next_state, (next_agent_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        result = None

        next_state = DriverProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)