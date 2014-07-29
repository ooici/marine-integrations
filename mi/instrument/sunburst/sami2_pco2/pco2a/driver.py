"""
@package mi.instrument.sunburst.sami2_pco2.pco2a.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/pco2a/driver.py
@author Christopher Wingard & Kevin Stiemke
@brief Driver for the Sunburst Sensors, SAMI2-PCO2 (PCO2W)
Release notes:
    Sunburst Sensors SAMI2-PCO2 pCO2 underwater sensor.
    Derived from initial code developed by Chris Center,
    and merged with a base class covering both the PCO2W
    and PHSEN instrument classes.
"""

__author__ = 'Christopher Wingard & Kevin Stiemke'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger

log = get_logger()

from mi.core.exceptions import SampleException

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiDataParticleType
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocolState
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocolEvent
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wCapability
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wParameter
from mi.instrument.sunburst.driver import Prompt, SamiBatteryVoltageDataParticle, SamiThermistorVoltageDataParticle
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiConfigurationDataParticleKey
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wInstrumentDriver
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocol
from mi.instrument.sunburst.driver import SAMI_REGULAR_STATUS_REGEX_MATCHER
from mi.instrument.sunburst.driver import SAMI_CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import SAMI_ERROR_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import SAMI_NEWLINE
from mi.instrument.sunburst.sami2_pco2.driver import PCO2W_SAMPLE_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiSampleDataParticle
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wInstrumentCommand
from mi.core.instrument.instrument_fsm import ThreadSafeFSM

###
#    Driver Constant Definitions
###

# Imported from base class

###
#    Driver RegEx Definitions
###

# Mostly defined in base class with these additional, instrument specfic
# additions

# PCO2W Configuration Record
PCO2WA_CONFIGURATION_REGEX = (
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
    SAMI_NEWLINE)
PCO2WA_CONFIGURATION_REGEX_MATCHER = re.compile(PCO2WA_CONFIGURATION_REGEX)


###
#    Begin Classes
###

class ProtocolState(Pco2wProtocolState):
    """
    Extend base class with instrument specific functionality.
    """


class ProtocolEvent(Pco2wProtocolEvent):
    """
    Extend base class with instrument specific functionality.
    """


class Capability(Pco2wCapability):
    """
    Extend base class with instrument specific functionality.
    """


class DataParticleType(Pco2wSamiDataParticleType):
    """
    Data particle types produced by this driver
    """
    PCO2W_A_CONFIGURATION = 'pco2w_a_configuration'
    PCO2W_A_DATA_RECORD = 'pco2w_a_data_record'
    PCO2W_A_REGULAR_STATUS = 'pco2w_a_regular_status'
    PCO2W_A_CONTROL_RECORD = 'pco2w_a_control_record'
    PCO2W_A_BATTERY_VOLTAGE = 'pco2w_a_battery_voltage'
    PCO2W_A_THERMISTOR_VOLTAGE = 'pco2w_a_thermistor_voltage'


class Parameter(Pco2wParameter):
    """
    Device specific parameters.
    """


class InstrumentCommand(Pco2wInstrumentCommand):
    """
    Device specfic Instrument command strings. Extends superclass
    SamiInstrumentCommand
    """


###############################################################################
# Data Particles
###############################################################################
#Redefine the data particle type so each particle has a unique name
SamiBatteryVoltageDataParticle._data_particle_type = DataParticleType.PCO2W_A_BATTERY_VOLTAGE
SamiThermistorVoltageDataParticle._data_particle_type = DataParticleType.PCO2W_A_THERMISTOR_VOLTAGE
SamiRegularStatusDataParticle._data_particle_type = DataParticleType.PCO2W_A_REGULAR_STATUS
SamiControlRecordDataParticle._data_particle_type = DataParticleType.PCO2W_A_CONTROL_RECORD


class Pco2waConfigurationDataParticleKey(Pco2wSamiConfigurationDataParticleKey):
    """
    Data particle key for the configuration record.
    """


