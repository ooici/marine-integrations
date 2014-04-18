"""
@package mi.instrument.sunburst.sami2_pco2.ooicore.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/ooicore/driver.py
@author Christopher Wingard
@brief Driver for the Sunburst Sensors, SAMI2-PCO2 (PCO2W)
Release notes:
    Sunburst Sensors SAMI2-PCO2 pCO2 underwater sensor.
    Derived from initial code developed by Chris Center,
    and merged with a base class covering both the PCO2W
    and PHSEN instrument classes.
"""

__author__ = 'Christopher Wingard'
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
from mi.instrument.sunburst.driver import CONFIG_WITH_0_PADDING
from mi.instrument.sunburst.driver import CONFIG_WITH_0_AND_F_PADDING
from mi.instrument.sunburst.driver import CONFIG_TERMINATOR
from mi.instrument.sunburst.driver import TIMEOUT
from mi.instrument.sunburst.driver import SAMI_TO_UNIX
from mi.instrument.sunburst.driver import SAMI_TO_NTP

log.debug('herb: ' + 'import sunburst/sami2_pco2/ooicore/driver.py')

###
#    Driver Constant Definitions
###

SAMPLE_DELAY = 180 ## TODO: Make configurable

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

# PCO2W Configuration Record
CONFIGURATION_REGEX = (
    r'([0-9A-Fa-f]{8})' +  # Launch time timestamp (seconds since 1904)
    '([0-9A-Fa-f]{8})' +  # start time (seconds from launch time)
    '([0-9A-Fa-f]{8})' +  # stop time (seconds from start time)
    '([0-9A-Fa-f]{2})' +  # mode bit field
    '([0-9A-Fa-f]{6})' +  # Sami sampling interval (seconds)
    '([0-9A-Fa-f]{2})' +  # Sami driver type (0A)
    '([0-9A-Fa-f]{2})' +  # Pointer to Sami ph config parameters
    '([0-9A-Fa-f]{6})' +  # Device 1 interval
    '([0-9A-Fa-f]{2})' +  # Device 1 driver type
    '([0-9A-Fa-f]{2})' +  # Device 1 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Device 2 interval
    '([0-9A-Fa-f]{2})' +  # Device 2 driver type
    '([0-9A-Fa-f]{2})' +  # Device 2 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Device 3 interval
    '([0-9A-Fa-f]{2})' +  # Device 3 driver type
    '([0-9A-Fa-f]{2})' +  # Device 3 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Prestart interval
    '([0-9A-Fa-f]{2})' +  # Prestart driver type
    '([0-9A-Fa-f]{2})' +  # Prestart pointer to config params
    '([0-9A-Fa-f]{2})' +  # Global config bit field
    '([0-9A-Fa-f]{2})' +  # pCO2-1: pump pulse duration
    '([0-9A-Fa-f]{2})' +  # pCO2-2: pump measurement duration
    '([0-9A-Fa-f]{2})' +  # pCO2-3: # samples per measurement
    '([0-9A-Fa-f]{2})' +  # pCO2-4: cycles between blanks
    '([0-9A-Fa-f]{2})' +  # pCO2-5: reagent cycles
    '([0-9A-Fa-f]{2})' +  # pCO2-6: blank cycles
    '([0-9A-Fa-f]{2})' +  # pCO2-7: flush pump interval
    '([0-9A-Fa-f]{2})' +  # pCO2-8: bit switches
    '([0-9A-Fa-f]{2})' +  # pCO2-9: extra pumps + cycle interval
    '([0-9A-Fa-f]{416})' +  # padding of 0's and then F's
    NEWLINE)
CONFIGURATION_REGEX_MATCHER = re.compile(CONFIGURATION_REGEX)

###
#    Begin Classes
###

