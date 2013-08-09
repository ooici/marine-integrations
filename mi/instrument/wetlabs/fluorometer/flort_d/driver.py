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
import string
import time
import binascii

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
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

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.core.instrument.driver_dict import DriverDictKey

# newline.
NEWLINE = '\n'

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
    #TEST = DriverProtocolState.TEST
    #CALIBRATE = DriverProtocolState.CALIBRATE

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
    #ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    #CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    #ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    #INIT_PARAMS = DriverEvent.INIT_PARAMS
    GET_MENU = 'PROTOCOL_EVENT_GET_MENU'
    GET_METADATA = 'PROTOCOL_EVENT_GET_METADATA'
    INTERRUPT_INSTRUMENT = 'PROTOCOL_EVENT_INTERRUPT_INSTRUMENT'

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    #ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    #CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    #ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    GET_MENU = ProtocolEvent.GET_MENU
    GET_METADATA = ProtocolEvent.GET_METADATA
    #INTERRUPT_INSTRUMENT = ProtocolEvent.INTERRUPT_INSTRUMENT

class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    Analog_scaling_value = "Asv"                # "Analog scaling value"  # int
    Measurements_per_reported_value = "Ave"     # "Measurements per reported value"  # int
    Measurement_1_dark_count_value = "M1d"      # "Measurement 1 dark count"  # int
    Measurement_1_slope_value = "M1s"           # "Measurement 1 slope value"  # float
    Measurement_2_dark_count_value = "M2d"      # "Measurement 2 dark count"  # int
    Measurement_2_slope_value = "M2s"           # "Measurement 2 slope value"  # float
    Measurement_3_dark_count_value = "M3d"      # "Measurement 3 dark count"  # int
    Measurement_3_slope_value = "M3s"           # "Measurement 3 slope value"  # float
    Measurements_per_packet_value = "Pkt"       # "Measurements per packet"  # int
    Baud_rate_value = "Rat"                     # "Baud rate"  # int
    Packets_per_set_value = "Set"               # "Packets per set"  # int
    Predefined_output_sequence_value = "Seq"    # "Predefined output sequence"  # int
    Recording_mode_value = "Rec"                # "Recording mode"  # int
    Manual_mode_value = "Man"                   # "Manual mode"  # int
    Sampling_interval_value = "Int"             # "Sampling interval"  # str
    Date_value = "Dat"                          # "Date"  # str
    Time_value = "Clk"                          # "Time"  # str
    Manual_start_time_value = "Mst"             # "Manual start time"  # str

    #
    # Hardware Data
    #

    Serial_number_value = "Ser"                 # "Serial number"  # str
    Firmware_version_value = "Ver"              # "Firmware version"  # str
    Internal_memory_value = "Mem"               # "Internal memory"  # int

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    
    FLORT-D does not have a prompt.
    """
    #Unrecognized_Command = "unrecognized command"
    #End_Of_Memory_Dump = "etx"

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    Interrupt_instrument = "!!!!!"
    Analog_scaling = "$asv"
    Averaging_value = "$ave"
    Measurement_1_dark_count = "$m1d"
    Measurement_1_slope = "$m1s"
    Measurement_2_dark_count = "$m2d"
    Measurement_2_slope = "$m2s"
    Measurement_3_dark_count = "$m3d"
    Measurement_3_slope = "$m3s"
    Print_metadata = "$met"
    Print_menu = "$mnu"
    Packet_size = "$pkt"
    Baud_rate = "$rat"
    Reload_factory_settings = "$rfd"
    Reload_settings_from_flash = "$rls"
    Run_settings = "$run"
    Select_predefined_output_sequence = "$seq"
    Store_settings_to_flash = "$sto"
    Set_clock = "$clk"
    Set_date = "$dat"
    Erase_memory = "$emc"
    Dump_memory = "$get"
    Sampling_interval = "$int"
    Manual_mode = "$man"
    Manual_start_time = "$mst"
    Recording_mode = "$rec"
    Set_size = "$set"

###############################################################################
# Data Particles
###############################################################################

#MNU_REGEX = r"(Ser.*?Mem.*?\S+)"
MNU_REGEX = r"(Ser.*?Mem [0-9]{1,6}\n)"
MNU_REGEX_MATCHER = re.compile(MNU_REGEX, re.DOTALL)

#RUN_REGEX = r"(mvs.*?\S+)"
RUN_REGEX = r"(mvs [0-9])"
RUN_REGEX_MATCHER = re.compile(RUN_REGEX, re.DOTALL)

#MET_REGEX = r"(0,.*?IOM=.)"
MET_REGEX = r"(0,.*?IOM=[0-9]\n)"
MET_REGEX_MATCHER = re.compile(MET_REGEX, re.DOTALL)

DUMP_MEMORY_REGEX = r"([0-9]{1,10} records to read\n)"  # '77222 records to read'
DUMP_MEMORY_REGEX_MATCHER = re.compile(DUMP_MEMORY_REGEX, re.DOTALL)

#SAMPLE_REGEX = r"(^[0-1][0-9]/.*?$\n)"
SAMPLE_REGEX = r"([0-1][0-9]/[0-3][0-9]/[0-1][0-9]\t[0-1][0-9]:[0-5][0-9]:[0-5][0-9](\t[0-9]{1,10}){7}\n)"
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
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FlortD_MNU

    LINE01 = r"Ser .*?"
    LINE02 = r"Ver .*?"
    LINE03 = r"Ave .*?"
    LINE04 = r"Pkt .*?"
    LINE05 = r"M1d .*?"
    LINE06 = r"M2d .*?"
    LINE07 = r"M3d .*?"
    LINE08 = r"M1s .*?"
    LINE09 = r"M2s .*?"
    LINE10 = r"M3s .*?"
    LINE11 = r"Seq .*?"
    LINE12 = r"Rat .*?"
    LINE13 = r"Set .*?"
    LINE14 = r"Rec .*?"
    LINE15 = r"Man .*?"
    LINE16 = r"Int .*?"
    LINE17 = r"Dat .*?"
    LINE18 = r"Clk .*?"
    LINE19 = r"Mst .*?"
    LINE20 = r"Mem .*?"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

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

        for line in self.raw_data.split('\n'):
            linecount = linecount + 1

            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        #val = match.group(index)
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
                            #single_var_matches[key] = time.strptime(val, "%m/%d/%y")
                            single_var_matches[key] = val

                        # time
                        elif key in [
                            FlortDMNU_ParticleKey.Int,
                            FlortDMNU_ParticleKey.Clk,
                            FlortDMNU_ParticleKey.Mst
                        ]:
                            # hh:mm:ss
                            #single_var_matches[key] = time.strptime(val, "%H:%M:%S")
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

    LINE00 = r"0,.*?"
    LINE01 = r"1,.*?"
    LINE02 = r"2,.*?"
    LINE03 = r"3,.*?"
    LINE04 = r"4,.*?"
    LINE05 = r"5,.*?"
    LINE06 = r"6,.*?"
    LINE07 = r"7,.*?"
    LINE08 = r"8,.*?"
    LINE09 = r"9,.*?"
    LINE10 = r"10,.*?"
    LINE11 = r"IHM=.*?"
    LINE12 = r"IOM=.*?"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

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
                        index = index + 1
                        #val = match.group(index)
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
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FlortD_RUN

    LINE1 = r"mvs .*?"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

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
                        index = index + 1
                        #val = match.group(index)
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


class FlortDDUMP_MEMORY_ParticleKey(BaseEnum):
    Get_response = "get_response"


class FlortDDUMP_MEMORY_Particle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.FlortD_DUMP_MEMORY

    #LINE1 = r"[0-9]* records to read.*?\n"
    LINE1 = r"[0-9]{1,10} records"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        # Initialize
        single_var_matches = {
            FlortDDUMP_MEMORY_ParticleKey.Get_response: None
        }

        multi_var_matchers = {
            re.compile(self.LINE1, re.DOTALL | re.MULTILINE): [
                FlortDDUMP_MEMORY_ParticleKey.Get_response,
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        #val = match.group(index)
                        val = line.split(' ')[0]

                        # int
                        if key in [
                            FlortDDUMP_MEMORY_ParticleKey.Get_response
                        ]:
                            single_var_matches[key] = int(val)

                        else:
                            raise SampleException("Unknown variable type in FlortDDUMP_MEMORY_Particle._build_parsed_values")

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

    #LINE1 = r".*?\t.*?\t.*?\t.*?\t.*?\t.*?\t.*?\t.*?\t.*?\n"
    LINE1 = r"[0-1][0-9]/[0-3][0-9]/[0-1][0-9]\t[0-1][0-9]:[0-5][0-9]:[0-5][0-9](\t[0-9]{1,10}){7}"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

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
                        index = index + 1
                        #val = match.group(index)
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
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_MENU, self._handler_command_get_menu)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_METADATA, self._handler_command_get_metadata)
#        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.INIT_PARAMS, self._handler_command_init_params)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.INTERRUPT_INSTRUMENT, self._handler_interrupt_instrument)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.INTERRUPT_INSTRUMENT, self._handler_interrupt_instrument)
#        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.INIT_PARAMS, self._handler_autosample_init_params)

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
        self._add_build_handler(InstrumentCommand.Analog_scaling, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Averaging_value, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_1_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_1_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_2_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_2_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_3_dark_count, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Measurement_3_slope, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Print_metadata, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Print_menu, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Packet_size, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Baud_rate, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Reload_factory_settings, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Reload_settings_from_flash, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Run_settings, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Select_predefined_output_sequence, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Store_settings_to_flash, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Set_clock, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Set_date, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Erase_memory, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Dump_memory, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.Sampling_interval, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Manual_mode, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Manual_start_time, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Recording_mode, self._build_single_parameter_command)
        self._add_build_handler(InstrumentCommand.Set_size, self._build_single_parameter_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.Interrupt_instrument, self._parse_interrupt_response)
        self._add_response_handler(InstrumentCommand.Analog_scaling, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Averaging_value, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_1_dark_count, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_1_slope, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_2_dark_count, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_2_slope, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_3_dark_count, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Measurement_3_slope, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Print_metadata, self._parse_met_response)
        self._add_response_handler(InstrumentCommand.Print_menu, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Packet_size, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Baud_rate, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Reload_factory_settings, self._parse_rfd_response)
        self._add_response_handler(InstrumentCommand.Reload_settings_from_flash, self._parse_rls_response)
        self._add_response_handler(InstrumentCommand.Run_settings, self._parse_run_response)
        self._add_response_handler(InstrumentCommand.Select_predefined_output_sequence, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Store_settings_to_flash, self._parse_sto_response)
        self._add_response_handler(InstrumentCommand.Set_clock, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Set_date, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Erase_memory, self._parse_erase_response)
        self._add_response_handler(InstrumentCommand.Dump_memory, self._parse_get_response)
        self._add_response_handler(InstrumentCommand.Sampling_interval, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Manual_mode, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Manual_start_time, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Recording_mode, self._parse_set_response)
        self._add_response_handler(InstrumentCommand.Set_size, self._parse_set_response)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        sieve_matchers = [ MNU_REGEX_MATCHER,
                           RUN_REGEX_MATCHER,
                           MET_REGEX_MATCHER,
                           DUMP_MEMORY_REGEX_MATCHER,
                           SAMPLE_REGEX_MATCHER ]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        log.debug("_parse_set_response RESPONSE = " + str(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        return response

    def _parse_get_response(self, response, prompt):

        log.debug("IN _parse_get_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_get_response : Set command not recognized: %s' % response)

        return response

    def _parse_interrupt_response(self, response, prompt):

        log.debug("IN _parse_interrupt_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_interrupt_response : Set command not recognized: %s' % response)

        return response

    def _parse_met_response(self, response, prompt):

        log.debug("IN _parse_met_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_met_response : Set command not recognized: %s' % response)

        return response

    def _parse_rfd_response(self, response, prompt):

        log.debug("IN _parse_rfd_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_rfd_response : Set command not recognized: %s' % response)

        return response

    def _parse_rls_response(self, response, prompt):

        log.debug("IN _parse_rls_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_rls_response : Set command not recognized: %s' % response)

        return response

    def _parse_run_response(self, response, prompt):

        log.debug("IN _parse_run_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_run_response : Set command not recognized: %s' % response)

        return response

    def _parse_sto_response(self, response, prompt):

        log.debug("IN _parse_sto_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_sto_response : Set command not recognized: %s' % response)

        return response

    def _parse_erase_response(self, response, prompt):

        log.debug("IN _parse_erase_response RESPONSE = " + repr(response))

        if ('unrecognized command' in response):
            raise InstrumentParameterException('Protocol._parse_erase_response : Set command not recognized: %s' % response)

        return response

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        log.debug("%%% IN _handler_unknown_discover")

        """
        #If we decide to listen for samples to determine the current state...

        (protocol_state, agent_state) =  self._discover()

        if(protocol_state == ProtocolState.COMMAND):
            agent_state = ResourceAgentState.IDLE

        return (protocol_state, agent_state)
        """

        timeout = kwargs.get('timeout', TIMEOUT)
        #result = self._do_cmd_resp(InstrumentCmds.Interrupt_instrument, timeout=timeout)
        result = self._do_cmd_resp(InstrumentCommand.Interrupt_instrument, timeout=timeout, response_regex=RUN_REGEX_MATCHER)
        return (ProtocolState.COMMAND, ResourceAgentState.IDLE)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    #def _handler_command_get(self, *args, **kwargs):
        """
    #    Get parameter
        """
    #    next_state = None
    #    result = None

    #    return (next_state, result)

    #def _handler_command_set(self, *args, **kwargs):
        """
    #    Set parameter
        """
    #    next_state = None
    #    result = None

    #    return (next_state, result)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.  First we set a baseline timestamp
        that all data expirations will be calculated against.  Then we try to get parameter
        value.  If we catch an expired parameter then we will update all parameters and get
        values using the original baseline time that we set at the beginning of this method.
        Assuming our _update_params is updating all parameter values properly then we can
        ensure that all data will be fresh.  Nobody likes stale data!
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @raise InstrumentParameterException if missing or invalid parameter.
        @raise InstrumentParameterExpirationException If we fail to update a parameter
        on the second pass this exception will be raised on expired data
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @param args[1] parameter : startup parameters?
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None
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

        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        """
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.AUTOSAMPLE
        result = None
        log.debug("_handler_command_start_autosample: entering Autosample mode")
        return (next_state, (next_agent_state, result))

    def _handler_command_get_menu(self, *args, **kwargs):
        """
        Run the $mnu Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        #result = self._do_cmd_resp(InstrumentCmds.Print_menu, timeout=timeout)
        result = self._do_cmd_resp(InstrumentCmds.Print_menu, timeout=timeout, response_regex=MNU_REGEX_MATCHER)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_metadata(self, *args, **kwargs):
        """
        Run the $met Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        #result = self._do_cmd_resp(InstrumentCmds.Print_metadata, timeout=timeout)
        result = self._do_cmd_resp(InstrumentCmds.Print_metadata, timeout=timeout, response_regex=MET_REGEX_MATCHER)

        return (next_state, (next_agent_state, result))

    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None

        self._init_params()
        return (next_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        result = self._do_cmd_no_resp(InstrumentCmds.Run_settings, *args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """

        log.debug("%%% IN _handler_autosample_stop_autosample")

        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        #self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        # Issue the stop command.
        #result = self._do_cmd_resp(InstrumentCmds.Interrupt_instrument, *args, **kwargs)
        result = self._do_cmd_resp(InstrumentCmds.Interrupt_instrument, *args, timeout=timeout, response_regex=RUN_REGEX_MATCHER)

        # Prompt device until command prompt is seen.
        #self._wakeup_until(timeout, Prompt.COMMAND)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_interrupt_instrument(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """

        log.debug("%%% IN _handler_instrument_interrupt")

        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        #self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        # Issue the stop command.
        #result = self._do_cmd_resp(InstrumentCmds.Interrupt_instrument, *args, **kwargs)
        result = self._do_cmd_resp(InstrumentCmds.Interrupt_instrument, *args, timeout=timeout, response_regex=RUN_REGEX_MATCHER)

        # Prompt device until command prompt is seen.
        #self._wakeup_until(timeout, Prompt.COMMAND)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """

        log.debug("%%% IN _handler_autosample_exit")

        pass

    def _handler_autosample_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None

        self._init_params()
        return (next_state, result)

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
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to be in command mode.
        """
        # Let's give it a try in unknown state
        log.debug("CURRENT STATE: %s", self.get_current_state())
        if (self.get_current_state() != DriverProtocolState.COMMAND) :
            raise InstrumentProtocolException("Not in command state. Unable to apply startup params")

        error = None

        log.debug("apply_startup_params now")
        self._apply_params()

        if(error):
            log.error("Error in apply_startup_params: %s", error)
            raise error

    ########################################################################
    # Private helpers.
    ########################################################################

    def _discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result)
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        log.debug("_handler_unknown_discover")
        next_state = None
        next_agent_state = None

        """
        sampling = self._is_sampling()
        log.debug("are we sampling? %s" % sampling)

        if(sampling == None):
            next_state = DriverProtocolState.UNKNOWN
            next_agent_state = ResourceAgentState.ACTIVE_UNKNOWN

        elif(sampling):
            next_state = DriverProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING

        else:
            next_state = DriverProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        """
        
        log.debug("_handler_unknown_discover. result start: %s" % next_state)
        return (next_state, next_agent_state)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.debug("_set_params start")

        startup = False
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        self._verify_not_readonly(*args, **kwargs)

        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            #result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
            result = self._do_cmd_resp(InstrumentCmds.SET, key, val, response_regex=MNU_REGEX_MATCHER)

        log.debug("_set_params update_params")
        self._update_params()
        log.debug("_set_params complete")

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. SETparam=val followed by newline.
        String val constructed by param dict formatting function.  <--- needs a better/clearer way
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            if None == str_val:
                raise InstrumentParameterException("Driver PARAM was None!!!!")
            set_cmd = '$%s %s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE
            log.debug("set_cmd = " + repr(set_cmd))
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _build_single_parameter_command(self, cmd, param, val):
        """
        Build handler for set commands. param val followed by newline.
        String val constructed by param dict formatting function.  <--- needs a better/clearer way
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            if None == str_val:
                raise InstrumentParameterException("Driver PARAM was None!!!!")
            set_cmd = '%s %s' % (cmd, str_val)
            set_cmd = set_cmd + NEWLINE
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

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.GET_MENU, display_name="get menu")
        self._cmd_dict.add(Capability.GET_METADATA, display_name="get metadata")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        log.debug("%%% IN _build_param_dict")
        # THIS wants to take advantage of the particle code,
        # as the particles handle parsing the fields out
        # no sense doing it again here

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
                             display_name="serial number"
                             )

        self._param_dict.add(Parameter.Firmware_version_value,
                             FlortDMNU_Particle.LINE02,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="firmware version"
                             )

        self._param_dict.add(Parameter.Measurements_per_reported_value,
                             FlortDMNU_Particle.LINE03,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurements per reported value",
                             default_value=1,
                             startup_param=True,
                             direct_access=False
                             )

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
                             direct_access=True
                             )

        self._param_dict.add(Parameter.Measurement_1_dark_count_value,
                             FlortDMNU_Particle.LINE05,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 1 dark count",
                             default_value=0,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Measurement_2_dark_count_value,
                             FlortDMNU_Particle.LINE06,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 2 dark count",
                             default_value=0,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Measurement_3_dark_count_value,
                             FlortDMNU_Particle.LINE07,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 3 dark count",
                             default_value=0,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Measurement_1_slope_value,
                             FlortDMNU_Particle.LINE08,
                             lambda match: int(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 1 slope value",
                             default_value=1.000E+00,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Measurement_2_slope_value,
                             FlortDMNU_Particle.LINE09,
                             lambda match: int(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 2 slope value",
                             default_value=1.000E+00,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Measurement_3_slope_value,
                             FlortDMNU_Particle.LINE10,
                             lambda match: int(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="measurement 3 slope value",
                             default_value=1.000E+00,
                             startup_param=True,
                             direct_access=False
                             )

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
                             direct_access=True
                             )

        self._param_dict.add(Parameter.Baud_rate_value,
                             FlortDMNU_Particle.LINE12,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="baud rate",
                             default_value=19200,
                             startup_param=False,
                             direct_access=False
                             )

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
                             direct_access=True
                             )

        self._param_dict.add(Parameter.Recording_mode_value,
                             FlortDMNU_Particle.LINE14,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="recording mode",
                             default_value=1,
                             startup_param=True,
                             direct_access=True
                             )

        self._param_dict.add(Parameter.Manual_mode_value,
                             FlortDMNU_Particle.LINE15,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             display_name="manual mode",
                             default_value=0,
                             startup_param=True,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Sampling_interval_value,
                             FlortDMNU_Particle.LINE16,
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="Time interval between packets",
                             default_value=None,
                             startup_param=False,
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Date_value,
                             FlortDMNU_Particle.LINE17,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="date",
                             default_value=None,
                             startup_param=True,
                             direct_access=True
                             )

        self._param_dict.add(Parameter.Time_value,
                             FlortDMNU_Particle.LINE18,
                             lambda match: match.group(1),
                             str,
                             type=ParameterDictType.STRING,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name="time",
                             default_value=None,
                             startup_param=True,
                             direct_access=True
                             )

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
                             direct_access=False
                             )

        self._param_dict.add(Parameter.Internal_memory_value,
                             FlortDMNU_Particle.LINE20,
                             lambda match: int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             expiration=None,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name="internal memory size"
                             )

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if(self._extract_sample(FlortDMNU_Particle, MNU_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(FlortDMET_Particle, MET_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(FlortDRUN_Particle, RUN_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(FlortDDUMP_MEMORY_Particle, DUMP_MEMORY_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(FlortDSample_Particle, SAMPLE_REGEX_MATCHER, chunk, timestamp)) : return

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the sbe26plus device.
        """
        log.debug("%%% IN _send_wakeup")
        self._connection.send(NEWLINE)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic sbe26plus commands.
        @param cmd the simple sbe37 command to format.
        @retval The command to be sent to the device.
        """
        log.debug("%%% IN _build_simple_command")
        return cmd + NEWLINE

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        log.debug("start _update_params")
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)

        log.debug("Run configure command: %s" % InstrumentCmds.Print_menu)
        #response = self._do_cmd_resp(InstrumentCmds.Print_menu, timeout=timeout)
        response = self._do_cmd_resp(InstrumentCmds.Print_menu, timeout=timeout, response_regex=MNU_REGEX_MATCHER)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)
        log.debug("configure command response: %s" % response)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s" % (new_config, old_config))
        if not dict_equal(old_config, new_config, ignore_keys=Parameter.TIME):
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @raise: InstrumentProtocolException if in wrong mode.
        """
        log.debug("_apply_params start")
        config = self.get_startup_config()
        log.debug("_apply_params startup config: %s", config)
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)
        log.debug("_apply_params done")

    #
    # Many of these will want to rise up to base class if not there already
    #
    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for set operations.
        @param v An int val.
        @retval an int string formatted for set operations.
        @throws InstrumentParameterException if value not an int.
        """
        log.debug("IN _int_to_string")

        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for set operations.
        @param v A float val.
        @retval a float string formatted for set operations.
        @throws InstrumentParameterException if value is not a float.
        """
        log.debug("IN _float_to_string")

        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            #return '%e' % v #This returns a exponential formatted float
            # every time. not what is needed
            return str(v) #return a simple float

    @staticmethod
    def _bool_to_int_string(v):
        # return a string of an into of 1 or 0 to indicate true/false

        if True == v:
            return "1"
        elif False == v:
            return "0"
        else:
            return None

################################ /Protocol #############################
