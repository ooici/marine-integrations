#!/usr/bin/env python
# coding=utf-8

"""
@package mi.instrument.wetlabs.fluorometer.flort_d.driver
@file marine-integrations/mi/instrument/wetlabs/fluorometer/flort_d/driver.py
@author Art Teranishi
@brief Driver for the flort_d
Release notes:

Initial development
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum

from mi.core.util import dict_equal

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentCommandException

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol

from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

from mi.core.instrument.chunker import StringChunker

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.time import get_timestamp_delayed

from mi.core.log import get_logging_metaclass

# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 30


###
#    Driver Constant Definitions
###
class ParameterUnit(BaseEnum):
    COUNTS = 'counts'
    TIME_INTERVAL = 'HH:MM:SS'
    DATE_INTERVAL = 'MM:DD:YY'
    PARTS_PER_MILLION = 'ppm'
    MICROGRAMS_PER_LITER = 'µg/L'
    PART_PER_METER_STERADIAN = '1/(m • sr)'


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    FLORTD_MNU = 'flort_d_status'
    FLORTD_SAMPLE = 'flort_d_data_record'


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
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    RUN_WIPER = 'PROTOCOL_EVENT_RUN_WIPER'
    RUN_WIPER_SCHEDULED = 'PROTOCOL_EVENT_RUN_WIPER_SCHEDULED'
    SCHEDULED_CLOCK_SYNC = DriverEvent.SCHEDULED_CLOCK_SYNC
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    SCHEDULED_ACQUIRE_STATUS = 'PROTOCOL_EVENT_SCHEDULED_ACQUIRE_STATUS'
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    RUN_WIPER = ProtocolEvent.RUN_WIPER
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    DISCOVER = ProtocolEvent.DISCOVER
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Parameters for the dictionary
    """

    #Device specific parameters.
    MEASUREMENTS_PER_REPORTED = "ave"     # Measurements per reported value    int
    MEASUREMENT_1_DARK_COUNT = "m1d"      # Measurement 1 dark count           int
    MEASUREMENT_1_SLOPE = "m1s"           # Measurement 1 slope value          float
    MEASUREMENT_2_DARK_COUNT = "m2d"      # Measurement 2 dark count           int
    MEASUREMENT_2_SLOPE = "m2s"           # Measurement 2 slope value          float
    MEASUREMENT_3_DARK_COUNT = "m3d"      # Measurement 3 dark count           int
    MEASUREMENT_3_SLOPE = "m3s"           # Measurement 3 slope value          float
    MEASUREMENTS_PER_PACKET = "pkt"       # Measurements per packet            int
    BAUD_RATE = "rat"                     # Baud rate                          int
    PACKETS_PER_SET = "set"               # Packets per set                    int
    PREDEFINED_OUTPUT_SEQ = "seq"         # Predefined output sequence         int
    RECORDING_MODE = "rec"                # Recording mode                     int
    MANUAL_MODE = "man"                   # Manual mode                        int
    SAMPLING_INTERVAL = "int"             # Sampling interval                  str
    DATE = "dat"                          # Date                               str
    TIME = "clk"                          # Time                               str
    MANUAL_START_TIME = "mst"             # Manual start time                  str

    #Hardware Data
    SERIAL_NUM = "ser"                    # Serial number                      str
    FIRMWARE_VERSION = "ver"              # Firmware version                   str
    INTERNAL_MEMORY = "mem"               # Internal memory                    int

    #Engineering param
    RUN_WIPER_INTERVAL = "wiper_interval"            # Interval to schedule running wiper    str
    RUN_CLOCK_SYNC_INTERVAL = 'clk_interval'         # Interval to schedule syncing clock    str
    RUN_ACQUIRE_STATUS_INTERVAL = 'status_interval'  # Interval to schedule status           str


class ScheduledJob(BaseEnum):
    """
    List of jobs to be scheduled
    """
    RUN_WIPER = 'run_wiper'
    CLOCK_SYNC = 'clock_sync'
    ACQUIRE_STATUS = 'acquire_status'


class Prompt(BaseEnum):
    """
    Device I/O prompts.
    FLORT-D does not have a prompt.
    """


class InstrumentCommand(BaseEnum):
    """
    Commands sent to the instrument

    """
    # Instrument command strings
    INTERRUPT_INSTRUMENT = "!!!!!"
    PRINT_METADATA = "$met"
    PRINT_MENU = "$mnu"
    RUN_SETTINGS = "$run"
    RUN_WIPER = "$mvs"
    #placeholder for all parameters
    SET = 'set'


