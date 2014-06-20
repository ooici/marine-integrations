"""
@package mi.instrument.noaa.driver
@file marine-integrations/mi/instrument/noaa/particles.py
@author Pete Cable
@brief Particles for BOTPT
Release notes:
"""

import re
import time

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, CommonDataParticleType
from mi.core.exceptions import SampleException
from mi.core.log import get_logging_metaclass


__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

METALOGGER = get_logging_metaclass('trace')

NEWLINE = '\n'
IRIS = 'IRIS'
LILY = 'LILY'
HEAT = 'HEAT'
NANO = 'NANO'
SYST = 'SYST'

common_regex_items = {
    'float': r'\s*-?\d*\.\d*\s*',
    'int': r'\s*-?\d+\s*',
    'date_time': r'\s*\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}\.?\d*\s*',
    'word': r'\s*\S+\s*',
    'newline': NEWLINE
}


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    LILY_SAMPLE = 'botpt_lily_sample'
    LILY_LEVELING = 'botpt_lily_leveling'
    IRIS_SAMPLE = 'botpt_iris_sample'
    NANO_SAMPLE = 'botpt_nano_sample'
    HEAT_SAMPLE = 'botpt_heat_sample'
    BOTPT_STATUS = 'botpt_status'


class IrisSampleParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "iris_x_tilt"
    Y_TILT = "iris_y_tilt"
    TEMP = "iris_temp"
    SN = "serial_number"


class HeatSampleParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "heat_x_tilt"
    Y_TILT = "heat_y_tilt"
    TEMP = "heat_temp"


class LilySampleParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    OUT_OF_RANGE = 'lily_out_of_range'


class LilyLevelingParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    STATUS = "lily_leveling_status"


class NanoSampleParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    PPS_SYNC = "time_sync_flag"
    PRESSURE = "bottom_pressure"
    TEMP = "press_trans_temp"


class BotptStatusParticleKey(BaseEnum):
    IRIS1 = 'botpt_iris_status_01'
    IRIS2 = 'botpt_iris_status_02'
    LILY1 = 'botpt_lily_status_01'
    LILY2 = 'botpt_lily_status_02'
    NANO = 'botpt_nano_status'
    SYST = 'botpt_syst_status'


class BotptDataParticle(DataParticle):
    _compiled_regex = None
    _compile_flags = None
    __metaclass__ = METALOGGER

    def __init__(self, *args, **kwargs):
        """
        Initialize the BotptDataParticle base class.
        perform the regex match, raise exception if no match found
        @throws SampleException
        """
        super(BotptDataParticle, self).__init__(*args, **kwargs)
        self.match = self.regex_compiled().match(self.raw_data)
        if not self.match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

    @staticmethod
    def regex():
        raise NotImplemented()

    @classmethod
    def regex_compiled(cls):
        """
        Compile the regex, caching the result for future calls
        @return: compiled regex
        """
        if cls._compiled_regex is None:
            if cls._compile_flags is None:
                cls._compiled_regex = re.compile(cls.regex())
            else:
                cls._compiled_regex = re.compile(cls.regex(), cls._compile_flags)
        return cls._compiled_regex

    def set_botpt_timestamp(self):
        """
        Set the internal timestamp based on the embedded timestamp in the sample
        """
        ts = self.match.group('date_time')
        if '.' in ts:
            ts, right = ts.split('.', 1)
            fraction = float('.' + right)
        else:
            fraction = 0
        timestamp = time.strptime(ts, "%Y/%m/%d %H:%M:%S")
        self.set_internal_timestamp(unix_time=time.mktime(timestamp) + fraction)

    def _encode_all(self):
        """
        Default implementation, return empty list
        @return: list of encoded values
        """
        return []

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        try:
            self.set_botpt_timestamp()
            result = self._encode_all()
        except Exception as e:
            raise SampleException("Exception [%s] while converting data: [%s]" % (e, self.raw_data))
        return result

    @staticmethod
    def _filter(filter_string):
        """
        Generate a filter function based on the supplied filter string
        @param filter_string
        @return: filter function
        """
        def inner(data):
            return NEWLINE.join(line for line in data.split(NEWLINE) if line.startswith(filter_string))
        return inner


class IrisSampleParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.IRIS_SAMPLE

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642
        @return: regex string
        """
        pattern = r'''
        (?x)                                # verbose
        IRIS,
        (?P<date_time>  %(date_time)s   ),
        (?P<x_tilt>     %(float)s       ),
        (?P<y_tilt>     %(float)s       ),
        (?P<temp>       %(float)s       ),
        (?P<serial>     %(word)s        )
        ''' % common_regex_items
        return pattern

    def _encode_all(self):
        return [
            self._encode_value(IrisSampleParticleKey.SENSOR_ID, 'IRIS', str),
            self._encode_value(IrisSampleParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(IrisSampleParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(IrisSampleParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(IrisSampleParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(IrisSampleParticleKey.SN, self.match.group('serial').strip(), str)
        ]


class HeatSampleParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.HEAT_SAMPLE

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        HEAT,2013/04/23 18:24:46,0000,0001,0025
        @return: regex string
        """
        pattern = r'''
        (?x)                                # verbose
        HEAT,
        (?P<date_time>  %(date_time)s ),
        (?P<x_tilt>     %(int)s       ),
        (?P<y_tilt>     %(int)s       ),
        (?P<temp>       %(int)s       )
        ''' % common_regex_items
        return pattern

    def _encode_all(self):
        return [
            self._encode_value(HeatSampleParticleKey.SENSOR_ID, 'HEAT', str),
            self._encode_value(HeatSampleParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(HeatSampleParticleKey.X_TILT, self.match.group('x_tilt'), int),
            self._encode_value(HeatSampleParticleKey.Y_TILT, self.match.group('y_tilt'), int),
            self._encode_value(HeatSampleParticleKey.TEMP, self.match.group('temp'), int)
        ]


class LilySampleParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.LILY_SAMPLE

    def __init__(self, *args, **kwargs):
        self.out_of_range = kwargs.get('out_of_range')
        super(LilySampleParticle, self).__init__(*args, **kwargs)

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        LILY,2013/06/24 23:22:00,-236.026,  25.666,194.25, 26.01,11.96,N9655
        @return: regex string
        """
        pattern = r'''
        (?x)                                # verbose
        LILY,
        (?P<date_time>  %(date_time)s   ),
        (?P<x_tilt>     %(float)s       ),
        (?P<y_tilt>     %(float)s       ),
        (?P<compass>    %(float)s       ),
        (?P<temp>       %(float)s       ),
        (?P<volts>      %(float)s       ),
        (?P<serial>     %(word)s        )
        ''' % common_regex_items
        return pattern

    def _encode_all(self):
        return [
            self._encode_value(LilySampleParticleKey.SENSOR_ID, 'LILY', str),
            self._encode_value(LilySampleParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(LilySampleParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(LilySampleParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(LilySampleParticleKey.MAG_COMPASS, self.match.group('compass'), float),
            self._encode_value(LilySampleParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(LilySampleParticleKey.SUPPLY_VOLTS, self.match.group('volts'), float),
            self._encode_value(LilySampleParticleKey.SN, self.match.group('serial').strip(), str),
            self._encode_value(LilySampleParticleKey.OUT_OF_RANGE, self.out_of_range, bool)
        ]


class NanoSampleParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.NANO_SAMPLE

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328
        @return: regex string
        """
        pattern = '''
        (?x)
        NANO,
        (?P<pps_sync>    V|P             ),
        (?P<date_time>  %(date_time)s   ),
        (?P<pressure>   %(float)s       ), # PSI
        (?P<temp>       %(float)s       )  # deg C
        %(newline)s
        ''' % common_regex_items
        return pattern

    def _encode_all(self):
        return [
            self._encode_value(NanoSampleParticleKey.SENSOR_ID, 'NANO', str),
            self._encode_value(NanoSampleParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(NanoSampleParticleKey.PRESSURE, self.match.group('pressure'), float),
            self._encode_value(NanoSampleParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(NanoSampleParticleKey.PPS_SYNC, self.match.group('pps_sync'), str),
        ]


# ##############################################################################
# Leveling Particles
###############################################################################


class LilyLevelingParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.LILY_LEVELING

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        LILY,2013/07/24 19:37:12,*  -7.625, 108.257,185.26, 28.14,11.87,N9651
        LILY,2013/06/28 18:04:41,*  -7.390, -14.063,190.91, 25.83,,Switching to Y!11.87,N9651
        LILY,2013/06/28 17:29:21,*  -2.277,  -2.165,190.81, 25.69,,Leveled!11.87,N9651
        LILY,2013/07/02 23:41:27,*  -5.296,  -2.640,185.18, 28.44,,Leveled!11.87,N9651
        LILY,2013/03/22 19:07:28,*-330.000,-330.000,185.45, -6.45,,X Axis out of range, switching to Y!11.37,N9651
        LILY,2013/03/22 19:07:29,*-330.000,-330.000,184.63, -6.43,,Y Axis out of range!11.34,N9651
        """
        pattern = r'''
        (?x)                                # verbose
        LILY,
        (?P<date_time>  %(date_time)s   ),
        \*                                  # leveling marker
        (?P<x_tilt>     %(float)s       ),
        (?P<y_tilt>     %(float)s       ),
        (?P<compass>    %(float)s       ),
        (?P<temp>       %(float)s       ),
        (?P<volts>      %(float)s|,\D*%(float)s ),  # leveling status stuffed here, mangled
        (?P<serial>     %(word)s        )
        ''' % common_regex_items
        return pattern

    def _encode_all(self):
        # handle the mangled leveling status...
        status = None
        supply_volts = self.match.group('volts')
        if supply_volts.startswith(','):
            status, supply_volts = supply_volts.split('!')
            status = status[1:]

        return [
            self._encode_value(LilyLevelingParticleKey.SENSOR_ID, 'LILY', str),
            self._encode_value(LilyLevelingParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(LilyLevelingParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(LilyLevelingParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(LilyLevelingParticleKey.MAG_COMPASS, self.match.group('compass'), float),
            self._encode_value(LilyLevelingParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(LilyLevelingParticleKey.SUPPLY_VOLTS, supply_volts, float),
            self._encode_value(LilyLevelingParticleKey.STATUS, status, str),
            self._encode_value(LilyLevelingParticleKey.SN, self.match.group('serial').strip(), str)
        ]


###############################################################################
# Status Particle
###############################################################################

class BotptStatusParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.BOTPT_STATUS
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        return r'''
            (?x)
            (SYST,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<syst_status>    \*BOTPT.*?root/bin)\n
            (?P<lily_status1>   LILY,%(date_time)s,\*APPLIED.*?,\*9900XY-DUMP-SETTINGS)\n
            (?P<lily_status2>   LILY,%(date_time)s,\*01:\ TBias.*?,\*9900XY-DUMP2)\n
            (?P<iris_status1>   IRIS,%(date_time)s,\*APPLIED.*?,\*9900XY-DUMP-SETTINGS)\n
            (?P<iris_status2>   IRIS,%(date_time)s,\*01:\ TBias.*?,\*9900XY-DUMP2)\n
            (?P<nano_status>    NANO,\*_____.*?ZV:\S+)
            ''' % common_regex_items

    def _to_dict(self, sample):
        result = {}
        for each in sample:
            result[each[DataParticleKey.VALUE_ID]] = each[DataParticleKey.VALUE]
        return result

    def _encode_all(self):
        syst_status = 'SYST,%s,%s' % (self.match.group('date_time'), self.match.group('syst_status'))
        return [
            self._encode_value(BotptStatusParticleKey.IRIS1, self.match.group('iris_status1'), self._filter('IRIS')),
            self._encode_value(BotptStatusParticleKey.IRIS2, self.match.group('iris_status2'), self._filter('IRIS')),
            self._encode_value(BotptStatusParticleKey.LILY1, self.match.group('lily_status1'), self._filter('LILY')),
            self._encode_value(BotptStatusParticleKey.LILY2, self.match.group('lily_status2'), self._filter('LILY')),
            self._encode_value(BotptStatusParticleKey.NANO, self.match.group('nano_status'), self._filter('NANO')),
            self._encode_value(BotptStatusParticleKey.SYST, syst_status, self._filter('SYST')),
        ]


# ##############################################################################
# Individual Status Particles
# These exist only to contain the regular expressions for filtering in the driver
###############################################################################


class IrisStatusParticle1(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        IRIS,2013/06/19 21:13:00,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01
        IRIS,2013/06/12 18:03:44,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
        IRIS,2013/06/12 18:03:44,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
        IRIS,2013/06/12 18:03:44,*01: Vmin:  -2.50  -2.50   2.50   2.50
        IRIS,2013/06/12 18:03:44,*01: Vmax:   2.50   2.50   2.50   2.50
        IRIS,2013/06/12 18:03:44,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/12 18:03:44,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/12 18:03:44,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/12 18:03:44,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        IRIS,2013/06/12 18:03:44,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
        HEAT,2013/06/12 18:04:02,-001,0001,0024
        IRIS,2013/06/12 18:03:44,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
        IRIS,2013/06/12 18:03:44,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00
        IRIS,2013/06/12 18:03:44,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-
        IRIS,2013/06/12 18:03:44,*01:*9900XY-DUMP-SETTINGS
        """
        return r'''
            (?x)                                # verbose
            (?P<name>       IRIS)(,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<status>     \*APPLIED.*)
            (IRIS,%(date_time)s,\*9900XY-DUMP-SETTINGS)
            ''' % common_regex_items


class IrisStatusParticle2(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        IRIS,2013/06/12 23:55:09,*01: TBias: 8.85
        IRIS,2013/06/12 23:55:09,*Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        IRIS,2013/06/12 23:55:09,*Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
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
        return r'''
            (?x)                                # verbose
            (?P<name>       IRIS)(,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<status>     \*01:\ TBias.*?)
            (IRIS,%(date_time)s,\*9900XY-DUMP2)
            ''' % common_regex_items


class LilyStatusParticle1(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        LILY,2014/06/09 18:13:50,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9651 ID01
        LILY,2014/06/09 18:13:50,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
        LILY,2014/06/09 18:13:50,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
        LILY,2014/06/09 18:13:50,*01: Vmin:  -2.50  -2.50   2.50   2.50
        LILY,2014/06/09 18:13:50,*01: Vmax:   2.50   2.50   2.50   2.50
        LILY,2014/06/09 18:13:50,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2014/06/09 18:13:50,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2014/06/09 18:13:50,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2014/06/09 18:13:50,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2014/06/09 18:13:50,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
        LILY,2014/06/09 18:13:51,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
        LILY,2014/06/09 18:13:51,*01: N_SAMP=  28 Xzero=  0.00 Yzero=  0.00
        LILY,2014/06/09 18:13:51,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-
        LILY,2014/06/09 18:13:51,*9900XY-DUMP-SETTINGS
        """
        return r'''
            (?x)                                # verbose
            (?P<name>       LILY)(,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<status>     \*APPLIED.*?)
            (LILY,%(date_time)s,\*9900XY-DUMP-SETTINGS)
            ''' % common_regex_items


class LilyStatusParticle2(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        LILY,2014/06/09 18:04:32,*01: TBias: 3.00
        LILY,2014/06/09 18:04:32,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        LILY,2014/06/09 18:04:32,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
        LILY,2014/06/09 18:04:32,*01: ADCDelay:  310
        LILY,2014/06/09 18:04:32,*01: PCA Model: 84833-14
        LILY,2014/06/09 18:04:32,*01: Firmware Version: 2.1 Rev D
        LILY,2014/06/09 18:04:32,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
        LILY,2014/06/09 18:04:32,*01: Calibrated in uRadian, Current Output Mode: uRadian
        LILY,2014/06/09 18:04:32,*01: Using RS232
        LILY,2014/06/09 18:04:32,*01: Real Time Clock: Installed
        LILY,2014/06/09 18:04:32,*01: Use RTC for Timing: Yes
        LILY,2014/06/09 18:04:32,*01: External Flash: 2162688 Bytes Installed
        LILY,2014/06/09 18:04:32,*01: Flash Status (in Samples) (Used/Total): (107/55424)
        LILY,2014/06/09 18:04:32,*01: Low Power Logger Data Rate: -1 Seconds per Sample
        LILY,2014/06/09 18:04:32,*01: Calibration method: Dynamic
        LILY,2014/06/09 18:04:32,*01: Positive Limit=330.00   Negative Limit=-330.00
        LILY,2014/06/09 18:04:32,*01: Calibration Points:023  X: Enabled  Y: Enabled
        LILY,2014/06/09 18:04:32,*01: Uniaxial (x2) Sensor Type (1)
        LILY,2014/06/09 18:04:32,*01: ADC: 16-bit(external)
        LILY,2014/06/09 18:04:32,*01: Compass: Installed   Magnetic Declination: 0.000000
        LILY,2014/06/09 18:04:32,*01: Compass: Xoffset:  124, Yoffset:  196, Xrange: 1349, Yrange: 1364
        LILY,2014/06/09 18:04:32,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
        LILY,2014/06/09 18:04:32,*01: Motor I_limit: 90.0mA
        LILY,2014/06/09 18:04:33,*01: Current Time: 12/12/00 00:32:30
        LILY,2014/06/09 18:04:33,*01: Supply Voltage: 11.87 Volts
        LILY,2014/06/09 18:04:33,*01: Memory Save Mode: Off
        LILY,2014/06/09 18:04:33,*01: Outputting Data: No
        LILY,2014/06/09 18:04:33,*01: Auto Power-Off Recovery Mode: On
        LILY,2014/06/09 18:04:33,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No
        LILY,2014/06/09 18:04:33,*9900XY-DUMP2
        """
        return r'''
            (?x)                                # verbose
            (?P<name>       LILY)(,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<status>     \*01:\ TBias.*?)(\n)
            (LILY,%(date_time)s,\*9900XY-DUMP2)
            ''' % common_regex_items


class NanoStatusParticle(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        NANO,*______________________________________________________________
        NANO,*PAROSCIENTIFIC SMT SYSTEM INFORMATION
        NANO,*Model Number: 42.4K-265
        NANO,*Serial Number: 120785
        NANO,*Firmware Revision: R5.20
        NANO,*Firmware Release Date: 03-25-13
        NANO,*PPS status: V : PPS signal NOT detected.
        NANO,*--------------------------------------------------------------
        NANO,*AA:7.161800     AC:7.290000     AH:160.0000     AM:0
        NANO,*AP:0            AR:160.0000     BL:0            BR1:115200
        NANO,*BR2:115200      BV:10.9         BX:112          C1:-9747.897
        NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4
        NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000
        NANO,*DL:0            DM:0            DO:0            DP:6
        NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479
        NANO,*FM:0            GD:0            GE:2            GF:0
        NANO,*GP::            GT:1            IA1:8           IA2:12
        NANO,*IB:0            ID:1            IE:0            IK:46
        NANO,*IM:0            IS:5            IY:0            KH:0
        NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198
        NANO,*MA:             MD:0            MU:             MX:0
        NANO,*NO:0            OI:0            OP:2100.000     OR:1.00
        NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000
        NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000
        NANO,*PO:0            PR:238          PS:0            PT:N
        NANO,*PX:3            RE:0            RS:5            RU:0
        NANO,*SD:12           SE:0            SI:OFF          SK:0
        NANO,*SL:0            SM:OFF          SP:0            ST:10
        NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434
        NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00
        NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0
        NANO,*TQ:1            TR:952          TS:1            TU:0
        NANO,*U0:5.839037     UE:0            UF:1.000000
        NANO,*UL:                             UM:user         UN:1
        NANO,*US:0            VP:4            WI:Def=15:00-061311
        NANO,*XC:8            XD:A            XM:1            XN:0
        NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53
        NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0
        NANO,*ZM:0            ZS:0            ZV:.0000000
        """
        return r'''
            (?x)                                # verbose
            (?P<name>       NANO)(,)
            (?P<status>     \*_____.*?ZV:\S+)
            ''' % common_regex_items

    def set_botpt_timestamp(self):
        """
        Overridden, no timestamp in this status
        """
        self.contents[DataParticleKey.INTERNAL_TIMESTAMP] = self.contents[DataParticleKey.PORT_TIMESTAMP]


class SystStatusParticle(BotptDataParticle):
    _compile_flags = re.DOTALL

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        SYST,2014/04/07 20:46:35,*BOTPT BPR and tilt instrument controller
        SYST,2014/04/07 20:46:35,*ts7550n3
        SYST,2014/04/07 20:46:35,*System uptime
        SYST,2014/04/07 20:46:35,* 20:17:02 up 13 days, 19:11,  0 users,  load average: 0.00, 0.00, 0.00
        SYST,2014/04/07 20:46:35,*Memory stats
        SYST,2014/04/07 20:46:35,*             total       used       free     shared    buffers     cached
        SYST,2014/04/07 20:46:35,*Mem:         62888      18520      44368          0       2260       5120
        SYST,2014/04/07 20:46:35,*-/+ buffers/cache:      11140      51748
        SYST,2014/04/07 20:46:35,*Swap:            0          0          0
        SYST,2014/04/07 20:46:35,*MemTotal:        62888 kB
        SYST,2014/04/07 20:46:35,*MemFree:         44392 kB
        SYST,2014/04/07 20:46:35,*Buffers:          2260 kB
        SYST,2014/04/07 20:46:35,*Cached:           5120 kB
        SYST,2014/04/07 20:46:35,*SwapCached:          0 kB
        SYST,2014/04/07 20:46:35,*Active:          10032 kB
        SYST,2014/04/07 20:46:35,*Inactive:         3328 kB
        SYST,2014/04/07 20:46:35,*SwapTotal:           0 kB
        SYST,2014/04/07 20:46:35,*SwapFree:            0 kB
        SYST,2014/04/07 20:46:35,*Dirty:               0 kB
        SYST,2014/04/07 20:46:35,*Writeback:           0 kB
        SYST,2014/04/07 20:46:35,*AnonPages:        6000 kB
        SYST,2014/04/07 20:46:35,*Mapped:           3976 kB
        SYST,2014/04/07 20:46:35,*Slab:             3128 kB
        SYST,2014/04/07 20:46:35,*SReclaimable:      800 kB
        SYST,2014/04/07 20:46:35,*SUnreclaim:       2328 kB
        SYST,2014/04/07 20:46:35,*PageTables:        512 kB
        SYST,2014/04/07 20:46:35,*NFS_Unstable:        0 kB
        SYST,2014/04/07 20:46:35,*Bounce:              0 kB
        SYST,2014/04/07 20:46:35,*CommitLimit:     31444 kB
        SYST,2014/04/07 20:46:35,*Committed_AS:   167276 kB
        SYST,2014/04/07 20:46:35,*VmallocTotal:   188416 kB
        SYST,2014/04/07 20:46:35,*VmallocUsed:         0 kB
        SYST,2014/04/07 20:46:35,*VmallocChunk:   188416 kB
        SYST,2014/04/07 20:46:35,*Listening network services
        SYST,2014/04/07 20:46:35,*tcp        0      0 *:9337-commands         *:*                     LISTEN
        SYST,2014/04/07 20:46:35,*tcp        0      0 *:9338-data             *:*                     LISTEN
        SYST,2014/04/07 20:46:35,*udp        0      0 *:323                   *:*
        SYST,2014/04/07 20:46:35,*udp        0      0 *:54361                 *:*
        SYST,2014/04/07 20:46:35,*udp        0      0 *:mdns                  *:*
        SYST,2014/04/07 20:46:35,*udp        0      0 *:ntp                   *:*
        SYST,2014/04/07 20:46:35,*Data processes
        SYST,2014/04/07 20:46:35,*root       643  0.0  2.2  20100  1436 ?        Sl   Mar25   0:01 /root/bin/COMMANDER
        SYST,2014/04/07 20:46:35,*root       647  0.0  2.5  21124  1604 ?        Sl   Mar25   0:16 /root/bin/SEND_DATA
        SYST,2014/04/07 20:46:35,*root       650  0.0  2.2  19960  1388 ?        Sl   Mar25   0:00 /root/bin/DIO_Rel1
        SYST,2014/04/07 20:46:35,*root       654  0.0  2.1  19960  1360 ?        Sl   Mar25   0:02 /root/bin/HEAT
        SYST,2014/04/07 20:46:35,*root       667  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/IRIS
        SYST,2014/04/07 20:46:35,*root       672  0.0  2.2  19960  1396 ?        Sl   Mar25   0:01 /root/bin/LILY
        SYST,2014/04/07 20:46:35,*root       678  0.0  2.2  19964  1400 ?        Sl   Mar25   0:12 /root/bin/NANO
        SYST,2014/04/07 20:46:35,*root       685  0.0  2.2  19960  1396 ?        Sl   Mar25   0:00 /root/bin/RESO
        SYST,2014/04/07 20:46:35,*root      7860  0.0  0.9   1704   604 ?        S    20:17   0:00 grep root/bin
        """
        return r'''
            (?x)                                # verbose
            (?P<name>       SYST)(,)
            (?P<date_time>  %(date_time)s)(,)
            (?P<status>     \*BOTPT.*?root/bin)
            ''' % common_regex_items
