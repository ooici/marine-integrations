"""
@package mi.instrument.wetlabs.fluorometer.flort_d.driver
@file marine-integrations/mi/instrument/wetlabs/fluorometer/flort_d/driver.py
@author Art Teranishi
@brief Driver for the flort_d
Release notes:

Initial development
"""

__author__ = 'Art Teranishi'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum

from mi.core.util import dict_equal

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
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


# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

###
#    Driver Constant Definitions
###


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    FlortD_MNU = 'flortd_mnu'
    FlortD_RUN = 'flortd_run'
    FlortD_MET = 'flortd_met'
    FlortD_DUMP_MEMORY = 'flortd_dump_memory'
    FlortD_SAMPLE = 'flortd_sample'


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
    GET_MENU = 'PROTOCOL_EVENT_GET_MENU'
    GET_METADATA = 'PROTOCOL_EVENT_GET_METADATA'
    RUN_WIPER = 'PROTOCOL_EVENT_RUN_WIPER'
    RUN_WIPER_SCHEDULED = 'PROTOCOL_EVENT_RUN_WIPER_SCHEDULED'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    RUN_WIPER = ProtocolEvent.RUN_WIPER


class Parameter(DriverParameter):
    #Device specific parameters.
    Measurements_per_reported_value = "ave"     # Measurements per reported value   # int
    Measurement_1_dark_count_value = "m1d"      # Measurement 1 dark count          # int
    Measurement_1_slope_value = "m1s"           # Measurement 1 slope value         # float
    Measurement_2_dark_count_value = "m2d"      # Measurement 2 dark count          # int
    Measurement_2_slope_value = "m2s"           # Measurement 2 slope value         # float
    Measurement_3_dark_count_value = "m3d"      # Measurement 3 dark count          # int
    Measurement_3_slope_value = "m3s"           # Measurement 3 slope value         # float
    Measurements_per_packet_value = "pkt"       # Measurements per packet           # int
    Baud_rate_value = "rat"                     # Baud rate                         # int
    Packets_per_set_value = "set"               # Packets per set                   # int
    Predefined_output_sequence_value = "seq"    # Predefined output sequence        # int
    Recording_mode_value = "rec"                # Recording mode                    # int
    Manual_mode_value = "man"                   # Manual mode                       # int
    Sampling_interval_value = "int"             # Sampling interval                 # str
    Date_value = "dat"                          # Date                              # str
    Time_value = "clk"                          # Time                              # str
    Manual_start_time_value = "mst"             # Manual start time                 # str

    #Hardware Data
    Serial_number_value = "ser"                 # Serial number                     # str
    Firmware_version_value = "ver"              # Firmware version                  # str
    Internal_memory_value = "mem"               # Internal memory                   # int

    #Command parameter
    Run_wiper_interval = "mvs"


class ScheduledJob(BaseEnum):
    RUN_WIPER = 'run_wiper'


class Prompt(BaseEnum):
    """
    Device I/O prompts.
    FLORT-D does not have a prompt.
    """


class InstrumentCommand(BaseEnum):
    # Instrument command strings
    Interrupt_instrument = "!!!!!"
    Print_metadata = "$met"
    Print_menu = "$mnu"
    Run_settings = "$run"
    Run_wiper = "$mvs"

    # Parameter Commands - sent at startup
    Averaging_value = "$ave"
    Measurement_1_dark_count = "$m1d"
    Measurement_1_slope = "$m1s"
    Measurement_2_dark_count = "$m2d"
    Measurement_2_slope = "$m2s"
    Measurement_3_dark_count = "$m3d"
    Measurement_3_slope = "$m3s"
    Packet_size = "$pkt"
    Select_predefined_output_sequence = "$seq"
    Set_clock = "$clk"
    Set_date = "$dat"
    Recording_mode = "$rec"
    Set_size = "$set"

    def from_string(self, str):
        instrument_cmd_dict = {
            "ave": InstrumentCommand.Averaging_value,
            "m1d": InstrumentCommand.Measurement_1_dark_count,
            "m2d": InstrumentCommand.Measurement_2_dark_count,
            "m3d": InstrumentCommand.Measurement_3_dark_count,
            "m1s": InstrumentCommand.Measurement_1_slope,
            "m2s": InstrumentCommand.Measurement_2_slope,
            "m3s": InstrumentCommand.Measurement_3_slope,
            "pkt": InstrumentCommand.Packet_size,
            "seq": InstrumentCommand.Select_predefined_output_sequence,
            "clk": InstrumentCommand.Set_clock,
            "dat": InstrumentCommand.Set_date,
            "rec": InstrumentCommand.Recording_mode,
            "set": InstrumentCommand.Set_size,
            "mvs": InstrumentCommand.Run_wiper
        }
        return instrument_cmd_dict.get(str)