class Pco2waConfigurationDataParticle(DataParticle):
    """
    Routines for parsing raw data into a configuration record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    _data_particle_type = DataParticleType.PCO2W_A_CONFIGURATION

    def _build_parsed_values(self):
        """
        Parse configuration record values from raw data into a dictionary
        """

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

        matched = PCO2WA_CONFIGURATION_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2waConfigurationDataParticleKey.LAUNCH_TIME,
                         Pco2waConfigurationDataParticleKey.START_TIME_OFFSET,
                         Pco2waConfigurationDataParticleKey.RECORDING_TIME,
                         Pco2waConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE,
                         Pco2waConfigurationDataParticleKey.TIMER_INTERVAL_SAMI,
                         Pco2waConfigurationDataParticleKey.DRIVER_ID_SAMI,
                         Pco2waConfigurationDataParticleKey.PARAMETER_POINTER_SAMI,
                         Pco2waConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE1,
                         Pco2waConfigurationDataParticleKey.DRIVER_ID_DEVICE1,
                         Pco2waConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE1,
                         Pco2waConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE2,
                         Pco2waConfigurationDataParticleKey.DRIVER_ID_DEVICE2,
                         Pco2waConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE2,
                         Pco2waConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE3,
                         Pco2waConfigurationDataParticleKey.DRIVER_ID_DEVICE3,
                         Pco2waConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE3,
                         Pco2waConfigurationDataParticleKey.TIMER_INTERVAL_PRESTART,
                         Pco2waConfigurationDataParticleKey.DRIVER_ID_PRESTART,
                         Pco2waConfigurationDataParticleKey.PARAMETER_POINTER_PRESTART,
                         Pco2waConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2waConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2waConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2waConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG,
                         Pco2waConfigurationDataParticleKey.PUMP_PULSE,
                         Pco2waConfigurationDataParticleKey.PUMP_DURATION,
                         Pco2waConfigurationDataParticleKey.SAMPLES_PER_MEASUREMENT,
                         Pco2waConfigurationDataParticleKey.CYCLES_BETWEEN_BLANKS,
                         Pco2waConfigurationDataParticleKey.NUMBER_REAGENT_CYCLES,
                         Pco2waConfigurationDataParticleKey.NUMBER_BLANK_CYCLES,
                         Pco2waConfigurationDataParticleKey.FLUSH_PUMP_INTERVAL,
                         Pco2waConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2waConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE,
                         Pco2waConfigurationDataParticleKey.NUMBER_EXTRA_PUMP_CYCLES]

        result = []
        grp_index = 1  # used to index through match groups, starting at 1
        mode_index = 0  # index through the bit fields for MODE_BITS,
        # GLOBAL_CONFIGURATION and SAMI_BIT_SWITCHES.
        glbl_index = 0
        sami_index = 0

        for key in particle_keys:
            if key in [Pco2waConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                       Pco2waConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE]:
                # if the keys match values represented by the bits in the one
                # byte mode bits value, parse bit-by-bit using the bit-shift
                # operator to determine the boolean value.
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(4), 16) & (1 << mode_index))})
                mode_index += 1  # bump the bit index
                grp_index = 5  # set the right group index for when we leave this part of the loop.

            elif key in [Pco2waConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2waConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2waConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2waConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(20), 16) & (1 << glbl_index))})

                glbl_index += 1  # bump the bit index
                # skip bit indices 3 through 6
                if glbl_index == 3:
                    glbl_index = 7
                grp_index = 21  # set the right group index for when we leave this part of the loop.

            elif key in [Pco2waConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2waConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(28), 16) & (1 << sami_index))})
                sami_index += 1  # bump the bit index
                grp_index = 29  # set the right group index for when we leave this part of the loop.

            else:
                # otherwise all values in the string are parsed to integers
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


###############################################################################
# Driver
###############################################################################
class InstrumentDriver(Pco2wInstrumentDriver):
    """
    InstrumentDriver subclass.
    Subclasses SamiInstrumentDriver and SingleConnectionInstrumentDriver with
    connection state machine.
    """

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

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

        self._protocol = Protocol(Prompt, SAMI_NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################
class Protocol(Pco2wProtocol):
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

        # Build protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(
            ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Construct protocol superclass.
        Pco2wProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # build the chunker
        self._chunker = StringChunker(Protocol.sieve_function)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """

        return [x for x in events if Capability.has(x)]

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        :param raw_data: data to filter
        """

        return_list = []

        sieve_matchers = [SAMI_REGULAR_STATUS_REGEX_MATCHER,
                          SAMI_CONTROL_RECORD_REGEX_MATCHER,
                          PCO2W_SAMPLE_REGEX_MATCHER,
                          PCO2WA_CONFIGURATION_REGEX_MATCHER,
                          SAMI_ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker. Pass it to
        extract_sample with the appropriate particle objects and REGEXes.
        """

        if any([self._extract_sample(SamiRegularStatusDataParticle, SAMI_REGULAR_STATUS_REGEX_MATCHER,
                                     chunk, timestamp),
                self._extract_sample(SamiControlRecordDataParticle, SAMI_CONTROL_RECORD_REGEX_MATCHER,
                                     chunk, timestamp),
                self._extract_sample(Pco2waConfigurationDataParticle, PCO2WA_CONFIGURATION_REGEX_MATCHER,
                                     chunk, timestamp)]):
            return

        sample = self._extract_sample(Pco2wSamiSampleDataParticle, PCO2W_SAMPLE_REGEX_MATCHER, chunk, timestamp)

        log.debug('Protocol._got_chunk(): get_current_state() == %s', self.get_current_state())

        if sample:
            self._verify_checksum(chunk, PCO2W_SAMPLE_REGEX_MATCHER)

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        Pco2wProtocol._build_param_dict(self)

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

        configuration_string_regex = self._get_configuration_string_regex()

        # Changed from 0x0A to 0x02 to indicate there is no external device, update IOS to indicate this is 0x02
        self._param_dict.add(Parameter.MODE_BITS, configuration_string_regex,
                             lambda match: int(match.group(4), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x02,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Mode Bits')

        ## Changed from 0x000E10 to 0x000000 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Sample Interval')

        ## Changed from 0x01 to 0x00 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Driver Version')

        ## Changed from 0x0B to 0x00 to indicate there is not external device
        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, configuration_string_regex,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Parameter Pointer')

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
        """
        Get configuration string regex.
        @retval configuration string regex.
        """
        return PCO2WA_CONFIGURATION_REGEX

    def _get_configuration_string_regex_matcher(self):
        """
        Get config string regex matcher.
        @retval configuration string regex matcher
        """
        return PCO2WA_CONFIGURATION_REGEX_MATCHER
