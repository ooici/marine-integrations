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
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import SampleException
from mi.core.log import get_logging_metaclass

__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

METALOGGER = get_logging_metaclass('debug')

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
    LILY_SAMPLE = 'botpt_lily_sample'
    LILY_LEVELING = 'botpt_lily_leveling'
    IRIS_SAMPLE = 'botpt_iris_sample'
    NANO_SAMPLE = 'botpt_nano_sample'
    HEAT_SAMPLE = 'botpt_heat_sample'

    IRIS_STATUS1 = 'botpt_iris_status1'
    IRIS_STATUS2 = 'botpt_iris_status2'
    LILY_STATUS1 = 'botpt_lily_status1'
    LILY_STATUS2 = 'botpt_lily_status2'
    NANO_STATUS = 'botpt_nano_status'


class IRISDataParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "iris_x_tilt"
    Y_TILT = "iris_y_tilt"
    TEMP = "iris_temp"
    SN = "serial_number"


class HEATDataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "heat_x_tilt"
    Y_TILT = "heat_y_tilt"
    TEMP = "heat_temp"


class LILYDataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    OUT_OF_RANGE = 'lily_out_of_range'


class LILYLevelingParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    STATUS = "lily_leveling_status"


class NANODataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    PPS_SYNC = "time_sync_flag"
    PRESSURE = "bottom_pressure"
    TEMP = "press_trans_temp"


class BotptStatusParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = 'date_time_string'
    STATUS = 'status_string'


class BotptDataParticle(DataParticle):
    _compiled_regex = None
    __metaclass__ = METALOGGER

    def __init__(self, *args, **kwargs):
        self.match = None
        super(BotptDataParticle, self).__init__(*args, **kwargs)

    @staticmethod
    def regex():
        raise NotImplemented()

    def _encode_all(self):
        raise NotImplemented()

    @classmethod
    def regex_compiled(cls):
        if cls._compiled_regex is None:
            cls._compiled_regex = re.compile(cls.regex())
        return cls._compiled_regex

    def get_match(self):
        self.match = self.regex_compiled().match(self.raw_data)
        if not self.match:
            raise SampleException("No regex match of parsed sample data: [%r]" % self.raw_data)

    def set_botpt_timestamp(self):
        ts = self.match.group('date_time')
        if '.' in ts:
            ts, right = ts.split('.', 1)
            fraction = float('.' + right)
        else:
            fraction = 0
        timestamp = time.strptime(ts, "%Y/%m/%d %H:%M:%S")
        self.set_internal_timestamp(unix_time=time.mktime(timestamp) + fraction)

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        self.get_match()

        try:
            self.set_botpt_timestamp()
            result = self._encode_all()
        except Exception as e:
            raise SampleException("Exception [%s] while converting data: [%s]" % (e, self.raw_data))
        return result


class IRISDataParticle(BotptDataParticle):
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
            self._encode_value(IRISDataParticleKey.SENSOR_ID, 'IRIS', str),
            self._encode_value(IRISDataParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(IRISDataParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(IRISDataParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(IRISDataParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(IRISDataParticleKey.SN, self.match.group('serial').strip(), str)
        ]


class HEATDataParticle(BotptDataParticle):
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
            self._encode_value(HEATDataParticleKey.SENSOR_ID, 'HEAT', str),
            self._encode_value(HEATDataParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(HEATDataParticleKey.X_TILT, self.match.group('x_tilt'), int),
            self._encode_value(HEATDataParticleKey.Y_TILT, self.match.group('y_tilt'), int),
            self._encode_value(HEATDataParticleKey.TEMP, self.match.group('temp'), int)
        ]


class LILYDataParticle(BotptDataParticle):
    _data_particle_type = DataParticleType.LILY_SAMPLE

    def __init__(self, *args, **kwargs):
        self.out_of_range = kwargs.get('out_of_range')
        super(LILYDataParticle, self).__init__(*args, **kwargs)

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
            self._encode_value(LILYDataParticleKey.SENSOR_ID, 'LILY', str),
            self._encode_value(LILYDataParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(LILYDataParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(LILYDataParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(LILYDataParticleKey.MAG_COMPASS, self.match.group('compass'), float),
            self._encode_value(LILYDataParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(LILYDataParticleKey.SUPPLY_VOLTS, self.match.group('volts'), float),
            self._encode_value(LILYDataParticleKey.SN, self.match.group('serial').strip(), str),
            self._encode_value(LILYDataParticleKey.OUT_OF_RANGE, self.out_of_range, bool)
        ]


# ##############################################################################
# Leveling Particles
###############################################################################


class LILYLevelingParticle(BotptDataParticle):
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
        status = None
        supply_volts = self.match.group('volts')
        if supply_volts.startswith(','):
            status, supply_volts = supply_volts.split('!')

        return [
            self._encode_value(LILYLevelingParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(LILYLevelingParticleKey.X_TILT, self.match.group('x_tilt'), float),
            self._encode_value(LILYLevelingParticleKey.Y_TILT, self.match.group('y_tilt'), float),
            self._encode_value(LILYLevelingParticleKey.MAG_COMPASS, self.match.group('compass'), float),
            self._encode_value(LILYLevelingParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(LILYLevelingParticleKey.SUPPLY_VOLTS, supply_volts, float),
            self._encode_value(LILYLevelingParticleKey.STATUS, status, str),
            self._encode_value(LILYLevelingParticleKey.SN, self.match.group('serial').strip(), str)
        ]


class NANODataParticle(BotptDataParticle):
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
            self._encode_value(NANODataParticleKey.SENSOR_ID, 'NANO', str),
            self._encode_value(NANODataParticleKey.TIME, self.match.group('date_time'), str),
            self._encode_value(NANODataParticleKey.PRESSURE, self.match.group('pressure'), float),
            self._encode_value(NANODataParticleKey.TEMP, self.match.group('temp'), float),
            self._encode_value(NANODataParticleKey.PPS_SYNC, self.match.group('pps_sync'), str),
        ]
