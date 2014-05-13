"""
@package mi.instrument.sunburst.sami2_pco2.pco2b.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/pco2b/driver.py
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
import time

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility

from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiDataParticleType
from mi.instrument.sunburst.sami2_pco2.driver import ProtocolState
from mi.instrument.sunburst.sami2_pco2.driver import ProtocolEvent
from mi.instrument.sunburst.sami2_pco2.driver import Capability
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiParameter
from mi.instrument.sunburst.sami2_pco2.driver import Prompt
from mi.instrument.sunburst.sami2_pco2.driver import SamiInstrumentCommand
from mi.instrument.sunburst.sami2_pco2.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.sami2_pco2.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.sami2_pco2.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.sami2_pco2.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiConfigurationDataParticleKey
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wInstrumentDriver
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wProtocol
from mi.instrument.sunburst.sami2_pco2.driver import REGULAR_STATUS_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import ERROR_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import NEWLINE
from mi.instrument.sunburst.sami2_pco2.driver import SAMI_SAMPLE_REGEX_MATCHER
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiSampleDataParticle
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wSamiSampleDataParticleKey
from mi.instrument.sunburst.sami2_pco2.driver import Pco2wInstrumentCommand
###
#    Driver Constant Definitions
###

SAMPLE_DELAY = 180

# Imported from base class

###
#    Driver RegEx Definitions
###

# Mostly defined in base class with these additional, instrument specfic
# additions

# Device 1 Sample Records (Type 0x11)
DEV1_SAMPLE_REGEX = (
    r'[\*]' +  #
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # length of data record (bytes)
    '(11)' +  # type of data record (11 for external Device 1, aka the external pump)
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{2})' +  # checksum
    NEWLINE)
DEV1_SAMPLE_REGEX_MATCHER = re.compile(DEV1_SAMPLE_REGEX)

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
    '([0-9A-Fa-f]{2})' +  # Device 1 (external pump) setting
    '([0-9A-Fa-f]{414})' +  # padding of 0's and then F's
    NEWLINE)
CONFIGURATION_REGEX_MATCHER = re.compile(CONFIGURATION_REGEX)


###
#    Begin Classes
###
class DataParticleType(Pco2wSamiDataParticleType):
    """
    Data particle types produced by this driver
    """
    # PCO2W driver extends the base class (SamiDataParticleType) with:
    DEV1_SAMPLE = 'pco2w_dev1_data_record'
    CONFIGURATION = 'pco2w_configuration'

class Parameter(Pco2wSamiParameter):
    """
    Device specific parameters.
    """

    # PCO2W driver extends the base class (Pco2SamiParameter) with:
    EXTERNAL_PUMP_SETTINGS = 'external_pump_setting'
    EXTERNAL_PUMP_DELAY = 'external_pump_delay'

class InstrumentCommand(Pco2wInstrumentCommand):
    """
    Device specfic Instrument command strings. Extends superclass
    SamiInstrumentCommand
    """
    # PCO2W driver extends the base class (SamiInstrumentCommand) with:
    ACQUIRE_SAMPLE_DEV1 = 'R1'

###############################################################################
# Data Particles
###############################################################################

class Pco2wDev1SampleDataParticleKey(BaseEnum):
    """
    Data particle key for the device 1 (external pump) records. These particles
    capture when a sample was collected.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    CHECKSUM = 'checksum'


class Pco2wDev1SampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a device 1 sample data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.DEV1_SAMPLE

    def _build_parsed_values(self):
        """
        Parse device 1 values from raw data into a dictionary
        """

        ### Device 1 Sample Record (External Pump)
        # Device 1 data records produced by the instrument on either command or
        # via an internal schedule whenever the external pump is run (via the
        # R1 command). Like the control records and SAMI data, these messages
        # are preceded by a '*' character and terminated with a '\r'. Sample
        # string:
        #
        #   *540711CEE91DE2CE
        #
        # A full description of the device 1 data record strings can be found
        # in the vendor supplied SAMI Record Format document.
        ###

        matched = DEV1_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wDev1SampleDataParticleKey.UNIQUE_ID,
                         Pco2wDev1SampleDataParticleKey.RECORD_LENGTH,
                         Pco2wDev1SampleDataParticleKey.RECORD_TYPE,
                         Pco2wDev1SampleDataParticleKey.RECORD_TIME,
                         Pco2wDev1SampleDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1

        for key in particle_keys:
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            grp_index += 1
        return result


class Pco2wConfigurationDataParticleKey(Pco2wSamiConfigurationDataParticleKey):
    """
    Data particle key for the configuration record.
    """

    EXTERNAL_PUMP_SETTINGS = 'external_pump_setting'

