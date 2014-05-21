"""
@package mi.instrument.noaa.driver
@file marine-integrations/mi/instrument/noaa/particles.py
@author Pete Cable
@brief Particles for BOTPT
Release notes:
"""

__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import SampleException


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

sample_data = {
    IRIS: [
        'IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642',
        'IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642',
    ],
    HEAT: [
        'HEAT,2013/04/23 18:24:46,0000,0001,0025',
        'HEAT,2013/04/19 22:54:11,001,0001,0025',
    ],
    LILY: [
        'LILY,2013/06/24 23:22:00,-236.026,  25.666,194.25, 26.01,11.96,N9655',
        'LILY,2013/06/24 23:22:02,-236.051,  25.611,194.25, 26.02,11.96,N9655',
        'LILY,2013/07/24 19:37:12,*  -7.625, 108.257,185.26, 28.14,11.87,N9651',
        'LILY,2013/06/28 18:04:41,*  -7.390, -14.063,190.91, 25.83,,Switching to Y!11.87,N9651',
        'LILY,2013/06/28 17:29:21,*  -2.277,  -2.165,190.81, 25.69,,Leveled!11.87,N9651',
        'LILY,2013/07/02 23:41:27,*  -5.296,  -2.640,185.18, 28.44,,Leveled!11.87,N9651',
        'LILY,2013/03/22 19:07:28,*-330.000,-330.000,185.45, -6.45,,X Axis out of range, switching to Y!11.37,N9651',
        'LILY,2013/03/22 19:07:29,*-330.000,-330.000,184.63, -6.43,,Y Axis out of range!11.34,N9651',
    ],
    NANO: [
        'NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328'
    ],
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


class IRISDataParticle(DataParticle):
    _data_particle_type = DataParticleType.IRIS_SAMPLE
    _compiled_regex = None

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
        pattern = 'IRIS,(%(date_time)s),(%(float)s),(%(float)s)(%(float)s)(%(word)s)%(newline)s' % common_regex_items

        # pattern = r'IRIS,'  # pattern starts with IRIS '
        # pattern += r'(.*),'  # 1 time
        # pattern += r'( -*[.0-9]+),'  # 2 x-tilt
        # pattern += r'( -*[.0-9]+),'  # 3 y-tilt
        # pattern += r'(.*),'  # 4 temp
        # pattern += r'(.*)'  # 5 serial number
        # pattern += NEWLINE
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
        @throws SampleException If there is a problem with sample creation
        """
        match = IRISDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            iris_time = match.group('date_time')
            x_tilt = float(match.group('x_tilt'))
            y_tilt = float(match.group('y_tilt'))
            temperature = float(match.group('temp'))
            sn = match.group('serial')

            timestamp = time.strptime(iris_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" % self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'IRIS'},
            {DataParticleKey.VALUE_ID: IRISDataParticleKey.TIME,
             DataParticleKey.VALUE: iris_time},
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


class HEATDataParticle(DataParticle):
    _data_particle_type = DataParticleType.HEAT_SAMPLE
    _compiled_regex = None

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
        # pattern = r'HEAT,'  # pattern starts with HEAT '
        # pattern += r'(.*),'  # 1 time
        # pattern += r'(-*[0-9]+),'  # 2 x-tilt
        # pattern += r'(-*[0-9]+),'  # 3 y-tilt
        # pattern += r'([0-9]{4})'  # 4 temp
        # pattern += NEWLINE
        # return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if HEATDataParticle._compiled_regex is None:
            HEATDataParticle._compiled_regex = re.compile(HEATDataParticle.regex())
        return HEATDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        match = HEATDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            heat_time = match.group('date_time')
            x_tilt = int(match.group('x_tilt'))
            y_tilt = int(match.group('y_tilt'))
            temperature = int(match.group('temp'))

            timestamp = time.strptime(heat_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'HEAT'},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.TIME,
             DataParticleKey.VALUE: heat_time},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: HEATDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature}
        ]

        return result


class LILYDataParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_SAMPLE
    _compiled_regex = None

    def __init__(self, raw_data, out_of_range=False,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP):

        super(LILYDataParticle, self).__init__(raw_data,
                                               port_timestamp,
                                               internal_timestamp,
                                               preferred_timestamp)
        self.out_of_range = out_of_range

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

        # pattern = [
        #     'LILY',
        #     LILY_TIME_REGEX,  # 1 time
        #     FLOAT_REGEX,  # 2 x-tilt
        #     FLOAT_REGEX,  # 3 y-tilt
        #     FLOAT_REGEX,  # 4 Magnetic Compass (degrees)
        #     FLOAT_REGEX,  # 5 temp
        #     FLOAT_REGEX,  # 6 SupplyVolts
        #     WORD_REGEX,  # 7 serial number
        # ]
        # return r'\s*,\s*'.join(pattern) + NEWLINE

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if LILYDataParticle._compiled_regex is None:
            LILYDataParticle._compiled_regex = re.compile(LILYDataParticle.regex())
        return LILYDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            lily_time = match.group('date_time')
            x_tilt = float(match.group('x_tilt'))
            y_tilt = float(match.group('y_tilt'))
            mag_compass = float(match.group('compass'))
            temperature = float(match.group('temp'))
            supply_volts = float(match.group('volts'))
            sn = match.group('serial')

            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'LILY'},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.TIME,
             DataParticleKey.VALUE: lily_time},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.MAG_COMPASS,
             DataParticleKey.VALUE: mag_compass},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SUPPLY_VOLTS,
             DataParticleKey.VALUE: supply_volts},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SN,
             DataParticleKey.VALUE: sn},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.OUT_OF_RANGE,
             DataParticleKey.VALUE: self.out_of_range},
        ]

        return result


###############################################################################
# Leveling Particles
###############################################################################


class LILYLevelingParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_LEVELING
    _compiled_regex = None

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

        # pattern = r'LILY,'  # pattern starts with LILY '
        # pattern += r'(.*?),'  # 1 time
        # pattern += r'\*'  # star
        # pattern += r'(.*?),'  # 2 x-tilt
        # pattern += r'(.*?),'  # 3 y-tilt
        # pattern += r'(.*?),'  # 4 Magnetic Compass (degrees)
        # pattern += r'(.*?),'  # 5 temp
        # pattern += r'(.*|,.*),'  # 6 SupplyVolts/status
        # pattern += r'(.*)'  # 7 serial number
        # pattern += NEWLINE
        # return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if LILYLevelingParticle._compiled_regex is None:
            LILYLevelingParticle._compiled_regex = re.compile(LILYLevelingParticle.regex())
        return LILYLevelingParticle._compiled_regex

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYLevelingParticle.regex_compiled().match(self.raw_data)
        status = 'Leveling'

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            lily_time = match.group('date_time')
            x_tilt = float(match.group('x_tilt'))
            y_tilt = float(match.group('y_tilt'))
            mag_compass = float(match.group('compass'))
            temperature = float(match.group('temp'))
            supply_volts = match.group('volts')
            if supply_volts.startswith(','):
                status, supply_volts = supply_volts.split('!')
            supply_volts = float(supply_volts)
            sn = str(match.group('serial'))

            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))

        except ValueError as e:
            raise SampleException("ValueError while converting data: [%r], [%r]" %
                                  (self.raw_data, e))

        result = [
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.TIME,
             DataParticleKey.VALUE: lily_time},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.MAG_COMPASS,
             DataParticleKey.VALUE: mag_compass},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.SUPPLY_VOLTS,
             DataParticleKey.VALUE: supply_volts},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.STATUS,
             DataParticleKey.VALUE: status},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.SN,
             DataParticleKey.VALUE: sn}
        ]
        return result


class NANODataParticle(DataParticle):
    _data_particle_type = DataParticleType.NANO_SAMPLE
    _compiled_regex = None

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
        # pattern = r'NANO,'  # pattern starts with NANO '
        # pattern += r'(V|P),'  # 1 time-sync (PPS or lost)
        # pattern += r'(.*),'  # 2 time
        # pattern += r'(-*[.0-9]+),'  # 3 pressure (PSIA)
        # pattern += r'(-*[.0-9]+)'  # 4 temperature (degrees)
        # pattern += r'.*'
        # pattern += NEWLINE
        # return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if NANODataParticle._compiled_regex is None:
            NANODataParticle._compiled_regex = re.compile(NANODataParticle.regex())
        return NANODataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)

        @throws SampleException If there is a problem with sample creation
        """
        match = NANODataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            pps_sync = match.group('pps_sync')
            nano_time = match.group('date_time')
            pressure = float(match.group('pressure'))
            temperature = float(match.group('temp'))

            timestamp = time.strptime(nano_time, "%Y/%m/%d %H:%M:%S.%f")
            fraction = float('.' + nano_time.split('.')[1])
            self.set_internal_timestamp(unix_time=time.mktime(timestamp) + fraction)

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: NANODataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'NANO'},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TIME,
             DataParticleKey.VALUE: nano_time},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PRESSURE,
             DataParticleKey.VALUE: pressure},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: NANODataParticleKey.PPS_SYNC,
             DataParticleKey.VALUE: pps_sync},
        ]

        return result


if __name__ == '__main__':
    regexes = [
        LILYDataParticle.regex_compiled(),
        LILYLevelingParticle.regex_compiled(),
        NANODataParticle.regex_compiled(),
        HEATDataParticle.regex_compiled(),
        IRISDataParticle.regex_compiled(),
    ]
    for instrument, lines in sample_data.items():
        print instrument
        for line in lines:
            line = line + NEWLINE
            print line
            for regex in regexes:
                #print regex.pattern, line
                match = regex.search(line)
                if match:
                    print match.groups()