###############################################################################
# Data Particles
###############################################################################
MNU_REGEX = r"(Ser.*?Mem\s[0-9]{1,6})"
MNU_REGEX_MATCHER = re.compile(MNU_REGEX, re.DOTALL)

RUN_REGEX = r"(mvs\s[0-1]\r\n)"
RUN_REGEX_MATCHER = re.compile(RUN_REGEX, re.DOTALL)

MET_REGEX = r"(Sig_1\S*).*?(Sig_2\S*).*?(Sig_3,counts,,SO,\S*?,\d+)"
MET_REGEX_MATCHER = re.compile(MET_REGEX, re.DOTALL)

TIME_INTERVAL = r"blahblahblahfakeregexdon'tmatchme"

SAMPLE_REGEX = r"(\d+/\d+/\d+\s+\d+:\d+:\d+(\s+\d+){7}\r\n)"
SAMPLE_REGEX_MATCHER = re.compile(SAMPLE_REGEX)


class FlortDMNU_ParticleKey(BaseEnum):
    SERIAL_NUM = "serial_number"
    FIRMWARE_VER = "firmware_version"
    AVE = "number_measurements_per_reported_value"
    PKT = "number_of_reported_values_per_packet"
    M1D = "measurement_1_dark_count_value"
    M2D = "measurement_2_dark_count_value"
    M3D = "measurement_3_dark_count_value"
    M1S = "measurement_1_slope_value"
    M2S = "measurement_2_slope_value"
    M3S = "measurement_3_slope_value"
    SEQ = "predefined_output_sequence"
    RAT = "baud_rate"
    SET = "number_of_packets_per_set"
    REC = "recording_mode"
    MAN = "manual_mode"
    INT = "sampling_interval"
    DAT = "date"
    CLK = "clock"
    MST = "manual_start_time"
    MEM = "internal_memory"


class FlortDMNU_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest comes along for free.
    """
    _data_particle_type = DataParticleType.FLORTD_MNU

    LINE01 = r"Ser\s*(\S*)"
    LINE02 = r"Ver\s*(\S*)"
    LINE03 = r"Ave\s*(\S*)"
    LINE04 = r"Pkt\s*(\S*)"
    LINE05 = r"M1d\s*(\S*)"
    LINE06 = r"M2d\s*(\S*)"
    LINE07 = r"M3d\s*(\S*)"
    LINE08 = r"M1s\s*(\S*)"
    LINE09 = r"M2s\s*(\S*)"
    LINE10 = r"M3s\s*(\S*)"
    LINE11 = r"Seq\s*(\S*)"
    LINE12 = r"Rat\s*(\S*)"
    LINE13 = r"Set\s*(\S*)"
    LINE14 = r"Rec\s*(\S*)"
    LINE15 = r"Man\s*(\S*)"
    LINE16 = r"Int\s*(\S*)"
    LINE17 = r"Dat\s*(\S*)"
    LINE18 = r"Clk\s*(\S*)"
    LINE19 = r"Mst\s*(\S*)"
    LINE20 = r"Mem\s*(\S*)"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags
        @throws SampleException If there is a problem with sample creation
        """
        log.debug("%% IN FlortDMNU_Particle:_build_parsed_values")
        log.debug("raw data = %r", self.raw_data)

        try:

            serial_num = str(re.compile(self.LINE01).search(self.raw_data).group(1))
            firmware_ver = str(re.compile(self.LINE02).search(self.raw_data).group(1))
            ave = int(re.compile(self.LINE03).search(self.raw_data).group(1))
            pkt = int(re.compile(self.LINE04).search(self.raw_data).group(1))
            m1d = int(re.compile(self.LINE05).search(self.raw_data).group(1))
            m2d = int(re.compile(self.LINE06).search(self.raw_data).group(1))
            m3d = int(re.compile(self.LINE07).search(self.raw_data).group(1))
            m1s = float(re.compile(self.LINE08).search(self.raw_data).group(1))
            m2s = float(re.compile(self.LINE09).search(self.raw_data).group(1))
            m3s = float(re.compile(self.LINE10).search(self.raw_data).group(1))
            seq = int(re.compile(self.LINE11).search(self.raw_data).group(1))
            rat = int(re.compile(self.LINE12).search(self.raw_data).group(1))
            set = int(re.compile(self.LINE13).search(self.raw_data).group(1))
            rec = int(re.compile(self.LINE14).search(self.raw_data).group(1))
            man = int(re.compile(self.LINE15).search(self.raw_data).group(1))
            interval = str(re.compile(self.LINE16).search(self.raw_data).group(1))
            dat = str(re.compile(self.LINE17).search(self.raw_data).group(1))
            clk = str(re.compile(self.LINE18).search(self.raw_data).group(1))
            mst = str(re.compile(self.LINE19).search(self.raw_data).group(1))
            mem = int(re.compile(self.LINE20).search(self.raw_data).group(1))

            result = [{DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.SERIAL_NUM, DataParticleKey.VALUE: serial_num},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.FIRMWARE_VER, DataParticleKey.VALUE: firmware_ver},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.AVE, DataParticleKey.VALUE: ave},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.PKT, DataParticleKey.VALUE: pkt},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M1D, DataParticleKey.VALUE: m1d},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M2D, DataParticleKey.VALUE: m2d},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M3D, DataParticleKey.VALUE: m3d},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M1S, DataParticleKey.VALUE: m1s},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M2S, DataParticleKey.VALUE: m2s},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.M3S, DataParticleKey.VALUE: m3s},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.SEQ, DataParticleKey.VALUE: seq},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.RAT, DataParticleKey.VALUE: rat},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.SET, DataParticleKey.VALUE: set},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.REC, DataParticleKey.VALUE: rec},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.MAN, DataParticleKey.VALUE: man},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.INT, DataParticleKey.VALUE: interval},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.DAT, DataParticleKey.VALUE: dat},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.CLK, DataParticleKey.VALUE: clk},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.MST, DataParticleKey.VALUE: mst},
                  {DataParticleKey.VALUE_ID: FlortDMNU_ParticleKey.MEM, DataParticleKey.VALUE: mem}]

            log.debug('parsed particle = %r', result)

            return result

        except Exception:
            raise SampleException('Error building FlortDMNU_Particle')