###############################################################################
# Data Particles
###############################################################################

MNU_REGEX = r"(Ser.*?Mem\s[0-9]{1,6})"
MNU_REGEX_MATCHER = re.compile(MNU_REGEX, re.DOTALL)

RUN_REGEX = r"(mvs\s[0-1]\r\n)"
RUN_REGEX_MATCHER = re.compile(RUN_REGEX, re.DOTALL)

MET_REGEX = r"(0,.*?IOM=[0-9])"
MET_REGEX_MATCHER = re.compile(MET_REGEX, re.DOTALL)

SAMPLE_REGEX = r"([0-1][0-9]/[0-3][0-9]/[0-9][0-9]\s[0-1][0-9]:[0-5][0-9]:[0-5][0-9](\s[0-9]{1,10}){7}\r\n)"
SAMPLE_REGEX_MATCHER = re.compile(SAMPLE_REGEX, re.DOTALL)


class FlortDMNU_ParticleKey(BaseEnum):
    Serial_number = "serial_number"
    Firmware_version = "firmware_version"
    Ave = "number_measurements_per_reported_value"
    Pkt = "number_of_reported_values_per_packet"
    M1d = "measurement_1_dark_count_value"
    M2d = "measurement_2_dark_count_value"
    M3d = "measurement_3_dark_count_value"
    M1s = "measurement_1_slope_value"
    M2s = "measurement_2_slope_value"
    M3s = "measurement_3_slope_value"
    Seq = "predefined_output_sequence"
    Rat = "baud_rate"
    Set = "number_of_packets_per_set"
    Rec = "recording_mode"
    Man = "manual_mode"
    Int = "sampling_interval"
    Dat = "date"
    Clk = "clock"
    Mst = "manual_start_time"
    Mem = "internal_memory"