class Parameter(SamiParameter):
    """
    Device specific parameters.
    """

    log.debug('herb: ' + 'class Parameter(SamiParameter)')

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

    log.debug('herb: ' + 'class Pco2wSamiSampleDataParticleKey(BaseEnum)')

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

    log.debug('herb: ' + 'class Pco2wSamiSampleDataParticle(DataParticle)')

    _data_particle_type = SamiDataParticleType.SAMI_SAMPLE

    def _build_parsed_values(self):
        """
        Parse SAMI2-PCO2 measurement records from raw data into a dictionary
        """

        log.debug('herb: ' + 'Pco2wSamiSampleDataParticle._build_parsed_values()')

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

class Pco2wConfigurationDataParticleKey(SamiConfigDataParticleKey):
    """
    Data particle key for the configuration record.
    """

    log.debug('herb: ' + 'class Pco2wConfigurationDataParticleKey(SamiConfigDataParticleKey)')

    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_duration'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measurement'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'number_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'number_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    DISABLE_START_BLANK_FLUSH = 'disable_start_blank_flush'
    MEASURE_AFTER_PUMP_PULSE = 'measure_after_pump_pulse'
    NUMBER_EXTRA_PUMP_CYCLES = 'number_extra_pump_cycles'

class Pco2wConfigurationDataParticle(DataParticle):
    """
    Routines for parsing raw data into a configuration record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    log.debug('herb: ' + 'class Pco2wConfigurationDataParticle(DataParticle)')

    _data_particle_type = SamiDataParticleType.CONFIGURATION

    def _build_parsed_values(self):
        """
        Parse configuration record values from raw data into a dictionary
        """

        log.debug('herb: ' + 'Pco2wConfigurationDataParticle._build_parsed_values()')

        ### SAMI-PCO2 Configuration String
        # Configuration string either sent to the instrument to configure it
        # (via the L5A command), or retrieved from the instrument in response
        # to the L command. Sample string (shown broken in multiple lines,
        # would not be received this way):
        #
        #   CEE90B0002C7EA0001E133800A000E100402000E10010B000000000D000000000D
        #   000000000D071020FF54181C010038000000000000000000000000000000000000
        #   000000000000000000000000000000000000000000000000000000000000000000
        #   000000000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        #   FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        #   FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        #   FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        #   FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        #
        # A full description of the configuration string can be found in the
        # vendor supplied Low Level Operation of the SAMI/AFT document.
        ###

        matched = CONFIGURATION_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wConfigurationDataParticleKey.LAUNCH_TIME,
                         Pco2wConfigurationDataParticleKey.START_TIME_OFFSET,
                         Pco2wConfigurationDataParticleKey.RECORDING_TIME,
                         Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_SAMI,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_SAMI,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_SAMI,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE1,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE1,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE1,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE2,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE2,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE2,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE3,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE3,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE3,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_PRESTART,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_PRESTART,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_PRESTART,
                         Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG,
                         Pco2wConfigurationDataParticleKey.PUMP_PULSE,
                         Pco2wConfigurationDataParticleKey.PUMP_DURATION,
                         Pco2wConfigurationDataParticleKey.SAMPLES_PER_MEASUREMENT,
                         Pco2wConfigurationDataParticleKey.CYCLES_BETWEEN_BLANKS,
                         Pco2wConfigurationDataParticleKey.NUMBER_REAGENT_CYCLES,
                         Pco2wConfigurationDataParticleKey.NUMBER_BLANK_CYCLES,
                         Pco2wConfigurationDataParticleKey.FLUSH_PUMP_INTERVAL,
                         Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE,
                         Pco2wConfigurationDataParticleKey.NUMBER_EXTRA_PUMP_CYCLES]

        result = []
        grp_index = 1   # used to index through match groups, starting at 1
        mode_index = 0  # index through the bit fields for MODE_BITS,
                        # GLOBAL_CONFIGURATION and SAMI_BIT_SWITCHES.
        glbl_index = 0
        sami_index = 0

        for key in particle_keys:
            if key in [Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE]:
                # if the keys match values represented by the bits in the one
                # byte mode bits value, parse bit-by-bit using the bit-shift
                # operator to determine the boolean value.
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(4), 16) & (1 << mode_index))})
                mode_index += 1  # bump the bit index
                grp_index = 5    # set the right group index for when we leave this part of the loop.

            elif key in [Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(20), 16) & (1 << glbl_index))})

                glbl_index += 1  # bump the bit index
                # skip bit indices 3 through 6
                if glbl_index == 3:
                    glbl_index = 7
                grp_index = 21  # set the right group index for when we leave this part of the loop.

            elif key in [Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(28), 16) & (1 << sami_index))})
                sami_index += 1  # bump the bit index
                grp_index = 29   # set the right group index for when we leave this part of the loop.

            else:
                # otherwise all values in the string are parsed to integers
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


###############################################################################
# Driver
###############################################################################
class InstrumentDriver(SamiInstrumentDriver):
    """
    InstrumentDriver subclass.
    Subclasses SamiInstrumentDriver and SingleConnectionInstrumentDriver with
    connection state machine.
    """

    log.debug('herb: ' + 'class InstrumentDriver(SamiInstrumentDriver)')

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """

        log.debug('herb: ' + 'InstrumentDriver.get_resource_params()')

        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """

        log.debug('herb: ' + 'InstrumentDriver._build_protocol()')

        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################
class Protocol(SamiProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    log.debug('herb: ' + 'class Protocol(SamiProtocol)')

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        log.debug('herb: ' + 'Protocol.__init__()')

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.

        ###
        # most of these are defined in the base class with exception of handlers
        # defined below that differ for the two instruments (what defines
        # success and the timeout duration)
        ###

        # this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        # while in the AUTOSAMPLE state and will last anywhere from a few
        # seconds to ~12 minutes depending on instrument and the type of
        # sampling.
        # self._protocol_fsm.add_handler(ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.SUCCESS,
        #                                self._handler_sample_success)
        # self._protocol_fsm.add_handler(ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.TIMEOUT,
        #                                self._handler_sample_timeout)

        # this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        # while in either the COMMAND state (or via the discover transition
        # from the UNKNOWN state with the instrument unresponsive) and will
        # last anywhere from a few seconds to 3 minutes depending on instrument
        # and sample type.
        # self._protocol_fsm.add_handler(ProtocolState.POLLED_SAMPLE, ProtocolEvent.SUCCESS,
        #                                self._handler_sample_success)
        # self._protocol_fsm.add_handler(ProtocolState.POLLED_SAMPLE, ProtocolEvent.TIMEOUT,
        #                                self._handler_sample_timeout)

        # Add build handlers for device commands.
        ### primarily defined in base class

        # Add sample handlers

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # build the chunker
        self._chunker = StringChunker(Protocol.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        log.debug('herb: ' + 'Protocol.sieve_function()')

        return_list = []

        sieve_matchers = [REGULAR_STATUS_REGEX_MATCHER,
                          CONTROL_RECORD_REGEX_MATCHER,
                          SAMI_SAMPLE_REGEX_MATCHER,
                          CONFIGURATION_REGEX_MATCHER,
                          ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

## TODO: Move to base class

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker. Pass it to
        extract_sample with the appropriate particle objects and REGEXes.
        """
        log.debug('herb: ' + 'Protocol._got_chunk(): chunk = ' + chunk)

        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(Pco2wConfigurationDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)
        sample = self._extract_sample(Pco2wSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)

        log.debug('herb: ' + 'Protocol._got_chunk(): get_current_state() == ' + self.get_current_state())

        if sample:

            matched = SAMI_SAMPLE_REGEX_MATCHER.match(chunk)
            record_type = matched.group(3)
            log.debug('herb: ' + 'Protocol._got_chunk(): sample record_type = ' + record_type)
            log.debug('herb: ' + 'Protocol._got_chunk(): sample chunk = ' + chunk)

            ## Remove any whitespace
            sample_string = chunk.rstrip()
            checksum = sample_string[-2:]
            checksum_int = int(checksum, 16)
            log.debug('Checksum = %s hex, %d dec' % (checksum, checksum_int))
            calculated_checksum_string = sample_string[3:-2]
            log.debug('Checksum String = %s' % calculated_checksum_string)
            calculated_checksum = self.calc_crc(calculated_checksum_string)
            log.debug('Checksum/Calculated Checksum = %d/%d' % (checksum_int,calculated_checksum))

            if (checksum_int != calculated_checksum):
                log.error("Sample Check Sum Invalid %d/%d, throwing exception." % (checksum_int,calculated_checksum))
                raise SampleException("Sample Check Sum Invalid %d/%d" % (checksum_int,calculated_checksum))

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        log.debug('herb: ' + 'Protocol._build_param_dict()')

        # Add parameter handlers to parameter dict.
        self._param_dict = ProtocolParameterDict()

        ### example configuration string
        # VALID_CONFIG_STRING = 'CEE90B0002C7EA0001E133800A000E100402000E10010B' + \
        #                       '000000000D000000000D000000000D07' + \
        #                       '1020FF54181C010038' + \
        #                       '000000000000000000000000000000000000000000000000000' + \
        #                       '000000000000000000000000000000000000000000000000000' + \
        #                       '000000000000000000000000000000' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE
        #
        ###

        self._param_dict.add(Parameter.LAUNCH_TIME, CONFIGURATION_REGEX,
                             lambda match: int(match.group(1), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00000000,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='launch time')

        self._param_dict.add(Parameter.START_TIME_FROM_LAUNCH, CONFIGURATION_REGEX,
                             lambda match: int(match.group(2), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x02C7EA00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='start time after launch time')

        self._param_dict.add(Parameter.STOP_TIME_FROM_START, CONFIGURATION_REGEX,
                             lambda match: int(match.group(3), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01E13380,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='stop time after start time')

        # Changed from 0x0A to 0x02 to indicate there is no external device, update IOS to indicate this is 0x02
        self._param_dict.add(Parameter.MODE_BITS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(4), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x02,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='mode bits (set to 00001010)')

        self._param_dict.add(Parameter.SAMI_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(5), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000E10,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='sami sample interval')

        self._param_dict.add(Parameter.SAMI_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='sami driver version')

        self._param_dict.add(Parameter.SAMI_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(7), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x02,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='sami parameter pointer')
        ## Changed from 0x000E10 to 0x000000 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 1 sample interval')

        ## Changed from 0x01 to 0x00 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 1 driver version')

        ## Changed from 0x0B to 0x00 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 1 parameter pointer')

        self._param_dict.add(Parameter.DEVICE2_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(11), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 2 sample interval')

        self._param_dict.add(Parameter.DEVICE2_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(12), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 2 driver version')

        ## Changed from 0x0D to 0x00 since there is not external device
        self._param_dict.add(Parameter.DEVICE2_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(13), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 2 parameter pointer')

        self._param_dict.add(Parameter.DEVICE3_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(14), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 3 sample interval')

        self._param_dict.add(Parameter.DEVICE3_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(15), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 3 driver version')

        ## Changed from 0x0D to 0x00 since there is not external device
        self._param_dict.add(Parameter.DEVICE3_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(16), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='device 3 parameter pointer')

        self._param_dict.add(Parameter.PRESTART_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(17), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='prestart sample interval')

        self._param_dict.add(Parameter.PRESTART_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(18), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='prestart driver version')

        ## Changed from 0x0D to 0x00 since there is not external device
        self._param_dict.add(Parameter.PRESTART_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(19), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='prestart parameter pointer')

        # Changed from invalid value 0x00 to 0x07 setting bits, (2) Send live records, (1) Send ^(record type),
        #   (0) 57600 serial port
        self._param_dict.add(Parameter.GLOBAL_CONFIGURATION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(20), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x07,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='global bits (set to 00000111)')

        self._param_dict.add(Parameter.PUMP_PULSE, CONFIGURATION_REGEX,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump pulse duration')

        self._param_dict.add(Parameter.PUMP_DURATION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump measurement duration')

        self._param_dict.add(Parameter.SAMPLES_PER_MEASUREMENT, CONFIGURATION_REGEX,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xFF,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='samples per measurement')

        self._param_dict.add(Parameter.CYCLES_BETWEEN_BLANKS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xA8,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name='cycles between blanks')

        self._param_dict.add(Parameter.NUMBER_REAGENT_CYCLES, CONFIGURATION_REGEX,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x18,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of reagent cycles')

        self._param_dict.add(Parameter.NUMBER_BLANK_CYCLES, CONFIGURATION_REGEX,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x1C,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of blank cycles')

        self._param_dict.add(Parameter.FLUSH_PUMP_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='flush pump interval')

        self._param_dict.add(Parameter.BIT_SWITCHES, CONFIGURATION_REGEX,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='bit switches')

        self._param_dict.add(Parameter.NUMBER_EXTRA_PUMP_CYCLES, CONFIGURATION_REGEX,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x38,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of extra pump cycles')

        ## Engineering parameter to set pseudo auto sample rate
        self._param_dict.add(Parameter.AUTO_SAMPLE_INTERVAL, r'Auto sample rate = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: int(x),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=False,
                             default_value=3600,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='auto sample interval')


    ########################################################################
    # Overridden base class methods
    ########################################################################

    def _get_specific_configuration_string_parameters(self):
        """
        Overridden by device specific subclasses.
        """

        # An ordered list of parameters, can not use unordered dict
        # PCO2W driver extends the base class (SamiParameter)
        parameter_list = [Parameter.START_TIME_FROM_LAUNCH,
                          Parameter.STOP_TIME_FROM_START,
                          Parameter.MODE_BITS,
                          Parameter.SAMI_SAMPLE_INTERVAL,
                          Parameter.SAMI_DRIVER_VERSION,
                          Parameter.SAMI_PARAMS_POINTER,
                          Parameter.DEVICE1_SAMPLE_INTERVAL,
                          Parameter.DEVICE1_DRIVER_VERSION,
                          Parameter.DEVICE1_PARAMS_POINTER,
                          Parameter.DEVICE2_SAMPLE_INTERVAL,
                          Parameter.DEVICE2_DRIVER_VERSION,
                          Parameter.DEVICE2_PARAMS_POINTER,
                          Parameter.DEVICE3_SAMPLE_INTERVAL,
                          Parameter.DEVICE3_DRIVER_VERSION,
                          Parameter.DEVICE3_PARAMS_POINTER,
                          Parameter.PRESTART_SAMPLE_INTERVAL,
                          Parameter.PRESTART_DRIVER_VERSION,
                          Parameter.PRESTART_PARAMS_POINTER,
                          Parameter.GLOBAL_CONFIGURATION,
                          Parameter.PUMP_PULSE,
                          Parameter.PUMP_DURATION,
                          Parameter.SAMPLES_PER_MEASUREMENT,
                          Parameter.CYCLES_BETWEEN_BLANKS,
                          Parameter.NUMBER_REAGENT_CYCLES,
                          Parameter.NUMBER_BLANK_CYCLES,
                          Parameter.FLUSH_PUMP_INTERVAL,
                          Parameter.BIT_SWITCHES,
                          Parameter.NUMBER_EXTRA_PUMP_CYCLES]

        return parameter_list

    def _get_configuration_string_regex(self):
        return CONFIGURATION_REGEX_MATCHER
    def _get_blank_sample_timeout(self):
        log.debug('herb: ' + 'Protocol._get_blank_sample_timeout()')
        return SAMPLE_DELAY
    def _get_sample_timeout(self):
        log.debug('herb: ' + 'Protocol._get_sample_timeout()')
        return SAMPLE_DELAY
    def _get_sample_regex(self):
        log.debug('herb: ' + 'Protocol._get_sample_regex()')
        return SAMI_SAMPLE_REGEX_MATCHER