class FlortDSample_ParticleKey(BaseEnum):
    date_string = 'date_string'
    time_string = 'time_string'
    wave_beta = 'measurement_wavelength_beta'
    raw_sig_beta = 'raw_signal_beta'
    wave_chl = 'measurement_wavelength_chl'
    raw_sig_chl = 'raw_signal_chl'
    wave_cdom = 'measurement_wavelength_cdom'
    raw_sig_cdom = 'raw_signal_cdom'
    raw_temp = 'raw_internal_temp'

    #the following comes from $met command
    #since these values will never change, on initialization they are stored and then used for the remainder
    SIG_1_SCALE_FACTOR = 'signal_1_scale_factor'
    SIG_1_OFFSET = 'signal_1_offset'
    SIG_2_SCALE_FACTOR = 'signal_2_scale_factor'
    SIG_2_OFFSET = 'signal_2_offset'
    SIG_3_SCALE_FACTOR = 'signal_3_scale_factor'
    SIG_3_OFFSET = 'signal_3_offset'


class FlortDSample_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FLORTD_SAMPLE
    _compiled_regex = None

    sig_1_offset = 0
    sig_1_scale = 0
    sig_2_offset = 0
    sig_2_scale = 0
    sig_3_offset = 0
    sig_3_scale = 0

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if FlortDSample_Particle._compiled_regex is None:
            FlortDSample_Particle._compiled_regex = re.compile(FlortDSample_Particle.regex())
        return FlortDSample_Particle._compiled_regex

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        return SAMPLE_REGEX

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        log.debug("%% IN FLORTDSample_Particle:_build_parsed_values")
        log.debug("raw data = %r", self.raw_data)

        match = FlortDSample_Particle.regex_compiled().search(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" % self.raw_data)

        try:

            split_data = match.group(0).split('\t')
            date_str = str(split_data[0])
            time_str = str(split_data[1])
            wave_beta = int(split_data[2])
            raw_sig_beta = int(split_data[3])
            wave_chl = int(split_data[4])
            raw_sig_chl = int(split_data[5])
            wave_cdom = int(split_data[6])
            raw_sig_cdom = int(split_data[7])
            raw_temp = int(split_data[8])

        except Exception:
            raise SampleException('FlortDSample_Particle: cannot parse thru data')

        result = [{DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.date_string, DataParticleKey.VALUE: date_str},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.time_string, DataParticleKey.VALUE: time_str},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.wave_beta, DataParticleKey.VALUE: wave_beta},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.raw_sig_beta, DataParticleKey.VALUE: raw_sig_beta},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.wave_chl, DataParticleKey.VALUE: wave_chl},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.raw_sig_chl, DataParticleKey.VALUE: raw_sig_chl},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.wave_cdom, DataParticleKey.VALUE: wave_cdom},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.raw_sig_cdom, DataParticleKey.VALUE: raw_sig_cdom},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.raw_temp, DataParticleKey.VALUE: raw_temp},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_1_OFFSET, DataParticleKey.VALUE: FlortDSample_Particle.sig_1_offset},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_1_SCALE_FACTOR, DataParticleKey.VALUE: FlortDSample_Particle.sig_1_scale},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_2_OFFSET, DataParticleKey.VALUE: FlortDSample_Particle.sig_2_offset},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_2_SCALE_FACTOR, DataParticleKey.VALUE: FlortDSample_Particle.sig_2_scale},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_3_OFFSET, DataParticleKey.VALUE: FlortDSample_Particle.sig_3_offset},
            {DataParticleKey.VALUE_ID: FlortDSample_ParticleKey.SIG_3_SCALE_FACTOR, DataParticleKey.VALUE: FlortDSample_Particle.sig_3_scale}]

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
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    @staticmethod
    def get_resource_params():
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


