"""
@package mi.instrument.wetlabs.ac_s.ooicore.driver
@file marine-integrations/mi/instrument/wetlabs/ac_s/ooicore/driver.py
@author Rachel Manoni
@brief Driver for the ooicore
Release notes:

initial version
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger, get_logging_metaclass
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.driver_dict import DriverDictKey

NEWLINE = '\n'

INDEX_OF_PACKET_RECORD_LENGTH = 4
INDEX_OF_START_OF_SCAN_DATA = 32
SIZE_OF_PACKET_RECORD_LENGTH = 2
SIZE_OF_SCAN_DATA_SIGNAL_COUNTS = 2
SIZE_OF_CHECKSUM_PLUS_PAD = 3   # three bytes for 2 byte checksum and 1 byte pad

PACKET_REGISTRATION_PATTERN = '\xff\x00\xff\x00'
PACKET_REGISTRATION_REGEX = re.compile(PACKET_REGISTRATION_PATTERN)

SAMPLE_HEADER_PATTERN = (r'^%s' % PACKET_REGISTRATION_PATTERN +
                         '(.{2})' +  # group 1  - record length
                         '(.{1})' +  # group 2  - packet type
                         '\x01' +    # reserved
                         '(.{1})' +  # group 3  - meter type
                         '(.{3})' +  # group 4  - serial number
                         '(.{2})' +  # group 5  - A reference dark counts
                         '(.{2})' +  # group 6  - pressure counts
                         '(.{2})' +  # group 7  - A signal dark counts
                         '(.{2})' +  # group 8  - raw external temp counts
                         '(.{2})' +  # group 9  - raw internal temp counts
                         '(.{2})' +  # group 10 - C reference dark counts
                         '(.{2})' +  # group 11 - C signal dark counts
                         '(.{4})' +  # group 12 - time in milliseconds since power up
                         '\x01' +    # reserved
                         '(.{1})')   # group 13 - number of output wavelengths
SAMPLE_RECORD_HEADER_REGEX = re.compile(SAMPLE_HEADER_PATTERN, re.DOTALL)

STATUS_PATTERN = r'AC-Spectra .+? quit\.'
STATUS_REGEX = re.compile(STATUS_PATTERN, re.DOTALL)

#Regexes for status particles
FLOAT_PATTERN = r'\d+\.\d+'
FLOAT_REGEX = re.compile(FLOAT_PATTERN)

DATE_PATTERN = r'\([A-Za-z]+\s+\d+\s+\d{4}\s+\d+:\d+:\d+\)'
DATE_REGEX = re.compile(DATE_PATTERN)

PERSISTOR_PATTERN = r'Persistor CF2 SN:\d+'
PERSISTOR_REGEX = re.compile(PERSISTOR_PATTERN)


####
#    Driver Constant Definitions
####
class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    OPTAA_SAMPLE = 'optaa_sample'
    OPTAA_STATUS = 'optaa_status'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE     
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    GET = DriverEvent.GET
    SET = DriverEvent.SET


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE


class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """


def get_two_byte_value(str_input, index=0):
    return ord(str_input[index])*2**8 + ord(str_input[index+1])


def get_three_byte_value(str_input, index=0):
    return ord(str_input[index])*2**16 + get_two_byte_value(str_input, index+1)


def get_four_byte_value(str_input, index=0):
    return ord(str_input[index])*2**24 + get_three_byte_value(str_input, index+1)
        

###############################################################################
# Data Particles
###############################################################################
class OptaaSampleDataParticleKey(BaseEnum):
    RECORD_LENGTH = 'record_length'
    PACKET_TYPE = 'packet_type'
    METER_TYPE = 'meter_type'
    SERIAL_NUMBER = 'serial_number'
    A_REFERENCE_DARK_COUNTS = 'a_reference_dark_counts'
    PRESSURE_COUNTS = 'pressure_counts'
    A_SIGNAL_DARK_COUNTS = 'a_signal_dark_counts'
    EXTERNAL_TEMP_RAW = 'external_temp_raw'
    INTERNAL_TEMP_RAW = 'internal_temp_raw'
    C_REFERENCE_DARK_COUNTS = 'c_reference_dark_counts'
    C_SIGNAL_DARK_COUNTS = 'c_signal_dark_counts'
    ELAPSED_RUN_TIME = 'elapsed_run_time'
    NUM_WAVELENGTHS = 'num_wavelengths'
    C_REFERENCE_COUNTS = 'c_reference_counts'
    A_REFERENCE_COUNTS = 'a_reference_counts'
    C_SIGNAL_COUNTS = 'c_signal_counts'
    A_SIGNAL_COUNTS = 'a_signal_counts'


class OptaaSampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.OPTAA_SAMPLE
        
    def _build_parsed_values(self):

        match = SAMPLE_RECORD_HEADER_REGEX.match(self.raw_data)
        if not match:
            raise SampleException("OPTAA_SampleDataParticle: No regex match of parsed sample data: [%r]"
                                  % self.raw_data)

        record_length = get_two_byte_value(match.group(1), 0)
        packet_checksum = get_two_byte_value(self.raw_data, record_length)
        checksum = 0

        for i in range(0, record_length):
            checksum += ord(self.raw_data[i])
            checksum &= 0xffff
        if checksum != packet_checksum:
            log.debug('OPTAA_SampleDataParticle: Checksum mismatch in data packet, rcvd=%d, calc=%d.', packet_checksum,
                      checksum)
            raise SampleException('OPTAA_SampleDataParticle: Checksum mismatch in data packet, rcvd=%d, calc=%d.'
                                  % (packet_checksum, checksum))

        ### Now build four vectors out of the wavelength data
        index = INDEX_OF_START_OF_SCAN_DATA
        c_ref_count_vector = []
        a_ref_count_vector = []
        c_signal_counts_vector = []
        a_signal_counts_vector = []

        while index < record_length:
            c_ref_count_vector.append(get_two_byte_value(self.raw_data, index))
            index += SIZE_OF_SCAN_DATA_SIGNAL_COUNTS
            a_ref_count_vector.append(get_two_byte_value(self.raw_data, index))
            index += SIZE_OF_SCAN_DATA_SIGNAL_COUNTS
            c_signal_counts_vector.append(get_two_byte_value(self.raw_data, index))
            index += SIZE_OF_SCAN_DATA_SIGNAL_COUNTS
            a_signal_counts_vector.append(get_two_byte_value(self.raw_data, index))
            index += SIZE_OF_SCAN_DATA_SIGNAL_COUNTS

        result = [
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.RECORD_LENGTH,
             DataParticleKey.VALUE: record_length},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.PACKET_TYPE,
             DataParticleKey.VALUE: ord(match.group(2))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.METER_TYPE,
             DataParticleKey.VALUE: ord(match.group(3))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.SERIAL_NUMBER,
             DataParticleKey.VALUE: get_three_byte_value(match.group(4))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.A_REFERENCE_DARK_COUNTS,
             DataParticleKey.VALUE: get_two_byte_value(match.group(5))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.PRESSURE_COUNTS,
             DataParticleKey.VALUE: get_two_byte_value(match.group(6))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.A_SIGNAL_DARK_COUNTS,
             DataParticleKey.VALUE: get_two_byte_value(match.group(7))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.EXTERNAL_TEMP_RAW,
             DataParticleKey.VALUE: get_two_byte_value(match.group(8))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.INTERNAL_TEMP_RAW,
             DataParticleKey.VALUE: get_two_byte_value(match.group(9))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.C_REFERENCE_DARK_COUNTS,
             DataParticleKey.VALUE: get_two_byte_value(match.group(10))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.C_SIGNAL_DARK_COUNTS,
             DataParticleKey.VALUE: get_two_byte_value(match.group(11))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.ELAPSED_RUN_TIME,
             DataParticleKey.VALUE: get_four_byte_value(match.group(12))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.NUM_WAVELENGTHS,
             DataParticleKey.VALUE: ord(match.group(13))},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.C_REFERENCE_COUNTS,
             DataParticleKey.VALUE: c_ref_count_vector},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.A_REFERENCE_COUNTS,
             DataParticleKey.VALUE: a_ref_count_vector},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.C_SIGNAL_COUNTS,
             DataParticleKey.VALUE: c_signal_counts_vector},
            {DataParticleKey.VALUE_ID: OptaaSampleDataParticleKey.A_SIGNAL_COUNTS,
             DataParticleKey.VALUE: a_signal_counts_vector}
        ]

        log.debug("raw data = %r", self.raw_data)
        log.debug('parsed particle = %r', result)

        return result
    
    
class OptaaStatusDataParticleKey(BaseEnum):
    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_DATE = 'firmware_date'
    PERSISTOR_CF_SERIAL_NUMBER = 'persistor_cf_serial_number'
    PERSISTOR_CF_BIOS_VERSION = 'persistor_cf_bios_version'
    PERSISTOR_CF_PICODOS_VERSION = 'persistor_cf_picodos_version'