class FlortDMNU_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest comes along for free.
    """
    _data_particle_type = DataParticleType.FlortD_MNU

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
        # Initialize
        single_var_matches = {
            FlortDMNU_ParticleKey.Serial_number: None,
            FlortDMNU_ParticleKey.Firmware_version: None,
            FlortDMNU_ParticleKey.Ave: None,
            FlortDMNU_ParticleKey.Pkt: None,
            FlortDMNU_ParticleKey.M1d: None,
            FlortDMNU_ParticleKey.M2d: None,
            FlortDMNU_ParticleKey.M3d: None,
            FlortDMNU_ParticleKey.M1s: None,
            FlortDMNU_ParticleKey.M2s: None,
            FlortDMNU_ParticleKey.M3s: None,
            FlortDMNU_ParticleKey.Seq: None,
            FlortDMNU_ParticleKey.Rat: None,
            FlortDMNU_ParticleKey.Set: None,
            FlortDMNU_ParticleKey.Rec: None,
            FlortDMNU_ParticleKey.Man: None,
            FlortDMNU_ParticleKey.Int: None,
            FlortDMNU_ParticleKey.Dat: None,
            FlortDMNU_ParticleKey.Clk: None,
            FlortDMNU_ParticleKey.Mst: None,
            FlortDMNU_ParticleKey.Mem: None
        }

        multi_var_matchers = {
            re.compile(self.LINE01, re.DOTALL): [
                FlortDMNU_ParticleKey.Serial_number,
            ],
            re.compile(self.LINE02, re.DOTALL): [
                FlortDMNU_ParticleKey.Firmware_version
            ],
            re.compile(self.LINE03, re.DOTALL): [
                FlortDMNU_ParticleKey.Ave
            ],
            re.compile(self.LINE04, re.DOTALL): [
                FlortDMNU_ParticleKey.Pkt
            ],
            re.compile(self.LINE05, re.DOTALL): [
                FlortDMNU_ParticleKey.M1d
            ],
            re.compile(self.LINE06, re.DOTALL): [
                FlortDMNU_ParticleKey.M2d
            ],
            re.compile(self.LINE07, re.DOTALL): [
                FlortDMNU_ParticleKey.M3d
            ],
            re.compile(self.LINE08, re.DOTALL): [
                FlortDMNU_ParticleKey.M1s,
            ],
            re.compile(self.LINE09, re.DOTALL): [
                FlortDMNU_ParticleKey.M2s
            ],
            re.compile(self.LINE10, re.DOTALL): [
                FlortDMNU_ParticleKey.M3s
            ],
            re.compile(self.LINE11, re.DOTALL): [
                FlortDMNU_ParticleKey.Seq,
            ],
            re.compile(self.LINE12, re.DOTALL): [
                FlortDMNU_ParticleKey.Rat
            ],
            re.compile(self.LINE13, re.DOTALL): [
                FlortDMNU_ParticleKey.Set
            ],
            re.compile(self.LINE14, re.DOTALL): [
                FlortDMNU_ParticleKey.Rec
            ],
            re.compile(self.LINE15, re.DOTALL): [
                FlortDMNU_ParticleKey.Man
            ],
            re.compile(self.LINE16, re.DOTALL): [
                FlortDMNU_ParticleKey.Int
            ],
            re.compile(self.LINE17, re.DOTALL): [
                FlortDMNU_ParticleKey.Dat
            ],
            re.compile(self.LINE18, re.DOTALL): [
                FlortDMNU_ParticleKey.Clk,
            ],
            re.compile(self.LINE19, re.DOTALL): [
                FlortDMNU_ParticleKey.Mst
            ],
            re.compile(self.LINE20, re.DOTALL): [
                FlortDMNU_ParticleKey.Mem
            ]
        }

        linecount = 0

        for line in self.raw_data.split(NEWLINE):
            linecount += 1

            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index += 1
                        log.debug('_build_parsed_values -- line: %r, matcher: %r', line, matcher.pattern)
                        val = line.split(' ')[1]
                        # str
                        if key in [
                            FlortDMNU_ParticleKey.Serial_number,
                            FlortDMNU_ParticleKey.Firmware_version
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            FlortDMNU_ParticleKey.Ave,
                            FlortDMNU_ParticleKey.Pkt,
                            FlortDMNU_ParticleKey.M1d,
                            FlortDMNU_ParticleKey.M2d,
                            FlortDMNU_ParticleKey.M3d,
                            FlortDMNU_ParticleKey.Seq,
                            FlortDMNU_ParticleKey.Rat,
                            FlortDMNU_ParticleKey.Set,
                            FlortDMNU_ParticleKey.Rec,
                            FlortDMNU_ParticleKey.Man,
                            FlortDMNU_ParticleKey.Mem
                        ]:
                            single_var_matches[key] = int(val)

                        #float
                        elif key in [
                            FlortDMNU_ParticleKey.M1s,
                            FlortDMNU_ParticleKey.M2s,
                            FlortDMNU_ParticleKey.M3s
                        ]:
                            single_var_matches[key] = float(val)

                        # date
                        elif key in [
                            FlortDMNU_ParticleKey.Dat
                        ]:
                            # mm/dd/yy
                            single_var_matches[key] = val

                        # time
                        elif key in [
                            FlortDMNU_ParticleKey.Int,
                            FlortDMNU_ParticleKey.Clk,
                            FlortDMNU_ParticleKey.Mst
                        ]:
                            # hh:mm:ss
                            single_var_matches[key] = val

                        else:
                            raise SampleException("Unknown variable type in FlortDMNU_Particle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result


class FlortDMET_ParticleKey(BaseEnum):
    Column_delimiter = "column_delimiter"
    Column_01_descriptor = "column_01_descriptor"
    Column_02_descriptor = "column_02_descriptor"
    Column_03_descriptor = "column_03_descriptor"
    Column_04_descriptor = "column_04_descriptor"
    Column_05_descriptor = "column_05_descriptor"
    Column_06_descriptor = "column_06_descriptor"
    Column_07_descriptor = "column_07_descriptor"
    Column_08_descriptor = "column_08_descriptor"
    Column_09_descriptor = "column_09_descriptor"
    Column_10_descriptor = "column_10_descriptor"
    IHM = "IHM"
    IOM = "IOM"


class FlortDMET_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FlortD_MET

    LINE00 = r"0,\S*"
    LINE01 = r"1,\S*"
    LINE02 = r"2,\S*"
    LINE03 = r"3,\S*"
    LINE04 = r"4,\S*"
    LINE05 = r"5,\S*"
    LINE06 = r"6,\S*"
    LINE07 = r"7,\S*"
    LINE08 = r"8,\S*"
    LINE09 = r"9,\S*"
    LINE10 = r"10,\S*"
    LINE11 = r"IHM=\S*"
    LINE12 = r"IOM=\S*"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags
        @throws SampleException If there is a problem with sample creation
        """
        log.debug("%% IN FlortDMET_Particle:_build_parsed_values")
        # Initialize
        single_var_matches = {
            FlortDMET_ParticleKey.Column_delimiter: None,
            FlortDMET_ParticleKey.Column_01_descriptor: None,
            FlortDMET_ParticleKey.Column_02_descriptor: None,
            FlortDMET_ParticleKey.Column_03_descriptor: None,
            FlortDMET_ParticleKey.Column_04_descriptor: None,
            FlortDMET_ParticleKey.Column_05_descriptor: None,
            FlortDMET_ParticleKey.Column_06_descriptor: None,
            FlortDMET_ParticleKey.Column_07_descriptor: None,
            FlortDMET_ParticleKey.Column_08_descriptor: None,
            FlortDMET_ParticleKey.Column_09_descriptor: None,
            FlortDMET_ParticleKey.Column_10_descriptor: None,
            FlortDMET_ParticleKey.IHM: None,
            FlortDMET_ParticleKey.IOM: None
        }

        multi_var_matchers = {
            re.compile(self.LINE00, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_delimiter,
            ],
            re.compile(self.LINE01, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_01_descriptor,
            ],
            re.compile(self.LINE02, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_02_descriptor
            ],
            re.compile(self.LINE03, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_03_descriptor
            ],
            re.compile(self.LINE04, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_04_descriptor
            ],
            re.compile(self.LINE05, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_05_descriptor
            ],
            re.compile(self.LINE06, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_06_descriptor
            ],
            re.compile(self.LINE07, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_07_descriptor
            ],
            re.compile(self.LINE08, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_08_descriptor,
            ],
            re.compile(self.LINE09, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_09_descriptor
            ],
            re.compile(self.LINE10, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.Column_10_descriptor
            ],
            re.compile(self.LINE11, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.IHM,
            ],
            re.compile(self.LINE12, re.DOTALL | re.MULTILINE): [
                FlortDMET_ParticleKey.IOM
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index += 1
                        val = line.rstrip('\r\n').lstrip('\r\n')

                        # str
                        if key in [
                            FlortDMET_ParticleKey.Column_delimiter,
                            FlortDMET_ParticleKey.Column_01_descriptor,
                            FlortDMET_ParticleKey.Column_02_descriptor,
                            FlortDMET_ParticleKey.Column_03_descriptor,
                            FlortDMET_ParticleKey.Column_04_descriptor,
                            FlortDMET_ParticleKey.Column_05_descriptor,
                            FlortDMET_ParticleKey.Column_06_descriptor,
                            FlortDMET_ParticleKey.Column_07_descriptor,
                            FlortDMET_ParticleKey.Column_08_descriptor,
                            FlortDMET_ParticleKey.Column_09_descriptor,
                            FlortDMET_ParticleKey.Column_10_descriptor
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            FlortDMET_ParticleKey.IHM,
                            FlortDMET_ParticleKey.IOM
                        ]:
                            val = line.split('=')[1]
                            single_var_matches[key] = int(val)

                        else:
                            raise SampleException("Unknown variable type in FlortDMET_Particle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result


class FlortDRUN_ParticleKey(BaseEnum):
    MVS = "mvs"


class FlortDRUN_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest comes along for free.
    """
    _data_particle_type = DataParticleType.FlortD_RUN

    LINE1 = r"mvs (.*?)"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        log.debug("%% IN FLORTDRUN_Particle:_build_parsed_values")
        # Initialize
        single_var_matches = {
            FlortDRUN_ParticleKey.MVS: None
        }

        multi_var_matchers = {
            re.compile(self.LINE1, re.DOTALL): [
                FlortDRUN_ParticleKey.MVS,
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index += 1
                        val = line.split(' ')[1]

                        # int
                        if key in [
                            FlortDRUN_ParticleKey.MVS
                        ]:
                            single_var_matches[key] = int(val)

                        else:
                            raise SampleException("Unknown variable type in FlortDRUN_Particle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result


class FlortDSample_ParticleKey(BaseEnum):
    SAMPLE = "sample"


class FlortDSample_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FlortD_SAMPLE

    LINE1 = SAMPLE_REGEX
    _compiled_regex = None

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
        pattern = [
            SAMPLE_REGEX
        ]
        return r'\s*,\s*'.join(pattern)

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        log.debug("%% IN FLORTDSample_Particle:_build_parsed_values")

        # Initialize
        single_var_matches = {
            FlortDSample_ParticleKey.SAMPLE: None
        }

        multi_var_matchers = {
            re.compile(self.LINE1, re.DOTALL | re.MULTILINE): [
                FlortDSample_ParticleKey.SAMPLE
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index += 1
                        val = line

                        # str
                        if key in [
                            FlortDSample_ParticleKey.SAMPLE
                        ]:
                            single_var_matches[key] = val

                        else:
                            raise SampleException("Unknown variable type in FlortDSample_Particle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result


################################ /Particles ###################################

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

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        log.debug("%% IN Protocol:__init__")
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_MENU, self._handler_command_get_menu)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_METADATA, self._handler_command_get_metadata)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RUN_WIPER, self._handler_command_run_wiper)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.RUN_WIPER_SCHEDULED, self._handler_autosample_run_wiper)

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
        self._add_build_handler(InstrumentCommand.Interrupt_instrument, self._build_no_eol_command)
        self._add_build_handler(InstrumentCommand.Averaging_value, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_1_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_1_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_2_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_2_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_3_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_3_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Select_predefined_output_sequence, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Packet_size, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Set_clock, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Set_date, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Recording_mode, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Set_size, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Run_settings, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Print_metadata, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Print_menu, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Run_wiper, self._build_simple_command)

        #all commands return a 'unrecognized command' if not recognized by the instrument
        self._add_response_handler(InstrumentCommand.Interrupt_instrument, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Averaging_value, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_1_dark_count, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_1_slope, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_2_dark_count, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_2_slope, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_3_dark_count, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Measurement_3_slope, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Select_predefined_output_sequence, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Packet_size, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Set_clock, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Set_date, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Recording_mode, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Set_size, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Run_settings, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Print_metadata, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Print_menu, self._parse_command_response)
        self._add_response_handler(InstrumentCommand.Run_wiper, self._parse_run_wiper_response)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []
        self._chunker = StringChunker(Protocol.sieve_function)

        # State state machine in UNKNOWN state.
        log.debug("%%% Starting in UNKNOWN state")
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        log.debug("%% IN sieve_function")
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
        log.debug("%% IN _filter_capabilities")
        return [x for x in events if Capability.has(x)]

    def _parse_command_response(self, response, prompt):
        log.debug("%% IN _parse_command_response RESPONSE = " + repr(response))
        #instrument will return 'unrecognized command' if command is not valid

        if 'unrecognized command' in response:
            log.debug('command was not recognized')
            raise InstrumentCommandException('unrecognized command')

        return response

    def _parse_run_wiper_response(self, response, prompt):
        log.debug("%% IN _parse_run_wiper_response RESPONSE = " + repr(response))
        #instrument will return 'unrecognized command' if command is not valid

        if 'unrecognized command' in response:
            log.debug('command was not recognized')
            raise InstrumentCommandException('unrecognized command')

        if '0' in response:
            log.debug('wiper was not successful')
            raise InstrumentCommandException('run wiper was not successful')

        return response

    ########################################################################
    # Unknown handlers.
    ########################################################################
    def _handler_unknown_enter(self, *args, **kwargs):

        log.debug("%%% IN _handler_unknown_enter")
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        #Exit unknown state.
        log.debug("%%% IN _handler_unknown_exit")
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        log.debug("%%% IN _handler_unknown_discover")

        next_state = None
        next_agent_state = None
        result = None

        try:
            #Listen to data stream to determine the current state
            response = self._get_response(timeout=1, response_regex=SAMPLE_REGEX_MATCHER)[0]
            log.debug('_handler_unknown_discover: response: [%r]', response)

            if FlortDSample_Particle.regex_compiled().search(response):
                next_state = DriverProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
                result = ProtocolState.AUTOSAMPLE
            else:
                next_state = DriverProtocolState.COMMAND
                next_agent_state = ResourceAgentState.COMMAND
                result = ProtocolState.COMMAND

        except InstrumentTimeoutException:
            #if an exception is caught, the response timed out looking for a SAMPLE in the buffer
            #if there are no samples in the buffer, than we are likely in command mode
            next_state = DriverProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
            result = ProtocolState.COMMAND

        finally:

            log.debug("_handler_unknown_discover. result start: %s" % next_state)
            return next_state, (next_agent_state, result)

    ########################################################################
    # Command handlers.
    ########################################################################
    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        log.debug('%% IN _handler_command_enter')
        # Update the parameter dictionary. Issue display status and display calibration commands. The parameter
        # dict will match line output and update itself.

        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.

        log.debug("Run configure command: %s" % InstrumentCommand.Print_menu)
        response = self._do_cmd_resp(InstrumentCommand.Print_menu, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)
        # for line in response.split(NEWLINE):
        #     self._param_dict.update(line)
        self._param_dict.update(response)
        log.debug("configure command response: %s" % response)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s" % (new_config, old_config))
        if not dict_equal(old_config, new_config, ignore_keys=Parameter.Time_value):
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        log.debug('%% IN _handler_command_get')
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        log.debug('%% IN _handler_command_set')
        startup = False

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
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
        log.debug('%% IN _handler_command_exit')
        pass

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode. ($run)
        """
        log.debug('%% IN _handler_command_start_autosample')
        result = self._do_cmd_resp(InstrumentCommand.Run_settings, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)

        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, result)

    def _handler_command_get_menu(self, *args, **kwargs):
        """
        Run the $mnu Command (print menu)
        """
        log.debug('%% IN _handler_command_get_menu')
        result = self._do_cmd_resp(InstrumentCommand.Print_menu, timeout=TIMEOUT, response_regex=MNU_REGEX_MATCHER)

        return None, (None, result)

    def _handler_command_get_metadata(self, *args, **kwargs):
        """
        Run the $met Command (print meta data)
        """
        log.debug('%% IN _handler_command_get_metadata')
        result = self._do_cmd_resp(InstrumentCommand.Print_metadata, timeout=TIMEOUT, response_regex=MET_REGEX_MATCHER)

        return None, (None, result)

    def _handler_command_run_wiper(self, *args, **kwargs):
        log.debug("%%% IN _handler_command_run_wiper")

        #Issue the run wiper command
        result = self._do_cmd_resp(InstrumentCommand.Run_wiper, *args, timeout=TIMEOUT,
                                   response_regex=RUN_REGEX_MATCHER)
        return None, (None, result)

    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        log.debug('%% IN _handler_command_init_params')
        self._init_params()
        return None, None

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state. configure and start the scheduled run wiper
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        log.debug('%% IN _handler_autosample_enter')

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        log.debug("Configuring the scheduler to run %i", self._param_dict.get(Parameter.Run_wiper_interval))
        if self._param_dict.get(Parameter.Run_wiper_interval) is not 0:

            #start the scheduler for running the wiper
            #job_name = ScheduledJob.RUN_WIPER
            config = { DriverConfigKey.SCHEDULER: {
                ScheduledJob.RUN_WIPER: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.Run_wiper_interval)
                        }
                    }
                }
            }
            log.debug("Initializing the scheduler")
            self.set_init_params(config)
            log.debug("Adding the scheduled event")
            self._add_scheduler_event(ScheduledJob.RUN_WIPER, ProtocolEvent.RUN_WIPER_SCHEDULED)
        else:
            log.debug("Attempting to remove the scheduler")
            if self._scheduler is not None:
                try:
                    log.debug("successfully removed scheduler")
                    self._remove_scheduler(ScheduledJob.RUN_WIPER)
                except KeyError:
                    log.debug("_remove_scheduler could not find ScheduleJob.RUN_WIPER")

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or incorrect prompt received.
        """
        log.debug("%%% IN _handler_autosample_stop_autosample")

        #Stop scheduled run of wiper
        if self._scheduler is not None:
            try:
                log.debug("Removing scheduled job: RUN WIPER")
                self._remove_scheduler(ScheduledJob.RUN_WIPER)
            except KeyError:
                log.debug("_remove_scheduler could not find ScheduleJob.RUN_WIPER")


        # Issue the stop command.
        result = self._do_cmd_resp(InstrumentCommand.Interrupt_instrument, *args, timeout=TIMEOUT,
                                   response_regex=RUN_REGEX_MATCHER)

        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, result)

    def _handler_autosample_run_wiper(self, *args, **kwargs):
        log.debug("%%% IN _handler_autosample_run_wiper")

        max_attempts = 5
        attempt = 0
        wiper_ran = False

        #put instrument into command mode to send run wiper command ($mvs)
        self._do_cmd_resp(InstrumentCommand.Interrupt_instrument, *args, timeout=TIMEOUT,
                               response_regex=MNU_REGEX_MATCHER)

        #try to send $mvs up to 5 times
        #if an error occurred while sending command, try again
        #if sent $mvs max times, then raise an error and do not proceed
        #if $mvs is sent successfully, put the instrument into autosample
        while (attempt < max_attempts) or wiper_ran == False:
            try:
                log.debug('Sending $mvs command, attempt %s', attempt)
                self._do_cmd_resp(InstrumentCommand.Run_wiper, *args, timeout=TIMEOUT,
                               response_regex=RUN_REGEX_MATCHER)
                wiper_ran = True
            except InstrumentCommandException as e:
                attempt += 1
            finally:
                if attempt == max_attempts:
                    raise InstrumentCommandException('ERROR: Wiper did not make it to the next cycle')

        result = self._do_cmd_resp(InstrumentCommand.Run_settings, timeout=TIMEOUT, response_regex=SAMPLE_REGEX_MATCHER)

        return None, (None, result)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        log.debug("%%% IN _handler_autosample_exit")

        #Stop scheduled run of wiper
        if self._scheduler is not None:
            try:
                log.debug("Removing scheduled job: RUN WIPER")
                self._remove_scheduler(ScheduledJob.RUN_WIPER)
            except KeyError:
                log.debug("_remove_scheduler could not find ScheduleJob.RUN_WIPER")
        pass

    def _handler_autosample_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        log.debug('%% IN _handler_autosample_init_params')
        next_state = None
        result = None

        self._init_params()
        return next_state, result

    ########################################################################
    # Direct access handlers.
    ########################################################################
    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        log.debug('%% IN _handler_direct_access_enter')
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        log.debug('%% IN _handler_direct_access_exit')
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        log.debug('%% IN _handler_direct_access_execute_direct')

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        log.debug('%% IN _handler_direct_access_stop_direct')
        return ProtocolState.UNKNOWN, (ResourceAgentState.ACTIVE_UNKNOWN, None)

    def _handler_start_direct(self):
        """
        Start direct access
        """
        log.debug('%% IN _handler_start_direct: entering DA mode')
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see if we need to set the parameters.
        If they are they are set correctly then we don't do anything.
        """
        log.debug('%% IN apply_startup_params')
        log.debug("CURRENT STATE: %s", self.get_current_state())
        if self.get_current_state() != DriverProtocolState.COMMAND:
            raise InstrumentProtocolException("Not in command state. Unable to apply startup params")

        self._set_params(True)

    ########################################################################
    # Private helpers.
    ########################################################################
    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.debug("%% IN _set_params")

        params = args[0]

        try:
            self._verify_not_readonly(*args, **kwargs)
            old_config = self._param_dict.get_config()

            response = None
            for (key, val) in params.iteritems():
                log.debug("KEY = " + str(key) + " VALUE = " + str(val))
                #if setting the mvs interval, do not send a command
                if key == 'mvs':
                    self._param_dict.set_value(key, val)
                else:
                    arg_command = InstrumentCommand.from_string(InstrumentCommand(), key)
                    log.debug('arg_command %s', arg_command)
                    response = self._do_cmd_resp(arg_command, key, val, response_regex=MNU_REGEX_MATCHER)

            self._param_dict.update(response)
            log.debug("configure command response: %s" % response)

            # Get new param dict config. If it differs from the old config,
            # tell driver superclass to publish a config change event.
            new_config = self._param_dict.get_config()
            log.debug("new_config: %s == old_config: %s" % (new_config, old_config))
            if not dict_equal(old_config, new_config, ignore_keys=Parameter.Time_value):
                log.debug("configuration has changed.  Send driver event")
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        except InstrumentParameterException as e:
            log.debug("Attempt to set read only parameter(s) (%s)", params)

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
        log.debug('%% IN _build_single_parameter_command')
        try:
            str_val = self._param_dict.format(param, val)
            if str_val is None:
                raise InstrumentParameterException("Driver PARAM was None!!!!")

            #do extra formatting if one of these commands
            if param == 'clk':
                str_val = str_val.replace(":", "")
            if param == 'dat':
                str_val = str_val.replace("/", "")

            set_cmd = '%s %s' % (cmd, str_val)
            set_cmd += NEWLINE
            log.debug("set_cmd = " + repr(set_cmd))
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _build_no_eol_command(self, cmd):
        """
        Build handler for commands issued without eol. Primarily for the instrument interrupt command.
        """
        log.debug("%%% IN _build_no_eol_command")
        return cmd

    def _build_simple_command(self, cmd, *args):
        """
        Build handler for basic commands.
        @param cmd the simple  command to format.
        @retval The command to be sent to the device.
        """
        log.debug("%%% IN _build_simple_command")
        return cmd + NEWLINE

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        log.debug('%% IN _got_chunk')
        if self._extract_sample(FlortDMNU_Particle, MNU_REGEX_MATCHER, chunk, timestamp):
            return
        if self._extract_sample(FlortDMET_Particle, MET_REGEX_MATCHER, chunk, timestamp):
            return
        if self._extract_sample(FlortDRUN_Particle, RUN_REGEX_MATCHER, chunk, timestamp):
            return
        if self._extract_sample(FlortDSample_Particle, SAMPLE_REGEX_MATCHER, chunk, timestamp):
            return

    def _wakeup(self, timeout, delay=1):
        """
        Override method: There is no wakeup for this instrument
        """
        log.debug('%% IN _wakeup')
        pass

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
        log.debug("%%% IN _build_driver_dict")
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands
        """
        log.debug("%%% IN _build_command_dict")
        self._cmd_dict.add(Capability.RUN_WIPER, display_name="run wiper")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters. For each parameter key, add match string, match lambda
        function, and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        log.debug("%%% IN _build_param_dict")

        #
        # StatusData
        #
        self._param_dict.add(Parameter.Serial_number_value,
                             FlortDMNU_Particle.LINE01,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="serial number",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Firmware_version_value,
                             FlortDMNU_Particle.LINE02,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="firmware version",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurements_per_reported_value,
                             FlortDMNU_Particle.LINE03,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="measurements per reported value",
                             default_value=1,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurements_per_packet_value,
                             FlortDMNU_Particle.LINE04,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="measurements per packet",
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.Measurement_1_dark_count_value,
                             FlortDMNU_Particle.LINE05,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 1 dark count",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurement_2_dark_count_value,
                             FlortDMNU_Particle.LINE06,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 2 dark count",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurement_3_dark_count_value,
                             FlortDMNU_Particle.LINE07,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 3 dark count",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurement_1_slope_value,
                             FlortDMNU_Particle.LINE08,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 1 slope value",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurement_2_slope_value,
                             FlortDMNU_Particle.LINE09,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 2 slope value",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Measurement_3_slope_value,
                             FlortDMNU_Particle.LINE10,
                             lambda match: float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="measurement 3 slope value",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Predefined_output_sequence_value,
                             FlortDMNU_Particle.LINE11,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="predefined output sequence",
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.Baud_rate_value,
                             FlortDMNU_Particle.LINE12,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="baud rate",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Packets_per_set_value,
                             FlortDMNU_Particle.LINE13,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="packets per set",
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.Recording_mode_value,
                             FlortDMNU_Particle.LINE14,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="recording mode",
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.Manual_mode_value,
                             FlortDMNU_Particle.LINE15,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="manual mode",
                             default_value=0,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.Sampling_interval_value,
                             FlortDMNU_Particle.LINE16,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="time interval between packets",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Date_value,
                             FlortDMNU_Particle.LINE17,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="date",
                             default_value=None,
                             startup_param=False,
                             direct_access=True)

        self._param_dict.add(Parameter.Time_value,
                             FlortDMNU_Particle.LINE18,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="time",
                             default_value=None,
                             startup_param=False,
                             direct_access=True)

        self._param_dict.add(Parameter.Manual_start_time_value,
                             FlortDMNU_Particle.LINE19,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="manual start time",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Internal_memory_value,
                             FlortDMNU_Particle.LINE20,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="internal memory size",
                             default_value=None,
                             startup_param=False,
                             direct_access=False)

        self._param_dict.add(Parameter.Run_wiper_interval,
                             RUN_REGEX,
                             lambda match: int(match.group(1)),
                             int,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="run wiper interval",
                             default_value=60,
                             startup_param=True,
                             direct_access=True)

        #need to set the values of the dictionary using set_default
        for param in self._param_dict.get_keys():
            self._param_dict.set_value(param, self._param_dict.get_default_value(param))


################################ /Protocol #############################