################################ /Driver ##################################

###########################################################################
# Protocol
###########################################################################
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    __metaclass__ = get_logging_metaclass(log_level='info')

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

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RUN_WIPER, self._handler_command_run_wiper)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.RUN_WIPER_SCHEDULED, self._handler_autosample_run_wiper)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        #GET is only used for configuring the driver when it discovers that it is in AUTOSAMPLE
        #will not be shown on the State Diagram
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.INTERRUPT_INSTRUMENT, self._build_no_eol_command)
        self._add_build_handler(InstrumentCommand.SET, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.RUN_SETTINGS, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.PRINT_METADATA, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.PRINT_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.RUN_WIPER, self._build_simple_command)

        #all commands return a 'unrecognized command' if not recognized by the instrument
        self._add_response_handler(InstrumentCommand.INTERRUPT_INSTRUMENT, self._parse_command_response)

        self._add_response_handler(InstrumentCommand.SET, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.RUN_SETTINGS, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.PRINT_METADATA, self._parse_metadata_response)
        self._add_response_handler(InstrumentCommand.PRINT_MENU, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.RUN_WIPER, self._parse_run_wiper_response)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []
        self._chunker = StringChunker(Protocol.sieve_function)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        return_list = []

        sieve_match = [MNU_REGEX_MATCHER,
                       RUN_REGEX_MATCHER,
                       MET_REGEX_MATCHER,
                       SAMPLE_REGEX_MATCHER]

        for matcher in sieve_match:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _parse_command_response(self, response, prompt):
        """
        Instrument will send an 'unrecognized command' response if
        an error occurred while sending a command.
        Raise an exception if this occurs.
        """
        log.debug("%% IN _parse_command_response RESPONSE = %r", response)

        if 'unrecognized command' in response:
            log.debug('command was not recognized')
            raise InstrumentCommandException('unrecognized command')

        return response

    def _parse_run_wiper_response(self, response, prompt):
        """
        After running wiper command, the instrument will send an 'unrecognized command' if the command
        was not received correctly.  Instrument will send a 'mvs 0' if the wiper does not complete
        its action.  Raise an exception if either occurs.
        """
        log.debug("%% IN _parse_run_wiper_response RESPONSE = %r", response)

        if 'unrecognized command' in response:
            log.debug('command was not recognized')
            raise InstrumentCommandException('unrecognized command')

        if '0' in response:
            log.debug('wiper was not successful')
            raise InstrumentCommandException('run wiper was not successful')

        return response

    def _parse_metadata_response(self, response, prompt):
        match = MET_REGEX_MATCHER.search(response)

        if not match:
            raise SampleException("No regex match of metadata data: [%r]" %
                                  response)

        try:
            sig_1_data = match.group(1)
            data = sig_1_data.split(',')
            FlortDSample_Particle.sig_1_offset = int(data[5])
            FlortDSample_Particle.sig_1_scale = float(data[4])

            sig_2_data = match.group(2)
            data = sig_2_data.split(',')
            FlortDSample_Particle.sig_2_offset = int(data[5])
            FlortDSample_Particle.sig_2_scale = float(data[4])

            sig_3_data = match.group(3)
            data = sig_3_data.split(',')
            FlortDSample_Particle.sig_3_offset = int(data[5])
            FlortDSample_Particle.sig_3_scale = float(data[4])
        except Exception:
            raise SampleException('Error parsing particle FlortDMET_Particle')

        return response


    ########################################################################
    # Unknown handlers.
    ########################################################################
    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Entering Unknown state
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exiting Unknown state
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        next_state = None
        next_agent_state = None

        try:
            #Listen to data stream to determine the current state
            response = self._get_response(timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)[0]
            log.debug('_handler_unknown_discover: response: [%r]', response)

            if FlortDSample_Particle.regex_compiled().search(response):
                next_state = DriverProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
            else:
                next_state = DriverProtocolState.COMMAND
                next_agent_state = ResourceAgentState.IDLE

        except InstrumentTimeoutException:
            #if an exception is caught, the response timed out looking for a SAMPLE in the buffer
            #if there are no samples in the buffer, than we are likely in command mode
            next_state = DriverProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        finally:
            return next_state, next_agent_state

    ########################################################################
    # Command handlers.
    ########################################################################ƒ
    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state. Update the param dictionary.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        self._init_params()

        # Issue command to driver to get menu with parameter values
        log.debug("Run configure command: %s" % InstrumentCommand.PRINT_MENU)
        response = self._do_cmd_resp(InstrumentCommand.PRINT_MENU, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)
        self._param_dict.update(response)
        log.debug("configure command response: %s" % response)

        #get the metadata once from the instrument
        self._do_cmd_resp(InstrumentCommand.PRINT_METADATA, timeout=TIMEOUT, response_regex=MET_REGEX_MATCHER)

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get commands
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set commands
        """
        try:
            params = args[0]
            log.debug('Params = %s', params)
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            startup = False
            log.debug("NO STARTUP VALUE")
            pass

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            self._set_params(params, startup)

        return None, None

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Get one sample from the instrument
        """
        self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)
        result = self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, *args, timeout=TIMEOUT,
                                   response_regex=MNU_REGEX_MATCHER)

        return None, (None, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode. ($run)
        """
        result = self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Run the $mnu Command (print menu)
        """
        result = self._do_cmd_resp(InstrumentCommand.PRINT_MENU, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)
        return None, (None, result)

    def _handler_command_run_wiper(self, *args, **kwargs):
        """
        Issue the run wiper command ($mvs)
        """
        result = self._do_cmd_resp(InstrumentCommand.RUN_WIPER, *args, timeout=TIMEOUT, response_regex=RUN_REGEX_MATCHER)
        return None, (None, result)

    def _handler_command_init_params(self, *args, **kwargs):
        """
        Initialize parameters
        """
        self._init_params()
        return None, None

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        Synchronize the clock
        """
        self._sync_clock()
        return None, (None, None)

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def stop_scheduled_job(self, schedule_job):
        """
        Remove the scheduled job
        """
        log.debug("Attempting to remove the scheduler")
        if self._scheduler is not None:
            try:
                self._remove_scheduler(schedule_job)
                log.debug("successfully removed scheduler")
            except KeyError:
                log.debug("_remove_scheduler could not find %s", schedule_job)

    def start_scheduled_job(self, param, schedule_job, protocol_event):
        """
        Add a scheduled job
        """
        interval = self._param_dict.get(param).split(':')
        hours = interval[0]
        minutes = interval[1]
        seconds = interval[2]
        log.debug("Setting scheduled interval to: %s %s %s", hours, minutes, seconds)

        config = {DriverConfigKey.SCHEDULER: {
            schedule_job: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.HOURS: int(hours),
                    DriverSchedulerConfigKey.MINUTES: int(minutes),
                    DriverSchedulerConfigKey.SECONDS: int(seconds)
                }
            }
        }
        }
        self.set_init_params(config)
        self._add_scheduler_event(schedule_job, protocol_event)

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state. configure and start the scheduled run wiper
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, *args, timeout=TIMEOUT,
                                   response_regex=MNU_REGEX_MATCHER)

        self._init_params()

        self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, *args, timeout=TIMEOUT,
                                   response_regex=SAMPLE_REGEX_MATCHER)

        #Start scheduling for running the wiper and syncing the clock
        log.debug("Configuring the scheduler to run wiper %s", self._param_dict.get(Parameter.RUN_WIPER_INTERVAL))
        if self._param_dict.get(Parameter.RUN_WIPER_INTERVAL) != '00:00:00':
            self.start_scheduled_job(Parameter.RUN_WIPER_INTERVAL, ScheduledJob.RUN_WIPER, ProtocolEvent.RUN_WIPER_SCHEDULED)

        log.debug("Configuring the scheduler to sync clock %s", self._param_dict.get(Parameter.RUN_CLOCK_SYNC_INTERVAL))
        if self._param_dict.get(Parameter.RUN_CLOCK_SYNC_INTERVAL) != '00:00:00':
            self.start_scheduled_job(Parameter.RUN_CLOCK_SYNC_INTERVAL, ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)

        log.debug("Configuring the scheduler to acquire status %s", self._param_dict.get(Parameter.RUN_ACQUIRE_STATUS_INTERVAL))
        if self._param_dict.get(Parameter.RUN_ACQUIRE_STATUS_INTERVAL) != '00:00:00':
            self.start_scheduled_job(Parameter.RUN_ACQUIRE_STATUS_INTERVAL, ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.SCHEDULED_ACQUIRE_STATUS)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or incorrect prompt received.
        """

        #Stop scheduled run of wiper, clock sync, & acquire status
        self.stop_scheduled_job(ScheduledJob.RUN_WIPER)
        self.stop_scheduled_job(ScheduledJob.CLOCK_SYNC)
        self.stop_scheduled_job(ScheduledJob.ACQUIRE_STATUS)

        # Issue the stop command.
        result = self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, *args, timeout=TIMEOUT,
                                   response_regex=MNU_REGEX_MATCHER)

        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, result)

    def _handler_autosample_run_wiper(self, *args, **kwargs):
        """
        Runs the wiper.  Puts the instrument into command mode, sends the command.  Will try up to 5 times to
        send the command.  If it fails, propogate the error to the operator, and keep instrument in command mode,
        no sense in trying collect samples.  If wiper is run successfully, put instrument back into
        autosample mode.
        """
        max_attempts = 5
        attempt = 0
        wiper_ran = False

        #put instrument into command mode to send run wiper command ($mvs)
        self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, *args, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)

        while (attempt < max_attempts) or wiper_ran == False:
            try:
                log.debug('Sending $mvs command, attempt %s', attempt)
                self._do_cmd_resp(InstrumentCommand.RUN_WIPER, *args, timeout=TIMEOUT, response_regex=RUN_REGEX_MATCHER)
                wiper_ran = True

            except InstrumentCommandException:
                attempt += 1
            finally:
                if attempt == max_attempts:
                    raise InstrumentCommandException('ERROR: Wiper did not make it to the next cycle')

        result = self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)
        return None, (None, result)

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get one sample from the instrument
        """

        #put instrument into command mode to send command ($mvs)
        self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)

        self._do_cmd_no_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)

        result = self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)

        return None, (None, result)

    def _handler_autosample_clock_sync(self, *args, **kwargs):
        """
        Syncs the clock.  Puts the instrument in command mode, synchronizes the clock, then puts the instrument
        back into autosample mode.
        """
        self._do_cmd_resp(InstrumentCommand.INTERRUPT_INSTRUMENT, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)
        self._sync_clock()
        result = self._do_cmd_resp(InstrumentCommand.RUN_SETTINGS, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)
        return None, (None, result)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

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
        Execute Direct Access command(s)
        """

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, None

    def _handler_direct_access_stop_direct(self):
        """
        Stop Direct Access, and put the driver into a healthy state by reverting itself back to the previous
        state before starting Direct Access.
        @throw InstrumentProtocolException on invalid command
        """

        #discover the state to go to next
        next_state, next_agent_state = self._handler_unknown_discover()
        if next_state == DriverProtocolState.COMMAND:
            next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, None)

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    ########################################################################
    # Private helpers.
    ########################################################################
    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        Also called when setting parameters during startup and direct access
        """

        params = args[0]

        # try:
        self._verify_not_readonly(*args, **kwargs)
        old_config = self._param_dict.get_config()

        response = None
        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            #if setting the mvs interval/clock sync interval/acquire status interval, do not send a command
            if key == Parameter.RUN_WIPER_INTERVAL or key == Parameter.RUN_CLOCK_SYNC_INTERVAL or key == Parameter.RUN_ACQUIRE_STATUS_INTERVAL:
                self._param_dict.set_value(key, val)
                log.debug('set value %s vs %s', val, self._param_dict.get(key))
            #else if setting the clock or date, run clock sync command
            elif key == Parameter.TIME or key == Parameter.DATE:
                self._sync_clock()
            #else perform regular command
            else:
                response = self._do_cmd_resp(InstrumentCommand.SET, key, val, response_regex=MNU_REGEX_MATCHER)

        self._param_dict.update(response)
        log.debug("configure command response: %r", response)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s", new_config, old_config)
        if not dict_equal(old_config, new_config, ignore_keys=Parameter.TIME):
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _build_single_parameter_command(self, cmd, param, val):
        """
        Build handler for set commands. param val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or if the formatting function could not
                                            accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            if str_val is None:
                raise InstrumentParameterException("Driver PARAM was None!!!!")

            #do extra formatting if one of these commands
            if param == 'clk':
                str_val = str_val.replace(":", "")
            if param == 'dat':
                str_val = str_val.replace("/", "")

            set_cmd = '%s %s' % (param, str_val)
            set_cmd += NEWLINE
            set_cmd = '$' + set_cmd
            log.debug("set_cmd = " + repr(set_cmd))
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _build_no_eol_command(self, cmd):
        """
        Build handler for commands issued without eol. Primarily for the instrument interrupt command.
        """
        return cmd

    def _build_simple_command(self, cmd, *args):
        """
        Build handler for basic commands.
        @param cmd the simple  command to format.
        @retval The command to be sent to the device.
        """
        return cmd + NEWLINE

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if self._extract_sample(FlortDMNU_Particle, MNU_REGEX_MATCHER, chunk, timestamp):
            return
        if self._extract_sample(FlortDSample_Particle, SAMPLE_REGEX_MATCHER, chunk, timestamp):
            return

    def _wakeup(self, timeout, delay=1):
        """
        Override method: There is no wakeup for this instrument
        """
        pass

    def _sync_clock(self, time_format="%m%d%y %H:%M:%S"):
        """
        Send the command to the instrument to synchronize the clock
        @param time_format: time format string for set command
        @raise: InstrumentProtocolException if command fails
        """
        #clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        str_val = get_timestamp_delayed(time_format).split(" ")
        date_val = str_val[0]
        clock_val = str_val[1]

        log.debug("Setting the clock to %s %s", clock_val, date_val)
        self._do_cmd_resp(InstrumentCommand.SET, Parameter.TIME, clock_val, timeout=TIMEOUT,
                          response_regex=MNU_REGEX_MATCHER)
        self._do_cmd_resp(InstrumentCommand.SET, Parameter.DATE, date_val, timout=TIMEOUT,
                          response_regex=MNU_REGEX_MATCHER)

    @staticmethod
    def _float_to_string(v):
        """
        Override base class method because it returns an exponential formatted float and that is not what is needed here
        Write a float value to string formatted for set operations.
        @param v A float val.
        @retval a float string formatted for set operations.
        @throws InstrumentParameterException if value is not a float.
        """
        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return str(v)

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands
        """
        self._cmd_dict.add(Capability.RUN_WIPER, display_name="run wiper")
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name='sync clock')
        self._cmd_dict.add(Capability.ACQUIRE_SAMPLE, display_name='acquire sample')
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name='start autosample')
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name='stop autosample')
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name='acquire status')

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters. For each parameter key, add match string, match lambda
        function, and value formatting function for set commands.
        """

        # StatusData
        self._param_dict.add(Parameter.SERIAL_NUM,
                             FlortDMNU_Particle.LINE01,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Serial Number",
                             description='Instrument serial number',
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.FIRMWARE_VERSION,
                             FlortDMNU_Particle.LINE02,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Firmware Version",
                             description='Firmware version',
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENTS_PER_REPORTED,
                             FlortDMNU_Particle.LINE03,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="Measurements per Reported Value",
                             description='Number of measurements for each reported value.',
                             default_value=1,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.MEASUREMENTS_PER_PACKET,
                             FlortDMNU_Particle.LINE04,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Measurements per Packet",
                             description='Number of individual measurements in each packet. 0 is continuous operation.',
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.MEASUREMENT_1_DARK_COUNT,
                             FlortDMNU_Particle.LINE05,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 1 Dark Count",
                             description='Measurement 1 dark count value for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.COUNTS,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENT_2_DARK_COUNT,
                             FlortDMNU_Particle.LINE06,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 2 Dark Count",
                             description='Measurement 2 dark count value for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.COUNTS,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENT_3_DARK_COUNT,
                             FlortDMNU_Particle.LINE07,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 3 Dark Count",
                             description='Measurement 3 dark count value for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.COUNTS,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENT_1_SLOPE,
                             FlortDMNU_Particle.LINE08,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 1 Slope Value",
                             description='Measurement 1 slope value used for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.PART_PER_METER_STERADIAN,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENT_2_SLOPE,
                             FlortDMNU_Particle.LINE09,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 2 Slope Value",
                             description='Measurement 2 slope value used for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.MICROGRAMS_PER_LITER,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.MEASUREMENT_3_SLOPE,
                             FlortDMNU_Particle.LINE10,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Measurement 3 Slope Value",
                             description='Measurement 3 slope value used for calculating engineering unit output.',
                             default_value=None,
                             units=ParameterUnit.PARTS_PER_MILLION,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.PREDEFINED_OUTPUT_SEQ,
                             FlortDMNU_Particle.LINE11,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Predefined Output Sequence",
                             description='Indicates which pre-defined output sequences to use when outputting data.',
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.BAUD_RATE,
                             FlortDMNU_Particle.LINE12,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Baud Rate",
                             description='Baud rate for instrument communications.',
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.PACKETS_PER_SET,
                             FlortDMNU_Particle.LINE13,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Recording Mode",
                             description='Number of packets in a set. 0 results in the stored configuration repeating continuously.',
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.RECORDING_MODE,
                             FlortDMNU_Particle.LINE14,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Packets per Set",
                             description='Enables (1) or disables (0) data recording to internal memory.',
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.MANUAL_MODE,
                             FlortDMNU_Particle.LINE15,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Manual Mode",
                             description='Enables (1) or disables (0) manual start time.',
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.SAMPLING_INTERVAL,
                             FlortDMNU_Particle.LINE16,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Time Interval Between Packets",
                             default_value=None,
                             description='Time from the start of one packet to the start of the next packet in a set.',
                             units=ParameterUnit.TIME_INTERVAL,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.DATE,
                             FlortDMNU_Particle.LINE17,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Date",
                             description='Date in the Real Time Clock.',
                             default_value=None,
                             units=ParameterUnit.DATE_INTERVAL,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.TIME,
                             FlortDMNU_Particle.LINE18,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Time",
                             description='Time in the Real Time Clock.',
                             default_value=None,
                             startup_param=False,
                             units=ParameterUnit.TIME_INTERVAL,
                             direct_access=False)

        self._param_dict.add(Parameter.MANUAL_START_TIME,
                             FlortDMNU_Particle.LINE19,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Manual Start Time",
                             default_value=None,
                             units=ParameterUnit.TIME_INTERVAL,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.INTERNAL_MEMORY,
                             FlortDMNU_Particle.LINE20,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Internal Memory Size",
                             description='Amount of internal memory.',
                             default_value=None,
                             startup_param=False,
                             direct_access=False)
        ########################
        # Engineering Parameters
        ########################
        self._param_dict.add(Parameter.RUN_WIPER_INTERVAL,
                             TIME_INTERVAL,
                             lambda match: match.group(0),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Run Wiper Interval",
                             default_value='00:00:00',
                             description='Time interval for running the wiper command.',
                             units=ParameterUnit.TIME_INTERVAL,
                             startup_param=True,
                             direct_access=False)

        self._param_dict.add(Parameter.RUN_CLOCK_SYNC_INTERVAL,
                             TIME_INTERVAL,
                             lambda match: match.group(0),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Run Clock Sync Interval",
                             description='Time interval for running clock sync.',
                             default_value='00:00:00',
                             units=ParameterUnit.TIME_INTERVAL,
                             startup_param=True,
                             direct_access=False)

        self._param_dict.add(Parameter.RUN_ACQUIRE_STATUS_INTERVAL,
                             TIME_INTERVAL,
                             lambda match: match.group(0),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="Acquire Status Interval",
                             description='Time interval for running acquiring status.',
                             default_value='00:00:00',
                             units=ParameterUnit.TIME_INTERVAL,
                             startup_param=True,
                             direct_access=False)
################################ /Protocol #############################