class OptaaStatusDataParticle(DataParticle):
    _data_particle_type = DataParticleType.OPTAA_STATUS
    
    def _build_parsed_values(self):
        
        data_stream = self.raw_data
            
        # This regex searching can be made a lot more specific, but at the expense of
        # more code. For now, grabbing all three floating point numbers in one sweep is
        # pretty efficient. Note, however, that if the manufacturer ever changes the
        # format of the status display, this code may have to be re-written.
        fp_results = re.findall(FLOAT_REGEX, data_stream)
        if len(fp_results) == 3:
            version = fp_results[0]
            bios = fp_results[1]
            picodos = fp_results[2]
        else:
            raise SampleException('Unable to find exactly three floating-point numbers in status message.')
            
        # find the date/time string and remove enclosing parens
        m = re.search(DATE_REGEX, data_stream)
        if m is not None:
                p = m.group()
                date_of_version = p[1:-1]
        else:
                date_of_version = 'None found'

        persistor = re.search(PERSISTOR_REGEX, data_stream)
        if persistor is not None:
            temp = persistor.group()
            temp1 = re.search(r'\d{2,10}', temp)
            if temp1 is not None:
                persistor_sn = temp1.group()
            else:
                persistor_sn = 'None found'
        else:
            persistor_sn = 'None found'
        
        result = [{DataParticleKey.VALUE_ID: OptaaStatusDataParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: str(version)},
                  {DataParticleKey.VALUE_ID: OptaaStatusDataParticleKey.FIRMWARE_DATE,
                  DataParticleKey.VALUE: date_of_version},
                  {DataParticleKey.VALUE_ID: OptaaStatusDataParticleKey.PERSISTOR_CF_SERIAL_NUMBER,
                   DataParticleKey.VALUE: int(persistor_sn)},
                  {DataParticleKey.VALUE_ID: OptaaStatusDataParticleKey.PERSISTOR_CF_BIOS_VERSION,
                   DataParticleKey.VALUE: str(bios)},
                  {DataParticleKey.VALUE_ID: OptaaStatusDataParticleKey.PERSISTOR_CF_PICODOS_VERSION,
                   DataParticleKey.VALUE: str(picodos)}]

        log.debug("raw data = %r", self.raw_data)
        log.debug('parsed particle = %r', result)

        return result                      


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
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return DriverParameter.list()

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
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    __metaclass__ = get_logging_metaclass(log_level='debug')

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,
                                       self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)

        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(Protocol.sieve_function)

        self._build_driver_dict()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        raw_data_len = len(raw_data)
        return_list = []
        
        # look for samples
        for match in PACKET_REGISTRATION_REGEX.finditer(raw_data):
            if match.start() + INDEX_OF_PACKET_RECORD_LENGTH + SIZE_OF_PACKET_RECORD_LENGTH < raw_data_len:
                packet_length = get_two_byte_value(raw_data,
                                                   match.start() + INDEX_OF_PACKET_RECORD_LENGTH) + SIZE_OF_CHECKSUM_PLUS_PAD

                if match.start() + packet_length <= raw_data_len:
                    return_list.append((match.start(), match.start() + packet_length))
                    
        # look for status
        for match in STATUS_REGEX.finditer(raw_data):
            return_list.append((match.start(), match.end()))
                    
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

        #On a rare occurrence the particle sample coming in will be missing a byte
        #trap the exception thrown and log an error
        try:
            if self._extract_sample(OptaaSampleDataParticle, PACKET_REGISTRATION_REGEX, chunk, timestamp):
                return
        except SampleException:
            log.debug("==== ERROR WITH SAMPLE %s", SampleException.msg)

        try:
            if self._extract_sample(OptaaStatusDataParticle, STATUS_REGEX, chunk, timestamp):
                return
        except SampleException:
            log.debug("===== ERROR WITH STATUS: %s", SampleException.msg)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    ########################################################################
    # Unknown handlers.
    ########################################################################
    def _handler_unknown_enter(self, *args, **kwargs):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can only be AUTOSAMPLE (instrument has no actual command mode).
        """
        return ProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING

    ########################################################################
    # Command handlers.
    # Implemented to make DA possible, instrument has no actual command mode
    ########################################################################
    def _handler_command_enter(self, *args, **kwargs):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        pass

    def _handler_command_get(self, *args, **kwargs):
        """
        Does nothing, implemented to make framework happy
        """
        return None, None

    def _handler_command_set(self, *args, **kwargs):
        """
        Does nothing, implemented to make framework happy
        """
        return None, None

    def _handler_command_start_direct(self, *args, **kwargs):
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_autosample(self, *args, **kwargs):
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_enter(self, *args, **kwargs):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        pass

    def _handler_autosample_stop_autosample(self):
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Direct access handlers.
    ########################################################################
    def _handler_direct_access_enter(self, *args, **kwargs):
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []
    
    def _handler_direct_access_exit(self, *args, **kwargs):
        pass

    def _handler_direct_access_execute_direct(self, data):
        self._do_cmd_direct(data)
        return None, None

    def _handler_direct_access_stop_direct(self):
        """
        Instead of using discover(), as is the norm, put instrument into
        Command state.  Instrument can only sample, even when in a command state.
        """
        return DriverProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)