"""
@package mi.instrument.sunburst.sami2_pco2.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/driver.py
@author Christopher Wingard
@brief Driver for the Sunburst Sensors, SAMI2-PCO2 (PCO2W)
Release notes:
    Sunburst Sensors SAMI2-PCO2 pCO2 underwater sensor.
    Derived from initial code developed by Chris Center,
    and merged with a base class covering both the PCO2W
    and PHSEN instrument classes.
"""

__author__ = 'Kevin Stiemke'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import ProtocolState
from mi.instrument.sunburst.driver import ProtocolEvent
from mi.instrument.sunburst.driver import Capability
from mi.instrument.sunburst.driver import SamiParameter
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol
from mi.instrument.sunburst.driver import REGULAR_STATUS_REGEX_MATCHER
from mi.instrument.sunburst.driver import CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import ERROR_REGEX_MATCHER
from mi.instrument.sunburst.driver import NEWLINE

###
#    Driver Constant Definitions
###

# Imported from base class

###
#    Driver RegEx Definitions
###

# Mostly defined in base class with these additional, instrument specfic
# additions

# SAMI Sample Records (Types 0x04 or 0x05)
SAMI_SAMPLE_REGEX = (
    r'[\*]' +  # record identifier
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # length of data record (bytes)
    '(04|05)' +  # type of data record (04 for measurement, 05 for blank)
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{56})' +  # 14 sets of light measurements (counts)
    '([0-9A-Fa-f]{4})' +  # battery voltage (counts)
    '([0-9A-Fa-f]{4})' +  # thermistor (counts)
    '([0-9A-Fa-f]{2})' +  # checksum
    NEWLINE)
SAMI_SAMPLE_REGEX_MATCHER = re.compile(SAMI_SAMPLE_REGEX)

###
#    Begin Classes
###

class Pco2wSamiDataParticleType(SamiDataParticleType):
    SAMI_SAMPLE = 'pco2w_sami_data_record'

class Pco2wSamiParameter(SamiParameter):
    """
    Device specific parameters.
    """

    # PCO2W driver extends the base class (SamiParameter) with:
    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_duration'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measurement'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'number_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'number_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    BIT_SWITCHES = 'bit_switches'
    NUMBER_EXTRA_PUMP_CYCLES = 'number_extra_pump_cycles'

###############################################################################
# Data Particles
###############################################################################
class Pco2wSamiSampleDataParticleKey(BaseEnum):
    """
    Data particle key for the SAMI2-PCO2 records. These particles
    capture when a sample was processed.
    """

    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    LIGHT_MEASUREMENTS = 'light_measurements'
    VOLTAGE_BATTERY = 'voltage_battery'
    THERMISTER_RAW = 'thermistor_raw'
    CHECKSUM = 'checksum'


class Pco2wSamiSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a SAMI2-PCO2 sample data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    _data_particle_type = Pco2wSamiDataParticleType.SAMI_SAMPLE

    def _build_parsed_values(self):
        """
        Parse SAMI2-PCO2 measurement records from raw data into a dictionary
        """

        ### SAMI Sample Record
        # Regular SAMI (PCO2) data records produced by the instrument on either
        # command or via an internal schedule. Like the control records, the
        # messages are preceded by a '*' character and terminated with a '\r'.
        # Sample string:
        #
        #   *542705CEE91CC800400019096206800730074C2CE04274003B0018096106800732074E0D82066124
        #
        # A full description of the data record strings can be found in the
        # vendor supplied SAMI Record Format document.
        ###

        matched = SAMI_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wSamiSampleDataParticleKey.UNIQUE_ID,
                         Pco2wSamiSampleDataParticleKey.RECORD_LENGTH,
                         Pco2wSamiSampleDataParticleKey.RECORD_TYPE,
                         Pco2wSamiSampleDataParticleKey.RECORD_TIME,
                         Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS,
                         Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY,
                         Pco2wSamiSampleDataParticleKey.THERMISTER_RAW,
                         Pco2wSamiSampleDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1

        for key in particle_keys:
            if key in [Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS]:
                # parse group 5 into 14, 2 byte (4 character) values stored in
                # an array.
                light = matched.group(grp_index)
                light = [int(light[i:i+4], 16) for i in range(0, len(light), 4)]
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: light})
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            grp_index += 1

        return result

class Pco2wSamiConfigurationDataParticleKey(SamiConfigDataParticleKey):
    """
    Data particle key for the configuration record.
    """

    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_on_to_measure'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measure'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'num_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'num_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    DISABLE_START_BLANK_FLUSH = 'disable_start_blank_flush'
    MEASURE_AFTER_PUMP_PULSE = 'measure_after_pump_pulse'
    NUMBER_EXTRA_PUMP_CYCLES = 'cycle_rate'

###############################################################################
# Driver
###############################################################################
class Pco2wInstrumentDriver(SamiInstrumentDriver):
    """
    InstrumentDriver subclass.
    Subclasses SamiInstrumentDriver and SingleConnectionInstrumentDriver with
    connection state machine.
    """

###########################################################################
# Protocol
###########################################################################
class Pco2wProtocol(SamiProtocol):
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

        log.debug('herb: ' + 'Pco2wProtocol.__init__()')

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        log.debug('herb: ' + 'Pco2wProtocol._build_param_dict()')

        SamiProtocol._build_param_dict(self)

        configuration_string_regex = self._get_configuration_string_regex()

        # PCO2 0x04, PHSEN 0x0A
        self._param_dict.add(Pco2wSamiParameter.SAMI_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami driver version')

        self._param_dict.add(Pco2wSamiParameter.PUMP_PULSE, configuration_string_regex,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump pulse duration')

        self._param_dict.add(Pco2wSamiParameter.PUMP_DURATION, configuration_string_regex,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump measurement duration')

        self._param_dict.add(Pco2wSamiParameter.SAMPLES_PER_MEASUREMENT, configuration_string_regex,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xFF,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='samples per measurement')

        self._param_dict.add(Pco2wSamiParameter.CYCLES_BETWEEN_BLANKS, configuration_string_regex,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xA8,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='cycles between blanks')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_REAGENT_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x18,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of reagent cycles')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_BLANK_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x1C,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of blank cycles')

        self._param_dict.add(Pco2wSamiParameter.FLUSH_PUMP_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='flush pump interval')

        self._param_dict.add(Pco2wSamiParameter.BIT_SWITCHES, configuration_string_regex,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='bit switches')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_EXTRA_PUMP_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x38,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of extra pump cycles')

    ########################################################################
    # Overridden base class methods
    ########################################################################

    def _get_sample_regex(self):
        log.debug('herb: ' + 'Protocol._get_sample_regex()')
        return SAMI_SAMPLE_REGEX_MATCHER