class Pco2wConfigurationDataParticle(DataParticle):
    """
    Routines for parsing raw data into a configuration record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    _data_particle_type = DataParticleType.CONFIGURATION

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
        #   000000000D071020FF54181C010038140000000000000000000000000000000000
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
                         Pco2wConfigurationDataParticleKey.NUMBER_EXTRA_PUMP_CYCLES,
                         Pco2wConfigurationDataParticleKey.EXTERNAL_PUMP_SETTINGS]

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

        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)

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

        # Construct protocol superclass.
        Pco2wProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.

        # Add build handlers for device commands.
        ### primarily defined in base class
        self._add_build_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_simple_command)
        # Add response handlers for device commands.
        ### primarily defined in base class
        self._add_response_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._parse_response_sample_dev1)

        # Add sample handlers

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # build the chunker
        self._chunker = StringChunker(Protocol.sieve_function)

        self._engineering_parameters.append(Parameter.EXTERNAL_PUMP_DELAY)

    def _parse_response_sample_dev1(self, response, prompt):
        """
        Parse response to take dev1 sample from instrument
        """
        pass

    def _pre_sample_processing(self):
        """
        Override in sub class if needed
        """
        log.debug('Protocol._pre_sample_processing(): Take Dev1 Sample START')

        start_time = time.time()

        dev1_timeout = self._param_dict.get(Parameter.EXTERNAL_PUMP_SETTINGS)

        log.debug('Protocol._pre_sample_processing(): Dev1 Timeout = ' + str(dev1_timeout))

        ## An exception is raised if timeout is hit.
        self._do_cmd_resp(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, timeout = dev1_timeout, response_regex=DEV1_SAMPLE_REGEX_MATCHER)

        sample_time = time.time() - start_time

        log.debug('Protocol._pre_sample_processing(): Dev1 Sample took ' + str(sample_time) + ' to FINISH')

        external_pump_delay = self._param_dict.get(Parameter.EXTERNAL_PUMP_DELAY)

        log.debug('Protocol._pre_sample_processing(): Delaying for %d seconds', external_pump_delay)

        time.sleep(external_pump_delay)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        sieve_matchers = [REGULAR_STATUS_REGEX_MATCHER,
                          CONTROL_RECORD_REGEX_MATCHER,
                          SAMI_SAMPLE_REGEX_MATCHER,
                          DEV1_SAMPLE_REGEX_MATCHER,
                          CONFIGURATION_REGEX_MATCHER,
                          ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker. Pass it to
        extract_sample with the appropriate particle objects and REGEXes.
        """

        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(Pco2wConfigurationDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)
        dev1_sample = self._extract_sample(Pco2wDev1SampleDataParticle, DEV1_SAMPLE_REGEX_MATCHER, chunk, timestamp)
        sami_sample = self._extract_sample(Pco2wSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)

        log.debug('Protocol._got_chunk(): get_current_state() == ' + self.get_current_state())

        if sami_sample:
            self._verify_checksum(chunk, SAMI_SAMPLE_REGEX_MATCHER)
        elif dev1_sample:
            self._verify_checksum(chunk, DEV1_SAMPLE_REGEX_MATCHER)

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        log.debug('Protocol._build_param_dict()')

        Pco2wProtocol._build_param_dict(self)

        ### example configuration string
        # VALID_CONFIG_STRING = 'CEE90B0002C7EA0001E133800A000E100402000E10010B' + \
        #                       '000000000D000000000D000000000D07' + \
        #                       '1020FF54181C01003814' + \
        #                       '000000000000000000000000000000000000000000000000000' + \
        #                       '000000000000000000000000000000000000000000000000000' + \
        #                       '0000000000000000000000000000' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #                       'FFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE
        #
        ###

        configuration_string_regex = self._get_configuration_string_regex()

        self._param_dict.add(Parameter.MODE_BITS, configuration_string_regex,
                             lambda match: int(match.group(4), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x0A,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='mode bits (set to 00001010)')

        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000E10,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 sample interval')

        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 driver version')

        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, configuration_string_regex,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x0B,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 parameter pointer')

        self._param_dict.add(Parameter.EXTERNAL_PUMP_SETTINGS, configuration_string_regex,
                             lambda match: int(match.group(30), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x14,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='external pump settings')

        ## Engineering parameter to set delay after running external pump to take a sample, set as startup parameter
        ##   because it is configurable by the user and should be reapplied on application of startup parameters.
        self._param_dict.add(Parameter.EXTERNAL_PUMP_DELAY, r'External pump delay = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: int(x),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=600,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='external pump delay')

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
                          Parameter.NUMBER_EXTRA_PUMP_CYCLES,
                          Parameter.EXTERNAL_PUMP_SETTINGS]

        return parameter_list

    def _get_configuration_string_regex(self):
        """
        Get configuration string regex.
        @retval configuration string regex.
        """
        return CONFIGURATION_REGEX

    def _get_configuration_string_regex_matcher(self):
        """
        Get config string regex matcher.
        @retval configuration string regex matcher
        """
        return CONFIGURATION_REGEX_MATCHER

    def _get_blank_sample_timeout(self):
        """
        Get blank sample timeout.
        @retval blank sample timeout in seconds.
        """
        return SAMPLE_DELAY

    def _get_sample_timeout(self):
        """
        Get sample timeout.
        @retval sample timeout in seconds.
        """
        return SAMPLE_DELAY
